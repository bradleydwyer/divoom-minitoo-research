"""Fixed 1 KiB upload/readback checks using fake USB devices only."""
import io
import json
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import minitoo_flash_id_upload as m
from test_minitoo_rom_check import Device, PROBE_BYTES, inquiry, response
from test_minitoo_ram_marker import CountingDevice


class WireTests(unittest.TestCase):
    def test_fixed_layout_and_every_changed_code_byte_is_rejected(self):
        p = m.payload
        block = p.make_block()
        self.assertEqual((p.ADDRESS, len(block), p.RESULT_OFFSET, p.RESULT_BYTES),
                         (0x120000, 1024, 0x3C0, 48))
        self.assertEqual(block[:626], p.CODE)
        self.assertEqual(block[626:], bytes(398))
        self.assertEqual(p.sha256(block), p.BLOCK_SHA256)
        for offset in range(len(p.CODE)):
            changed = bytearray(p.CODE)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                p.make_block(bytes(changed))
        for code in (p.CODE[:-1], p.CODE + b"\0", bytes(1024)):
            with self.assertRaises(ValueError):
                p.make_block(code)
        for name in ("ADDRESS", "SIZE", "RESULT_OFFSET", "RESULT_BYTES"):
            with self.subTest(constant=name), patch.object(p, name, getattr(p, name) + 4), \
                    self.assertRaises(ValueError):
                p.make_block()

    def test_continuous_cipher_matches_independent_community_golden(self):
        # Independently cross-checked with jltech.cipher.jl_crc_cipher + crcmod.
        # In particular, the stream must NOT restart at offset 512.
        stream = m.transform(bytes(1024))
        self.assertEqual(m.payload.sha256(stream),
                         "c9cadabb752ac65f85d2b68d6a8a7e9450b2fe0fd2e8d84249dff73a4a03354e")
        self.assertEqual(stream[496:528].hex(),
                         "4665827eb091c61ac3d0dd89e3fd3650f0a9fad9b09c2f169860b4c21218f53d")
        self.assertNotEqual(stream[:512], stream[512:])
        block = m.payload.make_block()
        self.assertEqual(m.transform(m.transform(block)), block)
        self.assertEqual(m.payload.sha256(m.transform(block)),
                         "83067e0ee9fbaf3b44588ea8180456eb7380e001f58d8b78a74c71ed9d6324bb")
        for length in (0, 512, 1023, 1025):
            with self.subTest(length=length), self.assertRaises(ValueError):
                m.transform(bytes(length))
        # Expanding this helper must not broaden the earlier 512-byte helper.
        with self.assertRaises(ValueError):
            m.marker.transform_block(block)

    def test_exact_wire_vectors_and_no_execution_command(self):
        upload, read = m.commands()
        self.assertEqual(upload.hex(), "fb060012000004000035f6ffffffffff")
        self.assertEqual(read.hex(), "fd07001200000400ffffffffffffffff")
        for cdb, data, direction in ((upload, m.transform(m.payload.make_block()), 0),
                                     (read, None, 0x80)):
            fields = struct.unpack("<4sIIBBB16s", m.upload_cbw(cdb, 1024, 7, data))
            self.assertEqual(fields, (b"USBC", 7, 1024, direction, 0, 16, cdb))
            for offset in range(16):
                changed = bytearray(cdb)
                changed[offset] ^= 1
                with self.subTest(offset=offset), self.assertRaises(ValueError):
                    m.upload_cbw(bytes(changed), 1024, 7, data)
        for cdb in (m.marker.commands()[2], m.rom.RESET, m.rom.ENTER):
            with self.assertRaises(ValueError):
                m.upload_cbw(cdb, 16, 7)
        for size in (0, 512, 1023, 1025):
            with self.assertRaises(ValueError):
                m.upload_cbw(read, size, 7)
        for data in (None, bytes(1024), m.transform(m.payload.make_block())[:-1]):
            with self.assertRaises(ValueError):
                m.upload_cbw(upload, 1024, 7, data)

    def test_plan_has_no_usb_access(self):
        with patch.object(m.rom, "enumerate_target") as enumerate_mock, \
                patch.object(m.rom.usb.backend.libusb1, "get_backend") as backend_mock:
            value = m.plan()
        enumerate_mock.assert_not_called()
        backend_mock.assert_not_called()
        self.assertFalse(value["execution_supported"])
        self.assertEqual(value["flash_chip_transactions"], 0)

    def test_cli_has_no_execution_file_address_or_length_option(self):
        for args in ([], ["--run-fixed-probe"], ["--execute"],
                     ["--roundtrip-only", "--plan"],
                     ["--roundtrip-only", "--file", "x"],
                     ["--roundtrip-only", "--address", "0x120000"],
                     ["--roundtrip-only", "--length", "1024"]):
            with self.subTest(args=args), patch.object(sys, "argv", ["upload"] + args), \
                    patch.object(m, "run") as run_mock, \
                    patch("sys.stderr", new_callable=io.StringIO), \
                    self.assertRaises(SystemExit) as error:
                m.main()
            self.assertEqual(error.exception.code, 2)
            run_mock.assert_not_called()

    def test_macos_privilege_guard_precedes_usb(self):
        with patch.object(sys, "argv", ["upload", "--roundtrip-only"]), \
                patch.object(sys, "platform", "darwin"), \
                patch.object(m.os, "geteuid", return_value=501), \
                patch.object(m, "run") as run_mock, \
                patch("sys.stderr", new_callable=io.StringIO), \
                self.assertRaises(SystemExit):
            m.main()
        run_mock.assert_not_called()


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        for name in ("claim_interface", "release_interface", "dispose_resources"):
            p = patch.object(m.rom.usb.util, name)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(m.rom.usb.backend.libusb1, "get_backend", return_value=object())
        p.start()
        self.addCleanup(p.stop)

    def devices(self):
        gone = m.rom.usb.core.USBError("Device disconnected", errno=19)
        app = Device(m.rom.APP_PID, response(inquiry("UDISK"), 1) + [gone])
        reads = response(inquiry("UBOOT1.00"), 1)
        for number, (_, data) in enumerate((*m.rom.ROM_FINGERPRINTS, *PROBE_BYTES), 2):
            reads += response(data, number)
        reads += response(b"", 14)[1:]
        reads += response(m.transform(m.payload.make_block()), 15)
        return app, CountingDevice(reads)

    def run_with(self, app, device):
        with patch.object(m.rom, "enumerate_target", side_effect=[[app], [device]]):
            result = m.run()
        cdbs = [w[15:] for w in device.writes if len(w) == 31]
        self.assertFalse(any(cdb.startswith(b"\xfb\x08") for cdb in cdbs))
        self.assertFalse(result[0]["execution_attempted"])
        return result

    def test_complete_roundtrip_has_only_one_upload_and_one_readback(self):
        app, device = self.devices()
        result, failed = self.run_with(app, device)
        self.assertFalse(failed, result)
        self.assertTrue(result["roundtrip_confirmed"])
        self.assertTrue(result["upload_readback_confirmed"])
        self.assertEqual(result["ram_uploads_attempted"], 1)
        self.assertEqual(device.reads, [])
        self.assertEqual((device.write_count, device.read_count), (16, 29))
        self.assertEqual([w for w in device.writes if len(w) != 31],
                         [m.transform(m.payload.make_block())])
        self.assertEqual([w[15:] for w in device.writes if len(w) == 31][-2:],
                         list(m.commands()))
        self.assertTrue(app.attached and device.attached)

    def test_every_read_failure_stops_immediately(self):
        for number in range(1, 30):
            app, device = self.devices()
            device.fail_read = number
            with self.subTest(number=number):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["roundtrip_confirmed"])
                self.assertEqual(device.read_count, number)
                self.assertTrue(device.attached)

    def test_every_write_failure_or_short_write_stops_immediately(self):
        for short in (False, True):
            for number in range(1, 17):
                app, device = self.devices()
                device.fail_write, device.short_write = number, short
                with self.subTest(number=number, short=short):
                    result, failed = self.run_with(app, device)
                    self.assertTrue(failed)
                    self.assertFalse(result["roundtrip_confirmed"])
                    self.assertEqual(device.write_count, number)
                    self.assertTrue(device.attached)

    def test_code_padding_and_result_readback_changes_are_all_rejected(self):
        for offset in (0, 511, 512, 625, 626, 959, 960, 1007, 1008, 1023):
            app, device = self.devices()
            changed = bytearray(m.payload.make_block())
            changed[offset] ^= 1
            device.reads[27] = m.transform(bytes(changed))
            with self.subTest(offset=offset):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["upload_readback_confirmed"])
                self.assertEqual((device.write_count, device.read_count), (16, 29))

    def test_short_readback_or_invalid_upload_readback_status_is_not_success(self):
        for index, replacement in ((27, bytes(1023)), (26, bytes(13)), (28, bytes(13))):
            app, device = self.devices()
            device.reads[index] = replacement
            with self.subTest(index=index):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["upload_readback_confirmed"])
                self.assertFalse(result["roundtrip_confirmed"])
                self.assertLessEqual(device.read_count, index + 1)

    def test_wrong_identity_and_each_fingerprint_prevent_upload(self):
        for index in range(0, 26, 2):
            app, device = self.devices()
            device.reads[index] = bytes(len(device.reads[index]))
            with self.subTest(index=index):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertEqual(result["ram_uploads_attempted"], 0)
        app, device = self.devices()
        app.reads[0] = inquiry("OTHER")
        result, failed = self.run_with(app, device)
        self.assertTrue(failed)
        self.assertEqual(len(app.writes), 1)
        self.assertEqual(device.writes, [])

    def test_cleanup_error_cannot_report_complete_success(self):
        app, device = self.devices()
        def fail_attach(_):
            raise m.rom.usb.core.USBError("Injected cleanup failure")
        device.attach_kernel_driver = fail_attach
        result, failed = self.run_with(app, device)
        self.assertTrue(failed)
        self.assertTrue(result["upload_readback_confirmed"])
        self.assertFalse(result["roundtrip_confirmed"])

    def test_absent_rom_or_multiple_devices_open_no_session(self):
        app, device = self.devices()
        for devices in ([], [device], [app, device]):
            with self.subTest(devices=devices), \
                    patch.object(m.rom, "enumerate_target", return_value=devices), \
                    patch.object(m, "UploadSession") as session_mock:
                result, failed = m.run()
            self.assertTrue(failed)
            self.assertEqual(result["sessions"], [])
            session_mock.assert_not_called()

    def test_changed_program_fails_before_backend_or_enumeration(self):
        with patch.object(m.payload, "CODE", bytes(626)), \
                patch.object(m.rom, "enumerate_target") as enumerate_mock, \
                patch.object(m.rom.usb.backend.libusb1, "get_backend") as backend_mock:
            result, failed = m.run()
        self.assertTrue(failed)
        self.assertEqual(result["sessions"], [])
        enumerate_mock.assert_not_called()
        backend_mock.assert_not_called()

    def test_session_rejects_execution_out_of_order_and_retries(self):
        _, device = self.devices()
        session = m.UploadSession(device, {}, {"ram_uploads_attempted": 0})
        for action in (session.upload, session.verify_upload, session.execute, session.verify_result):
            with self.subTest(action=action.__name__), self.assertRaises(ValueError):
                action()
        session.phase = "verified"
        with self.assertRaises(ValueError):
            session.upload()  # No identity/fingerprint verification.
        self.assertEqual(session.phase, "failed")
        with self.assertRaises(ValueError):
            session.upload()
        session.mode, session.verified, session.paths_verified = "rom", True, True
        session.phase = "calling"
        with self.assertRaises(ValueError):
            session._probe_transfer(m.marker.commands()[2], 16)
        for cdb in (m.rom.RESET, m.rom.ENTER):
            with self.assertRaises(ValueError):
                session._command(cdb, 16)
        self.assertEqual(device.writes, [])


if __name__ == "__main__":
    unittest.main()
