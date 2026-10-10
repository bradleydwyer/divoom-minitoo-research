"""Offline sampler instruction, bounds, wire and failure checks. No real USB."""
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import minitoo_flash_state as m
from test_minitoo_ram_marker import CountingDevice
from test_minitoo_rom_check import Device, PROBE_BYTES, inquiry, response

p = m.payload


def sample_result():
    values = [0x00000302, 0x80000, 0, 8, 0xFFFFFFF7, 0x10, 0xFFFFFFFF]
    block = bytearray(p.make_block())
    struct.pack_into("<8I", block, p.RESULT_OFFSET, p.MARKER, *values)
    return bytes(block), values


class PayloadTests(unittest.TestCase):
    def test_machine_bytes_read_only_fixed_sources_and_write_only_owned_ram(self):
        inputs = {address: 0xABCDEF00 + i for i, (_, address) in enumerate(p.SAMPLES)}
        audit = p.audit_code(p.CODE, inputs)
        self.assertEqual(audit["reads"], [0x19FC28, 0xFD6014, 0xFD1C00,
                                        0xFD5300, 0xFD5308, 0xFD5500, 0xFD5508])
        self.assertEqual(audit["writes"][-1], (0x1201D0, p.MARKER))
        self.assertTrue(all(0x1201D0 <= address < 0x1201F0 for address, _ in audit["writes"]))
        self.assertEqual(audit["instructions"], 23)
        self.assertEqual(len(p.CODE), 74)
        self.assertEqual(p.sha256(p.make_block()), p.BLOCK_SHA256)

    def test_every_changed_code_byte_and_wrong_length_is_rejected(self):
        for i in range(len(p.CODE)):
            code = bytearray(p.CODE)
            code[i] ^= 1
            with self.subTest(byte=i), self.assertRaises(ValueError):
                p.make_block(bytes(code))
        for code in (b"", p.CODE[:-1], p.CODE + b"\0"):
            with self.assertRaises(ValueError):
                p.make_block(code)

    def test_result_dynamic_words_decode_without_claiming_wiring(self):
        result, values = sample_result()
        decoded = p.decode_result(result)
        self.assertEqual(list(decoded["raw_values"].values()), [f"0x{x:08x}" for x in values])
        self.assertTrue(decoded["shadow_matches_group_bit"])
        changed = bytearray(result)
        struct.pack_into("<I", changed, p.RESULT_OFFSET + 4, 0x00010000)
        self.assertFalse(p.decode_result(changed)["shadow_matches_group_bit"])

    def test_every_byte_outside_dynamic_samples_must_match(self):
        result, _ = sample_result()
        for i in range(p.SIZE):
            if p.RESULT_OFFSET + 4 <= i < p.RESULT_OFFSET + 32:
                continue
            changed = bytearray(result)
            changed[i] ^= 1
            with self.subTest(byte=i), self.assertRaises(ValueError):
                p.decode_result(bytes(changed))
        for data in (result[:-1], result + b"\0", p.make_block()):
            with self.assertRaises(ValueError):
                p.decode_result(data)

    def test_wire_allowlist_rejects_every_changed_cdb_byte_and_other_payload(self):
        commands = m.commands()
        self.assertEqual(commands[0].hex(), "fb0600120000020000cb4fffffffffff")
        self.assertEqual(commands[1].hex(), "fd07001200000200ffffffffffffffff")
        self.assertEqual(commands[2].hex(), "fb08001200000000ffffffffffffffff")
        for cdb in commands:
            size, data = ((512, m.marker.transform_block(p.make_block()))
                          if cdb == commands[0] else (512 if cdb == commands[1] else 16, None))
            framed = struct.unpack("<4sIIBBB16s", m.snapshot_cbw(cdb, size, 7, data))
            self.assertEqual(framed[2:6], (size, 0 if data else 0x80, 0, 16))
            for i in range(16):
                changed = bytearray(cdb)
                changed[i] ^= 1
                with self.subTest(byte=i, cdb=cdb.hex()), self.assertRaises(ValueError):
                    m.snapshot_cbw(bytes(changed), size, 7, data)
            with self.assertRaises(ValueError):
                m.snapshot_cbw(cdb, size - 1, 7, data)
        with self.assertRaises(ValueError):
            m.snapshot_cbw(commands[0], 512, 7, m.marker.transform_block(m.marker.fixed_block()))

    def test_plan_never_enumerates_or_opens_backend(self):
        with patch.object(m.rom, "enumerate_target") as enumerate_mock, \
                patch.object(m.rom.usb.backend.libusb1, "get_backend") as backend_mock:
            plan = m.plan()
        enumerate_mock.assert_not_called()
        backend_mock.assert_not_called()
        self.assertEqual(plan["flash_commands"], 0)
        self.assertEqual(plan["payload_peripheral_writes"], 0)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        for name in ("claim_interface", "release_interface", "dispose_resources"):
            mock = patch.object(m.rom.usb.util, name)
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch.object(m.rom.usb.backend.libusb1, "get_backend", return_value=object())
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
        reads += response(m.marker.transform_block(p.make_block()), number + 1)
        reads += response(b"\xfb\x08" + bytes(14), number + 2)
        reads += response(m.marker.transform_block(sample_result()[0]), number + 3)
        reads += response(inquiry("UBOOT1.00"), number + 4)
        return app, CountingDevice(reads)

    def run_with(self, app, device, execute=True):
        with patch.object(m.rom, "enumerate_target", side_effect=[[app], [device]]):
            return m.run(execute=execute)

    def test_complete_sequence_and_no_other_payload_or_call(self):
        app, device = self.devices()
        result, failed = self.run_with(app, device)
        self.assertFalse(failed, result)
        self.assertTrue(result["snapshot_confirmed"])
        self.assertTrue(result["rom_return_confirmed"])
        self.assertEqual(device.read_count, 35)
        self.assertEqual(device.write_count, 19)
        self.assertEqual(device.reads, [])
        self.assertTrue(app.attached and device.attached)
        cdbs = [w[15:] for w in device.writes if len(w) == 31]
        self.assertEqual(cdbs[-5:], [m.commands()[0], m.commands()[1], m.commands()[2],
                                     m.commands()[1], m.rom.INQUIRY.ljust(16, b"\0")])
        self.assertNotIn(m.rom.RESET, cdbs)
        self.assertEqual([w for w in device.writes if len(w) != 31],
                         [m.marker.transform_block(p.make_block())])

    def test_upload_only_never_calls_or_claims_snapshot(self):
        app, device = self.devices()
        result, failed = self.run_with(app, device, execute=False)
        self.assertFalse(failed, result)
        self.assertTrue(result["upload_readback_confirmed"])
        self.assertFalse(result["execution_attempted"])
        self.assertFalse(result["snapshot_confirmed"])
        self.assertEqual((device.read_count, device.write_count), (29, 16))

    def test_every_read_exception_or_short_read_stops_immediately(self):
        for short in (False, True):
            for n in range(1, 36):
                app, device = self.devices()
                if short:
                    device.reads[n - 1] = device.reads[n - 1][:-1]
                else:
                    device.fail_read = n
                with self.subTest(short=short, read=n):
                    result, failed = self.run_with(app, device)
                    self.assertTrue(failed, result)
                    self.assertFalse(result["snapshot_confirmed"])
                    self.assertEqual(device.read_count, n)
                    self.assertTrue(device.attached)
                    if n <= 29:
                        self.assertFalse(result["execution_attempted"])

    def test_every_write_exception_or_short_write_stops_immediately(self):
        for short in (False, True):
            for n in range(1, 20):
                app, device = self.devices()
                device.fail_write, device.short_write = n, short
                with self.subTest(short=short, write=n):
                    result, failed = self.run_with(app, device)
                    self.assertTrue(failed, result)
                    self.assertFalse(result["snapshot_confirmed"])
                    self.assertEqual(device.write_count, n)
                    self.assertTrue(device.attached)
                    if n <= 16:
                        self.assertFalse(result["execution_attempted"])

    def test_bad_upload_prevents_call_and_bad_result_prevents_final_identity(self):
        for index, offset in ((27, 0), (27, 0x1D0), (31, 0), (31, 0x1D0), (31, 511)):
            app, device = self.devices()
            data = bytearray(p.make_block() if index == 27 else sample_result()[0])
            data[offset] ^= 1
            device.reads[index] = m.marker.transform_block(bytes(data))
            with self.subTest(index=index, offset=offset):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed, result)
                self.assertFalse(result["snapshot_confirmed"])
                if index == 27:
                    self.assertFalse(result["execution_attempted"])

    def test_bad_identity_call_response_or_cleanup_cannot_claim_success(self):
        for fault in ("app", "rom", "call", "return", "cleanup"):
            app, device = self.devices()
            if fault == "app":
                app.reads[0] = inquiry("OTHER")
            elif fault == "rom":
                device.reads[0] = inquiry("OTHER")
            elif fault == "call":
                device.reads[29] = bytes(16)
            elif fault == "return":
                device.reads[33] = inquiry("OTHER")
            else:
                device.attach_kernel_driver = lambda _: (_ for _ in ()).throw(
                    m.rom.usb.core.USBError("Injected cleanup failure"))
            with self.subTest(fault=fault):
                result, failed = self.run_with(app, device)
                self.assertTrue(failed, result)
                self.assertFalse(result["snapshot_confirmed"])

    def test_missing_already_rom_multiple_or_changed_payload_open_no_session(self):
        app, device = self.devices()
        for devices in ([], [device], [app, device]):
            with patch.object(m.rom, "enumerate_target", return_value=devices):
                result, failed = m.run(execute=True)
            self.assertTrue(failed)
            self.assertEqual(result["sessions"], [])
        with patch.object(p, "CODE", bytes(74)), patch.object(m.rom, "enumerate_target") as mock:
            result, failed = m.run(execute=True)
        self.assertTrue(failed)
        mock.assert_not_called()

    def test_state_guards_and_failure_prevent_retry(self):
        _, device = self.devices()
        session = m.SnapshotSession(device, {}, {"ram_uploads_attempted": 0})
        for action in (session.upload, session.verify_upload, session.execute,
                       session.verify_result, session.confirm_return):
            with self.assertRaises(ValueError):
                action()
        session.phase = "verified"
        with self.assertRaises(ValueError):
            session.upload()
        self.assertEqual(session.phase, "failed")
        with self.assertRaises(ValueError):
            session.upload()
        self.assertEqual(device.writes, [])
        for cdb in (m.rom.ENTER, m.rom.RESET):
            with self.assertRaises(ValueError):
                session._command(cdb, 16)

    def test_cli_rejects_conflicting_actions_and_arbitrary_arguments_before_usb(self):
        for args in ([], ["--plan", "--run-fixed-snapshot"], ["--address", "0xfd1c00"],
                     ["--run-fixed-snapshot", "--file", "other.bin"]):
            with patch.object(sys, "argv", ["snapshot", *args]), \
                    patch.object(m.rom, "enumerate_target") as mock, \
                    patch.object(sys, "stderr"), self.assertRaises(SystemExit):
                m.main()
            mock.assert_not_called()

    def test_macos_privilege_guard_prevents_device_action(self):
        with patch.object(sys, "argv", ["snapshot", "--run-fixed-snapshot"]), \
                patch.object(sys, "platform", "darwin"), patch.object(m.os, "geteuid", return_value=501), \
                patch.object(m, "run") as mock, patch.object(sys, "stderr"), \
                self.assertRaises(SystemExit):
            m.main()
        mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
