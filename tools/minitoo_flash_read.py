#!/usr/bin/env python3
"""Fixed BR28 two-pass 64-byte flash read; no persistent flash writes.

Fresh application USB, 12 ROM fingerprints and complete pinned RAM readback are
required before one call. Three released-data mode-exit frames precede ID, then two fixed 03 reads.
There are no payload/address/length inputs, retries,
automatic resets, protocol fallbacks, or arbitrary flash ranges. Leaves the unit in
ROM for the tested manual restart. --plan never accesses a device.
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

import minitoo_flash_id_upload as transport
import minitoo_flash_read_payload as payload
import minitoo_ram_marker as marker

rom = marker.rom
# Fixed a041be5d... block only; see docs/technical-notes.md.
EXECUTION_REVIEWED = True
CAPTURE_ROOT = Path(__file__).resolve().parents[1] / "artifacts/device-captures"



@lru_cache(maxsize=1)
def commands():
    uploads, reads = [], []
    for index in range(2):
        address = payload.ADDRESS + index * payload.CHUNK_BYTES
        chunk = payload.make_block()[index * 1024:(index + 1) * 1024]
        encoded = transport.transform(chunk)
        uploads.append(b"\xfb\x06" + struct.pack(">IH", address, 1024) + b"\0"
                       + struct.pack("<H", marker.crc16(encoded)) + b"\xff" * 5)
        reads.append(b"\xfd\x07" + struct.pack(">IH", address, 1024) + b"\xff" * 8)
    call = b"\xfb\x08" + struct.pack(">IH", payload.ADDRESS, 0) + b"\xff" * 8
    return tuple(uploads), tuple(reads), call


def read_cbw(cdb, length, tag, data=None):
    uploads, reads, call = commands()
    if cdb in uploads:
        index = uploads.index(cdb)
        expected = transport.transform(payload.make_block()[index * 1024:(index + 1) * 1024])
        if (length, data) != (1024, expected):
            raise ValueError("Wrong fixed ID upload block")
        direction = 0
    elif data is None and ((cdb in reads and length == 1024) or (cdb == call and length == 16)):
        direction = 0x80
    else:
        raise ValueError("Outside the fixed small-read allowlist")
    return struct.pack("<4sIIBBB16s", b"USBC", tag, length, direction, 0, 16, cdb)


class ReadSession(marker.ProbeSession):
    def __init__(self, device, report, result):
        super().__init__(device,report,result)
        self.cursor = 0
        self.copies = self.raw_result = None

    def _probe_transfer(self, cdb, length, data=None):
        uploads, reads, call = commands()
        if not (self.mode == "rom" and self.verified and self.paths_verified):
            raise ValueError("ID probe requires fresh ROM identity and all 12 excerpts")
        if self.phase == "uploading" and self.cursor < 2:
            expected = uploads[self.cursor]
        elif self.phase in ("reading-initial", "reading-result") and self.cursor < 2:
            expected = reads[self.cursor]
        elif self.phase == "calling":
            expected = call
        else:
            expected = None
        if cdb != expected:
            raise ValueError("Small-read transfer out of sequence")
        wrapper = read_cbw(cdb, length, self.tag + 1, data)
        self.tag += 1
        self.report.setdefault("commands_attempted", []).append(cdb.hex())
        if self.dev.write(self.outgoing, wrapper, timeout=2000) != 31:
            raise ValueError("Short small-read command wrapper")
        if data is not None:
            if self.dev.write(self.outgoing, data, timeout=2000) != 1024:
                raise ValueError("Short small-read upload; stopping without retry")
            reply = b""
        else:
            reply = bytes(self.dev.read(self.incoming, length, timeout=2000))
            if len(reply) != length:
                raise ValueError("Wrong small-read RAM-transfer response length")
        rom.check_csw(bytes(self.dev.read(self.incoming, 13, timeout=2000)), self.tag)
        self.cursor += 1
        return reply

    def upload(self):
        self.cursor = 0
        with self.step("verified", "uploading", "uploaded"):
            for index, cdb in enumerate(commands()[0]):
                self.result["ram_uploads_attempted"] += 1
                chunk = payload.make_block()[index * 1024:(index + 1) * 1024]
                self._probe_transfer(cdb, 1024, transport.transform(chunk))
            self.result["ram_upload_status_confirmed"] = True

    def read_blocks(self):
        self.cursor = 0
        return b"".join(transport.transform(self._probe_transfer(cdb, 1024)) for cdb in commands()[1])

    def verify_upload(self):
        with self.step("uploaded", "reading-initial", "readback-verified"):
            data = self.read_blocks()
            self.report["upload_readback_sha256"] = payload.sha256(data)
            if data != payload.make_block():
                raise ValueError("Complete 2 KiB upload mismatch; no execution follows")
            self.result["upload_readback_confirmed"] = True

    def execute(self):
        if not EXECUTION_REVIEWED:
            raise ValueError("Small-read execution review is incomplete")
        with self.step("readback-verified", "calling", "returned"):
            self.result["execution_attempted"] = True
            # A lost response cannot tell us whether the peripheral code ran.
            self.result["flash_chip_transactions"] = None
            self.result["flash_data_reads"] = None
            reply = self._probe_transfer(commands()[2], 16)
            self.report["call_response_prefix"] = reply[:2].hex()
            if reply[:2] != b"\xfb\x08":
                raise ValueError("Wrong small-read call response; stopping without retry")
            self.result["return_response_confirmed"] = True

    def verify_result(self):
        with self.step("returned", "reading-result", "result-verified"):
            data = self.read_blocks()
            self.report["result_readback_sha256"] = payload.sha256(data)
            self.raw_result = data
            capture,self.copies = payload.decode_result(data)
            self.report["flash_read_result"] = capture
            self.result["result_block_confirmed"] = True
            self.result["flash_chip_transactions"] = capture["transactions_started"] + capture["read_transactions_started"]
            self.result["flash_data_reads"] = capture["read_transactions_started"]


def plan():
    uploads, reads, call = commands()
    return {
        "purpose": "Offline plan for one fixed small-read experiment; no device access",
        "execution_reviewed": EXECUTION_REVIEWED,
        "entry_address": f"0x{payload.ADDRESS:08x}", "block_bytes": payload.SIZE,
        "block_sha256": payload.sha256(payload.make_block()),
        "upload_cdbs": [c.hex() for c in uploads], "readback_cdbs": [c.hex() for c in reads], "call_cdb": call.hex(),
        "chip_transactions": "Released-data 2/16/2 clocks, expected 9F ID, then two separate 03 00 00 00 + 64-byte reads",
        "volatile_mode_release_transactions_max": 3, "status_register_writes": 0,
        "flash_chip_transactions_max": 6, "flash_program_erase_commands": 0,
        "flash_data_reads_max": 2, "flash_address": "0x000000", "capture_bytes_per_pass": 64,
        "automatic_reset_commands": 0, "retries": 0,
        "sequence": ["fresh application identity", "one software ROM entry",
                     "ROM identity and 12 fingerprints", "two pinned 1 KiB RAM uploads",
                     "complete upload readback", "one call", "complete result validation",
                     "fresh ROM identity", "save both copies privately", "release capture; manual power-key restart"],
        "note": "Two reads of one fixed range; not a complete backup. Raw bytes are saved privately, not printed.",
    }


def reserve_capture():
    CAPTURE_ROOT.mkdir(parents=True,exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = Path(tempfile.mkdtemp(prefix=f"minitoo-flash-small-{stamp}-",dir=CAPTURE_ROOT))
    streams = {}
    try:
        for name in ("flash-000000-pass1.bin","flash-000000-pass2.bin","result-block.bin","report.json"):
            stream = (directory/name).open("xb")
            streams[name] = stream
            os.fchmod(stream.fileno(),0o600)
        if os.geteuid() == 0 and "SUDO_UID" in os.environ and "SUDO_GID" in os.environ:
            uid,gid = int(os.environ["SUDO_UID"]),int(os.environ["SUDO_GID"])
            for stream in streams.values():
                os.fchown(stream.fileno(),uid,gid)
            os.chown(directory,uid,gid)
        return directory,streams
    except BaseException:
        for stream in streams.values():
            stream.close()
        raise


def persist(stream,data):
    if stream.write(data) != len(data):
        raise OSError("Short private capture write")
    stream.flush()
    os.fsync(stream.fileno())


def run():
    result = {
        "purpose": "Two fixed 64-byte flash reads", "action": "run-fixed-small-read",
        "flash_program_erase_commands": 0, "status_register_writes": 0, "flash_data_reads": 0,
        "flash_chip_transactions": 0, "flash_chip_transactions_max": 6,
        "automatic_reset_commands": 0, "entry_confirmed": False,
        "rom_fingerprints_confirmed": False, "ram_uploads_attempted": 0,
        "ram_upload_status_confirmed": False, "upload_readback_confirmed": False,
        "execution_attempted": False, "return_response_confirmed": False,
        "result_block_confirmed": False, "rom_return_confirmed": False,
        "small_read_confirmed": False, "data_saved": False, "capture_bytes_per_pass": 64,
        "flash_address": "0x000000", "sessions": [],
    }
    streams,session,failed = {},None,True
    try:
        if not EXECUTION_REVIEWED:
            raise ValueError("Small-read execution review is incomplete; no device access")
        payload.make_block()
        directory,streams = reserve_capture()
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
        report = {"stage": "fixed-two-pass-small-read"}
        result["sessions"].append(report)
        with ReadSession(device, report, result) as session:
            session.identify("rom")
            result["entry_confirmed"] = True
            session.verify_paths()
            session.upload()
            session.verify_upload()
            session.execute()
            session.verify_result()
            session.confirm_return()
        capture = report["flash_read_result"]
        if not capture["small_read_confirmed"] or not capture["read_copies_match"]:
            raise ValueError(f"Small read unconfirmed: {capture['status']}; no retry or fallback")
        if capture["read_is_all_zero_or_ff"]:
            raise ValueError("Both reads are uniformly zero or FF; not accepting as a useful storage read")
        for n,data in enumerate(session.copies,1):
            persist(streams[f"flash-000000-pass{n}.bin"],data)
        result["data_saved"] = True
        result["small_read_confirmed"] = True
        result["note"] = (
            "Two separate 64-byte raw flash reads matched and were saved privately; ROM return verified. "
            "No status-register write, program/erase or automatic reset was sent. "
            "This is a small read, not a complete backup or a firmware update. Device remains in ROM. "
            "Use the tested front-left power-key hold (about 10 seconds), release at startup, then reconnect USB if needed.")
        failed = False
    except (rom.usb.core.USBError, ValueError, RuntimeError, OSError) as error:
        result["error"] = str(error)
        result["note"] = (
            "Stopped without retry, fallback or automatic reset. Small read is unconfirmed. "
            "If ROM entry was attempted, use the tested power-key restart and reconnect USB if needed. "
            "Reset from hung RAM code has not been independently tested.")
        if not result["sessions"]:
            result["note"] = "Stopped before opening a device session; no protocol commands sent."
    finally:
        try:
            if getattr(session, "raw_result", None) is not None:
                persist(streams["result-block.bin"],session.raw_result)
            if streams:
                persist(streams["report.json"],(json.dumps(result,indent=2)+"\n").encode())
        except OSError as error:
            result["metadata_save_error"] = str(error)
            result["small_read_confirmed"] = False
            failed = True
        finally:
            for stream in streams.values():
                stream.close()
    return result,failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true")
    action.add_argument("--run-fixed-small-read", action="store_true")
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
