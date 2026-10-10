#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Add the offline RAM fixture to a working copy of pinned fm1-emulator."""
import argparse
import hashlib
from pathlib import Path

PINS = {
    "tools/build.py": "7e8be0cdd79f3611172bfd238c2de48e5f8bb46ab69bb76751b41eab4c1da645",
    "tools/integrate.py": "7195cd31f066918b39feae0bd038e564d83a042b50b5d15e2e772f2928ed0f63",
    "src/target/pi32v2/cpu.c": "6ac99c465b9b54ccf023e96548b8fd4f8b223de604a29fe907ad98c73bbe1038",
    "src/target/pi32v2/helper.c": "0e95bb3e0a6f5ff2fec58b69a4e10bf854cca7a8b5e294de3c99b5608ab2d020",
    "src/target/pi32v2/translate.c": "8eeab3bbaba86c25802a7e3a34f330ba2a2ba46579ce08cb4b1ab7025c57ed3f",
}
MESON_SHA256 = "5fba11371cc521dffbc31ad4a1279e1778445bde359a5aea0dc9eca8af6539f4"
LINE = "pi32v2_hw.add(when: 'CONFIG_FM1_POC', if_true: files('minitoo-ram-check.c'))\n"
CPU_LINE = "pi32v2_hw.add(when: 'CONFIG_FM1_POC', if_true: files('minitoo-cpu-check.c'))\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("working_source", type=Path)
    args = parser.parse_args()
    root = args.working_source.resolve()
    for rel, expected in PINS.items():
        if hashlib.sha256((root / rel).read_bytes()).hexdigest() != expected:
            raise SystemExit(f"Pinned FM-1 source differs: {rel}")
    meson = root / "src/hw/pi32v2/meson.build"
    current = meson.read_text()
    original = current.replace(LINE, "").replace(CPU_LINE, "")
    if hashlib.sha256(original.encode()).hexdigest() != MESON_SHA256:
        raise SystemExit("Pinned FM-1 meson.build differs")
    anchor = "hw_arch += {'pi32v2': pi32v2_hw}\n"
    if original.count(anchor) != 1:
        raise SystemExit("Expected one hardware source-set anchor")
    fixture = Path(__file__).with_name("minitoo_ram_check.c").read_bytes()
    target = root / "src/hw/pi32v2/minitoo-ram-check.c"
    if target.exists() and target.read_bytes() != fixture:
        raise SystemExit("Existing fixture differs; preserve it before applying another revision")
    cpu_line = ""
    if CPU_LINE in current:
        cpu_fixture = root / "src/hw/pi32v2/minitoo-cpu-check.c"
        if cpu_fixture.read_bytes() != Path(__file__).with_name("minitoo_cpu_check.c").read_bytes():
            raise SystemExit("Existing CPU fixture differs")
        cpu_line = CPU_LINE
    target.write_bytes(fixture)
    meson.write_text(original.replace(anchor, LINE + cpu_line + anchor))
    print(f"Prepared {target}; CPU implementation unchanged. Rebuild using tools/build.py.")


if __name__ == "__main__":
    main()
