#!/usr/bin/env python3
"""Build and inspect the offline RAM-marker prototype. No device access.

Requires the locally acquired Jieli Linux toolchain and Docker. Produces an
ELF, its disassembly, and a plain 512-byte RAM block; not an update package.
There is deliberately no upload, execution, encryption, or USB command here.
"""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "firmware/ram-probe"
TOOLCHAIN = ROOT / "artifacts/tools/jieli-linux-toolchains-20260730.1"
OUTPUT = ROOT / "artifacts/ram-probe-offline"
CODE = bytes.fromhex("c0fff0011200c1ff4b4f544d81608000")


def make_block(code):
    """Accept exactly the reviewed four instructions; result starts at zero."""
    if code != CODE:
        raise ValueError("Compiler output differs from the reviewed 16-byte program")
    return code + bytes(512 - len(code))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if not (TOOLCHAIN / "pi32v2/bin/clang").is_file():
        raise SystemExit("Pinned local Jieli toolchain is absent; see backup investigation")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    container = [
        "docker", "run", "--rm", "--platform", "linux/amd64", "--network", "none",
        "--mount", f"type=bind,src={TOOLCHAIN},dst=/opt/jieli,readonly",
        "--mount", f"type=bind,src={SOURCE},dst=/src,readonly",
        "--mount", f"type=bind,src={OUTPUT},dst=/out", "ubuntu:24.04",
    ]
    commands = [
        ["clang", "-target", "pi32v2", "-mcpu=r3", "-ffreestanding",
         "-fno-builtin", "-Os", "-Wall", "-Wextra", "-Werror", "-c",
         "/src/probe.c", "-o", "/out/probe.o"],
        ["ld", "-m", "elf32pi32v2", "-T", "/src/probe.ld", "--no-undefined",
         "/out/probe.o", "-o", "/out/probe.elf"],
        ["objcopy", "-O", "binary", "-j", ".text",
         "/out/probe.elf", "/out/probe.text"],
        ["objdump", "-d", "-print-imm-hex", "/out/probe.elf"],
    ]
    outputs = []
    for command in commands:
        result = subprocess.run(container + ["/opt/jieli/pi32v2/bin/" + command[0]]
                                + command[1:], capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(f"{command[0]} failed: {result.stderr or result.stdout}")
        outputs.append(result.stdout)
    code = (OUTPUT / "probe.text").read_bytes()
    block = make_block(code)
    (OUTPUT / "probe.disassembly.txt").write_text(outputs[-1])
    (OUTPUT / "probe.ram-block.bin").write_bytes(block)
    manifest = {
        "purpose": "Offline RAM-marker prototype; no hardware operations",
        "hardware_tested": False,
        "entry_address": "0x00120000",
        "result_address": "0x001201f0",
        "result_u32": "0x4d544f4b",
        "code_bytes": len(code), "block_bytes": len(block),
        "code_sha256": digest(code), "block_sha256": digest(block),
        "source_sha256": digest((SOURCE / "probe.c").read_bytes()),
        "linker_sha256": digest((SOURCE / "probe.ld").read_bytes()),
        "compiler": "Jieli Linux toolchain 20260730.1, pi32v2 r3",
        "instructions": ["r0 = 0x001201f0", "r1 = 0x4d544f4b", "[r0] = r1", "rts"],
        "flash_operations": 0, "peripheral_operations": 0, "function_calls": 0,
        "note": "This is neither an installed-firmware backup nor a firmware update.",
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
