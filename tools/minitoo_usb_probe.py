#!/usr/bin/env python3
"""Fixed standard SCSI INQUIRY on MiniToo USB; no vendor/update commands.

Dependencies: pyusb==1.3.1, libusb-package==1.0.30.0.
Default checks interface access without sending a bulk command.
--inquiry sends only standard opcode 0x12 to LUN 0.
--capture temporarily releases OS drivers and requires --inquiry and root on
macOS. macOS capture affects ALL USB interfaces of this device, including audio.
Drivers are reattached in finally; USB may re-enumerate. No flash, memory-write,
firmware-reset, bootloader-entry, loader-upload, or arbitrary-command operation.
"""
import argparse
import json
import os
import struct
import sys

import libusb_package
import usb.backend.libusb1
import usb.core
import usb.util


def inquiry_cbw():
    return struct.pack("<4sIIBBB16s", b"USBC", 0x4D540001, 36, 0x80, 0, 6,
                       b"\x12\0\0\0\x24\0" + bytes(10))


def check_reply(data, csw):
    if len(data) != 36 or len(csw) != 13:
        raise ValueError("Wrong INQUIRY or status response length")
    signature, tag, residue, status = struct.unpack("<4sIIB", csw)
    if (signature, tag, residue, status) != (b"USBS", 0x4D540001, 0, 0):
        raise ValueError("INQUIRY status signature/tag/residue/status mismatch")
    return {"vendor": data[8:16].decode("ascii").strip(),
            "product": data[16:32].decode("ascii").strip(),
            "revision": data[32:36].decode("ascii").strip()}


def run(args):
    result = {"purpose": "USB access / standard INQUIRY only", "capture": args.capture,
              "vendor_commands_sent": False, "inquiry_sent": False}
    backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
    if backend is None:
        raise ValueError("libusb backend unavailable")
    devices = list(usb.core.find(find_all=True, idVendor=0x4C4A, idProduct=0x4E55,
                                backend=backend))
    if len(devices) != 1:
        raise ValueError(f"Expected exactly one USB 4c4a:4e55 device; found {len(devices)}")
    dev = devices[0]
    detached = claimed = False
    failed = False
    try:
        active = dev.is_kernel_driver_active(0)
        result["kernel_driver_active"] = active
        if args.capture and active:
            dev.detach_kernel_driver(0)
            detached = True
            result["drivers_temporarily_detached"] = True
        usb.util.claim_interface(dev, 0)
        claimed = True
        result["storage_interface_claimed"] = True
        if args.inquiry:
            interface = dev.get_active_configuration()[(0, 0)]
            if (interface.bInterfaceClass, interface.bInterfaceSubClass,
                    interface.bInterfaceProtocol) != (8, 6, 0x50):
                raise ValueError("Interface 0 is not SCSI bulk-only storage")
            bulk = [ep for ep in interface if usb.util.endpoint_type(ep.bmAttributes) == 2]
            incoming = [ep.bEndpointAddress for ep in bulk
                        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN]
            outgoing = [ep.bEndpointAddress for ep in bulk
                        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT]
            if len(incoming) != 1 or len(outgoing) != 1:
                raise ValueError("Expected one bulk IN and one bulk OUT endpoint")
            cbw = inquiry_cbw()
            result["inquiry_sent"] = True
            if dev.write(outgoing[0], cbw, timeout=2000) != len(cbw):
                raise ValueError("Short INQUIRY command transfer")
            data = bytes(dev.read(incoming[0], 36, timeout=2000))
            csw = bytes(dev.read(incoming[0], 13, timeout=2000))
            result["inquiry"] = check_reply(data, csw)
    except (usb.core.USBError, ValueError, NotImplementedError) as error:
        result["error"] = str(error)
        failed = True
    finally:
        if claimed:
            try:
                usb.util.release_interface(dev, 0)
            except usb.core.USBError as error:
                result["release_error"] = str(error)
                failed = True
        if detached:
            try:
                dev.attach_kernel_driver(0)
                result["drivers_reattached"] = True
            except (usb.core.USBError, NotImplementedError) as error:
                result["reattach_error"] = str(error)
                failed = True
        usb.util.dispose_resources(dev)
    return result, failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inquiry", action="store_true")
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    if args.capture and not args.inquiry:
        parser.error("--capture requires --inquiry")
    if args.capture and sys.platform == "darwin" and os.geteuid() != 0:
        parser.error("macOS USB capture requires sudo; no capture attempted")
    try:
        result, failed = run(args)
    except (usb.core.USBError, ValueError) as error:
        result, failed = {"error": str(error), "vendor_commands_sent": False}, True
    print(json.dumps(result, indent=2))
    raise SystemExit(int(failed))


if __name__ == "__main__":
    main()
