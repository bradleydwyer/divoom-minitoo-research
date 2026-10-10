#!/usr/bin/env python3
"""Compile/link the fixed flash-ID candidate for offline review; no USB access.

The ROM-call wrapper and memory bounds are checked at link time. Functional
model tests and successful linking do not clear the candidate for execution.
"""
import hashlib
import json
import struct
import subprocess

from build_minitoo_ram_probe import ROOT, TOOLCHAIN
import minitoo_flash_id_payload as payload


def inspect_object(data, *, executable=False, text_limit=0x3C0):
    """Check our compiler's ELF32 object or fixed linked ELF."""
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    if (header[0][:6] != b"\x7fELF\x01\x01" or header[1] != (2 if executable else 1)
            or header[11] != 40 or (executable and header[4] != 0x120000)):
        raise ValueError("Unexpected ELF format/type/entry point")
    sections = [struct.unpack_from("<10I", data, header[6] + i * header[11])
                for i in range(header[12])]
    names_section = sections[header[13]]
    names = data[names_section[4]:names_section[4] + names_section[5]]
    text = None
    for section in sections:
        name = names[section[0]:].split(b"\0", 1)[0]
        if section[1] in (4, 9) and section[5]:
            raise ValueError("Unexpected relocations: candidate needs further review")
        if section[2] & 2 and name != b".text":
            raise ValueError("Unexpected allocated data/runtime dependency")
        if name == b".text":
            if executable and (section[3] != 0x120000 or section[5] > text_limit):
                raise ValueError("Linked code is outside the fixed code area")
            text = data[section[4]:section[4] + section[5]]
        if section[1] == 2: # SHT_SYMTAB: any named undefined symbol is a dependency.
            for offset in range(section[4], section[4] + section[5], 16):
                symbol = struct.unpack_from("<IIIBBH", data, offset)
                if symbol[0] and symbol[5] == 0:
                    raise ValueError("Unexpected undefined symbol")
    if not text:
        raise ValueError("Candidate has no text")
    return {"text_bytes": len(text), "text_sha256": hashlib.sha256(text).hexdigest(),
            "relocations": 0, "undefined_symbols": 0, "allocated_data_sections": 0}


def main():
    source = ROOT / "firmware/flash-id-candidate"
    output = ROOT / "artifacts/flash-id-candidate-offline"
    output.mkdir(parents=True, exist_ok=True)
    container = [
        "docker", "run", "--rm", "--platform", "linux/amd64", "--network", "none",
        "--mount", f"type=bind,src={TOOLCHAIN},dst=/opt/jieli,readonly",
        "--mount", f"type=bind,src={source},dst=/src,readonly",
        "--mount", f"type=bind,src={output},dst=/out", "ubuntu:24.04",
    ]
    commands = [
        ["clang", "-target", "pi32v2", "-mcpu=r3", "-ffreestanding", "-fno-builtin",
         "-Os", "-Wall", "-Wextra", "-Werror", "-c", "/src/candidate.c", "-o", "/out/candidate.o"],
        ["clang", "-target", "pi32v2", "-mcpu=r3", "-ffreestanding", "-fno-builtin",
         "-Os", "-Wall", "-Wextra", "-Werror", "-c", "/src/entry.c", "-o", "/out/entry.o"],
        ["ld", "-m", "elf32pi32v2", "-T", "/src/candidate.ld", "--no-undefined",
         "/out/entry.o", "/out/candidate.o", "-o", "/out/candidate.elf"],
        ["objcopy", "-O", "binary", "-j", ".text", "/out/candidate.elf", "/out/candidate.text"],
        ["objdump", "-d", "-r", "-print-imm-hex", "/out/candidate.elf"],
    ]
    for command in commands:
        result = subprocess.run(container + ["/opt/jieli/pi32v2/bin/" + command[0]] + command[1:],
                                capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(f"{command[0]} failed: {result.stderr or result.stdout}")
        if command[0] == "objdump":
            (output / "candidate.disassembly.txt").write_text(result.stdout)
    block = payload.make_block((output / "candidate.text").read_bytes())
    (output / "candidate.ram-block.bin").write_bytes(block)
    manifest = {
        "purpose": "Offline fixed candidate build; upload/readback only",
        "hardware_ready": False,
        "device_access": False,
        "rom_entry_adapter": True,
        "upload_block_generated": True,
        "execution_supported_by_host_helper": False,
        "compiler": "Jieli Linux toolchain 20260730.1, pi32v2 r3",
        "object_inspection": inspect_object((output / "candidate.o").read_bytes()),
        "linked_inspection": inspect_object((output / "candidate.elf").read_bytes(), executable=True),
        "entry_address": "0x00120000",
        "result_address": "0x001203c0",
        "result_bytes": 48,
        "block_bytes": len(block),
        "block_sha256": payload.sha256(block),
        "files": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in {
            "candidate.c": source / "candidate.c", "candidate.h": source / "candidate.h",
            "candidate.o": output / "candidate.o",
            "entry.c": source / "entry.c", "candidate.ld": source / "candidate.ld",
            "candidate.elf": output / "candidate.elf",
            "candidate.ram-block.bin": output / "candidate.ram-block.bin",
        }.items()},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
