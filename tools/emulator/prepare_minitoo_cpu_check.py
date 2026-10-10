#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Add a second offline machine; retain the validated marker fixture unchanged."""
import argparse
import hashlib
from pathlib import Path

from prepare_minitoo_ram_check import PINS, MESON_SHA256, LINE as MARKER_LINE

LINE = "pi32v2_hw.add(when: 'CONFIG_FM1_POC', if_true: files('minitoo-cpu-check.c'))\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("working_source", type=Path)
    root = parser.parse_args().working_source.resolve()
    for rel, expected in PINS.items():
        if hashlib.sha256((root / rel).read_bytes()).hexdigest() != expected:
            raise SystemExit(f"Pinned FM-1 source differs: {rel}")
    meson = root / "src/hw/pi32v2/meson.build"
    original = meson.read_text().replace(MARKER_LINE, "").replace(LINE, "")
    if hashlib.sha256(original.encode()).hexdigest() != MESON_SHA256:
        raise SystemExit("Pinned original meson.build differs")
    fixture = Path(__file__).with_name("minitoo_cpu_check.c").read_bytes()
    target = root / "src/hw/pi32v2/minitoo-cpu-check.c"
    if target.exists() and target.read_bytes() != fixture:
        raise SystemExit("Existing CPU fixture differs; preserve it before changing")
    marker = root / "src/hw/pi32v2/minitoo-ram-check.c"
    additions = LINE
    if marker.exists():
        if marker.read_bytes() != Path(__file__).with_name("minitoo_ram_check.c").read_bytes():
            raise SystemExit("Existing marker fixture differs")
        additions = MARKER_LINE + additions
    anchor = "hw_arch += {'pi32v2': pi32v2_hw}\n"
    if original.count(anchor) != 1:
        raise SystemExit("Hardware anchor absent or ambiguous")
    target.write_bytes(fixture)
    meson.write_text(original.replace(anchor, additions + anchor))
    print(f"Prepared {target}; pinned CPU implementation unchanged.")


if __name__ == "__main__":
    main()
