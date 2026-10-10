#!/usr/bin/env python3
"""Two complete passes of the fixed 2 MiB main flash; no persistent writes.

Uploads one pinned reader with a checked sequential ordinal for each 4 KiB chunk.
No user-supplied addresses, lengths, opcodes, payloads, resume, retries or resets.
--plan is offline. Raw captures remain in ignored artifacts/device-captures.
"""
import argparse
import datetime
from functools import lru_cache
import json
import os
from pathlib import Path
import struct
import sys
import tempfile

import minitoo_flash_id_upload as transport
import minitoo_flash_dump_payload as payload
import minitoo_ram_marker as marker

rom = marker.rom
# Pinned code and fixed 1024-ordinal plan reviewed; see docs/flash-backup.md.
# Two complete physical passes were captured and independently verified.
EXECUTION_REVIEWED = True
CAPTURE_ROOT = Path(__file__).resolve().parents[1] / "artifacts/device-captures"



@lru_cache(maxsize=1024)
def commands(ordinal):
    uploads, reads = [], []
    for index in range(2):
        address = payload.ADDRESS + index * payload.CHUNK_BYTES
        chunk = payload.make_block(ordinal)[index * 1024:(index + 1) * 1024]
        encoded = transport.transform(chunk)
        uploads.append(b"\xfb\x06" + struct.pack(">IH", address, 1024) + b"\0"
                       + struct.pack("<H", marker.crc16(encoded)) + b"\xff" * 5)
        reads.append(b"\xfd\x07" + struct.pack(">IH", address, 1024) + b"\xff" * 8)
    call = b"\xfb\x08" + struct.pack(">IH", payload.ADDRESS, 0) + b"\xff" * 8
    data_reads = tuple(b"\xfd\x07" + struct.pack(">IH", payload.DATA_ADDRESS + i*1024, 1024) + b"\xff"*8 for i in range(4))
    return tuple(uploads), tuple(reads), call, data_reads


def read_cbw(ordinal, cdb, length, tag, data=None):
    uploads, reads, call, data_reads = commands(ordinal)
    if cdb in uploads:
        index = uploads.index(cdb)
        expected = transport.transform(payload.make_block(ordinal)[index * 1024:(index + 1) * 1024])
        if (length, data) != (1024, expected):
            raise ValueError("Wrong fixed ID upload block")
        direction = 0
    elif data is None and ((cdb in reads + data_reads and length == 1024) or (cdb == call and length == 16)):
        direction = 0x80
    else:
        raise ValueError("Outside the fixed dump allowlist")
    return struct.pack("<4sIIBBB16s", b"USBC", tag, length, direction, 0, 16, cdb)


class DumpSession(marker.ProbeSession):
    def __init__(self, device, report, result):
        super().__init__(device,report,result)
        self.cursor = 0
        self.ordinal = -1
        self.data = self.raw_result = None

    def _probe_transfer(self, cdb, length, data=None):
        uploads, reads, call, data_reads = commands(self.ordinal)
        if not (self.mode == "rom" and self.verified and self.paths_verified):
            raise ValueError("Dump reader requires fresh ROM identity and all 12 excerpts")
        if self.phase == "uploading" and self.cursor < 2:
            expected = uploads[self.cursor]
        elif self.phase in ("reading-initial", "reading-result") and self.cursor < 2:
            expected = reads[self.cursor]
        elif self.phase == "reading-data" and self.cursor < 4:
            expected = data_reads[self.cursor]
        elif self.phase == "calling":
            expected = call
        else:
            expected = None
        if cdb != expected:
            raise ValueError("Dump transfer out of sequence")
        wrapper = read_cbw(self.ordinal, cdb, length, self.tag + 1, data)
        self.tag += 1
        self.report.setdefault("commands_attempted", []).append(cdb.hex())
        if self.dev.write(self.outgoing, wrapper, timeout=2000) != 31:
            raise ValueError("Short dump command wrapper")
        if data is not None:
            if self.dev.write(self.outgoing, data, timeout=2000) != 1024:
                raise ValueError("Short dump upload; stopping without retry")
            reply = b""
        else:
            reply = bytes(self.dev.read(self.incoming, length, timeout=2000))
            if len(reply) != length:
                raise ValueError("Wrong dump RAM-transfer response length")
        rom.check_csw(bytes(self.dev.read(self.incoming, 13, timeout=2000)), self.tag)
        self.cursor += 1
        return reply

    def upload(self):
        self.cursor = 0
        with self.step("verified", "uploading", "uploaded"):
            for index, cdb in enumerate(commands(self.ordinal)[0]):
                self.result["ram_uploads_attempted"] += 1
                chunk = payload.make_block(self.ordinal)[index * 1024:(index + 1) * 1024]
                self._probe_transfer(cdb, 1024, transport.transform(chunk))
            self.result["ram_upload_status_confirmed"] = True

    def read_blocks(self):
        self.cursor = 0
        return b"".join(transport.transform(self._probe_transfer(cdb, 1024)) for cdb in commands(self.ordinal)[1])

    def verify_upload(self):
        with self.step("uploaded", "reading-initial", "readback-verified"):
            data = self.read_blocks()
            self.report["upload_readback_sha256"] = payload.sha256(data)
            if data != payload.make_block(self.ordinal):
                raise ValueError("Complete 2 KiB upload mismatch; no execution follows")
            self.result["upload_readback_confirmed"] = True

    def execute(self):
        if not EXECUTION_REVIEWED:
            raise ValueError("Dump execution review is incomplete")
        with self.step("readback-verified", "calling", "returned"):
            self.result["execution_attempted"] = True
            # A lost response cannot tell us whether the peripheral code ran.
            self.result["flash_chip_transactions"] = None
            self.result["flash_data_reads"] = None
            reply = self._probe_transfer(commands(self.ordinal)[2], 16)
            self.report["call_response_prefix"] = reply[:2].hex()
            if reply[:2] != b"\xfb\x08":
                raise ValueError("Wrong dump call response; stopping without retry")
            self.result["return_response_confirmed"] = True

    def verify_result(self):
        with self.step("returned", "reading-result", "result-verified"):
            data = self.read_blocks()
            self.report["result_readback_sha256"] = payload.sha256(data)
            self.raw_result = data
            capture = payload.decode_result(data,self.ordinal)
            self.report["flash_read_result"] = capture
            self.result["result_block_confirmed"] = True



    def confirm_return(self):
        with self.step('result-verified','checking-rom','complete'):
            self.identify('rom')
            # identify deliberately clears the fingerprint state. Refresh all
            # twelve excerpts before allowing another call in this session.
            self.report['rom_fingerprints'] = []
            self.report['probe_rom_fingerprints'] = []
            self.verify_rom(probe_check=True)
            self.result['rom_return_confirmed'] = True

    def begin(self, ordinal):
        if ordinal != self.ordinal+1 or self.phase != ('verified' if ordinal == 0 else 'complete'):
            raise ValueError('Dump chunk order or phase changed')
        payload.make_block(ordinal)
        self.ordinal = ordinal
        self.phase = 'verified'
        self.raw_result = self.data = None

    def read_data(self):
        with self.step('result-verified','reading-data','result-verified'):
            self.cursor = 0
            self.data = b''.join(transport.transform(self._probe_transfer(cdb,1024))
                                 for cdb in commands(self.ordinal)[3])
            self.report['data_sha256'] = payload.validate_data(self.data,self.report['flash_read_result'])

# The independently verified first 64 bytes from the preceding physical experiment.
HEADER_SHA256 = 'd4e8fdaf743d8873c35ca1d194346e448dbd01e0c080b5ff14bdbe3810607a1c'


def plan():
    return {'purpose':'Offline fixed main-flash backup plan; no device access',
            'execution_reviewed':EXECUTION_REVIEWED,'flash_bytes':payload.FLASH_BYTES,
            'passes':2,'chunks_per_pass':payload.CHUNKS_PER_PASS,
            'chunk_bytes':payload.CAPTURE_BYTES,'calls':payload.TOTAL_CHUNKS,
            'code_sha256':payload.CODE_SHA256,'first_block_sha256':payload.BLOCK_ZERO_SHA256,
            'ram_data_address':f'0x{payload.DATA_ADDRESS:08x}',
            'flash_chip_transactions_max':5*payload.TOTAL_CHUNKS,
            'status_register_writes':0,'flash_program_erase_commands':0,
            'automatic_reset_commands':0,'retries':0,
            'note':'Two complete sequential passes of the identified 2 MiB main chip. Other storage is excluded. Private local capture; restoration remains unproven.'}


def reserve_capture():
    CAPTURE_ROOT.mkdir(parents=True,exist_ok=True)
    if __import__('shutil').disk_usage(CAPTURE_ROOT).free < 16*1024*1024:
        raise OSError('Need at least 16 MiB free for private capture evidence')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = Path(tempfile.mkdtemp(prefix=f'minitoo-flash-full-{stamp}-',dir=CAPTURE_ROOT))
    streams = {}
    try:
        for name in ('flash-pass1.bin','flash-pass2.bin','result-blocks.bin','chunks.jsonl','report.json'):
            stream = (directory/name).open('x+b')
            streams[name] = stream
            os.fchmod(stream.fileno(),0o600)
        if os.geteuid() == 0 and 'SUDO_UID' in os.environ and 'SUDO_GID' in os.environ:
            uid,gid = int(os.environ['SUDO_UID']),int(os.environ['SUDO_GID'])
            for stream in streams.values(): os.fchown(stream.fileno(),uid,gid)
            os.chown(directory,uid,gid)
        return directory,streams
    except BaseException:
        for stream in streams.values(): stream.close()
        raise


def persist(stream,data):
    if stream.write(data) != len(data): raise OSError('Short private capture write')
    stream.flush()
    os.fsync(stream.fileno())


def file_digest(stream):
    stream.flush()
    stream.seek(0)
    data = stream.read()
    if len(data) != payload.FLASH_BYTES:
        raise ValueError('Full pass file size mismatch')
    return payload.sha256(data)


def run(progress=None):
    result = dict(purpose='Two complete raw main-flash passes',action='run-fixed-full-dump',
                  flash_program_erase_commands=0,status_register_writes=0,automatic_reset_commands=0,
                  entry_confirmed=False,rom_fingerprints_confirmed=False,
                  ram_uploads_attempted=0,ram_upload_status_confirmed=False,
                  upload_readback_confirmed=False,execution_attempted=False,
                  return_response_confirmed=False,result_block_confirmed=False,
                  rom_return_confirmed=False,flash_chip_transactions=0,flash_data_reads=0,
                  chunks_saved=0,chunk_bytes=payload.CAPTURE_BYTES,bytes_per_pass=payload.FLASH_BYTES,
                  full_dump_confirmed=False,data_saved=False,sessions=[])
    session = None
    streams = {}
    pending_result = False
    failed = True
    transactions = reads = 0
    try:
        if not EXECUTION_REVIEWED: raise ValueError('Full-reader review incomplete; no device access')
        for ordinal in range(payload.TOTAL_CHUNKS): payload.make_block(ordinal)
        directory,streams = reserve_capture()
        result['capture_directory'] = str(directory)
        backend = rom.usb.backend.libusb1.get_backend(find_library=rom.libusb_package.find_library)
        if backend is None: raise ValueError('libusb backend unavailable')
        device = rom.select(rom.enumerate_target(backend),rom.APP_PID)
        if device is None: raise ValueError('Fresh application USB required; restart and reconnect USB')
        port = rom.location(device)
        report = {'stage':'application-entry'}
        result['sessions'].append(report)
        with rom.Session(device,report) as session:
            session.identify('app')
            session.transition('enter')
        device = rom.wait_for(backend,rom.ROM_PID,port)
        report = {'stage':'fixed-two-pass-main-flash-dump'}
        result['sessions'].append(report)
        with DumpSession(device,report,result) as session:
            session.identify('rom')
            result['entry_confirmed'] = True
            session.verify_paths()
            for ordinal in range(payload.TOTAL_CHUNKS):
                session.begin(ordinal)
                # Retain only this chunk's detailed commands in the final report;
                # all chunk results and hashes are appended to the private journal.
                report['commands_attempted'] = []
                pending_result = True
                session.upload()
                session.verify_upload()
                session.execute()
                session.verify_result()
                persist(streams['result-blocks.bin'],session.raw_result)
                pending_result = False
                capture = report['flash_read_result']
                transactions += capture['transactions_started']+capture['read_transactions_started']
                reads += capture['read_transactions_started']
                result['flash_chip_transactions'],result['flash_data_reads'] = transactions,reads
                session.read_data()
                session.confirm_return()
                record = dict(ordinal=ordinal,**{k:v for k,v in report.items() if k != 'stage'})
                persist(streams['chunks.jsonl'],(json.dumps(record,separators=(',',':'))+'\n').encode())
                if not capture['chunk_confirmed']: raise ValueError(f"Chunk {ordinal} unconfirmed: {capture['status']}")
                index = ordinal % payload.CHUNKS_PER_PASS
                pass_number = ordinal // payload.CHUNKS_PER_PASS + 1
                if index == 0 and payload.sha256(session.data[:64]) != HEADER_SHA256:
                    raise ValueError('First flash bytes differ from the verified small read')
                if pass_number == 2:
                    streams['flash-pass1.bin'].seek(index*payload.CAPTURE_BYTES)
                    if streams['flash-pass1.bin'].read(payload.CAPTURE_BYTES) != session.data:
                        raise ValueError(f'Second complete pass differs at chunk {index}; no retry')
                persist(streams[f'flash-pass{pass_number}.bin'],session.data)
                result['chunks_saved'] += 1
                if progress and (index % 16 == 0 or index == payload.CHUNKS_PER_PASS-1):
                    progress({'pass':pass_number,'bytes_saved':(index+1)*payload.CAPTURE_BYTES,
                              'bytes_per_pass':payload.FLASH_BYTES})
        hashes = [file_digest(streams[f'flash-pass{n}.bin']) for n in (1,2)]
        if hashes[0] != hashes[1]: raise ValueError('Complete pass hashes differ')
        result.update(pass_sha256=hashes,data_saved=True,full_dump_confirmed=True)
        result['note'] = ('Two complete 2 MiB main-chip passes matched, with cleanup and ROM return checked after every chunk. '
                          'Saved locally in the private capture directory. Other storage is excluded; restoration is unproven. '
                          'Device remains in ROM; use the tested power-key restart and reconnect USB.')
        failed = False
    except (rom.usb.core.USBError,ValueError,RuntimeError,OSError,KeyboardInterrupt) as error:
        result['error'] = str(error) or type(error).__name__
        result['note'] = ('Stopped without retry, fallback or automatic reset. Partial evidence stays local. '
                          'Use the tested power-key restart if ROM entry occurred. Reset from hung RAM remains untested.')
    finally:
        try:
            if pending_result and getattr(session,'raw_result',None) is not None:
                persist(streams['result-blocks.bin'],session.raw_result)
            if streams: persist(streams['report.json'],(json.dumps(result,indent=2)+'\n').encode())
        except OSError as error:
            result['metadata_save_error'] = str(error)
            result['full_dump_confirmed'] = False
            failed = True
        finally:
            for stream in streams.values(): stream.close()
    return result,failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--plan',action='store_true')
    action.add_argument('--run-fixed-full-dump',action='store_true')
    args = parser.parse_args()
    if args.plan:
        print(json.dumps(plan(),indent=2)); return
    if sys.platform == 'darwin' and os.geteuid() != 0:
        parser.error('macOS USB capture requires sudo; no device action attempted')
    result,failed = run(progress=lambda value: print(json.dumps({'progress':value}),flush=True))
    print(json.dumps(result,indent=2),flush=True)
    raise SystemExit(int(failed))


if __name__ == '__main__': main()
