#!/usr/bin/env python3
# SPDX-License-Identifier: MIT AND Apache-2.0
# Copyright 2026 Brad Dwyer
# Original project code is MIT; the Jieli ROM table retains Apache-2.0.
# MengLi reference: jl-uboot-tool, Copyright (c) 2023 Andrey Grigoryev (kagaimiq).
# Includes an extracted Jieli ROM table; see ../NOTICE and ../LICENSES/MIT.txt.
# Modified for one fixed RAM block; the extracted table bytes are unchanged.
"""One fixed MiniToo RAM-marker experiment; no flash operations.

--plan is offline. --roundtrip-only enters fresh BR28 ROM through the working
application, verifies 12 pinned ROM excerpts, uploads exactly one known 512-byte
block, compares its entire decoded readback and stops WITHOUT executing it.
--run-fixed-probe adds one call, full result-block check and fresh ROM identity.
Both device actions leave the unit in ROM.
There are no file/address/length/argument inputs, loaders, hooks, flash commands,
automatic reset commands or retries. Requires the same USB venv as rom_check.
This is the first custom-code experiment, not a backup or recovery guarantee.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import struct
import sys

import minitoo_rom_check as rom

ADDRESS = 0x120000
SIZE = 512
RESULT_OFFSET = 0x1F0
MARKER = 0x4D544F4B
CODE = bytes.fromhex("c0fff0011200c1ff4b4f544d81608000")
BLOCK_SHA256 = "7346172b60c37a5656b1426637bc3493e953d9f5703c8491fe9769e263d60485"
MAGIC = bytes.fromhex("c3cfc0e8ced2b0aec4e3a3acd3f1c1d6")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def crc16(data, seed=0):
    """Unreflected CRC-16/0x1021, matching ROM's hardware accumulator."""
    crc = seed
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xFFFF
    return crc


def transform_block(data):
    """MengLi XOR for exactly one block; ROM resets the stream per command."""
    if len(data) != SIZE:
        raise ValueError("Only one complete 512-byte probe block is supported")
    crc = crc16(b"\xff\xff", 0xFFFF)
    result = bytearray(data)
    for i in range(SIZE):
        crc = crc16(MAGIC[i % len(MAGIC):i % len(MAGIC) + 1], crc)
        result[i] ^= crc & 0xFF
    return bytes(result)


def fixed_block():
    data = CODE + bytes(SIZE - len(CODE))
    if len(CODE) != 16 or sha256(data) != BLOCK_SHA256:
        raise ValueError("RAM program differs from the pinned reviewed block")
    return data


def result_block():
    data = bytearray(fixed_block())
    data[RESULT_OFFSET:RESULT_OFFSET + 4] = struct.pack("<I", MARKER)
    return bytes(data)


def commands():
    encrypted = transform_block(fixed_block())
    upload = (b"\xfb\x06" + struct.pack(">IH", ADDRESS, SIZE) + b"\0" +
              struct.pack("<H", crc16(encrypted)) + b"\xff" * 5)
    read = b"\xfd\x07" + struct.pack(">IH", ADDRESS, SIZE) + b"\xff" * 8
    call = b"\xfb\x08" + struct.pack(">IH", ADDRESS, 0) + b"\xff" * 8
    return upload, read, call


def probe_cbw(cdb, length, tag, payload=None):
    """Accept only these three exact transfers; never an arbitrary RAM command."""
    upload, read, call = commands()
    if (cdb, length, payload) == (upload, SIZE, transform_block(fixed_block())):
        direction = 0
    elif payload is None and (cdb, length) in ((read, SIZE), (call, 16)):
        direction = 0x80
    else:
        raise ValueError("Transfer is outside the fixed RAM-probe allowlist")
    return struct.pack("<4sIIBBB16s", b"USBC", tag, length, direction, 0, 16, cdb)


class ProbeSession(rom.Session):
    def __init__(self, device, report, result):
        super().__init__(device, report)
        self.result = result
        self.phase = "new"
        self.paths_verified = False

    def _command(self, cdb, length):
        # Inherited identity/fingerprint methods remain useful, but this session
        # must never call the existing ROM-reset stub or another mode transition.
        if cdb in (rom.ENTER, rom.RESET):
            raise ValueError("Mode transitions are forbidden in the probe session")
        return super()._command(cdb, length)

    @contextmanager
    def step(self, expected, active, complete):
        if self.phase != expected:
            raise ValueError(f"Probe step requires {expected}; current phase is {self.phase}")
        self.phase = active
        try:
            yield
        except BaseException:
            self.phase = "failed"
            raise
        else:
            self.phase = complete

    def verify_paths(self):
        with self.step("new", "verifying", "verified"):
            self.verify_rom(probe_check=True)
            self.paths_verified = True
            self.result["rom_fingerprints_confirmed"] = True

    def _probe_transfer(self, cdb, length, payload=None):
        upload, read, call = commands()
        allowed_phase = {upload: ("uploading",),
                         read: ("reading-initial", "reading-result"),
                         call: ("calling",)}
        if not (self.mode == "rom" and self.verified and self.paths_verified):
            raise ValueError("RAM transfer requires fresh exact ROM identity and 12 matching excerpts")
        if self.phase not in allowed_phase.get(cdb, ()):
            raise ValueError("RAM transfer is out of sequence")
        wrapper = probe_cbw(cdb, length, self.tag + 1, payload)
        self.tag += 1
        self.report.setdefault("commands_attempted", []).append(cdb.hex())
        if self.dev.write(self.outgoing, wrapper, timeout=2000) != 31:
            raise ValueError("Short probe command-wrapper transfer")
        if payload is not None:
            if self.dev.write(self.outgoing, payload, timeout=2000) != SIZE:
                raise ValueError("Short probe upload; no readback or execution will follow")
            data = b""
        else:
            data = bytes(self.dev.read(self.incoming, length, timeout=2000))
            if len(data) != length:
                raise ValueError("Wrong probe data length")
        rom.check_csw(bytes(self.dev.read(self.incoming, 13, timeout=2000)), self.tag)
        return data

    def upload(self):
        with self.step("verified", "uploading", "uploaded"):
            self.result["ram_uploads_attempted"] += 1
            self._probe_transfer(commands()[0], SIZE, transform_block(fixed_block()))
            self.result["ram_upload_status_confirmed"] = True

    def verify_upload(self):
        with self.step("uploaded", "reading-initial", "readback-verified"):
            data = transform_block(self._probe_transfer(commands()[1], SIZE))
            self.report["upload_readback_sha256"] = sha256(data)
            if data != fixed_block():
                raise ValueError("Complete upload readback differs; no execution will follow")
            self.result["upload_readback_confirmed"] = True

    def execute(self):
        with self.step("readback-verified", "calling", "returned"):
            self.result["execution_attempted"] = True
            data = self._probe_transfer(commands()[2], 16)
            self.report["call_response_prefix"] = data[:2].hex()
            if data[:2] != b"\xfb\x08":
                raise ValueError("Wrong RAM-call response; stopping without retry")
            # The remaining 14 bytes come from ROM's stack and are unspecified.
            self.result["return_response_confirmed"] = True

    def verify_result(self):
        with self.step("returned", "reading-result", "result-verified"):
            data = transform_block(self._probe_transfer(commands()[1], SIZE))
            self.report["result_readback_sha256"] = sha256(data)
            self.report["result_word"] = f"0x{struct.unpack_from('<I', data, RESULT_OFFSET)[0]:08x}"
            if data != result_block():
                raise ValueError("Complete result block differs from the expected single-word change")
            self.result["marker_confirmed"] = True

    def confirm_return(self):
        with self.step("result-verified", "checking-rom", "complete"):
            self.identify("rom")
            self.result["rom_return_confirmed"] = True


def plan():
    upload, read, call = commands()
    return {
        "purpose": "Offline plan for one fixed RAM marker; no device access",
        "entry_address": f"0x{ADDRESS:08x}",
        "block_bytes": SIZE, "code_bytes": len(CODE),
        "result_address": f"0x{ADDRESS + RESULT_OFFSET:08x}",
        "marker_u32": f"0x{MARKER:08x}",
        "block_sha256": sha256(fixed_block()),
        "encrypted_block_sha256": sha256(transform_block(fixed_block())),
        "expected_result_block_sha256": sha256(result_block()),
        "upload_cdb": upload.hex(), "readback_cdb": read.hex(), "call_cdb": call.hex(),
        "rom_fingerprint_regions": len(rom.ROM_FINGERPRINTS) + len(rom.PROBE_ROM_FINGERPRINTS),
        "first_device_action": "roundtrip-only; upload/readback with no execution call",
        "sequence": ["fresh application identity", "one software ROM entry",
                     "ROM identity and 12 fingerprints", "one fixed RAM upload",
                     "full upload readback", "one call", "full result readback",
                     "fresh ROM identity", "release USB capture; manual button restart"],
        "flash_commands": 0, "automatic_reset_commands": 0, "retries": 0,
    }


def run(execute=False):
    result = {"purpose": "One fixed 16-byte RAM-marker experiment",
              "action": "run-fixed-probe" if execute else "roundtrip-only", "flash_commands": 0,
              "entry_confirmed": False, "rom_fingerprints_confirmed": False,
              "ram_uploads_attempted": 0, "ram_upload_status_confirmed": False,
              "upload_readback_confirmed": False, "execution_attempted": False,
              "return_response_confirmed": False, "marker_confirmed": False,
              "rom_return_confirmed": False, "custom_code_confirmed": False,
              "automatic_reset_commands": 0, "sessions": []}
    try:
        fixed_block()  # Fail before even enumerating if the pinned code changed.
        backend = rom.usb.backend.libusb1.get_backend(find_library=rom.libusb_package.find_library)
        if backend is None:
            raise ValueError("libusb backend unavailable")
        devices = rom.enumerate_target(backend)
        device = rom.select(devices, rom.APP_PID)
        if device is None:
            raise ValueError("Fresh application USB required; finish the tested power-key restart and reconnect USB")
        port = rom.location(device)
        report = {"stage": "application-entry"}
        result["sessions"].append(report)
        with rom.Session(device, report) as session:
            session.identify("app")
            session.transition("enter")
        device = rom.wait_for(backend, rom.ROM_PID, port)
        report = {"stage": "fixed-ram-marker"}
        result["sessions"].append(report)
        with ProbeSession(device, report, result) as session:
            session.identify("rom")
            result["entry_confirmed"] = True
            session.verify_paths()
            session.upload()
            session.verify_upload()
            if execute:
                session.execute()
                session.verify_result()
                session.confirm_return()
        result["custom_code_confirmed"] = bool(execute)
        result["note"] = (
            ("The expected single-word RAM change and return to ROM were verified. " if execute else
             "One fixed RAM block was uploaded and its complete readback matched. No execution call was sent. ") +
            "Device remains in ROM; no firmware update or flash command was sent. "
            "Use the tested power-key restart and reconnect USB if needed.")
        return result, False
    except (rom.usb.core.USBError, ValueError, NotImplementedError) as error:
        result["error"] = str(error)
        result["note"] = ("Stopped without retry or automatic reset. Custom-code success is unconfirmed. "
                          "If ROM entry was attempted, the tested power-key restart may be needed. "
                          "Reset from hung RAM code has not been independently tested.")
        if not result["sessions"]:
            result["note"] = "Stopped before opening a device session; no protocol commands were sent."
        return result, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true", help="Print the offline plan; no device access")
    action.add_argument("--roundtrip-only", action="store_true",
                        help="First device check: upload/readback the fixed RAM block WITHOUT executing it")
    action.add_argument("--run-fixed-probe", action="store_true",
                        help="Upload/readback/call the fixed RAM-only marker once, then stop in ROM")
    args = parser.parse_args()
    if args.plan:
        print(json.dumps(plan(), indent=2))
        return
    if sys.platform == "darwin" and os.geteuid() != 0:
        parser.error("macOS USB capture requires sudo; no USB action attempted")
    result, failed = run(execute=args.run_fixed_probe)
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(int(failed))


if __name__ == "__main__":
    main()
