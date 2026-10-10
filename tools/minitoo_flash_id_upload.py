#!/usr/bin/env python3
"""Upload and read back one fixed 1 KiB candidate, WITHOUT executing it.

No execution action exists. No file/address/length override, flash operation,
payload peripheral write, automatic reset or retry is permitted by this tool.
The only live action requires fresh application USB and macOS privileged capture.
"""
import argparse
import json
import os
import struct
import sys

import minitoo_ram_marker as marker
import minitoo_flash_id_payload as payload

rom = marker.rom


def transform(data):
    """Exactly 1024 bytes, with one continuous ROM CRC/XOR stream per command."""
    if len(data) != payload.SIZE:
        raise ValueError("Only the fixed 1024-byte block is supported")
    crc = marker.crc16(b"\xff\xff", 0xFFFF)
    result = bytearray(data)
    for i in range(payload.SIZE):
        crc = marker.crc16(marker.MAGIC[i % 16:i % 16 + 1], crc)
        result[i] ^= crc & 255
    return bytes(result)


def commands():
    encoded = transform(payload.make_block())
    upload = (b"\xfb\x06" + struct.pack(">IH", payload.ADDRESS, payload.SIZE) + b"\0"
              + struct.pack("<H", marker.crc16(encoded)) + b"\xff" * 5)
    read = b"\xfd\x07" + struct.pack(">IH", payload.ADDRESS, payload.SIZE) + b"\xff" * 8
    return upload, read


def upload_cbw(cdb, length, tag, data=None):
    upload, read = commands()
    if (cdb, length, data) == (upload, payload.SIZE, transform(payload.make_block())):
        direction = 0
    elif (cdb, length, data) == (read, payload.SIZE, None):
        direction = 0x80
    else:
        raise ValueError("Outside the fixed upload/readback allowlist; execution is disabled")
    return struct.pack("<4sIIBBB16s", b"USBC", tag, length, direction, 0, 16, cdb)


class UploadSession(marker.ProbeSession):
    def _probe_transfer(self, cdb, length, data=None):
        upload, read = commands()
        phases = {upload: "uploading", read: "reading-initial"}
        if not (self.mode == "rom" and self.verified and self.paths_verified):
            raise ValueError("Upload requires fresh ROM identity and 12 matching excerpts")
        if self.phase != phases.get(cdb):
            raise ValueError("Upload/readback is out of sequence or forbidden")
        wrapper = upload_cbw(cdb, length, self.tag + 1, data)
        self.tag += 1
        self.report.setdefault("commands_attempted", []).append(cdb.hex())
        if self.dev.write(self.outgoing, wrapper, timeout=2000) != 31:
            raise ValueError("Short upload/readback command wrapper")
        if data is not None:
            if self.dev.write(self.outgoing, data, timeout=2000) != payload.SIZE:
                raise ValueError("Short candidate upload; stopping without readback or retry")
            reply = b""
        else:
            reply = bytes(self.dev.read(self.incoming, length, timeout=2000))
            if len(reply) != length:
                raise ValueError("Wrong candidate readback length")
        rom.check_csw(bytes(self.dev.read(self.incoming, 13, timeout=2000)), self.tag)
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
                raise ValueError("Complete candidate upload mismatch; stopping without retry")
            self.result["upload_readback_confirmed"] = True

    def execute(self):
        raise ValueError("Candidate execution is disabled")

    def verify_result(self):
        raise ValueError("Candidate execution/result checks are not implemented")


def plan():
    upload, read = commands()
    return {
        "purpose": "Offline plan for one fixed candidate upload/readback; no USB access",
        "address": f"0x{payload.ADDRESS:08x}", "block_bytes": payload.SIZE,
        "code_bytes": len(payload.CODE), "block_sha256": payload.sha256(payload.make_block()),
        "encoded_sha256": payload.sha256(transform(payload.make_block())),
        "upload_cdb": upload.hex(), "readback_cdb": read.hex(),
        "execution_supported": False, "flash_chip_transactions": 0,
        "automatic_reset_commands": 0, "retries": 0,
        "note": "Candidate contains peripheral-access code, but this helper cannot execute it.",
    }


def run():
    result = {
        "purpose": "One fixed 1 KiB RAM upload/readback only",
        "action": "roundtrip-only", "block_bytes": payload.SIZE,
        "execution_supported": False, "execution_attempted": False,
        "flash_chip_transactions": 0, "payload_peripheral_writes": 0,
        "entry_confirmed": False, "rom_fingerprints_confirmed": False,
        "ram_uploads_attempted": 0, "ram_upload_status_confirmed": False,
        "upload_readback_confirmed": False, "roundtrip_confirmed": False,
        "automatic_reset_commands": 0, "sessions": [],
    }
    try:
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
        report = {"stage": "fixed-1k-candidate-upload-readback"}
        result["sessions"].append(report)
        with UploadSession(device, report, result) as session:
            session.identify("rom")
            result["entry_confirmed"] = True
            session.verify_paths()
            session.upload()
            session.verify_upload()
        result["roundtrip_confirmed"] = True
        result["note"] = (
            "One fixed 1024-byte RAM upload and complete readback matched. No execution call, "
            "flash-chip transaction or automatic reset was sent. Device remains in ROM. "
            "Use the tested front-left power-key hold (about 10 seconds), release at startup, "
            "then reconnect USB if needed.")
        return result, False
    except (rom.usb.core.USBError, ValueError, RuntimeError) as error:
        result["error"] = str(error)
        result["note"] = ("Stopped without retry or automatic reset. If ROM entry was attempted, "
                          "use the tested power-key restart and reconnect USB if needed.")
        if not result["sessions"]:
            result["note"] = "Stopped before opening a device session; no protocol commands sent."
        return result, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true")
    action.add_argument("--roundtrip-only", action="store_true")
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
