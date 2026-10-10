"""Fixed dump host pipeline, persistence and interruption tests; fake USB only."""
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import minitoo_flash_dump as m
from test_minitoo_rom_check import Device,PROBE_BYTES,inquiry,response
from test_minitoo_ram_marker import CountingDevice


def chunk(ordinal):
    address=(ordinal % 512)*4096
    return bytes(((address+n)*37+((address+n)>>8)+7)&255 for n in range(4096))


def captured_block(ordinal):
    block=bytearray(m.payload.make_block(ordinal))
    words=[m.payload.COMPLETION,0,0,8,0x85,0x60,0x15,*([1]*8),0,*([0x66]*4),4,4100,1,1,0x66,4100]
    struct.pack_into('<26I',block,0x700,*words)
    struct.pack_into('<4I',block,0x7f0,m.payload.STACK_GUARD,0,0x180FF0,0x4ABC)
    return bytes(block)


class DumpTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='minitoo-dump-host-');self.addCleanup(self.temp.cleanup)
        for p in (patch.object(m,'CAPTURE_ROOT',Path(self.temp.name)),patch.object(m,'EXECUTION_REVIEWED',True),
                  patch.object(m,'HEADER_SHA256',m.payload.sha256(chunk(0)[:64])),
                  patch.object(m.rom.usb.backend.libusb1,'get_backend',return_value=object()),
                  *[patch.object(m.rom.usb.util,n) for n in ('claim_interface','release_interface','dispose_resources')]):
            p.start();self.addCleanup(p.stop)

    def devices(self,chunks=2,corrupt=None):
        gone=m.rom.usb.core.USBError('Device disconnected',errno=19)
        app=Device(m.rom.APP_PID,response(inquiry('UDISK'),1)+[gone])
        reads=response(inquiry('UBOOT1.00'),1)
        for number,(_,data) in enumerate((*m.rom.ROM_FINGERPRINTS,*PROBE_BYTES),2): reads+=response(data,number)
        tag=14
        for ordinal in range(chunks):
            for _ in range(2): reads+=response(b'',tag)[1:];tag+=1
            for block in (m.payload.make_block(ordinal),):
                for i in range(2):
                    data=block[i*1024:(i+1)*1024]
                    if corrupt==('upload',ordinal,i): data=bytes([data[0]^1])+data[1:]
                    reads+=response(m.transport.transform(data),tag);tag+=1
            reads+=response(b'\xfb\x08'+bytes(14),tag);tag+=1
            block=captured_block(ordinal)
            if corrupt==('result',ordinal,0): block=bytes([block[0]^1])+block[1:]
            for i in range(2): reads+=response(m.transport.transform(block[i*1024:(i+1)*1024]),tag);tag+=1
            data=chunk(ordinal)
            if corrupt==('data',ordinal,0): data=bytes([data[0]^1])+data[1:]
            for i in range(4): reads+=response(m.transport.transform(data[i*1024:(i+1)*1024]),tag);tag+=1
            reads+=response(inquiry('UBOOT1.00'),tag);tag+=1
            for _,data in (*m.rom.ROM_FINGERPRINTS,*PROBE_BYTES): reads+=response(data,tag);tag+=1
        reads += [m.rom.usb.core.USBError('End fake stream')]
        return app,CountingDevice(reads)

    def run_with(self,app,dev):
        with patch.object(m.rom,'enumerate_target',side_effect=[[app],[dev]]): return m.run()

    def test_full_fixed_plan_two_passes_persists_all_evidence_and_hashes(self):
        app,dev=self.devices(chunks=1024)
        result,failed=self.run_with(app,dev)
        self.assertFalse(failed,result)
        self.assertTrue(result['full_dump_confirmed'])
        self.assertEqual(result['chunks_saved'],1024)
        self.assertEqual((result['flash_chip_transactions'],result['flash_data_reads']),(5120,1024))
        root=Path(result['capture_directory'])
        expected=b''.join(chunk(i) for i in range(512))
        for name in ('flash-pass1.bin','flash-pass2.bin'):
            self.assertEqual((root/name).read_bytes(),expected)
            self.assertEqual((root/name).stat().st_mode&0o777,0o600)
        self.assertEqual(result['pass_sha256'],[m.payload.sha256(expected)]*2)
        self.assertEqual((root/'result-blocks.bin').stat().st_size,1024*2048)
        journal=[json.loads(line) for line in (root/'chunks.jsonl').read_text().splitlines()]
        self.assertEqual([row['ordinal'] for row in journal],list(range(1024)))
        self.assertEqual(json.loads((root/'report.json').read_text()),result)
        self.assertTrue(app.attached and dev.attached)

    def test_each_usb_interruption_and_short_write_in_first_and_next_chunk_stops(self):
        for number in range(1,119):
            app,dev=self.devices();dev.fail_read=number
            result,failed=self.run_with(app,dev)
            self.assertTrue(failed);self.assertFalse(result['full_dump_confirmed'])
            self.assertEqual(dev.read_count,number);self.assertTrue(dev.attached)
        for short in (False,True):
            for number in range(1,66):
                app,dev=self.devices();dev.fail_write=number;dev.short_write=short
                result,failed=self.run_with(app,dev)
                self.assertTrue(failed);self.assertFalse(result['full_dump_confirmed'])
                self.assertEqual(dev.write_count,number);self.assertTrue(dev.attached)

    def test_corrupted_upload_stops_before_call_and_bad_result_stops_before_data(self):
        for stage in ('upload','result'):
            app,dev=self.devices(corrupt=(stage,0,0));result,failed=self.run_with(app,dev)
            self.assertTrue(failed);self.assertEqual(result['chunks_saved'],0)
            self.assertEqual(result['execution_attempted'],stage=='result')
            if stage=='result': self.assertEqual((Path(result['capture_directory'])/'result-blocks.bin').stat().st_size,2048)
        app,dev=self.devices(corrupt=('data',0,0));result,failed=self.run_with(app,dev)
        self.assertTrue(failed);self.assertIn('First flash bytes',result['error'])

    def test_second_pass_mismatch_stops_and_retains_first_pass(self):
        app,dev=self.devices(chunks=513,corrupt=('data',512,0))
        # Permit first-byte comparison so the complete-chunk comparison is tested.
        original=m.payload.sha256
        def digest(data): return original(chunk(0)[:64]) if len(data)==64 else original(data)
        with patch.object(m.payload,'sha256',side_effect=digest): result,failed=self.run_with(app,dev)
        self.assertTrue(failed);self.assertIn('Second complete pass differs',result['error'])
        self.assertEqual(result['chunks_saved'],512)
        self.assertEqual((Path(result['capture_directory'])/'flash-pass1.bin').stat().st_size,2097152)
        self.assertEqual((Path(result['capture_directory'])/'flash-pass2.bin').stat().st_size,0)

    def test_reservation_gate_and_save_failures_stop_without_success(self):
        with patch.object(m,'EXECUTION_REVIEWED',False),patch.object(m.rom,'enumerate_target') as enum:
            result,failed=m.run();self.assertTrue(failed);enum.assert_not_called()
        with patch.object(m,'reserve_capture',side_effect=OSError('Disk full')),patch.object(m.rom,'enumerate_target') as enum:
            result,failed=m.run();self.assertTrue(failed);enum.assert_not_called()
        for name in ('flash-pass1.bin','result-blocks.bin','chunks.jsonl','report.json'):
            app,dev=self.devices();original=m.persist
            def fail(stream,data):
                if stream.name.endswith(name): raise OSError('Storage error')
                return original(stream,data)
            with patch.object(m,'persist',side_effect=fail): result,failed=self.run_with(app,dev)
            self.assertTrue(failed);self.assertFalse(result['full_dump_confirmed'])
            self.assertLessEqual(result['chunks_saved'],2)

    def test_request_bounds_allowlist_and_result_reserved_fields(self):
        for ordinal in (-1,1024,1.0,True):
            with self.assertRaises(ValueError): m.payload.make_block(ordinal)
        for ordinal in range(1024):
            block=m.payload.make_block(ordinal)
            self.assertEqual(struct.unpack_from('<2I',block,0x7d0),(ordinal,ordinal^0xFFFFFFFF))
        for offset in (0,0x700,0x768,0x7d0,0x7d4,0x7e0,0x7f0,0x7f4,0x7fc):
            block=bytearray(captured_block(0));block[offset]^=1
            with self.assertRaises(ValueError):m.payload.decode_result(bytes(block),0)
        uploads,reads,call,data_reads=m.commands(0)
        for cdb in (m.rom.ENTER,m.rom.RESET,b'\xff'*16):
            with self.assertRaises(ValueError):m.read_cbw(0,cdb,16,1)
        with self.assertRaises(ValueError):m.read_cbw(0,uploads[0],1024,1,bytes(1024))
        app,dev=self.devices()
        session=m.DumpSession(dev,{},{});session.phase='verified';session.begin(0)
        with self.assertRaises(ValueError):session.begin(1)
        with self.assertRaises(ValueError):session._probe_transfer(call,16)

if __name__=='__main__':unittest.main()
