#!/usr/bin/env python3
"""Inspect the fixed retained-SRAM capture offline; emit no UUID/reserved bytes.

The SDK's 80-byte flash_info layout is a candidate schema, not a guarantee
about installed firmware. Validate surrounding fields rather than ID bytes
alone. This tool imports no USB code and never opens a device.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


SOURCE = 0x10B000
CAPTURE_BYTES = 20480
STRUCTURE_BYTES = 80
SUCCESS_FLAGS = (
    "entry_confirmed", "rom_fingerprints_confirmed", "ram_upload_status_confirmed",
    "upload_readback_confirmed", "execution_attempted", "return_response_confirmed",
    "result_block_confirmed", "copy_read_twice_confirmed", "rom_return_confirmed",
    "data_saved", "snapshot_confirmed",
)


def validated_capture(path):
    """Check capture provenance against the neighbouring report before parsing."""
    report = json.loads(path.with_name("report.json").read_text())
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if (report.get("action") != "run-fixed-snapshot"
            or report.get("source_address") != f"0x{SOURCE:08x}"
            or report.get("capture_bytes") != CAPTURE_BYTES
            or len(data) != CAPTURE_BYTES):
        raise ValueError("Expected the fixed 20 KiB capture at 0x0010b000")
    if any(report.get(flag) is not True for flag in SUCCESS_FLAGS):
        raise ValueError("Capture report does not confirm the complete SRAM experiment")
    if report.get("capture_sha256") != sha:
        raise ValueError("Capture bytes do not match their report hash")
    sessions = [s for s in report.get("sessions", [])
                if s.get("stage") == "fixed-retained-sram-copy"]
    if len(sessions) != 1 or any(sessions[0].get(f"copy_read_{n}_sha256") != sha
                                 for n in (1, 2)):
        raise ValueError("Both copied-SRAM read hashes must match the saved capture")
    return data, sha


def candidate(data, offset):
    # Offsets come from the preserved SDK vm.c.o DWARF metadata and boot.h.
    # The two UUID arrays (+0..+31) and vm_res (+64..+67) are never emitted.
    init, mode0, mode1 = data[offset + 32:offset + 35]
    size, capacity, extra_capacity, jedec, extra_id = struct.unpack_from("<5I", data, offset + 36)
    alignment = data[offset + 56] * 256
    vm_start = struct.unpack_from("<I", data, offset + 60)[0]
    vm_size, sfc_base, app = struct.unpack_from("<3I", data, offset + 68)
    if init != 1 or mode0 not in (0, 1) or mode1 not in (0, 1):
        return None
    exponent = jedec & 0xFF
    if not (16 <= exponent <= 26 and jedec <= 0xFFFFFF
            and (jedec >> 16) not in (0, 0xFF) and capacity == 1 << exponent
            and 0 < size <= capacity):
        return None
    if not (alignment and alignment & (alignment - 1) == 0
            and vm_size > 0 and vm_start % alignment == 0 and vm_size % alignment == 0
            and vm_start + vm_size <= size and sfc_base < size
            and 0x06000000 <= app < 0x08000000 and app % 4 == 0):
        return None
    return {
        "address": f"0x{SOURCE + offset:08x}",
        "init": init,
        "sfc0_is_4byte_address_mode": bool(mode0),
        "sfc1_is_4byte_address_mode": bool(mode1),
        "flash_size": size,
        "flash_capacity": capacity,
        "extra_flash_capacity": extra_capacity,
        "cached_jedec_id": f"0x{jedec:06x}",
        "cached_extra_flash_id": f"0x{extra_id:08x}",
        "vm_alignment_bytes": alignment,
        "vm_start": f"0x{vm_start:08x}",
        "vm_bytes": vm_size,
        "sfc_base_address": f"0x{sfc_base:08x}",
        "application_address": f"0x{app:08x}",
    }


def inspect(data, sha):
    candidates = [item for offset in range(0, len(data) - STRUCTURE_BYTES + 1, 4)
                  if (item := candidate(data, offset)) is not None]
    return {
        "purpose": "Offline scan for SDK-shaped flash_info structures in retained SRAM",
        "source_address": f"0x{SOURCE:08x}",
        "capture_bytes": len(data),
        "capture_sha256": sha,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "limitations": [
            "Candidates are inferred cached application metadata, not live flash-chip responses.",
            "Address-mode flags do not establish SPI/QPI or continuous-read mode at ROM entry.",
            "This partial SRAM copy is not an installed-firmware backup or an atomic snapshot.",
            "UUID arrays and the reserved VM word are omitted from this output.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Saved .bin with adjacent report.json")
    args = parser.parse_args()
    try:
        data, sha = validated_capture(args.capture)
        print(json.dumps(inspect(data, sha), indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"SRAM inspection failed: {error}\n")


if __name__ == "__main__":
    main()
