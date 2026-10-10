#!/usr/bin/env python3
"""Build and audit the fixed retained-SRAM copier offline; no device access."""
import json
import subprocess

from build_minitoo_ram_probe import ROOT, TOOLCHAIN
import minitoo_sram_snapshot_payload as payload


def main():
    source = ROOT / "firmware/sram-snapshot"
    output = ROOT / "artifacts/sram-snapshot-offline"
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
        ["objdump", "-r", "/out/probe.elf"],
    ]
    for command in commands:
        result = subprocess.run(container + ["/opt/jieli/pi32v2/bin/" + command[0]]
                                + command[1:], capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(f"{command[0]} failed: {result.stderr or result.stdout}")
        if command[1] == "-d":
            (output / "probe.disassembly.txt").write_text(result.stdout)
        if command[1] == "-r":
            if "RELOCATION RECORDS" in result.stdout:
                raise SystemExit("Linked SRAM copier unexpectedly has relocations")
    code = (output / "probe.text").read_bytes()
    block = payload.make_block(code)
    audit = payload.audit_code(code, bytes(i % 251 for i in range(payload.CAPTURE_BYTES)))
    (output / "probe.ram-block.bin").write_bytes(block)
    manifest = {
        "purpose": "Offline fixed retained-application SRAM copy; no device access",
        "hardware_tested": False, "entry_address": f"0x{payload.ADDRESS:08x}",
        "source_address": f"0x{payload.SOURCE:08x}", "capture_bytes": payload.CAPTURE_BYTES,
        "copy_address": f"0x{payload.DESTINATION:08x}",
        "completion_address": f"0x{payload.ADDRESS + payload.RESULT_OFFSET:08x}",
        "code_bytes": len(code), "upload_bytes": payload.SIZE,
        "code_sha256": payload.sha256(code), "block_sha256": payload.sha256(block),
        "source_sha256": payload.sha256((source / "probe.c").read_bytes()),
        "linker_sha256": payload.sha256((source / "probe.ld").read_bytes()),
        "compiler": "Jieli Linux toolchain 20260730.1, pi32v2 r3",
        "executed_instructions": audit["instructions"], "copy_iterations": payload.CAPTURE_BYTES // 4,
        "source_loads": len(audit["reads"]), "destination_stores": len(audit["writes"]),
        "function_calls": 0, "stack_accesses": 0, "peripheral_accesses": 0, "flash_transactions": 0,
        "note": "Sequential partial SRAM capture after ROM entry; not a full SRAM or flash backup.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
