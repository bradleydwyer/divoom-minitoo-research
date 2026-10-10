#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline CPU1 validation in a RAM-only QEMU machine; never access USB."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import minitoo_cpu_probe_payload as p


def run(executable, directory, name, data):
    image = directory / (name + ".bin")
    image.write_bytes(data)
    command = [str(executable), "--qemu", "-M", "minitoo-cpu-check",
               "-accel", "tcg,thread=single", "-icount", "shift=3,align=off,sleep=off",
               "-display", "none", "-serial", "none", "-monitor", "none",
               "-nodefaults", "-no-user-config", "-kernel", str(image)]
    env = {k: v for k, v in os.environ.items() if not k.startswith("FM1_POC_")}
    result = subprocess.run(command, capture_output=True, text=True, timeout=15, env=env)
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
            "input_sha256": p.sha256(data)}


def validate(case):
    if case["returncode"] != 0:
        raise ValueError("Emulator failed")
    state = json.loads(case["stdout"])
    block = bytes.fromhex(state["block_hex"])
    decoded = p.decode_result(block)
    if not decoded["agrees_with_model"]:
        raise ValueError("Unexpected model result")
    expected_regs = [p.MARKER, p.CENTER, 1, 6] + [0x5A000000 + i for i in range(4, 16)]
    expected_ram = block + bytes(8192 - p.SIZE)
    if not (state["machine"] == "minitoo-cpu-check" and state["pc"] == state["rets"] == 0x120300
            and state["sp"] == 0x120FF0 and state["instructions"] == 63
            and state["irq_entries"] == 0 and state["registers"] == expected_regs
            and state["block_sha256"] == p.sha256(block)
            and state["ram_sha256"] == p.sha256(expected_ram)):
        raise ValueError("State/memory invariants failed")
    return decoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite report")
    executable = args.executable.resolve(strict=True)
    block = p.make_block()
    with tempfile.TemporaryDirectory(prefix="minitoo-cpu1-offline-") as tmp:
        directory = Path(tmp)
        positive = run(executable, directory, "cpu1", block)
        decoded = validate(positive)
        wrong = bytearray(block)
        wrong[0x112] ^= 1  # Completion literal.
        wrong_case = run(executable, directory, "wrong-completion", wrong)
        rejected = False
        if wrong_case["returncode"] == 0:
            try:
                validate(wrong_case)
            except ValueError:
                rejected = True
        mmio = bytearray(block)
        struct.pack_into("<I", mmio, 2, 0xFE2D48)  # First store -> FE2D24.
        mmio_case = run(executable, directory, "unmapped-store", mmio)
        mmio_rejected = mmio_case["returncode"] != 0 and "unmapped access at 0x00fe2d24" in mmio_case["stderr"]
        guard = bytearray(block)
        struct.pack_into("<I", guard, 2, p.ADDRESS + 0x24)  # First store -> code.
        guard_case = run(executable, directory, "code-write", guard)
        guard_rejected = guard_case["returncode"] != 0 and "guard" in guard_case["stderr"].lower()
        loop = bytes.fromhex("c0ff00000000705f") + bytes(504)
        loop_case = run(executable, directory, "bounded-loop", loop)
        loop_rejected = loop_case["returncode"] != 0 and "after 128 instructions" in loop_case["stderr"]
    report = {"purpose": "Offline fixed CPU1 emulator check; hardware result documented separately",
              "device_access": False, "executable_sha256": p.sha256(executable.read_bytes()),
              "block_sha256": p.BLOCK_SHA256, "audit": p.audit_code(),
              "result": decoded, "fixed_probe_passed": True,
              "wrong_completion_rejected": rejected, "unmapped_store_rejected": mmio_rejected,
              "code_write_rejected": guard_rejected, "runaway_guest_rejected": loop_rejected,
              "cases": {"cpu1": positive, "wrong_completion": wrong_case, "unmapped_store": mmio_case,
                        "code_write": guard_case, "bounded_loop": loop_case}}
    report["all_checks_passed"] = all((rejected, mmio_rejected, guard_rejected, loop_rejected))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("cases", "result")}, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
