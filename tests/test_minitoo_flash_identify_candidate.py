"""Actual C with synthetic MMIO and an independent flash-mode state model.

Models documented modes and clock counts, not electrical levels/timing or silicon.
"""
import ctypes
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import minitoo_flash_identify_payload as payload
from test_minitoo_flash_id_candidate import BASELINE, READ, WRITE, CON, BAUD, BUF, OUT, DIR, DIE, PU, PD
IN = 0xFD5304


class Result(ctypes.Structure):
    _fields_ = [('completion', ctypes.c_uint), ('status', ctypes.c_uint),
                ('preflight', ctypes.c_uint), ('count', ctypes.c_uint),
                ('ident', ctypes.c_uint * 3), ('polls', ctypes.c_uint * 8),
                ('cleanup', ctypes.c_uint), ('idle', ctypes.c_uint * 4),
                ('frames', ctypes.c_uint)]


class Model:
    def __init__(self, *, qpi=False, continuous=0, dtr=False, asleep=False,
                 ready=None, overrides=None, bad_idle=None, cleanup_error=False):
        self.regs = {**BASELINE, 0x1207F8: 0x180FB0, 0x1207FC: 0x4ABC, **(overrides or {})}
        self.qpi, self.continuous, self.dtr, self.asleep = qpi, continuous, dtr, asleep
        self.ready = ready or [1] * 8
        self.bad_idle, self.cleanup_error = bad_idle, cleanup_error
        self.reads, self.writes, self.attempts, self.frames, self.errors = [], [], [], [], []
        self.active, self.pending, self.polls = False, True, 0
        self.frame = None
        self.read_cb, self.write_cb = READ(self.read), WRITE(self.write)

    def cs(self):
        return bool((self.regs[OUT] if not self.regs[DIR] & 8 else self.regs[PU]) & 8)

    def read(self, address):
        self.reads.append(address)
        if address == CON and self.active:
            self.polls += 1
            threshold = self.ready[len(self.attempts) - 1]
            if threshold is not None and self.polls >= threshold:
                self.pending = True
            return self.regs[CON] | (0x8000 if self.pending else 0)
        if address == BUF:
            if len(self.attempts) >= 6:
                return [0x85, 0x60, 0x15][len(self.attempts) - 6] if not self.asleep else 255
            return 255
        if address == IN:
            return 0 if self.bad_idle == len(self.frames) else 0x66
        if address not in self.regs or address == BAUD:
            self.errors.append(f'Unexpected read {address:x}')
            return 0
        return self.regs[address]

    def close_frame(self):
        clocks = sum(8 // width for width, _, _ in self.frame)
        if not self.asleep:
            if self.continuous:
                # 24 address bits plus 8 mode bits; SDR or DTR, dual or quad.
                if clocks * self.continuous * (2 if self.dtr else 1) >= 32:
                    self.continuous = 0
            elif self.qpi and clocks == 2:
                self.qpi = False
        self.frames.append(self.frame)
        self.frame = None

    def write(self, address, value):
        before = self.cs()
        self.writes.append((address, value))
        if address not in (OUT, DIR, PU, PD, CON, BAUD, BUF):
            self.errors.append(f'Unexpected write {address:x}')
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
            con = self.regs[CON]
            if self.cs() or not con & 1 or len(self.attempts) >= 8:
                self.errors.append('Extra, disabled or deselected transfer')
                return
            width = 1 << ((con >> 10) & 3)
            released = bool(con & 0x1000) and not con & 8
            if len(self.attempts) < 4:
                if not released or self.regs[DIR] & 0x66 != 0x66 or self.regs[PU] & 0x66 != 0x66:
                    self.errors.append('Data actively driven or missing pull-ups during release')
            elif self.qpi or self.continuous:
                self.errors.append('Active ID transaction before ordinary SPI mode')
            self.frame.append((width, released, value))
            self.attempts.append((con, value))
            self.active, self.pending, self.polls = True, False, 0
        elif not (self.cleanup_error and address == PU and value == BASELINE[PU]):
            self.regs[address] = value
        if ((address == OUT and value & 0x10 != 0x10)
                or (address == DIR and value & 0x10)):
            self.errors.append('Flash power modified')
        after = self.cs()
        if before and not after:
            self.frame = []
        elif not before and after:
            self.close_frame()


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='minitoo-identify-model-')
        directory = Path(cls.temp.name)
        bridge = directory / 'bridge.c'
        bridge.write_text('''
static unsigned (*r)(unsigned);
static void (*w)(unsigned, unsigned);
void set_model(unsigned (*read)(unsigned), void (*write)(unsigned,unsigned)) { r=read; w=write; }
unsigned identify_model_read(unsigned a) { return r(a); }
void identify_model_write(unsigned a,unsigned v) { w(a,v); }
''')
        lib = directory / 'probe.so'
        subprocess.run([shutil.which('cc'), '-shared', '-fPIC', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-DMINITOO_IDENTIFY_OFFLINE_TEST', str(bridge),
                        str(ROOT/'firmware/flash-identify/probe.c'), '-o', str(lib)],
                       capture_output=True, text=True, check=True)
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.set_model.argtypes = [READ, WRITE]
        cls.lib.minitoo_flash_identify.argtypes = [ctypes.POINTER(Result)]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_model(self, **kwargs):
        class Guarded(ctypes.Structure):
            _fields_ = [('before', ctypes.c_uint * 4), ('result', Result), ('after', ctypes.c_uint * 4)]
        model, guarded = Model(**kwargs), Guarded()
        ctypes.memset(ctypes.byref(guarded), 0xA5, ctypes.sizeof(guarded))
        self.lib.set_model(model.read_cb, model.write_cb)
        self.lib.minitoo_flash_identify(ctypes.byref(guarded.result))
        self.assertEqual(list(guarded.before) + list(guarded.after), [0xA5A5A5A5] * 8)
        self.assertEqual(model.errors, [])
        result = guarded.result
        block = bytearray(payload.make_block())
        block[payload.RESULT_OFFSET:payload.RESULT_OFFSET+84] = bytes(result)
        struct.pack_into('<I', block, payload.RESULT_OFFSET+84, payload.STACK_GUARD)
        struct.pack_into('<2I', block, 2040, model.regs[0x1207F8], model.regs[0x1207FC])
        decoded = payload.decode_result(bytes(block))
        if result.status != 1:
            self.assertFalse(model.regs[CON] & 1)
            for a in (OUT, DIR, DIE, PD):
                self.assertEqual(model.regs[a], BASELINE[a])
            if not model.cleanup_error:
                self.assertTrue(model.cs())
                self.assertEqual(model.regs[PU], BASELINE[PU])
        return model, result, decoded

    def test_documented_initial_modes_have_no_active_data_drive_before_exit(self):
        for qpi in (False, True):
            for continuous in (0, 2, 4):
                for dtr in (False, True):
                    with self.subTest(qpi=qpi, continuous=continuous, dtr=dtr):
                        model, result, decoded = self.run_model(qpi=qpi, continuous=continuous, dtr=dtr)
                        self.assertEqual(result.status, 0)
                        self.assertTrue(decoded['matches_cached_id'])
                        self.assertFalse(model.qpi or model.continuous)
                        self.assertEqual([sum(8//width for width, _, _ in f) for f in model.frames], [2,16,2,32])
                        self.assertEqual([v for _, v in model.attempts], [255]*4 + [0x9F,255,255,255])
                        self.assertEqual(result.frames, 4)

    def test_timeout_at_each_stage_stops_and_restores(self):
        for stage in range(8):
            for threshold in (None, 65537):
                with self.subTest(stage=stage, threshold=threshold):
                    ready = [1]*8
                    ready[stage] = threshold
                    model, result, decoded = self.run_model(ready=ready)
                    self.assertEqual(result.status, 2)
                    self.assertEqual(result.count, stage)
                    self.assertEqual(len(model.attempts), stage + 1)
                    self.assertFalse(decoded['id_captured'])

    def test_last_allowed_poll_completes(self):
        _, result, decoded = self.run_model(ready=[65536]*8)
        self.assertEqual(list(result.polls), [65536]*8)
        self.assertTrue(decoded['matches_cached_id'])

    def test_each_preflight_change_writes_no_peripherals(self):
        for address, value in {**BASELINE, 0x1207F8:0x180FB0, 0x1207FC:0x4ABC}.items():
            changed = 0x100000 if address == 0x1207F8 else value ^ 1
            with self.subTest(address=hex(address)):
                model, result, _ = self.run_model(overrides={address:changed})
                self.assertEqual(result.status, 1)
                self.assertEqual(model.writes, [])

    def test_each_idle_refusal_stops_before_asserting_next_cs(self):
        for frame, count in enumerate((0,1,3,4)):
            model, result, _ = self.run_model(bad_idle=frame)
            self.assertEqual(result.status, 5)
            self.assertEqual((result.frames, result.count, len(model.frames)), (frame,count,frame))

    def test_cleanup_failure_is_not_success(self):
        _, result, decoded = self.run_model(cleanup_error=True)
        self.assertEqual(result.status, 3)
        self.assertFalse(decoded['id_captured'])

    def test_deep_power_down_does_not_trigger_wake_or_retry(self):
        model, result, _ = self.run_model(asleep=True)
        self.assertEqual(result.status, 4)
        self.assertEqual(len(model.attempts), 8)
        self.assertTrue(model.asleep)


if __name__ == '__main__':
    unittest.main()
