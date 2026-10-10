#!/usr/bin/env python3
"""Build the fixed configuration sampler offline; never access a USB device."""
import argparse
import json
import subprocess

from build_minitoo_ram_probe import ROOT, TOOLCHAIN
import minitoo_flash_state_payload as configuration
import minitoo_flash_bus_state_payload as bus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bus-state", action="store_true",
                        help="Build the separate, fixed SFC/clock/GPIO sampler")
    args = parser.parse_args()
    profile = bus if args.bus_state else configuration
    name = "flash-bus-state" if args.bus_state else "flash-state"
    source = ROOT / "firmware" / name
    output = ROOT / "artifacts" / (name + "-offline")
    if not (TOOLCHAIN / "pi32v2/bin/clang").is_file():
        raise SystemExit("Pinned local Jieli toolchain is absent")
    output.mkdir(parents=True, exist_ok=True)
    container = [
        "docker", "run", "--rm", "--platform", "linux/amd64", "--network", "none",
        "--mount", f"type=bind,src={TOOLCHAIN},dst=/opt/jieli,readonly",
        "--mount", f"type=bind,src={source},dst=/src,readonly",
        "--mount", f"type=bind,src={output},dst=/out", "ubuntu:24.04",
    ]
    commands = [
        ["clang", "-target", "pi32v2", "-mcpu=r3", "-ffreestanding", "-fno-builtin",
         "-Os", "-Wall", "-Wextra", "-Werror", "-c", "/src/probe.c", "-o", "/out/probe.o"],
        ["ld", "-m", "elf32pi32v2", "-T", "/src/probe.ld", "--no-undefined",
         "/out/probe.o", "-o", "/out/probe.elf"],
        ["objcopy", "-O", "binary", "-j", ".text", "/out/probe.elf", "/out/probe.text"],
        ["objdump", "-d", "-print-imm-hex", "/out/probe.elf"],
    ]
    for command in commands:
        result = subprocess.run(container + ["/opt/jieli/pi32v2/bin/" + command[0]]
                                + command[1:], capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(f"{command[0]} failed: {result.stderr or result.stdout}")
        if command[0] == "objdump":
            (output / "probe.disassembly.txt").write_text(result.stdout)
    code = (output / "probe.text").read_bytes()
    block = profile.make_block(code)  # Exact byte pin AND independent instruction-subset audit.
    (output / "probe.ram-block.bin").write_bytes(block)
    manifest = {
        "purpose": "Offline build of fixed configuration sampler; no device access",
        "snapshot_kind": "bus-state" if args.bus_state else "configuration",
        "hardware_tested": False, "entry_address": f"0x{profile.ADDRESS:08x}",
        "result_address": f"0x{profile.ADDRESS + profile.RESULT_OFFSET:08x}",
        "result_bytes": profile.RESULT_BYTES,
        "code_bytes": len(code), "block_bytes": profile.SIZE,
        "code_sha256": profile.sha256(code), "block_sha256": profile.sha256(block),
        "source_sha256": profile.sha256((source / "probe.c").read_bytes()),
        "linker_sha256": profile.sha256((source / "probe.ld").read_bytes()),
        "compiler": "Jieli Linux toolchain 20260730.1, pi32v2 r3",
        "fixed_reads": [{"name": name, "address": f"0x{address:08x}"} for name, address in profile.SAMPLES],
        "instructions": profile.INSTRUCTIONS, "function_calls": 0, "loops": 0,
        "peripheral_writes": 0, "flash_transactions": 0,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
