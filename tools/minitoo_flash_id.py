#!/usr/bin/env python3
"""One fixed BR28 flash-ID experiment, with no programming or erase commands.

Fresh application USB, 12 ROM fingerprints and complete pinned RAM readback are
required before one call. There are no payload/address/length inputs, retries,
automatic resets, protocol fallbacks, or flash-data reads. Leaves the unit in
ROM for the tested manual restart. --plan never accesses a device.
"""
import argparse
import json
import os
import struct
import sys

import minitoo_flash_id_upload as transport

payload = transport.payload
rom = transport.rom
EXECUTION_REVIEWED = False


def commands():
    upload, read = transport.commands()
    call = b"\xfb\x08" + struct.pack(">IH", payload.ADDRESS, 0) + b"\xff" * 8
    return upload, read, call


def id_cbw(cdb, length, tag, data=None):
    upload, read, call = commands()
    if (cdb, length, data) == (upload, payload.SIZE, transport.transform(payload.make_block())):
        direction = 0
    elif data is None and (cdb, length) in ((read, payload.SIZE), (call, 16)):
        direction = 0x80
    else:
        raise ValueError("Outside the fixed flash-ID RAM-transfer allowlist")
    return struct.pack("<4sIIBBB16s", b"USBC", tag, length, direction, 0, 16, cdb)


class IdSession(transport.UploadSession):
    def _probe_transfer(self, cdb, length, data=None):
        upload, read, call = commands()
        phases = {upload: ("uploading",), read: ("reading-initial", "reading-result"),
                  call: ("calling",)}
        if not (self.mode == "rom" and self.verified and self.paths_verified):
            raise ValueError("Flash ID requires fresh ROM identity and all 12 matching excerpts")
        if self.phase not in phases.get(cdb, ()):
            raise ValueError("Flash-ID RAM transfer is out of sequence")
        wrapper = id_cbw(cdb, length, self.tag + 1, data)
        self.tag += 1
        self.report.setdefault("commands_attempted", []).append(cdb.hex())
        if self.dev.write(self.outgoing, wrapper, timeout=2000) != 31:
            raise ValueError("Short flash-ID command wrapper")
        if data is not None:
            if self.dev.write(self.outgoing, data, timeout=2000) != payload.SIZE:
                raise ValueError("Short flash-ID upload; stopping without retry")
            reply = b""
        else:
            reply = bytes(self.dev.read(self.incoming, length, timeout=2000))
            if len(reply) != length:
                raise ValueError("Wrong flash-ID RAM-transfer response length")
        rom.check_csw(bytes(self.dev.read(self.incoming, 13, timeout=2000)), self.tag)
        return reply

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
            data = transport.transform(self._probe_transfer(commands()[1], payload.SIZE))
            self.report["result_readback_sha256"] = payload.sha256(data)
            capture = payload.decode_result(data)
            self.report["flash_id_result"] = capture
            self.result["result_block_confirmed"] = True
            self.result["flash_chip_transactions"] = int(capture["status"] != "preflight-refused")


def plan():
    upload, read, call = commands()
    return {
        "purpose": "Offline plan for one fixed flash-ID experiment; no device access",
        "execution_reviewed": EXECUTION_REVIEWED,
        "entry_address": f"0x{payload.ADDRESS:08x}", "block_bytes": payload.SIZE,
        "block_sha256": payload.sha256(payload.make_block()),
        "upload_cdb": upload.hex(), "readback_cdb": read.hex(), "call_cdb": call.hex(),
        "chip_transaction": "9F transmit, three FF receives, one chip-select assertion",
        "flash_chip_transactions_max": 1, "flash_program_erase_commands": 0,
        "flash_data_reads": 0, "automatic_reset_commands": 0, "retries": 0,
        "sequence": ["fresh application identity", "one software ROM entry",
                     "ROM identity and 12 fingerprints", "one pinned RAM upload",
                     "complete upload readback", "one call", "complete result validation",
                     "fresh ROM identity", "release capture; manual power-key restart"],
        "note": "Captured bytes do not establish physical part identity, capacity or a backup.",
    }


def run():
    result = {
        "purpose": "One fixed flash-ID experiment", "action": "run-fixed-id",
        "flash_program_erase_commands": 0, "flash_data_reads": 0,
        "flash_chip_transactions": 0, "flash_chip_transactions_max": 1,
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
        report = {"stage": "fixed-flash-id"}
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
        if not capture["id_captured"]:
            raise ValueError(f"Flash-ID experiment returned {capture['status']}; no retry or fallback")
        result["flash_id_capture_confirmed"] = True
        result["note"] = (
            "ID bytes captured and return to ROM verified. Physical part and capacity still need "
            "identification. No flash-data read, program/erase or automatic reset was sent. "
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
    action.add_argument("--run-fixed-id", action="store_true")
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
