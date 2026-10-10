"""Offline payload checks. These do not establish hardware execution/safety."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_minitoo_ram_probe as m


class PayloadTests(unittest.TestCase):
    def test_reviewed_program_and_zero_result_fit_one_block(self):
        block = m.make_block(m.CODE)
        self.assertEqual(len(block), 512)
        self.assertEqual(block[:16].hex(), "c0fff0011200c1ff4b4f544d81608000")
        self.assertEqual(block[16:], bytes(496))
        self.assertEqual(block[0x1f0:0x1f4], bytes(4))

    def test_every_single_byte_change_is_rejected(self):
        for offset in range(len(m.CODE)):
            changed = bytearray(m.CODE)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                m.make_block(bytes(changed))

    def test_truncation_and_extra_code_are_rejected(self):
        for code in (b"", m.CODE[:-1], m.CODE + b"\0\0"):
            with self.subTest(size=len(code)), self.assertRaises(ValueError):
                m.make_block(code)


if __name__ == "__main__":
    unittest.main()
