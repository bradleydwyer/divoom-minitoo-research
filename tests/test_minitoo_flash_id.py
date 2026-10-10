"""Exercise the complete one-call flash-ID workflow using fake USB only."""
import io
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import minitoo_flash_id as m
from test_minitoo_rom_check import Device, PROBE_BYTES, inquiry, response
from test_minitoo_ram_marker import CountingDevice


def captured_block(words=None):
    block = bytearray(m.payload.make_block())
    words = words or [m.payload.COMPLETION, 0, 0, 4, 0xEF, 0x40, 0x15, 1, 2, 3, 4, 0]
    struct.pack_into("<12I", block, m.payload.RESULT_OFFSET, *words)
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
        reads += response(b"", 14)[1:]
        reads += response(m.transport.transform(m.payload.make_block()), 15)
        reads += response(b"\xfb\x08" + bytes(14), 16)
        reads += response(m.transport.transform(result if result is not None else captured_block()), 17)
        reads += response(inquiry("UBOOT1.00"), 18)
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
        self.assertEqual(result["flash_chip_transactions"], 1)
        self.assertEqual(result["sessions"][-1]["flash_id_result"]["id_bytes"], "ef4015")
        self.assertEqual(result["flash_program_erase_commands"], 0)
        self.assertEqual((device.write_count, device.read_count), (19, 35))
        self.assertEqual(self.cdbs(device)[-5:],
                         [*m.commands(), m.commands()[1], m.rom.INQUIRY.ljust(16, b"\0")])
        self.assertEqual(self.cdbs(device).count(m.commands()[2]), 1)
        self.assertTrue(app.attached and device.attached)

    def test_each_usb_failure_or_short_write_stops_at_that_transfer(self):
        for number in range(1, 36):
            app, device = self.devices()
            device.fail_read = number
            with self.subTest(read=number):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["flash_id_capture_confirmed"])
                self.assertEqual(device.read_count, number)
                self.assertTrue(device.attached)
        for short in (False, True):
            for number in range(1, 20):
                app, device = self.devices()
                device.fail_write, device.short_write = number, short
                with self.subTest(write=number, short=short):
                    result, failed = self.run_with(app, device)
                    self.assertTrue(failed)
                    self.assertFalse(result["flash_id_capture_confirmed"])
                    self.assertEqual(device.write_count, number)
                    self.assertTrue(device.attached)

    def test_initial_readback_corruption_never_calls(self):
        for offset in (0, 511, 512, 625, 626, 959, 960, 1007, 1008, 1023):
            app, device = self.devices()
            changed = bytearray(m.payload.make_block())
            changed[offset] ^= 1
            device.reads[27] = m.transport.transform(bytes(changed))
            with self.subTest(offset=offset):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["execution_attempted"])
                self.assertNotIn(m.commands()[2], self.cdbs(device))

    def test_wrong_call_response_or_status_stops_before_result_read(self):
        for index, replacement in ((29, bytes(16)), (29, b"\xfb\x08"), (30, bytes(13))):
            app, device = self.devices()
            device.reads[index] = replacement
            with self.subTest(index=index, length=len(replacement)):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["return_response_confirmed"])
                self.assertIsNone(result["flash_chip_transactions"])
                self.assertEqual(self.cdbs(device)[-1], m.commands()[2])

    def test_invalid_result_stops_before_inquiry_or_any_retry(self):
        for offset in (0, 626, 960, 1008, 1023):
            block = bytearray(captured_block())
            block[offset] ^= 1
            app, device = self.devices(bytes(block))
            with self.subTest(offset=offset):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertFalse(result["result_block_confirmed"])
                self.assertFalse(result["rom_return_confirmed"])
                self.assertEqual(self.cdbs(device)[-1], m.commands()[1])
                self.assertEqual(self.cdbs(device).count(m.commands()[2]), 1)

    def test_valid_refusal_timeout_cleanup_and_no_response_are_not_id_success(self):
        for status, count, preflight, cleanup, ident, polls in (
                (1, 0, 1, 0, [0, 0, 0], [0, 0, 0, 0]),
                (2, 1, 0, 0, [0, 0, 0], [1, 65536, 0, 0]),
                (3, 4, 0, 1, [0xEF, 0x40, 0x15], [1, 2, 3, 4]),
                (4, 4, 0, 0, [255, 255, 255], [1, 2, 3, 4])):
            block = captured_block([m.payload.COMPLETION, status, preflight, count,
                                    *ident, *polls, cleanup])
            app, device = self.devices(block)
            with self.subTest(status=status):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed)
                self.assertTrue(result["result_block_confirmed"])
                self.assertTrue(result["rom_return_confirmed"])
                self.assertFalse(result["flash_id_capture_confirmed"])
                self.assertEqual(result["flash_chip_transactions"], int(status != 1))
                self.assertEqual(self.cdbs(device).count(m.commands()[2]), 1)

    def test_bad_return_identity_or_capture_cleanup_prevents_success(self):
        for fail_cleanup in (False, True):
            app, device = self.devices()
            if fail_cleanup:
                def fail_attach(_):
                    raise m.rom.usb.core.USBError("Injected cleanup failure")
                device.attach_kernel_driver = fail_attach
            else:
                device.reads[33] = inquiry("UDISK")
            result, failed = self.run_with(app, device)
            self.assertTrue(failed)
            self.assertFalse(result["flash_id_capture_confirmed"])

    def test_review_gate_and_changed_payload_fail_before_usb(self):
        for p in (patch.object(m, "EXECUTION_REVIEWED", False),
                  patch.object(m.payload, "CODE", bytes(626))):
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
        upload, read, call = m.commands()
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
            self.assertEqual(m.plan()["flash_chip_transactions_max"], 1)
        enum.assert_not_called()
        backend.assert_not_called()
        for args in ([], ["--execute"], ["--run-fixed-id", "--plan"],
                     ["--run-fixed-id", "--file", "x"],
                     ["--run-fixed-id", "--address", "0x120000"],
                     ["--run-fixed-id", "--length", "1024"]):
            with self.subTest(args=args), patch.object(sys, "argv", ["id"] + args), \
                    patch.object(m, "run") as run, patch("sys.stderr", new_callable=io.StringIO), \
                    self.assertRaises(SystemExit) as error:
                m.main()
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()
        with patch.object(sys, "argv", ["id", "--run-fixed-id"]), \
                patch.object(sys, "platform", "darwin"), patch.object(m.os, "geteuid", return_value=501), \
                patch.object(m, "run") as run, patch("sys.stderr", new_callable=io.StringIO), \
                self.assertRaises(SystemExit):
            m.main()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
