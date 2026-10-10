#!/usr/bin/env python3
# SPDX-License-Identifier: MIT AND Apache-2.0
# Copyright 2026 Brad Dwyer
# Original project code is MIT; the Jieli ROM excerpts retain Apache-2.0.
# Includes extracted Jieli-Tech/fw-Bootloader ROM excerpts; see ../NOTICE.
# Excerpts are rendered as constants; original instruction bytes are unchanged.
"""MiniToo BR28 software ROM-entry/exit check; no firmware/loader upload.

Requires pyusb==1.3.1 and libusb-package==1.0.30.0. Run with sudo on macOS.
Temporarily captures the whole USB device (audio/HID included).
--enter-exit sends ONE fixed FC0A to a BR28 UDISK, waits for BR28 UBOOT1.00
on the same USB port, reads four fixed ROM fingerprints, then calls the existing
ROM chip_reset function. --exit-rom resumes the verification/reset step only.
--enter-verify stops after ROM identification/fingerprints, releases USB capture,
and leaves the device in ROM mode for a separately performed button check.
--enter-probe-check additionally fingerprints eight fixed immutable-ROM regions
used in the offline RAM-probe review. It also stops in ROM, without uploading or
executing a RAM probe. Matching bytes do not establish runtime cache state.
On the tested unit, normal power-button startup was needed after ROM reset.
No arbitrary commands, addresses, mutable-memory reads, data-OUT payloads,
memory-write, flash-read/write/erase, key-write, or loader operations exist here.
This tests software entry, not recovery from a broken application.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import time

import libusb_package
import usb.backend.libusb1
import usb.core
import usb.util

VID = 0x4C4A
APP_PID = 0x4E55
ROM_PID = 0x3442  # Official BR28 ROM USB descriptor at 0x45fb.
APP_ID = {"vendor": "BR28", "product": "UDISK", "revision": "1.00"}
ROM_ID = {"vendor": "BR28", "product": "UBOOT1.00", "revision": "1.00"}
INQUIRY = b"\x12\0\0\0\x24\0"
ENTER = b"\xfc\x0a" + b"\xff" * 14
RESET = b"\xfb\x08\x00\x01\xfd\xf4\0\0" + b"\xff" * 8

# From Jieli-Tech/fw-Bootloader ff3b9299, BR28 output/rom.image (128 KiB).
# SHA256 7cae0a02e3ab3755c1e392f03c89222dd701065ec9bd3ec8ac109a7b3f40f793.
# Verify both the reset stub and its body, plus boot-tag consumption/clearing.
# FD07's BR28 implementation XORs at the requested address before/after sending;
# only immutable mask-ROM addresses are allowed here, never RAM/peripherals.
ROM_FINGERPRINTS = (
    (0x1FDF0, bytes.fromhex("ffea6923ffea8723")),
    (0x4506, bytes.fromhex("c0ff80c2f20000ef1000f79f")),
    (0x4470, bytes.fromhex(
        "7404c4ff00081800c1ff684400004228401680ff7cfcffff0056"
        "c1ff604400004228401680ff6afcffff004fc1ff584400004228"
        "401680ff58fcffff011640208149402604834022048140234220"
        "432050ec41205404")),
    (0xC38E, bytes.fromhex("80ffdc80ffff0416b45b")),
)

# Additional immutable-ROM excerpts reviewed in docs/technical-notes.md.
# SHA-256 values are pinned here, not supplied by a CLI or an external manifest.
PROBE_ROM_FINGERPRINTS = (
    (0x468A, 158, "b2c527ebbdc3c1860f049cd6f8c5dc311b97f9a0001e25aa3a3f81c88907a6e8"),
    (0x4738, 122, "b8aeb501a499d14b6a18f241d40c69136f0cddb599ae7c501f8924c6b21b0c2a"),
    (0x4948, 82, "ec2e886c3c5c55e86693dc475bb7e7555ddc3066b4e08416a518f5c7df69b844"),
    (0x499A, 90, "c6ac77e5597ec4ae3fdd75a2c09a99bc49f4f007057e166d22223f375bec56e4"),
    (0x4A70, 110, "9d1e9fe0045a8e640e220c6ac2f423cdbebf0ab0e143b8ff3f44dd01ac8ad912"),
    (0xAA1E, 68, "0a0118c9693fbcc1d1fd3ef2d0aa61d098c1abd7b998278e74c58f234bcd744c"),
    (0x1F619, 16, "2f3e78fc341f7ee59c7577e9318cd3e10cd9b5b4222ad02274408cdca61f3936"),
    (0xA120, 158, "634cec37169fd633bfe6cc6fcd121d7a1d64ba1d584f675ed2a44bc4e2c1301f"),
)


def rom_read_cdb(address, length):
    """Only fingerprints fixed above can be read; no address CLI."""
    allowed = [(a, len(b)) for a, b in ROM_FINGERPRINTS]
    allowed += [(a, size) for a, size, _ in PROBE_ROM_FINGERPRINTS]
    if (address, length) not in allowed:
        raise ValueError("ROM read is outside the fixed fingerprint allowlist")
    return b"\xfd\x07" + struct.pack(">IH", address, length) + b"\xff" * 8


def cbw(cdb, length, tag):
    allowed = [(INQUIRY, 36), (ENTER, 16), (RESET, 16)]
    allowed += [(rom_read_cdb(a, len(b)), len(b)) for a, b in ROM_FINGERPRINTS]
    allowed += [(rom_read_cdb(a, size), size) for a, size, _ in PROBE_ROM_FINGERPRINTS]
    if (cdb, length) not in allowed:
        raise ValueError("Command is outside the fixed allowlist")
    return struct.pack("<4sIIBBB16s", b"USBC", tag, length, 0x80, 0,
                       len(cdb), cdb.ljust(16, b"\0"))


def check_csw(csw, tag):
    if len(csw) != 13:
        raise ValueError("Wrong bulk-only status length")
    if struct.unpack("<4sIIB", csw) != (b"USBS", tag, 0, 0):
        raise ValueError("Bulk-only status signature/tag/residue/status mismatch")


def location(device):
    ports = tuple(device.port_numbers or ())
    if device.bus is None or not ports:
        raise ValueError("USB physical port information unavailable; refusing transition")
    return device.bus, ports


def enumerate_target(backend):
    return [d for d in usb.core.find(find_all=True, idVendor=VID, backend=backend)
            if d.idProduct in (APP_PID, ROM_PID)]


def select(devices, pid, expected_port=None):
    if len(devices) > 1:
        raise ValueError("Multiple matching Jieli devices; unplug the other device")
    if not devices:
        return None
    device = devices[0]
    port = location(device)
    if expected_port is not None and port != expected_port:
        raise ValueError("USB physical port changed; refusing to operate")
    return device if device.idProduct == pid else None


def wait_for(backend, pid, port, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        dev = select(enumerate_target(backend), pid, port)
        if dev is not None:
            return dev
        time.sleep(0.25)
    raise ValueError(f"Timed out waiting for USB {VID:04x}:{pid:04x} on the original port")


class Session:
    def __init__(self, device, report):
        self.dev = device
        self.report = report
        self.detached = self.claimed = False
        self.tag = 0x4D540100
        self.mode = None
        self.verified = False

    def __enter__(self):
        try:
            active = self.dev.is_kernel_driver_active(0)
            self.report["kernel_driver_active"] = active
            if active:
                self.dev.detach_kernel_driver(0)
                self.detached = True
                self.report["drivers_temporarily_detached"] = True
            usb.util.claim_interface(self.dev, 0)
            self.claimed = True
            interface = self.dev.get_active_configuration()[(0, 0)]
            if (interface.bInterfaceClass, interface.bInterfaceSubClass,
                    interface.bInterfaceProtocol) != (8, 6, 0x50):
                raise ValueError("Interface 0 is not SCSI bulk-only storage")
            bulk = [ep.bEndpointAddress for ep in interface
                    if usb.util.endpoint_type(ep.bmAttributes) == 2]
            incoming = [ep for ep in bulk if ep & 0x80]
            outgoing = [ep for ep in bulk if not ep & 0x80]
            if len(incoming) != 1 or len(outgoing) != 1:
                raise ValueError("Expected one bulk IN and one bulk OUT endpoint")
            self.incoming, self.outgoing = incoming[0], outgoing[0]
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(self, exc_type, exc, traceback):
        # Reset/entry may invalidate the old handle. Do not reuse it or send a
        # BOT reset/control recovery request; new enumeration is checked instead.
        errors = []
        if self.claimed:
            try:
                usb.util.release_interface(self.dev, 0)
            except usb.core.USBError as error:
                errors.append(f"release: {error}")
        if self.detached:
            try:
                self.dev.attach_kernel_driver(0)
                self.report["drivers_reattached"] = True
            except (usb.core.USBError, NotImplementedError) as error:
                errors.append(f"reattach: {error}")
        try:
            usb.util.dispose_resources(self.dev)
        except usb.core.USBError as error:
            errors.append(f"dispose: {error}")
        if errors:
            self.report["cleanup_errors"] = errors
        if errors and not self.report.get("transition_attempted") and exc is None:
            raise ValueError("USB cleanup failed: " + "; ".join(errors))
        return False

    def _command(self, cdb, length):
        # Authorization is enforced here as well as in the named methods.
        if cdb == ENTER and self.mode != "app":
            raise ValueError("Entry requires the exact application identity")
        if cdb == RESET and not (self.mode == "rom" and self.verified):
            raise ValueError("Reset requires the exact ROM identity and all fingerprints")
        if cdb[:2] == b"\xfd\x07" and self.mode != "rom":
            raise ValueError("ROM read requires the exact ROM identity")
        self.tag += 1
        wrapper = cbw(cdb, length, self.tag)
        commands = self.report.setdefault("commands_attempted", [])
        commands.append(cdb.hex())
        if self.dev.write(self.outgoing, wrapper, timeout=2000) != len(wrapper):
            raise ValueError("Short bulk command-wrapper transfer")
        data = bytes(self.dev.read(self.incoming, length, timeout=2000))
        if len(data) != length:
            raise ValueError("Wrong bulk data length")
        check_csw(bytes(self.dev.read(self.incoming, 13, timeout=2000)), self.tag)
        return data

    def identify(self, mode):
        expected = {"app": APP_ID, "rom": ROM_ID}[mode]
        expected_pid = {"app": APP_PID, "rom": ROM_PID}[mode]
        if self.dev.idVendor != VID or self.dev.idProduct != expected_pid:
            raise ValueError("Wrong USB VID/PID for requested mode")
        self.mode = None
        self.verified = False
        data = self._command(INQUIRY, 36)
        actual = {"vendor": data[8:16].decode("ascii").strip(),
                  "product": data[16:32].decode("ascii").strip(),
                  "revision": data[32:36].decode("ascii").strip()}
        self.report["inquiry"] = actual
        if actual != expected:
            raise ValueError(f"Unexpected {mode} INQUIRY identity; stopping")
        self.mode = mode

    def verify_rom(self, probe_check=False):
        self.verified = False
        matches = self.report.setdefault("rom_fingerprints", [])
        for address, expected in ROM_FINGERPRINTS:
            actual = self._command(rom_read_cdb(address, len(expected)), len(expected))
            matches.append({"address": f"0x{address:08x}", "size": len(expected),
                            "match": actual == expected})
            if actual != expected:
                raise ValueError(f"ROM fingerprint differs at {address:#x}; no reset sent")
        if probe_check:
            matches = self.report.setdefault("probe_rom_fingerprints", [])
            for address, size, expected_hash in PROBE_ROM_FINGERPRINTS:
                actual = self._command(rom_read_cdb(address, size), size)
                actual_hash = hashlib.sha256(actual).hexdigest()
                matches.append({"address": f"0x{address:08x}", "size": size,
                                "sha256": actual_hash,
                                "match": actual_hash == expected_hash})
                if actual_hash != expected_hash:
                    raise ValueError(f"Probe-path ROM fingerprint differs at {address:#x}; stopping")
        self.verified = True

    def transition(self, kind):
        if kind not in ("enter", "reset"):
            raise ValueError("Unsupported transition")
        command = {"enter": ENTER, "reset": RESET}[kind]
        # Set only after guards pass, so errors cannot disguise a refusal as a
        # possibly successful reset. No transition is ever retried.
        if kind == "enter" and self.mode != "app":
            raise ValueError("Entry requires the exact application identity")
        if kind == "reset" and not (self.mode == "rom" and self.verified):
            raise ValueError("Reset requires all ROM fingerprints")
        self.report["transition_attempted"] = kind
        try:
            data = self._command(command, 16)
            self.report["transition_response_prefix"] = data[:2].hex()
        except (usb.core.USBError, ValueError) as error:
            # A disconnect, stall or timeout is expected here, but it is never
            # counted as success. Only the next mode's INQUIRY establishes that.
            self.report["transition_transport_result"] = str(error)


def run(exit_only=False, enter_verify=False, probe_check=False):
    leave_in_rom = enter_verify or probe_check
    result = {"purpose": "BR28 software ROM entry/exit check",
              "action": ("enter-probe-check" if probe_check else
                         "enter-verify" if enter_verify else
                         "exit-rom" if exit_only else "enter-exit"),
              "firmware_uploads": 0, "memory_write_commands": 0,
              "flash_commands": 0, "entry_confirmed": False,
              "rom_fingerprints_confirmed": False,
              "probe_rom_fingerprints_confirmed": False,
              "rom_reset_attempted": False,
              "application_return_confirmed": False, "sessions": []}
    try:
        if sum(map(bool, (exit_only, enter_verify, probe_check))) > 1:
            raise ValueError("Cannot combine ROM-check actions")
        backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
        if backend is None:
            raise ValueError("libusb backend unavailable")
        pid = ROM_PID if exit_only else APP_PID
        devices = enumerate_target(backend)
        device = select(devices, pid)
        if device is None:
            if not devices:
                raise ValueError("MiniToo USB device not found; check power and reconnect its data cable")
            if exit_only:
                raise ValueError("Application USB PID is present; --exit-rom requires ROM mode")
            raise ValueError("ROM USB PID is already present; --exit-rom requires fresh ROM identity/fingerprint checks")
        port = location(device)
        if not exit_only:
            report = {"stage": "application-entry"}
            result["sessions"].append(report)
            with Session(device, report) as session:
                session.identify("app")
                session.transition("enter")
            device = wait_for(backend, ROM_PID, port)
        report = {"stage": ("rom-probe-path-verify" if probe_check else
                            "rom-verify" if enter_verify else "rom-verify-reset")}
        result["sessions"].append(report)
        with Session(device, report) as session:
            session.identify("rom")
            result["entry_confirmed"] = True
            session.verify_rom(probe_check=probe_check)
            result["rom_fingerprints_confirmed"] = True
            result["probe_rom_fingerprints_confirmed"] = bool(probe_check)
            if not leave_in_rom:
                session.transition("reset")
                result["rom_reset_attempted"] = True
        if leave_in_rom:
            result["note"] = ("ROM verified and USB capture released; device remains in ROM. "
                              "No RAM payload was uploaded or executed and no reset command was sent. "
                              "Use the tested front-left power-key hold (about 10 seconds), "
                              "release at startup, then reconnect USB if needed. "
                              "The existing --exit-rom action remains available.")
            return result, False
        print("ROM reset requested. If the screen stays dark, turn the MiniToo "
              "on normally. If USB stays absent, reconnect its cable to the same "
              "port. Waiting up to 30 seconds for application USB.",
              file=sys.stderr, flush=True)
        device = wait_for(backend, APP_PID, port)
        report = {"stage": "application-return"}
        result["sessions"].append(report)
        with Session(device, report) as session:
            session.identify("app")
        result["application_return_confirmed"] = True
        result["note"] = "Software entry/exit only; installed firmware is not backed up"
        return result, False
    except (usb.core.USBError, ValueError, NotImplementedError) as error:
        result["error"] = str(error)
        result["note"] = "Stopped without retrying transitions; device may remain in ROM mode"
        if not result["sessions"]:
            result["note"] = ("Stopped before opening a device session; no protocol commands "
                              "or entry/reset commands were sent.")
        elif result["rom_reset_attempted"]:
            result["note"] = ("ROM reset attempted, but application USB return unconfirmed; "
                              "normal power-on and/or USB reconnect may be needed. "
                              "No firmware was uploaded and no transition will be retried.")
        elif not any(s.get("transition_attempted") for s in result["sessions"]):
            result["note"] = ("Stopped before any mode transition; no entry/reset command "
                              "was sent. The current device mode is not changed by this action.")
        return result, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--enter-exit", action="store_true")
    action.add_argument("--exit-rom", action="store_true")
    action.add_argument("--enter-verify", action="store_true",
                        help="Verify ROM, release USB capture and leave the device in ROM")
    action.add_argument("--enter-probe-check", action="store_true",
                        help="Also verify fixed probe-path ROM excerpts; no RAM upload/execution")
    args = parser.parse_args()
    if sys.platform == "darwin" and os.geteuid() != 0:
        parser.error("macOS USB capture requires sudo; no USB action attempted")
    # The report survives ordinary failures. Ctrl-C still unwinds driver cleanup;
    # --exit-rom can resume the fixed verification/reset path after interruption.
    result, failed = run(exit_only=args.exit_rom, enter_verify=args.enter_verify,
                         probe_check=args.enter_probe_check)
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(int(failed))


if __name__ == "__main__":
    main()
