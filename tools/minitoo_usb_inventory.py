#!/usr/bin/env python3
"""Read macOS registry metadata only; no USB commands or mode changes.

Omits device serial numbers. UDISK is not proof of ROM recovery access.
"""
import argparse
import json
import plistlib
import subprocess
from pathlib import Path


def registry(cls):
    raw = subprocess.check_output(["ioreg", "-r", "-c", cls, "-a", "-l"])
    # ioreg emits no plist when the requested class has no registered instances,
    # e.g. while the MiniToo has disconnected for a ROM transition/reset.
    return plistlib.loads(raw) if raw.strip() else []


def inventory():
    devices = []
    for item in registry("IOUSBHostDevice"):
        if item.get("idVendor") == 0x4C4A:
            pid = item.get("idProduct")
            devices.append({"vendor_id": "0x4c4a",
                            "product_id": f"0x{pid:04x}" if isinstance(pid, int) else None,
                            "mode_hint": {0x4E55: "application", 0x3442: "ROM"}.get(pid, "unknown"),
                            "vendor": item.get("USB Vendor Name"),
                            "product": item.get("USB Product Name")})
    interfaces = []
    for item in registry("IOUSBHostInterface"):
        if item.get("idVendor") == 0x4C4A:
            interfaces.append({k: item[k] for k in ["bInterfaceNumber", "bInterfaceClass",
                               "bInterfaceSubClass", "bInterfaceProtocol", "bNumEndpoints",
                               "kUSBString"] if k in item})
    storage = []
    for item in registry("IOSCSIPeripheralDeviceNub"):
        if item.get("Vendor Identification", "").strip() == "BR28":
            storage.append({k: item[k] for k in ["Vendor Identification",
                            "Product Identification", "Product Revision Level",
                            "SCSI Logical Unit Number"] if k in item})
    return {"devices": devices, "interfaces": interfaces, "br28_storage": storage,
            "limitations": ["Registry snapshot only; no USB requests sent by this tool",
                            "Does not establish ROM recovery, flash-read access, or compatibility"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(inventory(), indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
