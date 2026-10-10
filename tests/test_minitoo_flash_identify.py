"""Exercise the complete one-call flash-ID workflow using fake USB only."""
import io
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import minitoo_flash_identify as m
from test_minitoo_rom_check import Device, PROBE_BYTES, inquiry, response
from test_minitoo_ram_marker import CountingDevice


def captured_block(words=None):
    block = bytearray(m.payload.make_block())
    words = words or [m.payload.COMPLETION, 0, 0, 8, 0x85, 0x60, 0x15, *([1]*8), 0, *([0x66]*4), 4]
    words = [*words, m.payload.STACK_GUARD, *([0]*24), 0x180FB0, 0x4ABC]
    struct.pack_into("<48I", block, m.payload.RESULT_OFFSET, *words)
    return bytes(block)


class IdTests(unittest.TestCase):
    def setUp(self):
        for name in ("claim_interface", "release_interface", "dispose_resources"):
            p = patch.object(m.rom.usb.util, name)
            p.start()
            self.addCleanup(p.stop)
        for p in (patch.object(m, "EXECUTION_REVIEWED", True),
                  patch.object(m.rom.usb.backend.libusb1, "get_backend", return_value=object())):
            p.start()
            self.addCleanup(p.stop)

    def devices(self, result=None):
        gone = m.rom.usb.core.USBError("Device disconnected", errno=19)
        app = Device(m.rom.APP_PID, response(inquiry("UDISK"), 1) + [gone])
        reads = response(inquiry("UBOOT1.00"), 1)
        for number, (_, data) in enumerate((*m.rom.ROM_FINGERPRINTS, *PROBE_BYTES), 2):
            reads += response(data, number)
        for tag in (14,15):
            reads += response(b"", tag)[1:]
        for index, tag in enumerate((16,17)):
            reads += response(m.transport.transform(m.payload.make_block()[index*1024:(index+1)*1024]), tag)
        reads += response(b"\xfb\x08" + bytes(14), 18)
        for index, tag in enumerate((19,20)):
            block = result if result is not None else captured_block()
            reads += response(m.transport.transform(block[index*1024:(index+1)*1024]), tag)
        reads += response(inquiry("UBOOT1.00"), 21)
        return app, CountingDevice(reads)

    def run_with(self, app, device):
        with patch.object(m.rom, "enumerate_target", side_effect=[[app], [device]]):
            return m.run()

    def cdbs(self, device):
        return [data[15:] for data in device.writes if len(data) == 31]

    def test_complete_run_calls_once_checks_full_result_and_fresh_rom(self):
        app, device = self.devices()
        result, failed = self.run_with(app, device)
        self.assertFalse(failed, result)
        for flag in ("upload_readback_confirmed", "return_response_confirmed", "result_block_confirmed",
                     "rom_return_confirmed", "flash_id_capture_confirmed"):
            self.assertTrue(result[flag], flag)
        self.assertEqual(result["flash_chip_transactions"], 4)
        self.assertEqual(result["sessions"][-1]["flash_id_result"]["id_bytes"], "856015")
        self.assertEqual(result["flash_program_erase_commands"], 0)
        self.assertEqual((device.write_count, device.read_count), (23, 40))
        self.assertEqual(self.cdbs(device)[-8:],
                         [*m.commands()[0], *m.commands()[1], m.commands()[2],
                          *m.commands()[1], m.rom.INQUIRY.ljust(16, b"\0")])
        self.assertEqual(self.cdbs(device).count(m.commands()[2]), 1)
        self.assertTrue(app.attached and device.attached)

    def test_each_usb_failure_or_short_write_stops_at_that_transfer(self):
        for number in range(1, 41):
            app, device = self.devices()
            device.fail_read = number
            with self.subTest(read=number):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["flash_id_capture_confirmed"])
                self.assertEqual(device.read_count, number)
                self.assertTrue(device.attached)
        for short in (False, True):
            for number in range(1, 24):
                app, device = self.devices()
                device.fail_write, device.short_write = number, short
                with self.subTest(write=number, short=short):
                    result, failed = self.run_with(app, device)
                    self.assertTrue(failed)
                    self.assertFalse(result["flash_id_capture_confirmed"])
                    self.assertEqual(device.write_count, number)
                    self.assertTrue(device.attached)

    def test_initial_readback_corruption_never_calls(self):
        for offset in (0, 511, 1023, 1024, 1053, 1054, 1855, 1856, 2040, 2047):
            app, device = self.devices()
            changed = bytearray(m.payload.make_block())
            changed[offset] ^= 1
            chunk = offset // 1024
            device.reads[28 + chunk*2] = m.transport.transform(bytes(changed[chunk*1024:(chunk+1)*1024]))
            with self.subTest(offset=offset):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["execution_attempted"])
                self.assertNotIn(m.commands()[2], self.cdbs(device))

    def test_wrong_call_response_or_status_stops_before_result_read(self):
        for index, replacement in ((32, bytes(16)), (32, b"\xfb\x08"), (33, bytes(13))):
            app, device = self.devices()
            device.reads[index] = replacement
            with self.subTest(index=index, length=len(replacement)):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["return_response_confirmed"])
                self.assertIsNone(result["flash_chip_transactions"])
                self.assertEqual(self.cdbs(device)[-1], m.commands()[2])

    def test_invalid_result_stops_before_inquiry_or_any_retry(self):
        for offset in (0, 1054, 1855, 1856, 1940, 1944, 2039, 2040, 2047):
            block = bytearray(captured_block())
            block[offset] ^= 1
            app, device = self.devices(bytes(block))
            with self.subTest(offset=offset):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["result_block_confirmed"])
                self.assertFalse(result["rom_return_confirmed"])
                self.assertEqual(self.cdbs(device)[-1], m.commands()[1][-1])
                self.assertEqual(self.cdbs(device).count(m.commands()[2]), 1)

    def test_valid_refusal_timeout_cleanup_and_no_response_are_not_id_success(self):
        for status, count, preflight, cleanup, ident, polls, idle, frames in (
                (1, 0, 1, 0, [0,0,0], [0]*8, [0]*4, 0),
                (2, 1, 0, 0, [0,0,0], [1,65536,0,0,0,0,0,0], [0x66,0x66,0,0], 2),
                (3, 8, 0, 1, [0x85,0x60,0x15], [1]*8, [0x66]*4, 4),
                (4, 8, 0, 0, [255]*3, [1]*8, [0x66]*4, 4),
                (5, 3, 0, 0, [0,0,0], [1,1,1,0,0,0,0,0], [0x66,0x66,0,0], 2),
                (0, 8, 0, 0, [0xEF,0x40,0x15], [1]*8, [0x66]*4, 4)):
            block = captured_block([m.payload.COMPLETION, status, preflight, count,
                                    *ident, *polls, cleanup, *idle, frames])
            app, device = self.devices(block)
            with self.subTest(status=status):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertTrue(result["result_block_confirmed"], result)
                self.assertTrue(result["rom_return_confirmed"])
                self.assertFalse(result["flash_id_capture_confirmed"])
                self.assertEqual(result["flash_chip_transactions"], frames)
                self.assertEqual(self.cdbs(device).count(m.commands()[2]), 1)

    def test_bad_return_identity_or_capture_cleanup_prevents_success(self):
        for fail_cleanup in (False, True):
            app, device = self.devices()
            if fail_cleanup:
                def fail_attach(_):
                    raise m.rom.usb.core.USBError("Injected cleanup failure")
                device.attach_kernel_driver = fail_attach
            else:
                device.reads[38] = inquiry("UDISK")
            result, failed = self.run_with(app, device)
            self.assertTrue(failed)
            self.assertFalse(result["flash_id_capture_confirmed"])

    def test_review_gate_and_changed_payload_fail_before_usb(self):
        for p in (patch.object(m, "EXECUTION_REVIEWED", False),
                  patch.object(m.payload, "CODE", bytes(1054))):
            with p, patch.object(m.rom, "enumerate_target") as enum, \
                    patch.object(m.rom.usb.backend.libusb1, "get_backend") as backend:
                result, failed = m.run()
            self.assertTrue(failed)
            self.assertEqual(result["sessions"], [])
            enum.assert_not_called()
            backend.assert_not_called()

    def test_only_fresh_single_application_device_is_allowed(self):
        app, device = self.devices()
        for devices in ([], [device], [app, device]):
            with self.subTest(count=len(devices)), \
                    patch.object(m.rom, "enumerate_target", return_value=devices), \
                    patch.object(m, "IdSession") as session:
                result, failed = m.run()
            self.assertTrue(failed)
            self.assertEqual(result["sessions"], [])
            session.assert_not_called()

    def test_allowlist_pins_call_and_keeps_upload_only_helper_restricted(self):
        uploads, reads, call = m.commands()
        self.assertEqual(call.hex(), "fb08001200000000ffffffffffffffff")
        self.assertEqual(m.id_cbw(call, 16, 9),
                         struct.pack("<4sIIBBB16s", b"USBC", 9, 16, 0x80, 0, 16, call))
        for index in range(16):
            changed = bytearray(call)
            changed[index] ^= 1
            with self.subTest(index=index), self.assertRaises(ValueError):
                m.id_cbw(bytes(changed), 16, 9)
        for command, size, data in ((call, 1024, None), (call, 16, b"x"),
                                    (m.rom.RESET, 16, None), (m.rom.ENTER, 16, None)):
            with self.assertRaises(ValueError):
                m.id_cbw(command, size, 9, data)
        with self.assertRaises(ValueError):
            m.transport.upload_cbw(call, 16, 9)
        for index, upload in enumerate(uploads):
            encoded = m.transport.transform(m.payload.make_block()[index*1024:(index+1)*1024])
            self.assertEqual(len(m.id_cbw(upload,1024,9,encoded)),31)
            for command, size, data in ((upload,1023,encoded),
                                        (upload,1024,encoded[:-1]+bytes([encoded[-1]^1])),
                                        (upload,1024,None), (reads[index],1024,encoded)):
                with self.assertRaises(ValueError):
                    m.id_cbw(command,size,9,data)

    def test_chunk_order_and_duplicate_upload_are_rejected(self):
        _, device = self.devices()
        session = m.IdSession(device, {}, {})
        session.mode, session.verified, session.paths_verified = 'rom', True, True
        session.phase, session.cursor = 'uploading', 0
        second = m.transport.transform(m.payload.make_block()[1024:])
        with self.assertRaises(ValueError):
            session._probe_transfer(m.commands()[0][1],1024,second)
        self.assertEqual(device.writes,[])
        session.phase, session.cursor = 'uploading', 1
        first = m.transport.transform(m.payload.make_block()[:1024])
        with self.assertRaises(ValueError):
            session._probe_transfer(m.commands()[0][0],1024,first)
        self.assertEqual(device.writes,[])

    def test_session_rejects_out_of_order_call_result_and_retry(self):
        _, device = self.devices()
        session = m.IdSession(device, {}, {"execution_attempted": False})
        for method in (session.execute, session.verify_result, session.confirm_return):
            with self.assertRaises(ValueError):
                method()
        session.phase = "readback-verified"
        with self.assertRaises(ValueError):
            session.execute()  # Missing identity/fingerprint verification.
        self.assertEqual(session.phase, "failed")
        with self.assertRaises(ValueError):
            session.execute()
        self.assertEqual(device.writes, [])

    def test_plan_and_cli_inputs_cannot_access_usb(self):
        with patch.object(m.rom, "enumerate_target") as enum, \
                patch.object(m.rom.usb.backend.libusb1, "get_backend") as backend:
            self.assertEqual(m.plan()["flash_chip_transactions_max"], 4)
        enum.assert_not_called()
        backend.assert_not_called()
        for args in ([], ["--execute"], ["--run-fixed-identification", "--plan"],
                     ["--run-fixed-identification", "--file", "x"],
                     ["--run-fixed-identification", "--address", "0x120000"],
                     ["--run-fixed-identification", "--length", "1024"]):
            with self.subTest(args=args), patch.object(sys, "argv", ["id"] + args), \
                    patch.object(m, "run") as run, patch("sys.stderr", new_callable=io.StringIO), \
                    self.assertRaises(SystemExit) as error:
                m.main()
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()
        with patch.object(sys, "argv", ["id", "--run-fixed-identification"]), \
                patch.object(sys, "platform", "darwin"), patch.object(m.os, "geteuid", return_value=501), \
                patch.object(m, "run") as run, patch("sys.stderr", new_callable=io.StringIO), \
                self.assertRaises(SystemExit):
            m.main()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
