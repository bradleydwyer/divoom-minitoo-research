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
import minitoo_flash_dump_payload as payload
from test_minitoo_flash_id_candidate import BASELINE, READ, WRITE, CON, BAUD, BUF, OUT, DIR, DIE, PU, PD
IN = 0xFD5304


class Result(ctypes.Structure):
    _fields_ = [('completion', ctypes.c_uint), ('status', ctypes.c_uint),
                ('preflight', ctypes.c_uint), ('count', ctypes.c_uint),
                ('ident', ctypes.c_uint * 3), ('polls', ctypes.c_uint * 8),
                ('cleanup', ctypes.c_uint), ('idle', ctypes.c_uint * 4),
                ('frames',ctypes.c_uint),('read_completed',ctypes.c_uint),
                ('read_max',ctypes.c_uint),('read_frames',ctypes.c_uint),
                ('read_idle',ctypes.c_uint),('read_total',ctypes.c_uint)]


class Model:
    def __init__(self, *, qpi=False, continuous=0, dtr=False, asleep=False,
                 ready=None, overrides=None, bad_idle=None, cleanup_error=False, ident=(0x85,0x60,0x15), mismatch=False, ordinal=0):
        self.ordinal = ordinal
        self.regs = {**BASELINE, CON: 0x8000 if ordinal == 0 else 0, 0x1207D0:ordinal,0x1207D4:ordinal^0xFFFFFFFF, 0x1207F8: 0x180FB0, 0x1207FC: 0x4ABC, **(overrides or {})}
        self.qpi, self.continuous, self.dtr, self.asleep = qpi, continuous, dtr, asleep
        self.ready = ready or [1] * 4108
        self.ident, self.mismatch = ident, mismatch
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
            if 6 <= len(self.attempts) <= 8:
                return self.ident[len(self.attempts)-6] if not self.asleep else 255
            if len(self.attempts) > 8:
                n = len(self.attempts)-13
                if n < 0:
                    self.errors.append('Read BUF during address transmit')
                    return 0
                address = (self.ordinal % 512)*4096+n
                return (address*37+(address >> 8)+7)&255
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
            if self.cs() or not con & 1 or len(self.attempts) >= 4108:
                self.errors.append('Extra, disabled or deselected transfer')
                return
            width = 1 << ((con >> 10) & 3)
            released = bool(con & 0x1000) and not con & 8
            if len(self.attempts) < 4:
                if not released or self.regs[DIR] & 0x66 != 0x66 or self.regs[PU] & 0x66 != 0x66:
                    self.errors.append('Data actively driven or missing pull-ups during release')
            elif self.qpi or self.continuous:
                self.errors.append('Active ID transaction before ordinary SPI mode')
            if len(self.attempts) >= 8:
                stage = len(self.attempts)-8
                address = (self.ordinal % 512)*4096
                expected = 3 if stage == 0 else (address >> ((3-stage)*8)) & 255 if stage < 4 else 255
                if value != expected or con != (0x29 if stage < 4 else 0x1029):
                    self.errors.append('Unexpected raw read command, address, length or mode')
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
static volatile unsigned char *d;
void set_data(unsigned char *p) { d=p; }
volatile unsigned char *dump_model_data(void) { return d; }
void set_model(unsigned (*read)(unsigned), void (*write)(unsigned,unsigned)) { r=read; w=write; }
unsigned dump_model_read(unsigned a) { return r(a); }
void dump_model_write(unsigned a,unsigned v) { w(a,v); }
''')
        lib = directory / 'probe.so'
        subprocess.run([shutil.which('cc'), '-shared', '-fPIC', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-DMINITOO_DUMP_OFFLINE_TEST', str(bridge),
                        str(ROOT/'firmware/flash-dump/probe.c'), '-o', str(lib)],
                       capture_output=True, text=True, check=True)
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.set_model.argtypes = [READ, WRITE]
        cls.lib.minitoo_flash_dump.argtypes = [ctypes.POINTER(Result)]
        cls.lib.set_data.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_model(self, **kwargs):
        class Guarded(ctypes.Structure):
            _fields_ = [('before', ctypes.c_uint * 4), ('result', Result), ('after', ctypes.c_uint * 4)]
        model, guarded = Model(**kwargs), Guarded()
        ctypes.memset(ctypes.byref(guarded), 0xA5, ctypes.sizeof(guarded))
        data = (ctypes.c_ubyte * 4104)(*([0xA5]*4104))
        self.lib.set_data(ctypes.cast(ctypes.byref(data,4),ctypes.POINTER(ctypes.c_ubyte)))
        self.lib.set_model(model.read_cb, model.write_cb)
        self.lib.minitoo_flash_dump(ctypes.byref(guarded.result))
        self.assertEqual(list(guarded.before) + list(guarded.after), [0xA5A5A5A5] * 8)
        self.assertEqual(model.errors, [])
        result = guarded.result
        block = bytearray(payload.make_block(model.ordinal if 0 <= model.ordinal < 1024 else 0))
        block[payload.RESULT_OFFSET:payload.RESULT_OFFSET+104] = bytes(result)
        struct.pack_into('<I', block, payload.RESULT_OFFSET+240, payload.STACK_GUARD)
        struct.pack_into('<2I', block, 2040, model.regs[0x1207F8], model.regs[0x1207FC])
        self.assertEqual(bytes(data[:4]+data[-4:]),bytes([0xA5]*8))
        chunk = bytes(data[4:4100])
        if not 0 <= model.ordinal < 1024: return model,result,None
        decoded = payload.decode_result(bytes(block),model.ordinal)
        payload.validate_data(chunk,decoded)
        if result.status not in (1,9):
            self.assertFalse(model.regs[CON] & 1)
            for a in (OUT, DIR, DIE, PD):
                self.assertEqual(model.regs[a], BASELINE[a])
            if not model.cleanup_error:
                self.assertTrue(model.cs())
                self.assertEqual(model.regs[PU], BASELINE[PU])
        return model, result, decoded

    def test_fixed_address_bytes_and_both_passes_all_documented_initial_modes(self):
        for ordinal in (0,1,255,256,511,512,513,1023):
            for qpi,continuous,dtr in ((False,0,False),(True,0,False),(True,2,False),(True,4,True)):
                with self.subTest(ordinal=ordinal,qpi=qpi,continuous=continuous,dtr=dtr):
                    model,result,decoded = self.run_model(ordinal=ordinal,qpi=qpi,continuous=continuous,dtr=dtr)
                    self.assertTrue(decoded['chunk_confirmed'])
                    self.assertEqual((result.frames,result.read_frames,result.read_completed),(4,1,4100))
                    self.assertEqual([sum(8//width for width,_,_ in f) for f in model.frames],[2,16,2,32,32800])
                    self.assertEqual(result.read_total,4100)

    def test_timeouts_at_id_address_and_distributed_data_boundaries_stop_and_restore(self):
        for stage in sorted(set(range(13)) | set(range(13,4108,127)) | {4106,4107}):
            ready = [1]*4108;ready[stage]=None
            with self.subTest(stage=stage):
                model,result,decoded = self.run_model(ready=ready)
                self.assertEqual(result.status,2 if stage < 8 else 7)
                self.assertEqual(len(model.attempts),stage+1)
                self.assertFalse(decoded['chunk_confirmed'])

    def test_whole_chunk_poll_budget_stops_before_unbounded_call(self):
        model,result,decoded = self.run_model(ready=[1]*8+[3000]*4100)
        self.assertEqual(result.status,10)
        self.assertEqual(result.read_completed,700)
        self.assertEqual(result.read_total,2100000)
        self.assertLess(len(model.attempts),4108)
        self.assertFalse(decoded['chunk_confirmed'])

    def test_preconditions_requests_and_spi_pending_reentry_baseline(self):
        for address,value in {**BASELINE,0x1207F8:0x180FB0,0x1207FC:0x4ABC}.items():
            changed = 0x100000 if address == 0x1207F8 else value^1
            model,result,_ = self.run_model(overrides={address:changed})
            self.assertEqual(result.status,1);self.assertEqual(model.writes,[])
        for kwargs in ({'ordinal':1024},{'overrides':{0x1207D4:0}}, {'ordinal':1,'overrides':{CON:0x8000}}):
            model,result,_ = self.run_model(**kwargs)
            self.assertIn(result.status,(1,9));self.assertEqual(model.writes,[])

    def test_idle_refusals_unexpected_id_and_cleanup_failure(self):
        for frame in range(5):
            model,result,_=self.run_model(bad_idle=frame)
            self.assertEqual(result.status,5 if frame < 4 else 8)
            self.assertEqual(len(model.frames),frame)
        for ident in ((0,0,0),(255,255,255),(0x85,0x60,0x16)):
            model,result,_=self.run_model(ident=ident)
            self.assertEqual(len(model.attempts),8)
            self.assertIn(result.status,(4,6))
        _,result,_=self.run_model(cleanup_error=True)
        self.assertEqual(result.status,3)

    def test_poll_boundary_and_private_data_bounds(self):
        for stage in (0,8,11,12,4107):
            for limit in (65536,65537):
                ready=[1]*4108;ready[stage]=limit
                _,result,decoded=self.run_model(ready=ready)
                self.assertEqual(result.status,0 if limit==65536 else 2 if stage<8 else 7)
                self.assertEqual(decoded['chunk_confirmed'],limit==65536)

if __name__ == '__main__': unittest.main()
