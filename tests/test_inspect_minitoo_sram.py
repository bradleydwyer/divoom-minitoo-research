"""Synthetic captures only: no raw device bytes or identifiers in these tests."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import inspect_minitoo_sram as scanner


def synthetic_capture(offset=0x1720):
    data = bytearray(scanner.CAPTURE_BYTES)
    data[offset:offset + 32] = b"PRIVATE-UUID-DO-NOT-EMIT".ljust(32, b"!")
    data[offset + 32:offset + 35] = b"\x01\0\0"
    struct.pack_into("<5I", data, offset + 36, 0x1FF000, 0x200000, 0, 0x856015, 0)
    data[offset + 56] = 16
    struct.pack_into("<6I", data, offset + 60, 0x1D4000, 0xDEADBEEF,
                     0x2A000, 0x2000, 0x6000000, 24000000)
    return data


class SRAMInspectorTests(unittest.TestCase):
    def test_consistent_candidate_and_identifier_omission(self):
        data = synthetic_capture()
        result = scanner.inspect(data, hashlib.sha256(data).hexdigest())
        self.assertEqual(result["candidate_count"], 1)
        found = result["candidates"][0]
        self.assertEqual(found["address"], "0x0010c720")
        self.assertEqual(found["cached_jedec_id"], "0x856015")
        self.assertEqual(found["flash_capacity"], 2097152)
        self.assertFalse(found["sfc0_is_4byte_address_mode"])
        rendered = json.dumps(result)
        self.assertNotIn("PRIVATE-UUID", rendered)
        self.assertNotIn("deadbeef", rendered.lower())
        self.assertNotIn(str(0xDEADBEEF), rendered)

    def test_id_alone_is_insufficient(self):
        for field, value in ((40, 0x400000), (60, 0x1FF000), (68, 0), (76, 0)):
            data = synthetic_capture()
            struct.pack_into("<I", data, 0x1720 + field, value)
            self.assertEqual(scanner.inspect(data, "unused")["candidate_count"], 0)

    def test_ambiguous_structures_are_both_reported(self):
        first, second = synthetic_capture(), synthetic_capture(0x1820)
        first[0x1820:0x1870] = second[0x1820:0x1870]
        result = scanner.inspect(first, "unused")
        self.assertEqual(result["candidate_count"], 2)

    def test_empty_capture_has_no_candidate(self):
        self.assertEqual(scanner.inspect(bytes(scanner.CAPTURE_BYTES), "unused")["candidates"], [])

    def test_capture_report_checks(self):
        data = synthetic_capture()
        sha = hashlib.sha256(data).hexdigest()
        good = {
            "action": "run-fixed-snapshot", "source_address": "0x0010b000",
            "capture_bytes": len(data), "capture_sha256": sha,
            **{flag: True for flag in scanner.SUCCESS_FLAGS},
            "sessions": [{"stage": "fixed-retained-sram-copy",
                          "copy_read_1_sha256": sha, "copy_read_2_sha256": sha}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.bin"
            report = path.with_name("report.json")
            path.write_bytes(data)
            report.write_text(json.dumps(good))
            self.assertEqual(scanner.validated_capture(path), (data, sha))
            changes = [{"source_address": "0x00100000"}, {"capture_bytes": 1024},
                       {"capture_sha256": "wrong"}, {"snapshot_confirmed": False},
                       {"copy_read_twice_confirmed": 1}, {"sessions": []}]
            for change in changes:
                with self.subTest(change=change):
                    report.write_text(json.dumps({**good, **change}))
                    with self.assertRaises(ValueError):
                        scanner.validated_capture(path)
            report.write_text(json.dumps(good))
            path.write_bytes(data[:-1])
            with self.assertRaises(ValueError):
                scanner.validated_capture(path)


if __name__ == "__main__":
    unittest.main()
