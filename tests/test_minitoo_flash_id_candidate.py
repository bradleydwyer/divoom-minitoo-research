"""Run the candidate C against a synthetic MMIO model, never a USB device.

This tests C control flow and cleanup ordering. It does not emulate BR28 silicon,
flash protocol, electrical behaviour, PI32v2 instructions or physical timing.
"""
import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import minitoo_flash_id_payload as payload
CON, BAUD, BUF = 0xFD1C00, 0xFD1C04, 0xFD1C08
OUT, DIR, DIE, PU, PD = 0xFD5300, 0xFD5308, 0xFD530C, 0xFD5310, 0xFD5314
BASELINE = {
    0x19FC28: 0x84000300, 0x19FC2C: 24000000, 0x19FC30: 48000000,
    0xFD6014: 0, CON: 0x8000, 0xFE0200: 0x01580034, 0xFE0218: 0,
    0xFD4100: 0, 0xFD0014: 0, 0xFD0018: 0x31, 0xFD001C: 0x1643,
    OUT: 0x10, DIR: 0x6F, DIE: 0x7F, PU: 0x18, PD: 0,
}
LIMIT = 65536
READ = ctypes.CFUNCTYPE(ctypes.c_uint, ctypes.c_uint)
WRITE = ctypes.CFUNCTYPE(None, ctypes.c_uint, ctypes.c_uint)


class Result(ctypes.Structure):
    _fields_ = [("completion", ctypes.c_uint), ("status", ctypes.c_uint),
                ("preflight_mismatches", ctypes.c_uint), ("transfers_completed", ctypes.c_uint),
                ("id_bytes", ctypes.c_uint * 3), ("polls", ctypes.c_uint * 4),
                ("cleanup_mismatches", ctypes.c_uint)]


class Model:
    def __init__(self, ready=(1, 1, 1, 1), data=(0x12, 0x34, 0x56), overrides=None,
                 fail_restore_pu=False):
        self.regs = dict(BASELINE)
        self.regs.update(overrides or {})
        self.ready, self.data = ready, data
        self.reads, self.writes, self.attempts, self.cs_edges, self.errors = [], [], [], [], []
        self.active, self.pending, self.polls = False, True, 0
        self.fail_restore_pu = fail_restore_pu
        self.read_callback, self.write_callback = READ(self.read), WRITE(self.write)

    def cs(self):
        # Synthetic GPIO only; no claim about peripheral mux/electrical timing.
        if not self.regs[DIR] & 8:
            return bool(self.regs[OUT] & 8)
        return bool(self.regs[PU] & 8)

    def read(self, address):
        self.reads.append(address)
        if address == BAUD:
            self.errors.append("Read of write-only BAUD")
            return 0
        if address == CON and self.active:
            self.polls += 1
            threshold = self.ready[len(self.attempts) - 1]
            if threshold is not None and self.polls >= threshold:
                self.pending = True
            return self.regs[CON] | (0x8000 if self.pending else 0)
        if address == BUF:
            if not self.attempts or not self.attempts[-1][1]:
                self.errors.append("Unexpected transmit-buffer read")
                return 0
            return self.data[len(self.attempts) - 2]
        if address not in self.regs:
            self.errors.append(f"Unexpected read {address:x}")
            return 0
        return self.regs[address]

    def write(self, address, value):
        before_cs = self.cs()
        self.writes.append((address, value))
        if address not in (OUT, DIR, PU, PD, CON, BAUD, BUF):
            self.errors.append(f"Unexpected write {address:x}")
            return
        if address == CON:
            if value & 0x4000:
                if self.pending:
                    self.active = False
                self.pending = False
            self.regs[CON] = value & ~0xC000
            if not value & 1:
                self.active = False
        elif address == BUF:
            if self.cs() or not self.regs[CON] & 1:
                self.errors.append("Transfer while deselected/disabled")
            if len(self.attempts) >= 4:
                self.errors.append("Extra transfer")
                return
            self.attempts.append((value, bool(self.regs[CON] & 0x1000), self.regs[CON]))
            self.active, self.pending, self.polls = True, False, 0
        elif not (self.fail_restore_pu and address == PU and value == BASELINE[PU]):
            self.regs[address] = value
        after_cs = self.cs()
        if after_cs != before_cs:
            self.cs_edges.append(after_cs)


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("cc")
        if compiler is None:
            raise RuntimeError("A native C compiler is required for candidate control-flow tests")
        cls.temporary = tempfile.TemporaryDirectory(prefix="minitoo-id-model-")
        directory = Path(cls.temporary.name)
        bridge = directory / "bridge.c"
        bridge.write_text("""
static unsigned (*read_cb)(unsigned);
static void (*write_cb)(unsigned, unsigned);
void id_set_model(unsigned (*r)(unsigned), void (*w)(unsigned, unsigned)) {
    read_cb = r; write_cb = w;
}
unsigned id_model_read(unsigned a) { return read_cb(a); }
void id_model_write(unsigned a, unsigned v) { write_cb(a, v); }
""")
        library = directory / "candidate.so"
        subprocess.run([compiler, "-shared", "-fPIC", "-std=c11", "-O2", "-Wall", "-Wextra",
                        "-Werror", "-DMINITOO_ID_OFFLINE_TEST", str(bridge),
                        str(ROOT / "firmware/flash-id-candidate/candidate.c"),
                        "-o", str(library)], capture_output=True, text=True, check=True)
        cls.library = ctypes.CDLL(str(library))
        cls.library.id_set_model.argtypes = [READ, WRITE]
        cls.library.minitoo_flash_id_candidate.argtypes = [ctypes.POINTER(Result)]
        cls.library.minitoo_flash_id_candidate.restype = None

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_model(self, **kwargs):
        class Guarded(ctypes.Structure):
            _fields_ = [("before", ctypes.c_uint * 4), ("result", Result),
                        ("after", ctypes.c_uint * 4)]
        model, guarded = Model(**kwargs), Guarded()
        ctypes.memset(ctypes.byref(guarded), 0xA5, ctypes.sizeof(guarded))
        result = guarded.result
        self.library.id_set_model(model.read_callback, model.write_callback)
        self.library.minitoo_flash_id_candidate(ctypes.byref(result))
        self.assertEqual(list(guarded.before) + list(guarded.after), [0xA5A5A5A5] * 8)
        self.assertEqual(model.errors, [])
        self.assertEqual(result.completion, 0x4D544944)
        self.assertNotIn(BAUD, model.reads)
        # Check every native-C result against the independent host schema too.
        block = bytearray(payload.make_block())
        block[payload.RESULT_OFFSET:payload.RESULT_OFFSET + payload.RESULT_BYTES] = bytes(result)
        decoded = payload.decode_result(bytes(block))
        self.assertEqual(decoded["transfers_completed"], result.transfers_completed)
        return model, result

    def assert_cleanup(self, model):
        self.assertTrue(model.cs())
        self.assertFalse(model.regs[CON] & 1)
        for address in (OUT, DIR, DIE, PU, PD):
            self.assertEqual(model.regs[address], BASELINE[address])
        self.assertEqual(model.cs_edges, [False, True])
        self.assertEqual(model.writes[-7:], [
            (OUT, 0x18), (CON, 0x4020), (PU, 0x18), (PD, 0),
            (DIR, 0x6F), (OUT, 0x10), (CON, 0x4000),
        ])

    def test_one_command_three_receives_and_restored_gpio(self):
        model, result = self.run_model(ready=(1, 2, 3, 4))
        self.assertEqual(result.status, 0)
        self.assertEqual(result.transfers_completed, 4)
        self.assertEqual(list(result.id_bytes), [0x12, 0x34, 0x56])
        self.assertEqual(list(result.polls), [1, 2, 3, 4])
        self.assertEqual([(v, receive) for v, receive, _ in model.attempts],
                         [(0x9F, False), (0xFF, True), (0xFF, True), (0xFF, True)])
        self.assert_cleanup(model)

    def test_timeout_at_every_transfer_stops_without_retry_and_cleans_up(self):
        for stage in range(4):
            with self.subTest(stage=stage):
                ready = [1] * 4
                ready[stage] = None
                model, result = self.run_model(ready=ready)
                self.assertEqual(result.status, 2)
                self.assertEqual(result.transfers_completed, stage)
                self.assertEqual(len(model.attempts), stage + 1)
                self.assertEqual(result.polls[stage], LIMIT)
                self.assertEqual(list(result.polls)[stage + 1:], [0] * (3 - stage))
                self.assertEqual(result.cleanup_mismatches, 0)
                self.assert_cleanup(model)

    def test_last_allowed_poll_can_complete(self):
        model, result = self.run_model(ready=(LIMIT,) * 4)
        self.assertEqual(result.status, 0)
        self.assertEqual(list(result.polls), [LIMIT] * 4)
        self.assert_cleanup(model)

    def test_completion_after_poll_limit_is_not_accepted(self):
        model, result = self.run_model(ready=(LIMIT + 1, 1, 1, 1))
        self.assertEqual(result.status, 2)
        self.assertEqual(result.transfers_completed, 0)
        self.assertEqual(list(result.polls), [LIMIT, 0, 0, 0])
        self.assert_cleanup(model)

    def test_preflight_refuses_each_changed_baseline_without_peripheral_writes(self):
        for address, value in BASELINE.items():
            with self.subTest(address=hex(address)):
                model, result = self.run_model(overrides={address: value ^ 1})
                self.assertEqual(result.status, 1)
                self.assertNotEqual(result.preflight_mismatches, 0)
                self.assertEqual(model.writes, [])
                self.assertEqual(model.attempts, [])
                self.assertEqual(result.transfers_completed, 0)

    def test_setup_and_cleanup_preserve_power_and_unrelated_pins(self):
        model, _ = self.run_model()
        masks = {OUT: 8, DIR: 0x4F, PU: 0x4F, PD: 0x4F}
        for address, value in model.writes:
            if address in masks:
                self.assertEqual(value & ~masks[address], BASELINE[address] & ~masks[address])
            if address == CON:
                self.assertEqual(value & (0x2000 | 0xC00 | 2), 0) # No IRQ/multibit/slave.
        self.assertNotIn(DIE, [a for a, _ in model.writes])
        self.assertEqual([v for a, v in model.writes if a == BAUD], [255])

    def test_all_zero_and_all_one_responses_are_not_captured_success(self):
        for data in ((0, 0, 0), (255, 255, 255)):
            with self.subTest(data=data):
                model, result = self.run_model(data=data)
                self.assertEqual(result.status, 4)
                self.assertEqual(list(result.id_bytes), list(data))
                self.assert_cleanup(model)

    def test_cleanup_readback_mismatch_overrides_capture_success(self):
        model, result = self.run_model(fail_restore_pu=True)
        self.assertEqual(result.status, 3)
        self.assertEqual(result.cleanup_mismatches, 4)
        self.assertEqual(result.transfers_completed, 4)
        self.assertEqual(len(model.attempts), 4)
        self.assertFalse(model.regs[CON] & 1)


if __name__ == "__main__":
    unittest.main()
