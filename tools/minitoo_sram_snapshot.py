#!/usr/bin/env python3
"""Copy one fixed 20 KiB application-SRAM window, read its copy twice, save locally.

Fresh application USB, 12 ROM fingerprints and complete pinned upload readback
are required. The source is only loaded by the payload; FD07 reads only our
code/result and copied output. No arbitrary ranges, file/payload inputs,
peripherals, flash transactions, automatic resets or retries. Leaves ROM active.
Raw data is saved privately under ignored artifacts/device-captures/, not printed.
"""
import argparse
import datetime
from functools import lru_cache
import json
import os
from pathlib import Path
import struct
import sys
import tempfile

import minitoo_ram_marker as marker
from minitoo_flash_id_upload import transform
import minitoo_sram_snapshot_payload as payload

rom = marker.rom
CAPTURE_ROOT = Path(__file__).resolve().parents[1] / "artifacts/device-captures"


@lru_cache(maxsize=1)
def commands():
    encoded = transform(payload.make_block())
    upload = (b"\xfb\x06" + struct.pack(">IH", payload.ADDRESS, payload.SIZE) + b"\0"
              + struct.pack("<H", marker.crc16(encoded)) + b"\xff" * 5)
    read = b"\xfd\x07" + struct.pack(">IH", payload.ADDRESS, payload.SIZE) + b"\xff" * 8
    call = b"\xfb\x08" + struct.pack(">IH", payload.ADDRESS, 0) + b"\xff" * 8
    chunks = tuple(b"\xfd\x07" + struct.pack(">IH", address, payload.SIZE) + b"\xff" * 8
                   for address in range(payload.DESTINATION,
                                        payload.DESTINATION + payload.CAPTURE_BYTES, payload.SIZE))
    return upload, read, call, chunks


def snapshot_cbw(cdb, length, tag, data=None):
    upload, read, call, chunks = commands()
    if cdb == upload and (length, data) == (payload.SIZE, transform(payload.make_block())):
        direction = 0
    elif data is None and ((cdb, length) in ((read, payload.SIZE), (call, 16))
                           or cdb in chunks and length == payload.SIZE):
        direction = 0x80
    else:
        raise ValueError("Outside the fixed SRAM-copy transfer allowlist")
    return struct.pack("<4sIIBBB16s", b"USBC", tag, length, direction, 0, 16, cdb)


class SnapshotSession(marker.ProbeSession):
    def __init__(self, device, report, result):
        super().__init__(device, report, result)
        self.chunk_index = 0
        self.captured = None

    def _probe_transfer(self, cdb, length, data=None):
        upload, read, call, chunks = commands()
        if not (self.mode == "rom" and self.verified and self.paths_verified):
            raise ValueError("SRAM copy requires fresh ROM identity and all 12 matching excerpts")
        if self.phase in ("copy-first", "copy-second"):
            expected = chunks[self.chunk_index] if self.chunk_index < len(chunks) else None
        else:
            expected = {"uploading": upload, "reading-initial": read,
                        "calling": call, "reading-result": read}.get(self.phase)
        if cdb != expected:
            raise ValueError("SRAM-copy transfer is out of sequence")
        wrapper = snapshot_cbw(cdb, length, self.tag + 1, data)
        self.tag += 1
        self.report.setdefault("commands_attempted", []).append(cdb.hex())
        if self.dev.write(self.outgoing, wrapper, timeout=2000) != 31:
            raise ValueError("Short SRAM-copy command wrapper")
        if data is not None:
            if self.dev.write(self.outgoing, data, timeout=2000) != payload.SIZE:
                raise ValueError("Short SRAM-copy upload; stopping without retry")
            reply = b""
        else:
            reply = bytes(self.dev.read(self.incoming, length, timeout=2000))
            if len(reply) != length:
                raise ValueError("Wrong SRAM-copy transfer length")
        rom.check_csw(bytes(self.dev.read(self.incoming, 13, timeout=2000)), self.tag)
        if self.phase in ("copy-first", "copy-second"):
            self.chunk_index += 1
        return reply

    def upload(self):
        with self.step("verified", "uploading", "uploaded"):
            self.result["ram_uploads_attempted"] += 1
            self._probe_transfer(commands()[0], payload.SIZE, transform(payload.make_block()))
            self.result["ram_upload_status_confirmed"] = True

    def verify_upload(self):
        with self.step("uploaded", "reading-initial", "readback-verified"):
            data = transform(self._probe_transfer(commands()[1], payload.SIZE))
            self.report["upload_readback_sha256"] = payload.sha256(data)
            if data != payload.make_block():
                raise ValueError("Complete SRAM-copy upload mismatch; no execution will follow")
            self.result["upload_readback_confirmed"] = True

    def execute(self):
        with self.step("readback-verified", "calling", "returned"):
            self.result["execution_attempted"] = True
            reply = self._probe_transfer(commands()[2], 16)
            self.report["call_response_prefix"] = reply[:2].hex()
            if reply[:2] != b"\xfb\x08":
                raise ValueError("Wrong SRAM-copy call response; stopping without retry")
            self.result["return_response_confirmed"] = True

    def verify_result(self):
        with self.step("returned", "reading-result", "completion-verified"):
            data = transform(self._probe_transfer(commands()[1], payload.SIZE))
            payload.validate_result(data)
            self.report["result_readback_sha256"] = payload.sha256(data)
            self.result["result_block_confirmed"] = True
        for pass_number, (expected, active, complete) in enumerate((
                ("completion-verified", "copy-first", "first-read-complete"),
                ("first-read-complete", "copy-second", "result-verified")), 1):
            self.chunk_index = 0
            with self.step(expected, active, complete):
                chunks = []
                for index, cdb in enumerate(commands()[3]):
                    chunk = transform(self._probe_transfer(cdb, payload.SIZE))
                    if pass_number == 2 and chunk != self.captured[index * payload.SIZE:(index + 1) * payload.SIZE]:
                        raise ValueError(f"Copied SRAM differs on second read, chunk {index}; stopping")
                    chunks.append(chunk)
                data = b"".join(chunks)
                if len(data) != payload.CAPTURE_BYTES:
                    raise ValueError("Incomplete copied SRAM capture")
                self.report[f"copy_read_{pass_number}_sha256"] = payload.sha256(data)
                if pass_number == 1:
                    self.captured = data
        self.result["copy_read_twice_confirmed"] = True


def plan():
    upload, read, call, chunks = commands()
    return {
        "purpose": "Offline plan for fixed retained-application SRAM copy; no device access",
        "source_address": f"0x{payload.SOURCE:08x}", "capture_bytes": payload.CAPTURE_BYTES,
        "copy_address": f"0x{payload.DESTINATION:08x}", "entry_address": f"0x{payload.ADDRESS:08x}",
        "code_bytes": len(payload.CODE), "upload_bytes": payload.SIZE,
        "block_sha256": payload.sha256(payload.make_block()),
        "upload_cdb": upload.hex(), "code_read_cdb": read.hex(), "call_cdb": call.hex(),
        "copy_read_cdbs": [cdb.hex() for cdb in chunks], "copy_read_passes": 2,
        "flash_chip_transactions": 0, "payload_peripheral_accesses": 0,
        "source_writes": 0, "automatic_reset_commands": 0, "retries": 0,
        "output_root": str(CAPTURE_ROOT),
        "note": "Partial sequential SRAM capture after ROM entry; not a full SRAM or installed-flash backup.",
    }


def reserve_capture():
    """Reserve private output files before USB; retain empty files on failure."""
    CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = Path(tempfile.mkdtemp(prefix=f"minitoo-sram-{stamp}-", dir=CAPTURE_ROOT))
    streams = []
    try:
        for name in ("sram-10b000-110000.bin", "report.json"):
            stream = (directory / name).open("xb")
            streams.append(stream)
            os.fchmod(stream.fileno(), 0o600)
        if os.geteuid() == 0 and "SUDO_UID" in os.environ and "SUDO_GID" in os.environ:
            uid, gid = int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"])
            for stream in streams:
                os.fchown(stream.fileno(), uid, gid)
            os.chown(directory, uid, gid)
        return directory, streams[0], streams[1]
    except BaseException:
        for stream in streams:
            stream.close()
        raise


def run():
    result = {
        "purpose": "One fixed 20 KiB retained-application SRAM copy", "action": "run-fixed-snapshot",
        "flash_chip_transactions": 0, "payload_peripheral_accesses": 0, "source_writes": 0,
        "automatic_reset_commands": 0, "entry_confirmed": False, "rom_fingerprints_confirmed": False,
        "ram_uploads_attempted": 0, "ram_upload_status_confirmed": False, "upload_readback_confirmed": False,
        "execution_attempted": False, "return_response_confirmed": False, "result_block_confirmed": False,
        "copy_read_twice_confirmed": False, "rom_return_confirmed": False, "data_saved": False,
        "snapshot_confirmed": False, "source_address": f"0x{payload.SOURCE:08x}",
        "capture_bytes": payload.CAPTURE_BYTES, "sessions": [],
    }
    raw = metadata = None
    failed = True
    try:
        payload.make_block()
        directory, raw, metadata = reserve_capture()
        result["capture_directory"] = str(directory)
        backend = rom.usb.backend.libusb1.get_backend(find_library=rom.libusb_package.find_library)
        if backend is None:
            raise ValueError("libusb backend unavailable")
        device = rom.select(rom.enumerate_target(backend), rom.APP_PID)
        if device is None:
            raise ValueError("Fresh application USB required; finish the tested power-key restart and reconnect USB")
        port = rom.location(device)
        report = {"stage": "application-entry"}
        result["sessions"].append(report)
        with rom.Session(device, report) as session:
            session.identify("app")
            session.transition("enter")
        device = rom.wait_for(backend, rom.ROM_PID, port)
        report = {"stage": "fixed-retained-sram-copy"}
        result["sessions"].append(report)
        with SnapshotSession(device, report, result) as session:
            session.identify("rom")
            result["entry_confirmed"] = True
            session.verify_paths()
            session.upload()
            session.verify_upload()
            session.execute()
            session.verify_result()
            session.confirm_return()
        if raw.write(session.captured) != payload.CAPTURE_BYTES:
            raise OSError("Short capture-file write")
        raw.flush()
        os.fsync(raw.fileno())
        result["data_saved"] = True
        result["snapshot_confirmed"] = True
        result["capture_sha256"] = payload.sha256(session.captured)
        result["note"] = (
            "Fixed SRAM copy, two matching reads of that copy, return to ROM and local save verified. "
            "This is partial SRAM after ROM entry, not a flash backup. No source/peripheral write or flash "
            "transaction was in the payload. Device remains in ROM. Use the tested front-left power-key "
            "hold (about 10 seconds), release at startup, then reconnect USB if needed.")
        failed = False
    except (rom.usb.core.USBError, ValueError, RuntimeError, OSError) as error:
        result["error"] = str(error)
        result["note"] = (
            "Stopped without retry or automatic reset. SRAM capture is unconfirmed. If ROM entry was "
            "attempted, use the tested power-key restart and reconnect USB if needed. "
            "Reset from hung RAM code has not been independently tested.")
        if not result["sessions"]:
            result["note"] = "Stopped before opening a device session; no protocol commands sent."
    finally:
        if raw is not None:
            raw.close()
        if metadata is not None:
            try:
                metadata.write((json.dumps(result, indent=2) + "\n").encode())
                metadata.flush()
                os.fsync(metadata.fileno())
            except OSError as error:
                result["metadata_save_error"] = str(error)
                result["snapshot_confirmed"] = False
                failed = True
            finally:
                metadata.close()
    return result, failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true")
    action.add_argument("--run-fixed-snapshot", action="store_true")
    args = parser.parse_args()
    if args.plan:
        print(json.dumps(plan(), indent=2))
        return
    if sys.platform == "darwin" and os.geteuid() != 0:
        parser.error("macOS USB capture requires sudo; no USB action attempted")
    result, failed = run()
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(int(failed))


if __name__ == "__main__":
    main()
