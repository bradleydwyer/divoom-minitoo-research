#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the exact known MiniToo RAM marker in an offline QEMU RAM fixture.

No USB imports, device discovery, network or passthrough arguments are used.
The supplied executable must contain the minitoo-ram-check machine.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

CODE = bytes.fromhex("c0fff0011200c1ff4b4f544d81608000")
BLOCK = CODE + bytes(512 - len(CODE))
BLOCK_SHA256 = "7346172b60c37a5656b1426637bc3493e953d9f5703c8491fe9769e263d60485"
RESULT_SHA256 = "bb968eb834b094c8aa17dd375c4e27bcdf3ec2dd780dca8c01824bafa7e5eaaa"
MARKER = 0x4D544F4B
RETURN_PC = 0x00120300


def run(executable, directory, name, block):
    image = directory / (name + ".bin")
    image.write_bytes(block)
    command = [str(executable), "--qemu", "-M", "minitoo-ram-check",
               "-accel", "tcg,thread=single", "-icount", "shift=3,align=off,sleep=off",
               "-display", "none", "-serial", "none", "-monitor", "none",
               "-nodefaults", "-no-user-config", "-kernel", str(image)]
    env = {k: v for k, v in os.environ.items() if not k.startswith("FM1_POC_")}
    try:
        result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=15)
    except subprocess.TimeoutExpired as error:
        def decoded(value):
            return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
        return {"returncode": None, "timed_out": True,
                "stdout": decoded(error.stdout), "stderr": decoded(error.stderr),
                "input_sha256": hashlib.sha256(block).hexdigest()}
    return {"returncode": result.returncode, "stdout": result.stdout,
            "stderr": result.stderr, "input_sha256": hashlib.sha256(block).hexdigest()}


def expected_state(state):
    if not isinstance(state, dict):
        return False
    expected_ram = bytearray(BLOCK + bytes(8192 - len(BLOCK)))
    struct.pack_into("<I", expected_ram, 0x1F0, MARKER)
    return (state.get("machine") == "minitoo-ram-check" and
            state.get("pc") == RETURN_PC and state.get("rets") == RETURN_PC and
            state.get("sp") == 0x00120FF0 and state.get("instructions") == 4 and
            state.get("irq_entries") == 0 and state.get("result_word") == MARKER and
            state.get("registers") == [0x001201F0, MARKER] + [0] * 14 and
            state.get("block_sha256") == RESULT_SHA256 and
            state.get("ram_sha256") == hashlib.sha256(expected_ram).hexdigest())


def completed_state(case):
    if case["returncode"] != 0:
        return None
    try:
        return json.loads(case["stdout"])
    except json.JSONDecodeError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to replace an existing report")
    if hashlib.sha256(BLOCK).hexdigest() != BLOCK_SHA256:
        raise SystemExit("Known marker block differs")
    executable = args.executable.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="minitoo-offline-marker-") as tmp:
        directory = Path(tmp)
        positive = run(executable, directory, "marker", BLOCK)
        positive_ok = expected_state(completed_state(positive))

        # A completed run alone must not count as a correct result.
        wrong = bytearray(BLOCK)
        wrong[8] ^= 1
        wrong_result = run(executable, directory, "wrong-marker", wrong)
        wrong_state = completed_state(wrong_result)
        wrong_rejected = (wrong_state is not None and not expected_state(wrong_state))

        # Guest peripheral access must fault, without an invented MMIO model.
        mmio = bytearray(BLOCK)
        struct.pack_into("<I", mmio, 2, 0x00FE2D24)
        mmio_result = run(executable, directory, "unmapped-mmio", mmio)
        mmio_rejected = (mmio_result["returncode"] not in (0, None) and
                         "unmapped access at 0x00fe2d24" in mmio_result["stderr"])

        # A self-branch has to stop at the guest instruction budget.
        loop = struct.pack("<H", 0x5F70) + bytes(510)
        loop_result = run(executable, directory, "bounded-loop", loop)
        loop_rejected = (loop_result["returncode"] not in (0, None) and
                         "instruction limit reached" in loop_result["stderr"] and
                         "after 64 instructions" in loop_result["stderr"])

    report = {
        "purpose": "Offline exact-byte RAM-marker check; not a BR28 board emulator",
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "device_access": False, "ram_base": "0x00120000", "ram_bytes": 8192,
        "synthetic_return_pc": hex(RETURN_PC), "instruction_limit": 64,
        "marker_confirmed": positive_ok, "wrong_result_rejected": wrong_rejected,
        "unmapped_mmio_rejected": mmio_rejected, "runaway_guest_rejected": loop_rejected,
        "cases": {"marker": positive, "wrong_marker": wrong_result,
                  "unmapped_mmio": mmio_result, "bounded_loop": loop_result},
    }
    report["all_checks_passed"] = all([positive_ok, wrong_rejected, mmio_rejected, loop_rejected])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
