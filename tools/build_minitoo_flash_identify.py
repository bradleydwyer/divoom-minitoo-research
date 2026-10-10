#!/usr/bin/env python3
"""Rebuild and verify the fixed mode-release/ID probe offline; no device access."""
import json
import subprocess

from build_minitoo_ram_probe import ROOT, TOOLCHAIN
from build_minitoo_flash_id_candidate import inspect_object
import minitoo_flash_identify_payload as payload


def main():
    source = ROOT / "firmware/flash-identify"
    output = ROOT / "artifacts/flash-identify-offline"
    output.mkdir(parents=True, exist_ok=True)
    prefix = ["docker", "run", "--rm", "--platform", "linux/amd64", "--network", "none",
              "--mount", f"type=bind,src={TOOLCHAIN},dst=/opt/jieli,readonly",
              "--mount", f"type=bind,src={source},dst=/src,readonly",
              "--mount", f"type=bind,src={output},dst=/out", "ubuntu:24.04"]
    commands = [
        ["clang", "-target", "pi32v2", "-mcpu=r3", "-ffreestanding", "-fno-builtin",
         "-Os", "-Wall", "-Wextra", "-Werror", "-c", "/src/probe.c", "-o", "/out/probe.o"],
        ["clang", "-target", "pi32v2", "-mcpu=r3", "-c", "/src/entry.S", "-o", "/out/entry.o"],
        ["ld", "-m", "elf32pi32v2", "-T", "/src/probe.ld", "--no-undefined",
         "/out/entry.o", "/out/probe.o", "-o", "/out/probe.elf"],
        ["objcopy", "-O", "binary", "-j", ".text", "/out/probe.elf", "/out/probe.text"],
        ["objdump", "-d", "-r", "-print-imm-hex", "/out/probe.elf"],
    ]
    for command in commands:
        result = subprocess.run(prefix + ["/opt/jieli/pi32v2/bin/" + command[0]] + command[1:],
                                capture_output=True, text=True, check=True)
        if command[0] == "objdump":
            (output / "probe.disassembly.txt").write_text(result.stdout)
    block = payload.make_block((output / "probe.text").read_bytes())
    (output / "probe.ram-block.bin").write_bytes(block)
    manifest = {
        "purpose": "Offline reproducible build of fixed mode-release/ID probe",
        "device_access": False, "hardware_tested": False,
        "compiler": "Jieli Linux toolchain 20260730.1, pi32v2 r3",
        "linked_inspection": inspect_object((output / "probe.elf").read_bytes(),
                                            executable=True, text_limit=payload.RESULT_OFFSET),
        "entry_address": f"0x{payload.ADDRESS:08x}",
        "upload_bytes": len(block), "upload_chunks": 2, "chunk_bytes": 1024,
        "block_sha256": payload.sha256(block), "result_offset": payload.RESULT_OFFSET,
        "private_stack_bottom": f"0x{payload.STACK_BOTTOM:08x}",
        "private_stack_top": f"0x{payload.STACK_TOP:08x}",
        "maximum_candidate_stack_bytes": 92,
        "stack_limit_note": "Candidate frames only; not a measured ROM interrupt stack maximum.",
        "files": {str(path.relative_to(ROOT)): payload.sha256(path.read_bytes())
                  for path in [source / "probe.c", source / "probe.h", source / "entry.S",
                               source / "probe.ld", output / "probe.elf"]},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
