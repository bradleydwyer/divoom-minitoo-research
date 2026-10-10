"""Offline wire/state/failure checks; no MiniToo commands are sent."""
import io
import json
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import minitoo_ram_marker as m
import build_minitoo_ram_probe as builder
from test_minitoo_rom_check import Device, PROBE_BYTES, inquiry, response


class WireTests(unittest.TestCase):
    def test_crc_known_check_and_pinned_payload(self):
        self.assertEqual(m.crc16(b"123456789"), 0x31C3)
        self.assertEqual(m.crc16(b"123456789", 0xFFFF), 0x29B1)
        self.assertEqual(m.fixed_block(), builder.make_block(builder.CODE))
        after = m.result_block()
        self.assertEqual(after[:m.RESULT_OFFSET], m.fixed_block()[:m.RESULT_OFFSET])
        self.assertEqual(after[m.RESULT_OFFSET:m.RESULT_OFFSET + 4], b"KOTM")
        self.assertEqual(after[m.RESULT_OFFSET + 4:], bytes(12))

    def test_cipher_known_vector_and_involution(self):
        # Golden stream independently obtained from the pinned community cipher;
        # see the offline cross-check recorded in docs/usb-and-ram.md.
        golden = bytes.fromhex("2fa481cc4ec15deaeea2b6a6298ad4f70384ebe1cf8a8a14bde6dd1cd0f8463b")
        self.assertEqual(m.transform_block(bytes(512))[:len(golden)], golden)
        encrypted = m.transform_block(m.fixed_block())
        self.assertNotEqual(encrypted, m.fixed_block())
        self.assertEqual(m.transform_block(encrypted), m.fixed_block())
        for length in (0, 16, 511, 513, 1024):
            with self.subTest(length=length), self.assertRaises(ValueError):
                m.transform_block(bytes(length))

    def test_exact_wire_vectors(self):
        upload, read, call = m.commands()
        self.assertEqual(upload.hex(), "fb0600120000020000b2e4ffffffffff")
        self.assertEqual(read.hex(), "fd07001200000200ffffffffffffffff")
        self.assertEqual(call.hex(), "fb08001200000000ffffffffffffffff")
        for cdb, length, payload, direction in (
                (upload, 512, m.transform_block(m.fixed_block()), 0),
                (read, 512, None, 0x80), (call, 16, None, 0x80)):
            with self.subTest(cdb=cdb.hex()):
                value = struct.unpack("<4sIIBBB16s", m.probe_cbw(cdb, length, 7, payload))
                self.assertEqual(value, (b"USBC", 7, length, direction, 0, 16, cdb))

    def test_no_other_address_length_payload_or_command_can_be_framed(self):
        upload, read, call = m.commands()
        encrypted = m.transform_block(m.fixed_block())
        bad_payload = bytearray(encrypted)
        bad_payload[0] ^= 1
        cases = [(upload, 512, bytes(bad_payload)), (upload, 512, encrypted[:-1]),
                 (upload, 512, encrypted + b"\0"), (upload, 512, None),
                 (read, 511, None), (read, 513, None), (read, 512, encrypted),
                 (call, 512, None), (m.rom.RESET, 16, None),
                 (b"\xfb\x04" + upload[2:], 512, encrypted)]
        for cdb in (upload, read, call):
            for offset in range(16):
                altered = bytearray(cdb)
                altered[offset] ^= 1
                cases.append((bytes(altered), 512 if cdb != call else 16,
                              encrypted if cdb == upload else None))
        for cdb, size, data in cases:
            with self.subTest(cdb=cdb.hex(), size=size), self.assertRaises(ValueError):
                m.probe_cbw(cdb, size, 7, data)

    def test_plan_never_accesses_usb(self):
        with patch.object(m.rom, "enumerate_target") as enumerate_mock, \
                patch.object(m.rom.usb.backend.libusb1, "get_backend") as backend_mock:
            value = m.plan()
        enumerate_mock.assert_not_called()
        backend_mock.assert_not_called()
        self.assertEqual(value["flash_commands"], 0)
        self.assertEqual(value["retries"], 0)


class CountingDevice(Device):
    def __init__(self, reads):
        super().__init__(m.rom.ROM_PID, reads)
        self.read_count = 0
        self.write_count = 0
        self.fail_read = self.fail_write = None
        self.short_write = False

    def write(self, endpoint, data, timeout):
        self.write_count += 1
        count = super().write(endpoint, data, timeout)
        if self.write_count == self.fail_write:
            if self.short_write:
                return count - 1
            raise m.rom.usb.core.USBError("Injected write failure", errno=5)
        return count

    def read(self, endpoint, size, timeout):
        self.read_count += 1
        if self.read_count == self.fail_read:
            raise m.rom.usb.core.USBError("Injected read failure", errno=5)
        return super().read(endpoint, size, timeout)


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
        number = 2
        for _, data in m.rom.ROM_FINGERPRINTS:
            reads += response(data, number)
            number += 1
        for _, data in PROBE_BYTES:
            reads += response(data, number)
            number += 1
        reads += response(b"", number)[1:]  # Upload has CSW only.
        number += 1
        reads += response(m.transform_block(m.fixed_block()), number)
        number += 1
        reads += response(b"\xfb\x08" + bytes(14), number)
        number += 1
        reads += response(m.transform_block(m.result_block()), number)
        number += 1
        reads += response(inquiry("UBOOT1.00"), number)
        return app, CountingDevice(reads)

    def run_with(self, app, device):
        with patch.object(m.rom, "enumerate_target", side_effect=[[app], [device]]):
            return m.run(execute=True)

    def test_roundtrip_stops_after_readback_without_any_execution_call(self):
        app, device = self.devices()
        with patch.object(m.rom, "enumerate_target", side_effect=[[app], [device]]):
            result, failed = m.run()  # The function default also excludes execution.
        self.assertFalse(failed, result)
        self.assertEqual(result["action"], "roundtrip-only")
        self.assertTrue(result["upload_readback_confirmed"])
        self.assertFalse(result["execution_attempted"])
        self.assertFalse(result["custom_code_confirmed"])
        self.assertEqual(device.write_count, 16)
        self.assertNotIn(m.commands()[2], [w[15:] for w in device.writes if len(w) == 31])
        self.assertTrue(device.attached)
        self.assertEqual(device.read_count, 29)

    def test_complete_sequence_requires_marker_and_fresh_identity(self):
        app, device = self.devices()
        result, failed = self.run_with(app, device)
        self.assertFalse(failed, result)
        for field in ("rom_fingerprints_confirmed", "upload_readback_confirmed",
                      "execution_attempted", "return_response_confirmed",
                      "marker_confirmed", "rom_return_confirmed", "custom_code_confirmed"):
            self.assertTrue(result[field], field)
        self.assertEqual(result["ram_uploads_attempted"], 1)
        self.assertEqual(device.reads, [])
        self.assertTrue(app.attached and device.attached)
        payloads = [w for w in device.writes if len(w) != 31]
        self.assertEqual(payloads, [m.transform_block(m.fixed_block())])
        cdbs = [w[15:] for w in device.writes if len(w) == 31]
        self.assertEqual(cdbs[-5:], [m.commands()[0], m.commands()[1], m.commands()[2],
                                     m.commands()[1], m.rom.INQUIRY.ljust(16, b"\0")])
        self.assertNotIn(m.rom.RESET, cdbs)

    def test_every_rom_read_failure_stops_immediately_without_retry(self):
        for failed_read in range(1, 36):
            app, device = self.devices()
            device.fail_read = failed_read
            with self.subTest(failed_read=failed_read):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed, result)
                self.assertFalse(result["custom_code_confirmed"])
                self.assertEqual(device.read_count, failed_read)
                self.assertTrue(device.attached)
                self.assertLessEqual(result["ram_uploads_attempted"], 1)
                if failed_read <= 29:  # Up to upload-readback CSW, before call.
                    self.assertFalse(result["execution_attempted"])

    def test_every_rom_write_failure_or_short_write_stops_without_retry(self):
        for short in (False, True):
            for failed_write in range(1, 20):
                app, device = self.devices()
                device.fail_write = failed_write
                device.short_write = short
                with self.subTest(short=short, failed_write=failed_write):
                    result, failed = self.run_with(app, device)
                    self.assertTrue(failed, result)
                    self.assertFalse(result["custom_code_confirmed"])
                    self.assertEqual(device.write_count, failed_write)
                    self.assertTrue(device.attached)
                    if failed_write <= 16:  # Includes upload payload/readback CBW.
                        self.assertFalse(result["execution_attempted"])

    def test_bad_upload_readback_blocks_call_even_with_valid_status(self):
        for offset in (0, 15, 16, 0x1F0, 511):
            app, device = self.devices()
            changed = bytearray(m.fixed_block())
            changed[offset] ^= 1
            device.reads[27] = m.transform_block(bytes(changed))
            with self.subTest(offset=offset):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["execution_attempted"])
                self.assertEqual(device.write_count, 16)

    def test_bad_call_response_or_status_stops_before_result_read(self):
        for bad_status in (False, True):
            app, device = self.devices()
            device.reads[30 if bad_status else 29] = (
                struct.pack("<4sIIB", b"USBS", 0, 0, 0) if bad_status else bytes(16))
            with self.subTest(bad_status=bad_status):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertTrue(result["execution_attempted"])
                self.assertFalse(result["return_response_confirmed"])
                self.assertFalse(result["marker_confirmed"])
                self.assertEqual(device.write_count, 17)

    def test_wrong_marker_or_change_outside_marker_is_not_success(self):
        for offset in (0, 16, 0x1F0, 511):
            app, device = self.devices()
            data = bytearray(m.result_block())
            data[offset] ^= 1
            device.reads[31] = m.transform_block(bytes(data))
            with self.subTest(offset=offset):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["marker_confirmed"])
                self.assertFalse(result["custom_code_confirmed"])
                self.assertEqual(device.write_count, 18)

    def test_wrong_fresh_identity_or_cleanup_error_is_not_success(self):
        for cleanup in (False, True):
            app, device = self.devices()
            if cleanup:
                device.attach_kernel_driver = lambda _: (_ for _ in ()).throw(
                    m.rom.usb.core.USBError("Injected cleanup failure"))
            else:
                device.reads[33] = inquiry("OTHER")
            with self.subTest(cleanup=cleanup):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertTrue(result["marker_confirmed"])
                self.assertFalse(result["custom_code_confirmed"])

    def test_already_rom_absent_or_multiple_devices_open_no_session(self):
        app, device = self.devices()
        for devices in ([], [device], [app, device]):
            with self.subTest(count=len(devices)), \
                    patch.object(m.rom, "enumerate_target", return_value=devices), \
                    patch.object(m, "ProbeSession") as session_mock:
                result, failed = m.run(execute=True)
            self.assertTrue(failed)
            self.assertEqual(result["sessions"], [])
            session_mock.assert_not_called()

    def test_wrong_application_or_rom_identity_prevents_upload(self):
        for wrong_app in (False, True):
            app, device = self.devices()
            (app if wrong_app else device).reads[0] = inquiry("OTHER")
            with self.subTest(wrong_app=wrong_app):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertEqual(result["ram_uploads_attempted"], 0)
                self.assertFalse(result["execution_attempted"])
                if wrong_app:
                    self.assertEqual(len(app.writes), 1)

    def test_state_guards_and_poisoned_session_prevent_second_attempt(self):
        _, device = self.devices()
        session = m.ProbeSession(device, {}, {"ram_uploads_attempted": 0})
        for action in (session.upload, session.verify_upload, session.execute,
                       session.verify_result, session.confirm_return):
            with self.subTest(action=action.__name__), self.assertRaises(ValueError):
                action()
        session.phase = "verified"
        with self.assertRaises(ValueError):  # No ROM identity/fingerprints.
            session.upload()
        self.assertEqual(session.phase, "failed")
        with self.assertRaises(ValueError):
            session.upload()
        self.assertEqual(device.writes, [])
        for cdb in (m.rom.ENTER, m.rom.RESET):
            with self.assertRaises(ValueError):
                session._command(cdb, 16)

    def test_changed_program_fails_before_enumerating(self):
        with patch.object(m, "CODE", bytes(16)), \
                patch.object(m.rom, "enumerate_target") as enumerate_mock:
            result, failed = m.run(execute=True)
        self.assertTrue(failed)
        enumerate_mock.assert_not_called()
        self.assertEqual(result["sessions"], [])


if __name__ == "__main__":
    unittest.main()
