"""Offline bounds and USB failure checks for the separate bus-state sampler."""
import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import minitoo_flash_state as m
from test_minitoo_ram_marker import CountingDevice
from test_minitoo_rom_check import Device, PROBE_BYTES, inquiry, response

p = m.bus_payload


def result_block():
    values = [0x84000300, 24000000, 48000000, 0, 0x8000, 0, 0, 0,
              0x321, 0x30, 0x643, 0x10, 0x6F, 0, 0, 0, 0, 0x1FF]
    data = bytearray(p.make_block())
    struct.pack_into("<19I", data, p.RESULT_OFFSET, p.MARKER, *values)
    return bytes(data)


class BusPayloadTests(unittest.TestCase):
    def test_machine_bytes_read_exact_fixed_registers_and_write_only_owned_ram(self):
        expected = [0x19FC28, 0x19FC2C, 0x19FC30, 0xFD6014, 0xFD1C00,
                    0xFE0200, 0xFE0218, 0xFD4100, 0xFD0014, 0xFD0018,
                    0xFD001C, 0xFD5300, 0xFD5308, 0xFD530C, 0xFD5310,
                    0xFD5314, 0xFD5500, 0xFD5508]
        for pattern in (0, 0xFFFFFFFF, 0x12345678):
            inputs = {a: (pattern ^ i) for i, a in enumerate(expected)}
            audit = p.audit_code(p.CODE, inputs)
            self.assertEqual(audit["reads"], expected)
            self.assertEqual(audit["instructions"], 49)
            self.assertEqual(audit["writes"],
                             [(0x1201B4 + i * 4, inputs[a]) for i, a in enumerate(expected)]
                             + [(0x1201B0, 0x4D544253)])
        self.assertEqual(len(p.CODE), 140)
        self.assertEqual(p.sha256(p.make_block()), p.BLOCK_SHA256)

    def test_mutated_code_and_result_bounds_fail_closed(self):
        for i in range(len(p.CODE)):
            code = bytearray(p.CODE)
            code[i] ^= 1
            with self.subTest(code_byte=i), self.assertRaises(ValueError):
                p.make_block(bytes(code))
        data = result_block()
        for i in range(p.SIZE):
            if p.RESULT_OFFSET + 4 <= i < p.RESULT_OFFSET + p.RESULT_BYTES:
                continue
            changed = bytearray(data)
            changed[i] ^= 1
            with self.subTest(result_byte=i), self.assertRaises(ValueError):
                p.decode_result(bytes(changed))
        for changed in (data[:-1], data + b"\0", p.make_block()):
            with self.assertRaises(ValueError):
                p.decode_result(changed)

    def test_independent_mux_and_clock_fields_are_not_conflated(self):
        for spi_group in (0, 1):
            for sfc_group in (0, 1):
                data = bytearray(result_block())
                struct.pack_into("<I", data, p.RESULT_OFFSET + 16,
                                 spi_group << 14 | sfc_group << 16 | 1 << 13)
                decoded = p.decode_result(bytes(data))
                self.assertEqual(decoded["spi0_group_bit14"], spi_group)
                self.assertEqual(decoded["sfc_group_bit16"], sfc_group)
                self.assertEqual(decoded["spi0_crossbar_bit13"], 1)
                self.assertFalse(decoded["spi0_enabled"])
                self.assertFalse(decoded["sfc_enabled"])
        self.assertEqual(decoded["clock_fields"], {"hsb_divider_field": 0x21,
                         "lsb_divider_field": 3, "sfc_divider_field": 0,
                         "main_clock_selector": 6})

    def test_wire_allowlist_rejects_mutations_and_cross_profile_uploads(self):
        commands = m.bus_commands()
        self.assertEqual(commands[0].hex(), "fb0600120000020000c80cffffffffff")
        encoded = m.marker.transform_block(p.make_block())
        for cdb in commands:
            length, data = ((512, encoded) if cdb == commands[0] else
                            (512 if cdb == commands[1] else 16, None))
            m.snapshot_cbw(cdb, length, 1, data, bus_state=True)
            for i in range(16):
                changed = bytearray(cdb)
                changed[i] ^= 1
                with self.subTest(cdb=cdb.hex(), byte=i), self.assertRaises(ValueError):
                    m.snapshot_cbw(bytes(changed), length, 1, data, bus_state=True)
            with self.assertRaises(ValueError):
                m.snapshot_cbw(cdb, length - 1, 1, data, bus_state=True)
        with self.assertRaises(ValueError):
            m.snapshot_cbw(commands[0], 512, 1, encoded)
        with self.assertRaises(ValueError):
            m.snapshot_cbw(m.commands()[0], 512, 1,
                           m.marker.transform_block(m.payload.make_block()), bus_state=True)
        with self.assertRaises(ValueError):
            m.snapshot_cbw(commands[0], 512, 1,
                           m.marker.transform_block(m.payload.make_block()), bus_state=True)

    def test_reported_snapshots_reconstruct_complete_result_hashes(self):
        fixture = Path(__file__).parent / "fixtures/register-snapshot-results.json"
        snapshots = json.loads(fixture.read_text())
        for filename, profile in (("usb-flash-state-reported.json", m.payload),
                                  ("usb-flash-bus-state-reported.json", p)):
            with self.subTest(report=filename):
                report = snapshots[filename]
                session = report
                values = session["snapshot"]["raw_values"]
                data = bytearray(profile.make_block())
                struct.pack_into(f"<{len(profile.SAMPLES) + 1}I", data,
                                 profile.RESULT_OFFSET, profile.MARKER,
                                 *(int(values[name], 16) for name, _ in profile.SAMPLES))
                self.assertEqual(hashlib.sha256(data).hexdigest(), session["result_readback_sha256"])
                self.assertEqual(profile.decode_result(bytes(data)), session["snapshot"])
                self.assertEqual(profile.BLOCK_SHA256, session["upload_readback_sha256"])
                self.assertTrue(report["snapshot_confirmed"])
                self.assertTrue(report["rom_return_confirmed"])


class BusWorkflowTests(unittest.TestCase):
    def setUp(self):
        for name in ("claim_interface", "release_interface", "dispose_resources"):
            mocked = patch.object(m.rom.usb.util, name)
            mocked.start()
            self.addCleanup(mocked.stop)
        mocked = patch.object(m.rom.usb.backend.libusb1, "get_backend", return_value=object())
        mocked.start()
        self.addCleanup(mocked.stop)

    def devices(self):
        gone = m.rom.usb.core.USBError("Device disconnected", errno=19)
        app = Device(m.rom.APP_PID, response(inquiry("UDISK"), 1) + [gone])
        reads = response(inquiry("UBOOT1.00"), 1)
        for number, (_, data) in enumerate((*m.rom.ROM_FINGERPRINTS, *PROBE_BYTES), 2):
            reads += response(data, number)
        reads += response(b"", 14)[1:]
        reads += response(m.marker.transform_block(p.make_block()), 15)
        reads += response(b"\xfb\x08" + bytes(14), 16)
        reads += response(m.marker.transform_block(result_block()), 17)
        reads += response(inquiry("UBOOT1.00"), 18)
        return app, CountingDevice(reads)

    def run_with(self, app, device, execute=True):
        with patch.object(m.rom, "enumerate_target", side_effect=[[app], [device]]):
            return m.run(execute=execute, bus_state=True)

    def test_one_bus_upload_one_call_return_and_cleanup(self):
        app, device = self.devices()
        result, failed = self.run_with(app, device)
        self.assertFalse(failed, result)
        self.assertTrue(result["snapshot_confirmed"])
        self.assertEqual(result["action"], "run-fixed-bus-snapshot")
        self.assertTrue(result["rom_return_confirmed"])
        self.assertTrue(app.attached and device.attached)
        self.assertEqual((device.read_count, device.write_count), (35, 19))
        self.assertEqual(device.reads, [])
        self.assertEqual([w for w in device.writes if len(w) != 31],
                         [m.marker.transform_block(p.make_block())])
        self.assertEqual([w[15:] for w in device.writes if len(w) == 31][-5:],
                         [*m.bus_commands(), m.bus_commands()[1], m.rom.INQUIRY.ljust(16, b"\0")])

    def test_upload_only_cannot_claim_execution_or_snapshot(self):
        result, failed = self.run_with(*self.devices(), execute=False)
        self.assertFalse(failed, result)
        self.assertTrue(result["upload_readback_confirmed"])
        self.assertFalse(result["execution_attempted"])
        self.assertFalse(result["snapshot_confirmed"])

    def test_every_read_and_write_failure_stops_without_retry(self):
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

    def test_wrong_upload_result_identity_or_cleanup_cannot_claim_success(self):
        for fault in ("upload", "result", "call", "return", "cleanup"):
            app, device = self.devices()
            if fault in ("upload", "result"):
                index = 27 if fault == "upload" else 31
                data = bytearray(p.make_block() if fault == "upload" else result_block())
                data[p.RESULT_OFFSET] ^= 1
                device.reads[index] = m.marker.transform_block(bytes(data))
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
                if fault == "upload":
                    self.assertFalse(result["execution_attempted"])

    def test_wrong_mode_changed_program_or_unverified_session_sends_nothing(self):
        app, device = self.devices()
        for devices in ([], [device], [app, device]):
            with patch.object(m.rom, "enumerate_target", return_value=devices):
                result, failed = m.run(execute=True, bus_state=True)
            self.assertTrue(failed)
            self.assertEqual(result["sessions"], [])
        with patch.object(p, "CODE", bytes(140)), patch.object(m.rom, "enumerate_target") as mocked:
            result, failed = m.run(execute=True, bus_state=True)
        self.assertTrue(failed)
        mocked.assert_not_called()
        session = m.BusStateSession(device, {}, {"ram_uploads_attempted": 0})
        for method in (session.upload, session.verify_upload, session.execute, session.verify_result):
            with self.assertRaises(ValueError):
                method()
        self.assertEqual(device.writes, [])

    def test_plan_and_cli_guards_precede_device_access(self):
        with patch.object(m.rom, "enumerate_target") as enumerate_mock, \
                patch.object(m.rom.usb.backend.libusb1, "get_backend") as backend_mock:
            self.assertEqual(m.plan(bus_state=True)["instructions"], 49)
        enumerate_mock.assert_not_called()
        backend_mock.assert_not_called()
        for args in (["--run-fixed-bus-snapshot", "--run-fixed-snapshot"],
                     ["--bus-plan", "--run-fixed-bus-snapshot"],
                     ["--run-fixed-bus-snapshot", "--file", "other.bin"]):
            with patch.object(sys, "argv", ["snapshot", *args]), \
                    patch.object(m.rom, "enumerate_target") as mocked, \
                    patch.object(sys, "stderr"), self.assertRaises(SystemExit):
                m.main()
            mocked.assert_not_called()
        with patch.object(sys, "argv", ["snapshot", "--run-fixed-bus-snapshot"]), \
                patch.object(sys, "platform", "darwin"), patch.object(m.os, "geteuid", return_value=501), \
                patch.object(m, "run") as mocked, patch.object(sys, "stderr"), \
                self.assertRaises(SystemExit):
            m.main()
        mocked.assert_not_called()

    def test_cli_selects_only_the_named_fixed_program_and_execution_mode(self):
        for option, execute, bus_state in (("--run-fixed-bus-snapshot", True, True),
                                           ("--bus-roundtrip-only", False, True),
                                           ("--run-fixed-snapshot", True, False),
                                           ("--roundtrip-only", False, False)):
            with self.subTest(option=option), \
                    patch.object(sys, "argv", ["snapshot", option]), \
                    patch.object(m.os, "geteuid", return_value=0), \
                    patch.object(m, "run", return_value=({}, False)) as run_mock, \
                    patch("builtins.print"), self.assertRaises(SystemExit) as stopped:
                m.main()
            self.assertEqual(stopped.exception.code, 0)
            run_mock.assert_called_once_with(execute=execute, bus_state=bus_state)
        with patch.object(sys, "argv", ["snapshot", "--bus-plan"]), \
                patch.object(m.os, "geteuid", return_value=501), \
                patch.object(m.rom.usb.backend.libusb1, "get_backend") as backend_mock, \
                patch("builtins.print") as print_mock:
            m.main()
        backend_mock.assert_not_called()
        self.assertEqual(json.loads(print_mock.call_args.args[0])["snapshot_kind"], "bus-state")


if __name__ == "__main__":
    unittest.main()
