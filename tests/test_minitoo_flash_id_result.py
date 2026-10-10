"""Offline validation of the future fixed ID result; no execution tool exists."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import minitoo_flash_id_payload as p


def block(words=None):
    data = bytearray(p.make_block())
    if words is None:
        words = [p.COMPLETION, 0, 0, 4, 0x12, 0x34, 0x56, 1, 2, 3, 4, 0]
    struct.pack_into("<12I", data, p.RESULT_OFFSET, *words)
    return bytes(data)


class ResultTests(unittest.TestCase):
    def test_every_code_or_padding_change_is_rejected(self):
        valid = block()
        for offset in range(p.SIZE):
            if p.RESULT_OFFSET <= offset < p.RESULT_OFFSET + p.RESULT_BYTES:
                continue
            changed = bytearray(valid)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                p.decode_result(bytes(changed))
        for data in (valid[:-1], valid + b"\0", p.make_block()):
            with self.assertRaises(ValueError):
                p.decode_result(data)

    def test_capture_does_not_claim_identification_or_backup(self):
        result = p.decode_result(block())
        self.assertTrue(result["id_captured"])
        self.assertEqual(result["id_bytes"], "123456")
        self.assertEqual(result["polls"], [1, 2, 3, 4])
        self.assertNotIn("capacity", result)

    def test_valid_refusal_timeout_no_response_and_cleanup_errors(self):
        cases = [[p.COMPLETION, 1, 0xFFF, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                 [p.COMPLETION, 3, 0, 4, 0x12, 0x34, 0x56, 1, 2, 3, 4, 0x3F]]
        for data in ([0, 0, 0], [255, 255, 255]):
            cases.append([p.COMPLETION, 4, 0, 4, *data, 1, 1, 1, 1, 0])
        for stage in range(4):
            ident = [0x12, 0x34, 0x56][:max(stage - 1, 0)] + [0] * (4 - max(stage, 1))
            polls = [1] * stage + [p.POLL_LIMIT] + [0] * (3 - stage)
            for cleanup in (0, 4):
                cases.append([p.COMPLETION, 3 if cleanup else 2, 0, stage,
                              *ident, *polls, cleanup])
        for words in cases:
            with self.subTest(words=words):
                result = p.decode_result(block(words))
                self.assertFalse(result["id_captured"])

    def test_inconsistent_marker_status_flags_counts_and_bytes_are_rejected(self):
        words = list(struct.unpack_from("<12I", block(), p.RESULT_OFFSET))
        for index, value in ((0, 0), (1, 5), (1, 1), (1, 2), (1, 3), (1, 4),
                             (2, 1), (2, 0x1000), (3, 3), (3, 5), (4, 256),
                             (7, 0), (8, p.POLL_LIMIT + 1), (11, 1), (11, 0x40)):
            altered = words.copy()
            altered[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                p.decode_result(block(altered))
        for ident in ([0, 0, 0], [255, 255, 255]):
            altered = words.copy()
            altered[4:7] = ident
            with self.assertRaises(ValueError):
                p.decode_result(block(altered))

    def test_inconsistent_failure_results_are_rejected(self):
        cases = [
            [p.COMPLETION, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [p.COMPLETION, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0],
            [p.COMPLETION, 2, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
            [p.COMPLETION, 2, 0, 1, 1, 0, 0, 1, p.POLL_LIMIT, 0, 0, 0],
            [p.COMPLETION, 2, 0, 2, 1, 0, 0, 1, 1, p.POLL_LIMIT, 1, 0],
            [p.COMPLETION, 3, 0, 4, 1, 2, 3, 1, 1, 1, 1, 0],
        ]
        for words in cases:
            with self.subTest(words=words), self.assertRaises(ValueError):
                p.decode_result(block(words))


if __name__ == "__main__":
    unittest.main()
