#!/usr/bin/env python3
"""Fixed BR28 volatile-mode release and JEDEC ID; no persistent flash writes.

Fresh application USB, 12 ROM fingerprints and complete pinned RAM readback are
required before one call. Three released-data mode-exit frames precede ID.
There are no payload/address/length inputs, retries,
automatic resets, protocol fallbacks, or flash-data reads. Leaves the unit in
ROM for the tested manual restart. --plan never accesses a device.
"""
import argparse
from functools import lru_cache
import json
import os
import struct
import sys

import minitoo_flash_id_upload as transport
import minitoo_flash_identify_payload as payload
import minitoo_ram_marker as marker

rom = marker.rom
# Fixed block e75fdc94... only; review and limits in docs/technical-notes.md.
# The original minitoo_flash_id.py candidate remains disabled.
EXECUTION_REVIEWED = True


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


def id_cbw(cdb, length, tag, data=None):
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
        raise ValueError("Outside the fixed mode-release/ID allowlist")
    return struct.pack("<4sIIBBB16s", b"USBC", tag, length, direction, 0, 16, cdb)


class IdSession(marker.ProbeSession):
    cursor = 0

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
            raise ValueError("Mode-release/ID transfer out of sequence")
        wrapper = id_cbw(cdb, length, self.tag + 1, data)
        self.tag += 1
        self.report.setdefault("commands_attempted", []).append(cdb.hex())
        if self.dev.write(self.outgoing, wrapper, timeout=2000) != 31:
            raise ValueError("Short flash-ID command wrapper")
        if data is not None:
            if self.dev.write(self.outgoing, data, timeout=2000) != 1024:
                raise ValueError("Short flash-ID upload; stopping without retry")
            reply = b""
        else:
            reply = bytes(self.dev.read(self.incoming, length, timeout=2000))
            if len(reply) != length:
                raise ValueError("Wrong flash-ID RAM-transfer response length")
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
            raise ValueError("Flash-ID execution review is incomplete")
        with self.step("readback-verified", "calling", "returned"):
            self.result["execution_attempted"] = True
            # A lost response cannot tell us whether the peripheral code ran.
            self.result["flash_chip_transactions"] = None
            reply = self._probe_transfer(commands()[2], 16)
            self.report["call_response_prefix"] = reply[:2].hex()
            if reply[:2] != b"\xfb\x08":
                raise ValueError("Wrong flash-ID call response; stopping without retry")
            self.result["return_response_confirmed"] = True

    def verify_result(self):
        with self.step("returned", "reading-result", "result-verified"):
            data = self.read_blocks()
            self.report["result_readback_sha256"] = payload.sha256(data)
            capture = payload.decode_result(data)
            self.report["flash_id_result"] = capture
            self.result["result_block_confirmed"] = True
            self.result["flash_chip_transactions"] = capture["transactions_started"]


def plan():
    uploads, reads, call = commands()
    return {
        "purpose": "Offline plan for one fixed flash-ID experiment; no device access",
        "execution_reviewed": EXECUTION_REVIEWED,
        "entry_address": f"0x{payload.ADDRESS:08x}", "block_bytes": payload.SIZE,
        "block_sha256": payload.sha256(payload.make_block()),
        "upload_cdbs": [c.hex() for c in uploads], "readback_cdbs": [c.hex() for c in reads], "call_cdb": call.hex(),
        "chip_transactions": "Released data lines: 2/16/2 clocks in separate frames; then 9F and 3 ID bytes",
        "volatile_mode_release_transactions_max": 3, "status_register_writes": 0,
        "flash_chip_transactions_max": 4, "flash_program_erase_commands": 0,
        "flash_data_reads": 0, "automatic_reset_commands": 0, "retries": 0,
        "sequence": ["fresh application identity", "one software ROM entry",
                     "ROM identity and 12 fingerprints", "two pinned 1 KiB RAM uploads",
                     "complete upload readback", "one call", "complete result validation",
                     "fresh ROM identity", "release capture; manual power-key restart"],
        "note": "Captured bytes do not establish physical part identity, capacity or a backup.",
    }


def run():
    result = {
        "purpose": "One fixed flash-ID experiment", "action": "run-fixed-identification",
        "flash_program_erase_commands": 0, "status_register_writes": 0, "flash_data_reads": 0,
        "flash_chip_transactions": 0, "flash_chip_transactions_max": 4,
        "automatic_reset_commands": 0, "entry_confirmed": False,
        "rom_fingerprints_confirmed": False, "ram_uploads_attempted": 0,
        "ram_upload_status_confirmed": False, "upload_readback_confirmed": False,
        "execution_attempted": False, "return_response_confirmed": False,
        "result_block_confirmed": False, "rom_return_confirmed": False,
        "flash_id_capture_confirmed": False, "sessions": [],
    }
    try:
        if not EXECUTION_REVIEWED:
            raise ValueError("Flash-ID execution review is incomplete; no device access")
        payload.make_block()
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
        report = {"stage": "fixed-mode-release-id"}
        result["sessions"].append(report)
        with IdSession(device, report, result) as session:
            session.identify("rom")
            result["entry_confirmed"] = True
            session.verify_paths()
            session.upload()
            session.verify_upload()
            session.execute()
            session.verify_result()
            session.confirm_return()
        capture = report["flash_id_result"]
        if not capture["matches_cached_id"]:
            raise ValueError(f"ID result {capture['status']} / {capture['id_bytes']} does not confirm expected 856015; no retry or fallback")
        result["flash_id_capture_confirmed"] = True
        result["note"] = (
            "Live ID 85 60 15 agrees with cached SRAM metadata; return to ROM verified. "
            "Three fixed volatile-mode release frames preceded ID. No flash-data read, "
            "status-register write, program/erase or automatic reset was sent. "
            "Device remains in ROM. Use the tested front-left power-key hold (about 10 seconds), "
            "release at startup, then reconnect USB if needed.")
        return result, False
    except (rom.usb.core.USBError, ValueError, RuntimeError) as error:
        result["error"] = str(error)
        result["note"] = (
            "Stopped without retry, fallback or automatic reset. ID capture is unconfirmed. "
            "If ROM entry was attempted, use the tested power-key restart and reconnect USB if needed. "
            "Reset from hung RAM code has not been independently tested.")
        if not result["sessions"]:
            result["note"] = "Stopped before opening a device session; no protocol commands sent."
        return result, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true")
    action.add_argument("--run-fixed-identification", action="store_true")
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
