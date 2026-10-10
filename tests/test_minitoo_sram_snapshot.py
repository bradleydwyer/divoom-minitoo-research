"""Fixed copier instruction/bounds, private persistence and fake-USB failures."""
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import minitoo_sram_snapshot as m
from test_minitoo_rom_check import Device, PROBE_BYTES, inquiry, response
from test_minitoo_ram_marker import CountingDevice

p = m.payload
CAPTURE = bytes(i % 251 for i in range(p.CAPTURE_BYTES))


class PayloadTests(unittest.TestCase):
    def test_exact_machine_code_copies_every_word_and_marks_completion_last(self):
        for source in (CAPTURE, bytes(p.CAPTURE_BYTES), b"\xff" * p.CAPTURE_BYTES):
            audit = p.audit_code(p.CODE, source)
            self.assertEqual(audit["output"], source)
            self.assertEqual(audit["reads"], list(range(0x10B000, 0x110000, 4)))
            self.assertEqual([a for a, _ in audit["writes"][:-1]], list(range(0x120400, 0x125400, 4)))
            self.assertEqual(audit["writes"][-1], (0x1203F0, p.MARKER))
            self.assertEqual(audit["instructions"], 20487)
        self.assertEqual(len(p.CODE), 42)
        self.assertEqual(p.sha256(p.make_block()), p.BLOCK_SHA256)

    def test_changed_program_and_every_unexpected_result_byte_rejected(self):
        for index in range(len(p.CODE)):
            code = bytearray(p.CODE)
            code[index] ^= 1
            with self.subTest(code_byte=index), self.assertRaises(ValueError):
                p.make_block(bytes(code))
        for bad in (p.CODE[:-1], p.CODE + b"\0"):
            with self.assertRaises(ValueError):
                p.make_block(bad)
        result = p.result_block()
        p.validate_result(result)
        for index in range(p.SIZE):
            changed = bytearray(result)
            changed[index] ^= 1
            with self.subTest(result_byte=index), self.assertRaises(ValueError):
                p.validate_result(bytes(changed))
        for bad in (result[:-1], result + b"\0", p.make_block()):
            with self.assertRaises(ValueError):
                p.validate_result(bad)

    def test_allowlist_never_reads_original_application_sram_or_rom_working_memory(self):
        upload, read, call, chunks = m.commands()
        self.assertEqual(len(chunks), 20)
        self.assertEqual(chunks[0].hex(), "fd07001204000400ffffffffffffffff")
        self.assertEqual(chunks[-1].hex(), "fd07001250000400ffffffffffffffff")
        for cdb in (upload, read, call, *chunks):
            size = 16 if cdb == call else p.SIZE
            data = m.transform(p.make_block()) if cdb == upload else None
            m.snapshot_cbw(cdb, size, 1, data)
            for index in range(16):
                changed = bytearray(cdb)
                changed[index] ^= 1
                if bytes(changed) in chunks:  # Another chunk is allowed by address, ordered by session.
                    continue
                with self.subTest(command=cdb.hex(), byte=index), self.assertRaises(ValueError):
                    m.snapshot_cbw(bytes(changed), size, 1, data)
            with self.assertRaises(ValueError):
                m.snapshot_cbw(cdb, size - 1, 1, data)
        for address in (p.SOURCE, 0x100000, 0x181040, 0x19FC00, 0xFD1C00, 0x6000000):
            cdb = b"\xfd\x07" + struct.pack(">IH", address, p.SIZE) + b"\xff" * 8
            with self.assertRaises(ValueError):
                m.snapshot_cbw(cdb, p.SIZE, 1)

    def test_plan_is_offline(self):
        with patch.object(m.rom, "enumerate_target") as enumerate_mock, \
                patch.object(m.rom.usb.backend.libusb1, "get_backend") as backend, \
                patch.object(m, "reserve_capture") as reserve:
            plan = m.plan()
        enumerate_mock.assert_not_called()
        backend.assert_not_called()
        reserve.assert_not_called()
        self.assertEqual(plan["source_writes"], 0)
        self.assertEqual(plan["flash_chip_transactions"], 0)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        for name in ("claim_interface", "release_interface", "dispose_resources"):
            mock = patch.object(m.rom.usb.util, name)
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch.object(m.rom.usb.backend.libusb1, "get_backend", return_value=object())
        mock.start()
        self.addCleanup(mock.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        mock = patch.object(m, "CAPTURE_ROOT", Path(temporary.name))
        mock.start()
        self.addCleanup(mock.stop)
        mock = patch.dict(m.os.environ, {}, clear=True)
        mock.start()
        self.addCleanup(mock.stop)

    def devices(self):
        gone = m.rom.usb.core.USBError("Device disconnected", errno=19)
        app = Device(m.rom.APP_PID, response(inquiry("UDISK"), 1) + [gone])
        reads = response(inquiry("UBOOT1.00"), 1)
        number = 2
        for _, data in (*m.rom.ROM_FINGERPRINTS, *PROBE_BYTES):
            reads += response(data, number)
            number += 1
        reads += response(b"", number)[1:]
        number += 1
        for data in (m.transform(p.make_block()), b"\xfb\x08" + bytes(14), m.transform(p.result_block())):
            reads += response(data, number)
            number += 1
        for _ in range(2):
            for offset in range(0, len(CAPTURE), p.SIZE):
                reads += response(m.transform(CAPTURE[offset:offset + p.SIZE]), number)
                number += 1
        reads += response(inquiry("UBOOT1.00"), number)
        return app, CountingDevice(reads)

    def run_with(self, app, device):
        with patch.object(m.rom, "enumerate_target", side_effect=[[app], [device]]):
            return m.run()

    def cdbs(self, device):
        return [data[15:] for data in device.writes if len(data) == 31]

    def test_complete_copy_two_reads_return_and_private_save(self):
        app, device = self.devices()
        result, failed = self.run_with(app, device)
        self.assertFalse(failed, result)
        self.assertTrue(result["snapshot_confirmed"])
        self.assertTrue(result["copy_read_twice_confirmed"])
        self.assertTrue(result["rom_return_confirmed"])
        self.assertEqual(result["capture_sha256"], p.sha256(CAPTURE))
        directory = Path(result["capture_directory"])
        raw = directory / "sram-10b000-110000.bin"
        self.assertEqual(raw.read_bytes(), CAPTURE)
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(raw.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads((directory / "report.json").read_text()), result)
        self.assertEqual((device.write_count, device.read_count), (59, 115))
        upload, read, call, chunks = m.commands()
        self.assertEqual(self.cdbs(device)[-45:],
                         [upload, read, call, read, *chunks, *chunks, m.rom.INQUIRY.ljust(16, b"\0")])
        self.assertEqual(self.cdbs(device).count(call), 1)
        self.assertTrue(app.attached and device.attached)
        # A later experiment reserves another directory, never overwrites the first.
        app, device = self.devices()
        second, failed = self.run_with(app, device)
        self.assertFalse(failed)
        self.assertNotEqual(second["capture_directory"], result["capture_directory"])
        self.assertEqual(raw.read_bytes(), CAPTURE)

    def test_every_usb_error_or_short_write_stops_without_retry_or_data_save(self):
        # Reuse precomputed encrypted fixtures; each fake gets a fresh response list.
        _, template = self.devices()
        for operation, maximum in (("read", 115), ("write", 59), ("short-write", 59)):
            for number in range(1, maximum + 1):
                gone = m.rom.usb.core.USBError("Device disconnected", errno=19)
                app = Device(m.rom.APP_PID, response(inquiry("UDISK"), 1) + [gone])
                device = CountingDevice(template.reads)
                if operation == "read":
                    device.fail_read = number
                else:
                    device.fail_write = number
                    device.short_write = operation == "short-write"
                with self.subTest(operation=operation, number=number):
                    result, failed = self.run_with(app, device)
                    self.assertTrue(failed)
                    self.assertFalse(result["snapshot_confirmed"])
                    self.assertFalse(result["data_saved"])
                    self.assertEqual(device.read_count if operation == "read" else device.write_count, number)
                    self.assertTrue(device.attached)

    def test_changed_upload_stops_before_execution_and_changed_completion_before_copy_reads(self):
        for response_index, block in ((27, p.make_block()), (31, p.result_block())):
            app, device = self.devices()
            changed = bytearray(block)
            changed[0] ^= 1
            device.reads[response_index] = m.transform(bytes(changed))
            with self.subTest(response_index=response_index):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["data_saved"])
                self.assertEqual(self.cdbs(device)[-1], m.commands()[1])
                self.assertFalse(result["execution_attempted"] if response_index == 27
                                 else result["result_block_confirmed"])

    def test_each_second_read_mismatch_stops_at_that_chunk(self):
        _, template = self.devices()
        for index in range(20):
            gone = m.rom.usb.core.USBError("Device disconnected", errno=19)
            app = Device(m.rom.APP_PID, response(inquiry("UDISK"), 1) + [gone])
            device = CountingDevice(template.reads)
            changed = bytearray(CAPTURE[index * p.SIZE:(index + 1) * p.SIZE])
            changed[-1] ^= 1
            device.reads[73 + 2 * index] = m.transform(bytes(changed))
            with self.subTest(chunk=index):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["copy_read_twice_confirmed"])
                self.assertFalse(result["rom_return_confirmed"])
                self.assertFalse(result["data_saved"])
                self.assertEqual(device.read_count, 75 + 2 * index)

    def test_invalid_payload_responses_and_statuses_stop_before_the_next_command(self):
        for index, replacement, last_command in (
                (29, bytes(16), m.commands()[2]),
                (29, b"\xfb\x08", m.commands()[2]),
                (30, bytes(13), m.commands()[2]),
                (31, bytes(1023), m.commands()[1]),
                (33, bytes(1023), m.commands()[3][0]),
                (34, bytes(13), m.commands()[3][0])):
            app, device = self.devices()
            device.reads[index] = replacement
            with self.subTest(response_index=index):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["data_saved"])
                self.assertFalse(result["snapshot_confirmed"])
                self.assertEqual(self.cdbs(device)[-1], last_command)

    def test_capture_or_metadata_flush_failure_cannot_report_success(self):
        for calls in (None, [None, OSError("No space for metadata")]):
            app, device = self.devices()
            options = ({"side_effect": OSError("No space for capture")} if calls is None
                       else {"side_effect": calls})
            with patch.object(m.os, "fsync", **options):
                result, failed = self.run_with(app, device)
            with self.subTest(metadata_only=calls is not None):
                self.assertTrue(failed)
                self.assertFalse(result["snapshot_confirmed"])
                self.assertTrue(result["rom_return_confirmed"])
                self.assertEqual((device.write_count, device.read_count), (59, 115))

    def test_output_failure_bad_code_or_absent_app_sends_no_device_commands(self):
        for context in (patch.object(m, "reserve_capture", side_effect=OSError("No space")),
                        patch.object(p, "CODE", b"changed")):
            with context, patch.object(m.rom, "enumerate_target") as enumerate_mock:
                result, failed = m.run()
            self.assertTrue(failed)
            enumerate_mock.assert_not_called()
            self.assertEqual(result["sessions"], [])
        for devices in ([], [Device(m.rom.ROM_PID)], [Device(m.rom.APP_PID), Device(m.rom.APP_PID)]):
            with patch.object(m.rom, "enumerate_target", return_value=devices):
                result, failed = m.run()
            self.assertTrue(failed)
            self.assertEqual(result["sessions"], [])
            self.assertTrue(all(not device.writes for device in devices))

    def test_wrong_return_or_cleanup_never_saves_capture(self):
        for cleanup in (False, True):
            app, device = self.devices()
            if cleanup:
                def fail_attach(_):
                    raise m.rom.usb.core.USBError("Injected reattach error")
                device.attach_kernel_driver = fail_attach
            else:
                device.reads[-2] = inquiry("UDISK")
            with self.subTest(cleanup=cleanup):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["data_saved"])
                self.assertFalse(result["snapshot_confirmed"])

    def test_phase_order_rejects_source_reads_repeated_calls_and_out_of_order_chunks(self):
        _, device = self.devices()
        session = m.SnapshotSession(device, {}, {})
        session.mode, session.verified, session.paths_verified = "rom", True, True
        upload, read, call, chunks = m.commands()
        for phase, cdb in (("verified", call), ("returned", call), ("copy-first", chunks[1]),
                           ("copy-second", read), ("reading-result", chunks[0])):
            session.phase = phase
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                session._probe_transfer(cdb, 16 if cdb == call else p.SIZE)
        self.assertEqual(device.writes, [])

    def test_cli_requires_sudo_and_has_no_arbitrary_range_or_payload_options(self):
        for arguments in (("--address", "0x100000"), ("--length", "640000"), ("--payload", "x")):
            with patch.object(sys, "argv", ["snapshot", "--run-fixed-snapshot", *arguments]), \
                    patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as raised:
                m.main()
            self.assertEqual(raised.exception.code, 2)
        with patch.object(sys, "argv", ["snapshot", "--run-fixed-snapshot"]), \
                patch.object(sys, "platform", "darwin"), patch.object(m.os, "geteuid", return_value=501), \
                patch.object(m, "run") as run_mock, patch("sys.stderr", io.StringIO()), \
                self.assertRaises(SystemExit):
            m.main()
        run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
