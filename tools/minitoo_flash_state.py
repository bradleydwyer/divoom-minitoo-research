#!/usr/bin/env python3
"""One fixed ROM-mode GPIO/SPI configuration snapshot, with no flash transaction.

--plan is offline. --roundtrip-only uploads and verifies the fixed 512-byte RAM
block without executing it. --run-fixed-snapshot additionally calls it once,
checks the complete result block, and confirms return to ROM. Fresh application
USB is required for either device action. No payload files, addresses, lengths,
flash commands, peripheral writes, automatic resets, retries or mode bypasses.
Uses the existing USB venv and requires sudo for macOS device actions.

--bus-plan, --bus-roundtrip-only and --run-fixed-bus-snapshot select a second
fixed, read-only program that includes the main SFC and clock configuration.
"""
import argparse
import json
import os
import struct
import sys

import minitoo_ram_marker as marker
import minitoo_flash_state_payload as payload
import minitoo_flash_bus_state_payload as bus_payload

rom = marker.rom


def _commands(profile):
    encoded = marker.transform_block(profile.make_block())
    upload = (b"\xfb\x06" + struct.pack(">IH", profile.ADDRESS, profile.SIZE) + b"\0"
              + struct.pack("<H", marker.crc16(encoded)) + b"\xff" * 5)
    read = b"\xfd\x07" + struct.pack(">IH", profile.ADDRESS, profile.SIZE) + b"\xff" * 8
    call = b"\xfb\x08" + struct.pack(">IH", profile.ADDRESS, 0) + b"\xff" * 8
    return upload, read, call


def commands():
    return _commands(payload)


def bus_commands():
    return _commands(bus_payload)


def snapshot_cbw(cdb, length, tag, data=None, *, bus_state=False):
    profile = bus_payload if bus_state else payload
    upload, read, call = _commands(profile)
    if (cdb, length, data) == (upload, profile.SIZE, marker.transform_block(profile.make_block())):
        direction = 0
    elif data is None and (cdb, length) in ((read, profile.SIZE), (call, 16)):
        direction = 0x80
    else:
        raise ValueError("Transfer is outside the fixed configuration-snapshot allowlist")
    return struct.pack("<4sIIBBB16s", b"USBC", tag, length, direction, 0, 16, cdb)


class SnapshotSession(marker.ProbeSession):
    # Reuse the tested capture, phase, identity, 12-fingerprint and cleanup
    # logic. Override all payload-specific transfer/upload/call/result handling.
    payload = payload
    commands = staticmethod(commands)
    bus_state = False

    def _probe_transfer(self, cdb, length, data=None):
        upload, read, call = self.commands()
        phases = {upload: ("uploading",), read: ("reading-initial", "reading-result"),
                  call: ("calling",)}
        if not (self.mode == "rom" and self.verified and self.paths_verified):
            raise ValueError("Snapshot requires fresh ROM identity and all 12 matching excerpts")
        if self.phase not in phases.get(cdb, ()):
            raise ValueError("Snapshot transfer is out of sequence")
        wrapper = snapshot_cbw(cdb, length, self.tag + 1, data, bus_state=self.bus_state)
        self.tag += 1
        self.report.setdefault("commands_attempted", []).append(cdb.hex())
        if self.dev.write(self.outgoing, wrapper, timeout=2000) != 31:
            raise ValueError("Short snapshot command-wrapper transfer")
        if data is not None:
            if self.dev.write(self.outgoing, data, timeout=2000) != self.payload.SIZE:
                raise ValueError("Short snapshot upload; no further commands will follow")
            reply = b""
        else:
            reply = bytes(self.dev.read(self.incoming, length, timeout=2000))
            if len(reply) != length:
                raise ValueError("Wrong snapshot data length")
        rom.check_csw(bytes(self.dev.read(self.incoming, 13, timeout=2000)), self.tag)
        return reply

    def upload(self):
        with self.step("verified", "uploading", "uploaded"):
            self.result["ram_uploads_attempted"] += 1
            self._probe_transfer(self.commands()[0], self.payload.SIZE,
                                 marker.transform_block(self.payload.make_block()))
            self.result["ram_upload_status_confirmed"] = True

    def verify_upload(self):
        with self.step("uploaded", "reading-initial", "readback-verified"):
            data = marker.transform_block(self._probe_transfer(self.commands()[1], self.payload.SIZE))
            self.report["upload_readback_sha256"] = self.payload.sha256(data)
            if data != self.payload.make_block():
                raise ValueError("Complete snapshot upload differs; no execution will follow")
            self.result["upload_readback_confirmed"] = True

    def verify_result(self):
        with self.step("returned", "reading-result", "result-verified"):
            data = marker.transform_block(self._probe_transfer(self.commands()[1], self.payload.SIZE))
            self.report["result_readback_sha256"] = self.payload.sha256(data)
            self.report["snapshot"] = self.payload.decode_result(data)
            self.result["result_block_confirmed"] = True

    def execute(self):
        with self.step("readback-verified", "calling", "returned"):
            self.result["execution_attempted"] = True
            data = self._probe_transfer(self.commands()[2], 16)
            self.report["call_response_prefix"] = data[:2].hex()
            if data[:2] != b"\xfb\x08":
                raise ValueError("Wrong snapshot-call response; stopping without retry")
            self.result["return_response_confirmed"] = True


class BusStateSession(SnapshotSession):
    payload = bus_payload
    commands = staticmethod(bus_commands)
    bus_state = True


def plan(bus_state=False):
    profile = bus_payload if bus_state else payload
    upload, read, call = _commands(profile)
    return {
        "purpose": "Offline plan for a fixed GPIO/SPI configuration snapshot; no USB access",
        "snapshot_kind": "bus-state" if bus_state else "configuration",
        "entry_address": f"0x{profile.ADDRESS:08x}", "block_bytes": profile.SIZE,
        "code_bytes": len(profile.CODE), "instructions": profile.INSTRUCTIONS,
        "result_address": f"0x{profile.ADDRESS + profile.RESULT_OFFSET:08x}",
        "result_bytes": profile.RESULT_BYTES, "block_sha256": profile.sha256(profile.make_block()),
        "encrypted_block_sha256": profile.sha256(marker.transform_block(profile.make_block())),
        "fixed_reads": [{"name": name, "address": f"0x{address:08x}"}
                        for name, address in profile.SAMPLES],
        "upload_cdb": upload.hex(), "readback_cdb": read.hex(), "call_cdb": call.hex(),
        "rom_fingerprint_regions": 12, "flash_commands": 0,
        "payload_peripheral_writes": 0, "automatic_reset_commands": 0, "retries": 0,
        "sequence": ["fresh application identity", "one software ROM entry",
                     "ROM identity and 12 fingerprints", "one pinned RAM upload",
                     "complete upload readback", "one call if explicitly selected",
                     "complete result validation", "fresh ROM identity", "release capture"],
        "note": ("Reads configuration only; does not identify or read the flash chip. "
                 + ("Physical bus-state snapshot succeeded. See docs/technical-notes.md."
                    if bus_state else "Physical configuration snapshot succeeded. See docs/technical-notes.md.")),
    }


def run(execute=False, bus_state=False):
    session_type = BusStateSession if bus_state else SnapshotSession
    result = {
        "purpose": "One fixed SFC/clock/GPIO snapshot" if bus_state else "One fixed GPIO/SPI configuration snapshot",
        "action": (("run-fixed-bus-snapshot" if execute else "bus-roundtrip-only") if bus_state
                   else ("run-fixed-snapshot" if execute else "roundtrip-only")),
        "flash_commands": 0, "payload_peripheral_writes": 0,
        "entry_confirmed": False, "rom_fingerprints_confirmed": False,
        "ram_uploads_attempted": 0, "ram_upload_status_confirmed": False,
        "upload_readback_confirmed": False, "execution_attempted": False,
        "return_response_confirmed": False, "result_block_confirmed": False,
        "rom_return_confirmed": False, "snapshot_confirmed": False,
        "automatic_reset_commands": 0, "sessions": [],
    }
    try:
        session_type.payload.make_block()  # Fail before enumeration if the pinned program changed.
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
        report = {"stage": "fixed-bus-state-snapshot" if bus_state else "fixed-configuration-snapshot"}
        result["sessions"].append(report)
        with session_type(device, report, result) as session:
            session.identify("rom")
            result["entry_confirmed"] = True
            session.verify_paths()
            session.upload()
            session.verify_upload()
            if execute:
                session.execute()
                session.verify_result()
                session.confirm_return()
        result["snapshot_confirmed"] = bool(execute)
        result["note"] = (
            ("Fixed configuration snapshot and return to ROM verified. " if execute else
             "Fixed RAM upload and complete readback verified; no execution call sent. ")
            + "Device remains in ROM. No flash-chip transaction or peripheral write was in the payload. "
            "Use the tested front-left power-key hold (about 10 seconds), release at startup, "
            "then reconnect USB if needed.")
        return result, False
    except (rom.usb.core.USBError, ValueError, UnicodeError, struct.error, NotImplementedError) as error:
        result["error"] = str(error)
        result["note"] = (
            "Stopped without retry or automatic reset. Snapshot success is unconfirmed. "
            "If ROM entry was attempted, the tested power-key restart may be needed; "
            "reset from hung RAM code has not been independently tested.")
        if not result["sessions"]:
            result["note"] = "Stopped before opening a device session; no protocol commands sent."
        return result, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true")
    action.add_argument("--roundtrip-only", action="store_true")
    action.add_argument("--run-fixed-snapshot", action="store_true")
    action.add_argument("--bus-plan", action="store_true")
    action.add_argument("--bus-roundtrip-only", action="store_true")
    action.add_argument("--run-fixed-bus-snapshot", action="store_true")
    args = parser.parse_args()
    if args.plan or args.bus_plan:
        print(json.dumps(plan(bus_state=args.bus_plan), indent=2))
        return
    if sys.platform == "darwin" and os.geteuid() != 0:
        parser.error("macOS USB capture requires sudo; no USB action attempted")
    result, failed = run(execute=args.run_fixed_snapshot or args.run_fixed_bus_snapshot,
                         bus_state=args.bus_roundtrip_only or args.run_fixed_bus_snapshot)
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(int(failed))


if __name__ == "__main__":
    main()
