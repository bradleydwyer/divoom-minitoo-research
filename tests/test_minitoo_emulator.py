# SPDX-License-Identifier: Apache-2.0
"""Offline CPU1 bounds and result validation. No emulator or device required."""
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/emulator"))
import minitoo_cpu_probe_payload as p
import check_minitoo_cpu as checker


def synthetic_result(initial_psr=0):
    block = bytearray(p.make_block())
    words = [p.MARKER, initial_psr, 1, 1, 0, 0, 0,
             0x11223344, 0x15B, 0xAABBCCDD, 0xFFFFFFFE,
             0, 6, 0x80000000, 9, 0xFFFFFFFF, 8, 0, 6]
    struct.pack_into("<19I", block, p.RESULT_OFFSET, *words)
    return bytes(block)


def synthetic_state():
    block = synthetic_result()
    return {"machine": "minitoo-cpu-check", "pc": 0x120300,
            "rets": 0x120300, "sp": 0x120FF0, "instructions": 63,
            "irq_entries": 0, "registers": [p.MARKER, p.CENTER, 1, 6]
            + [0x5A000000 + i for i in range(4, 16)],
            "block_hex": block.hex(), "block_sha256": p.sha256(block),
            "ram_sha256": p.sha256(block + bytes(8192 - p.SIZE))}


class CpuFixtureTests(unittest.TestCase):
    def test_all_paths_and_every_code_byte_are_checked(self):
        audit = p.audit_code()
        self.assertEqual((audit["paths_checked"], audit["instructions_min"],
                          audit["instructions_max"]), (32, 60, 65))
        self.assertEqual(audit["result_words_written"], 19)
        self.assertEqual(audit["explicit_special_register_writes"], [])
        self.assertEqual(p.sha256(p.make_block()), p.BLOCK_SHA256)
        for offset in range(len(p.CODE)):
            changed = bytearray(p.CODE)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                p.make_block(bytes(changed))

    def test_result_disagreement_is_accepted_and_reported(self):
        self.assertTrue(p.decode_result(synthetic_result())["agrees_with_model"])
        for word in range(2, 19):
            changed = bytearray(synthetic_result())
            changed[p.RESULT_OFFSET + word * 4] ^= 1
            with self.subTest(word=word):
                self.assertFalse(p.decode_result(changed)["agrees_with_model"])

    def test_every_byte_outside_results_and_completion_are_checked(self):
        result = synthetic_result()
        for offset in range(p.SIZE):
            if p.RESULT_OFFSET + 4 <= offset < p.RESULT_OFFSET + p.RESULT_BYTES:
                continue
            changed = bytearray(result)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                p.decode_result(changed)
        for invalid in (b"", result[:-1], result + b"\0", p.make_block()):
            with self.assertRaises(ValueError):
                p.decode_result(invalid)

    def test_high_psr_bits_do_not_change_low_flag_comparison(self):
        result = bytearray(synthetic_result(initial_psr=0xA0))
        for word in (12, 14, 16, 18):
            result[p.RESULT_OFFSET + word * 4] |= 0xA0
        decoded = p.decode_result(result)
        self.assertEqual(decoded["initial_psr"], "0x000000a0")
        self.assertTrue(decoded["agrees_with_model"])

    def test_emulator_validation_checks_preserved_state_and_all_ram(self):
        def case(state):
            return {"returncode": 0, "stdout": json.dumps(state)}

        self.assertTrue(checker.validate(case(synthetic_state()))["agrees_with_model"])
        mutations = {"pc": 0, "rets": 0, "sp": 0, "instructions": 64,
                     "irq_entries": 1, "block_sha256": "wrong", "ram_sha256": "wrong"}
        for key, value in mutations.items():
            state = synthetic_state()
            state[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                checker.validate(case(state))
        for reg in range(4, 16):
            state = synthetic_state()
            state["registers"][reg] ^= 1
            with self.subTest(register=reg), self.assertRaises(ValueError):
                checker.validate(case(state))

    def test_public_observations_match_reproducible_synthetic_result(self):
        published = json.loads((ROOT / "docs/emulator-results.json").read_text())
        self.assertEqual(published["observations"], p.decode_result(synthetic_result()))
        self.assertEqual(published["synthetic_program"]["input_sha256"], p.sha256(p.make_block()))
        self.assertEqual(published["synthetic_program"]["result_sha256"], p.sha256(synthetic_result()))


if __name__ == "__main__":
    unittest.main()
