"""Hardware-free checks for the bounded BR28 entry/exit workflow."""
import struct
import sys
import unittest
import io
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import minitoo_rom_check as m

ROOT = Path(__file__).resolve().parents[1]
PROBE_FIXTURE = json.loads((ROOT / "tests/fixtures/br28-probe-rom-regions.json").read_text())
PROBE_BYTES = tuple((int(row["address"], 16), bytes.fromhex(row["hex"]))
                    for row in PROBE_FIXTURE["regions"])


def inquiry(product):
    return bytes(8) + b"BR28    " + product.encode().ljust(16, b" ") + b"1.00"


def response(data, number):
    return [data, struct.pack("<4sIIB", b"USBS", 0x4D540100 + number, 0, 0)]


class Endpoint:
    bmAttributes = 2

    def __init__(self, address):
        self.bEndpointAddress = address


class Interface(list):
    bInterfaceClass, bInterfaceSubClass, bInterfaceProtocol = 8, 6, 0x50


class Device:
    idVendor = m.VID
    bus = 1
    port_numbers = (1,)

    def __init__(self, pid, reads=()):
        self.idProduct = pid
        self.reads = list(reads)
        self.writes = []
        self.detached = self.attached = False
        self.interface = Interface([Endpoint(0x81), Endpoint(2)])

    def is_kernel_driver_active(self, interface):
        return True

    def detach_kernel_driver(self, interface):
        self.detached = True

    def attach_kernel_driver(self, interface):
        self.attached = True

    def get_active_configuration(self):
        return {(0, 0): self.interface}

    def write(self, endpoint, data, timeout):
        assert endpoint == 2
        self.writes.append(bytes(data))
        return len(data)

    def read(self, endpoint, size, timeout):
        assert endpoint == 0x81
        value = self.reads.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class ProtocolTests(unittest.TestCase):
    def session(self, device):
        s = m.Session(device, {})
        s.incoming, s.outgoing = 0x81, 2
        return s

    def test_exact_entry_and_reset_wire_vectors(self):
        self.assertEqual(m.cbw(m.ENTER, 16, 0x4D540102).hex(),
                         "555342430201544d10000000800010fc0a" + "ff" * 14)
        self.assertEqual(m.RESET.hex(), "fb080001fdf40000ffffffffffffffff")
        self.assertEqual(m.rom_read_cdb(0x1FDF0, 8).hex(),
                         "fd070001fdf00008ffffffffffffffff")

    def test_other_commands_and_read_ranges_rejected(self):
        for cdb in [b"\xfb\x04" + bytes(14), b"\xfb\x06" + bytes(14),
                    b"\xfb\x02" + bytes(14), b"\xfc\x12" + bytes(14),
                    b"\xfd\x05" + bytes(14)]:
            with self.subTest(cdb=cdb.hex()), self.assertRaises(ValueError):
                m.cbw(cdb, 16, 1)
        for address, size in [(0x100000, 8), (0xFD0000, 8), (0x1FDF0, 9)]:
            with self.subTest(address=address), self.assertRaises(ValueError):
                m.rom_read_cdb(address, size)
        with self.assertRaises(ValueError):
            m.cbw(m.INQUIRY, 37, 1)

    def test_probe_fingerprints_match_pinned_rom_fixture_and_review_manifest(self):
        manifest = json.loads((ROOT / "tests/fixtures/core-rom-regions.json").read_text())
        self.assertEqual(PROBE_FIXTURE["rom_sha256"], manifest["rom_sha256"])
        actual = tuple((address, len(data), hashlib.sha256(data).hexdigest())
                       for address, data in PROBE_BYTES)
        reviewed = tuple((int(row["address"], 16), row["bytes"], row["sha256"])
                         for row in manifest["regions"])
        self.assertEqual(actual, reviewed)
        self.assertEqual(actual, m.PROBE_ROM_FINGERPRINTS)
        self.assertEqual(sum(size for _, size, _ in actual), 804)

    def test_extended_rom_reads_are_exact_and_remain_device_to_host(self):
        for address, size, _ in m.PROBE_ROM_FINGERPRINTS:
            with self.subTest(address=address):
                cdb = m.rom_read_cdb(address, size)
                self.assertEqual(cdb[:8], b"\xfd\x07" + struct.pack(">IH", address, size))
                fields = struct.unpack("<4sIIBBB16s", m.cbw(cdb, size, 1))
                self.assertEqual(fields[2:6], (size, 0x80, 0, 16))
                for bad_size in (size - 1, size + 1):
                    with self.assertRaises(ValueError):
                        m.rom_read_cdb(address, bad_size)
                with self.assertRaises(ValueError):
                    m.rom_read_cdb(address + 1, size)

    def test_status_corruption_rejected(self):
        for value in [(b"BAD!", 1, 0, 0), (b"USBS", 2, 0, 0),
                      (b"USBS", 1, 1, 0), (b"USBS", 1, 0, 1),
                      (b"USBS", 1, 0, 2)]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.check_csw(struct.pack("<4sIIB", *value), 1)
        with self.assertRaises(ValueError):
            m.check_csw(bytes(12), 1)

    def test_no_vendor_command_before_identity(self):
        d = Device(m.APP_PID)
        s = self.session(d)
        for command in [m.ENTER, m.RESET, m.rom_read_cdb(0x1FDF0, 8)]:
            with self.subTest(command=command.hex()), self.assertRaises(ValueError):
                s._command(command, 8 if command[:2] == b"\xfd\x07" else 16)
        self.assertEqual(d.writes, [])

    def test_wrong_identity_stops_before_entry(self):
        d = Device(m.APP_PID, response(inquiry("OTHER"), 1))
        s = self.session(d)
        with self.assertRaises(ValueError):
            s.identify("app")
        with self.assertRaises(ValueError):
            s.transition("enter")
        self.assertEqual(len(d.writes), 1)

    def test_one_wrong_rom_fingerprint_blocks_reset(self):
        d = Device(m.ROM_PID, response(inquiry("UBOOT1.00"), 1) +
                   response(bytes(8), 2))
        s = self.session(d)
        s.identify("rom")
        with self.assertRaises(ValueError):
            s.verify_rom()
        with self.assertRaises(ValueError):
            s.transition("reset")
        self.assertEqual(len(d.writes), 2)
        self.assertNotIn(m.RESET, [w[15:] for w in d.writes])

    def test_short_and_stale_replies_block_identification(self):
        replies = [[bytes(35)], [inquiry("UDISK"), b"USBS" + bytes(9)]]
        for reads in replies:
            d = Device(m.APP_PID, reads)
            s = self.session(d)
            with self.subTest(reads=reads), self.assertRaises(ValueError):
                s.identify("app")
            self.assertIsNone(s.mode)

    def test_port_and_device_count_guards(self):
        d = Device(m.ROM_PID)
        with self.assertRaises(ValueError):
            m.select([d, Device(m.APP_PID)], m.ROM_PID)
        with self.assertRaises(ValueError):
            m.select([d], m.ROM_PID, (1, (2,)))
        d.port_numbers = ()
        with self.assertRaises(ValueError):
            m.select([d], m.ROM_PID)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        p = patch.object(m.sys, "stderr", io.StringIO())
        p.start()
        self.addCleanup(p.stop)
        for name in ("claim_interface", "release_interface", "dispose_resources"):
            p = patch.object(m.usb.util, name)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(m.usb.backend.libusb1, "get_backend", return_value=object())
        p.start()
        self.addCleanup(p.stop)

    def devices(self, probe_check=False):
        gone = m.usb.core.USBError("Device disconnected", errno=19)
        app = Device(m.APP_PID, response(inquiry("UDISK"), 1) + [gone])
        reads = response(inquiry("UBOOT1.00"), 1)
        for number, (_, expected) in enumerate(m.ROM_FINGERPRINTS, 2):
            reads += response(expected, number)
        if probe_check:
            for number, (_, data) in enumerate(PROBE_BYTES, 2 + len(m.ROM_FINGERPRINTS)):
                reads += response(data, number)
        rom = Device(m.ROM_PID, reads + [gone])
        returned = Device(m.APP_PID, response(inquiry("UDISK"), 1))
        return app, rom, returned

    def test_entry_exit_success_only_after_final_inquiry(self):
        app, rom, returned = self.devices()
        with patch.object(m, "enumerate_target", side_effect=[[app], [rom], [returned]]):
            result, failed = m.run()
        self.assertFalse(failed, result)
        self.assertTrue(result["entry_confirmed"])
        self.assertTrue(result["application_return_confirmed"])
        commands = [w[15:17].hex() for d in (app, rom, returned) for w in d.writes]
        self.assertEqual(commands, ["1200", "fc0a", "1200", "fd07", "fd07",
                                    "fd07", "fd07", "fb08", "1200"])
        for d in (app, rom, returned):
            self.assertTrue(d.attached)
            self.assertEqual(d.reads, [])
            self.assertTrue(all(len(w) == 31 and w[12] == 0x80 for w in d.writes))

    def test_entry_timeout_never_retries_or_sends_reset(self):
        app, _, _ = self.devices()
        with patch.object(m, "enumerate_target", return_value=[app]), \
                patch.object(m, "wait_for", side_effect=ValueError("timeout")):
            result, failed = m.run()
        self.assertTrue(failed)
        self.assertFalse(result["entry_confirmed"])
        self.assertFalse(result["application_return_confirmed"])
        self.assertEqual(len(app.writes), 2)
        self.assertTrue(app.attached)

    def test_enter_verify_releases_capture_without_reset_or_return_wait(self):
        app, rom, _ = self.devices()
        rom.reads.pop()  # No reset/disconnect response should be consumed.
        with patch.object(m, "enumerate_target", side_effect=[[app], [rom]]):
            result, failed = m.run(enter_verify=True)
        self.assertFalse(failed, result)
        self.assertEqual(result["action"], "enter-verify")
        self.assertTrue(result["entry_confirmed"])
        self.assertTrue(result["rom_fingerprints_confirmed"])
        self.assertFalse(result["rom_reset_attempted"])
        self.assertFalse(result["application_return_confirmed"])
        commands = [w[15:17].hex() for d in (app, rom) for w in d.writes]
        self.assertEqual(commands, ["1200", "fc0a", "1200", "fd07", "fd07",
                                    "fd07", "fd07"])
        self.assertTrue(rom.attached)
        self.assertEqual(rom.reads, [])

    def test_enter_verify_fingerprint_mismatch_stops_without_reset(self):
        app, rom, _ = self.devices()
        rom.reads[2] = bytes(8)
        with patch.object(m, "enumerate_target", side_effect=[[app], [rom]]):
            result, failed = m.run(enter_verify=True)
        self.assertTrue(failed)
        self.assertTrue(result["entry_confirmed"])
        self.assertFalse(result["rom_fingerprints_confirmed"])
        self.assertFalse(result["rom_reset_attempted"])
        self.assertEqual(len(rom.writes), 2)
        self.assertTrue(rom.attached)

    def test_probe_check_matches_twelve_excerpts_without_upload_call_or_reset(self):
        app, rom, _ = self.devices(probe_check=True)
        rom.reads.pop()
        with patch.object(m, "enumerate_target", side_effect=[[app], [rom]]):
            result, failed = m.run(probe_check=True)
        self.assertFalse(failed, result)
        self.assertEqual(result["action"], "enter-probe-check")
        self.assertTrue(result["rom_fingerprints_confirmed"])
        self.assertTrue(result["probe_rom_fingerprints_confirmed"])
        self.assertFalse(result["rom_reset_attempted"])
        self.assertFalse(result["application_return_confirmed"])
        self.assertEqual(len(rom.writes), 13)  # INQUIRY + 4 existing + 8 additional
        self.assertEqual(len(result["sessions"][1]["probe_rom_fingerprints"]), 8)
        self.assertEqual(rom.reads, [])
        self.assertTrue(rom.attached)
        self.assertEqual([w[15:17].hex() for w in rom.writes], ["1200"] + ["fd07"] * 12)
        self.assertTrue(all(len(w) == 31 and w[12] == 0x80 for w in app.writes + rom.writes))

    def test_probe_mismatch_stops_at_first_failure_and_releases_capture(self):
        for index in (0, 7):
            app, rom, _ = self.devices(probe_check=True)
            data_index = (1 + len(m.ROM_FINGERPRINTS) + index) * 2
            altered = bytearray(rom.reads[data_index])
            altered[0] ^= 1
            rom.reads[data_index] = bytes(altered)
            with self.subTest(index=index), \
                    patch.object(m, "enumerate_target", side_effect=[[app], [rom]]):
                result, failed = m.run(probe_check=True)
            self.assertTrue(failed)
            self.assertFalse(result["probe_rom_fingerprints_confirmed"])
            self.assertFalse(result["rom_reset_attempted"])
            self.assertEqual(len(rom.writes), 6 + index)
            self.assertTrue(rom.attached)
            self.assertIn("Probe-path ROM fingerprint differs", result["error"])

    def test_probe_short_reply_or_bad_status_stops_without_retry(self):
        for bad_status in (False, True):
            app, rom, _ = self.devices(probe_check=True)
            data_index = (1 + len(m.ROM_FINGERPRINTS)) * 2
            if bad_status:
                rom.reads[data_index + 1] = struct.pack("<4sIIB", b"USBS", 0, 0, 0)
            else:
                rom.reads[data_index] = rom.reads[data_index][:-1]
            with self.subTest(bad_status=bad_status), \
                    patch.object(m, "enumerate_target", side_effect=[[app], [rom]]):
                result, failed = m.run(probe_check=True)
            self.assertTrue(failed)
            self.assertFalse(result["probe_rom_fingerprints_confirmed"])
            self.assertFalse(result["rom_reset_attempted"])
            self.assertEqual(len(rom.writes), 6)
            self.assertTrue(rom.attached)

    def test_enter_verify_cleanup_error_is_not_success(self):
        app, rom, _ = self.devices()
        rom.attach_kernel_driver = lambda _: (_ for _ in ()).throw(
            m.usb.core.USBError("reattach failed"))
        with patch.object(m, "enumerate_target", side_effect=[[app], [rom]]):
            result, failed = m.run(enter_verify=True)
        self.assertTrue(failed)
        self.assertTrue(result["rom_fingerprints_confirmed"])
        self.assertFalse(result["rom_reset_attempted"])
        self.assertIn("cleanup", result["error"].lower())

    def test_conflicting_actions_rejected_before_device_access(self):
        for kwargs in ({"exit_only": True, "enter_verify": True},
                       {"exit_only": True, "probe_check": True},
                       {"enter_verify": True, "probe_check": True}):
            with self.subTest(kwargs=kwargs), patch.object(m, "enumerate_target") as enumerate_mock:
                result, failed = m.run(**kwargs)
            self.assertTrue(failed)
            enumerate_mock.assert_not_called()
            self.assertEqual(result["sessions"], [])

    def test_absent_device_does_not_imply_rom_entry_or_open_session(self):
        for kwargs in ({}, {"enter_verify": True}, {"exit_only": True}, {"probe_check": True}):
            with self.subTest(kwargs=kwargs), \
                    patch.object(m, "enumerate_target", return_value=[]), \
                    patch.object(m, "Session") as session_mock:
                result, failed = m.run(**kwargs)
            self.assertTrue(failed)
            session_mock.assert_not_called()
            self.assertEqual(result["sessions"], [])
            self.assertFalse(result["entry_confirmed"])
            self.assertIn("not found", result["error"])
            self.assertNotIn("--exit-rom", result["error"])
            self.assertIn("no protocol commands", result["note"])
            self.assertNotIn("may remain in ROM", result["note"])

    def test_wrong_initial_mode_is_reported_without_commands(self):
        cases = [(m.ROM_PID, {"enter_verify": True}, "ROM USB PID"),
                 (m.APP_PID, {"exit_only": True}, "Application USB PID")]
        for pid, kwargs, expected_error in cases:
            device = Device(pid)
            with self.subTest(pid=pid), \
                    patch.object(m, "enumerate_target", return_value=[device]), \
                    patch.object(m, "Session") as session_mock:
                result, failed = m.run(**kwargs)
            self.assertTrue(failed)
            session_mock.assert_not_called()
            self.assertEqual(device.writes, [])
            self.assertIn(expected_error, result["error"])
            self.assertIn("no protocol commands", result["note"])

    def test_wrong_initial_identity_reports_no_transition_after_inquiry(self):
        app = Device(m.APP_PID, response(inquiry("OTHER"), 1))
        with patch.object(m, "enumerate_target", return_value=[app]):
            result, failed = m.run(enter_verify=True)
        self.assertTrue(failed)
        self.assertEqual(len(app.writes), 1)
        self.assertIn("no entry/reset command", result["note"])
        self.assertNotIn("no protocol commands", result["note"])

    def test_exit_only_does_not_send_entry(self):
        _, rom, returned = self.devices()
        with patch.object(m, "enumerate_target", side_effect=[[rom], [returned]]):
            result, failed = m.run(exit_only=True)
        self.assertFalse(failed, result)
        self.assertNotIn(m.ENTER, [w[15:] for w in rom.writes])

    def test_no_usb_return_after_rom_reset_preserves_partial_success(self):
        app, rom, _ = self.devices()
        with patch.object(m, "enumerate_target", return_value=[app]), \
                patch.object(m, "wait_for", side_effect=[rom, ValueError("timeout")]):
            result, failed = m.run()
        self.assertTrue(failed)
        self.assertTrue(result["entry_confirmed"])
        self.assertTrue(result["rom_reset_attempted"])
        self.assertFalse(result["application_return_confirmed"])
        self.assertIn("normal power-on", result["note"])
        self.assertEqual(len(rom.writes), 6)

    def test_wrong_return_identity_is_not_success(self):
        app, rom, returned = self.devices()
        returned.reads = response(inquiry("OTHER"), 1)
        with patch.object(m, "enumerate_target", side_effect=[[app], [rom], [returned]]):
            result, failed = m.run()
        self.assertTrue(failed)
        self.assertFalse(result["application_return_confirmed"])
        self.assertTrue(returned.attached)

    def test_failed_claim_restores_detached_drivers(self):
        app, _, _ = self.devices()
        with patch.object(m, "enumerate_target", return_value=[app]), \
                patch.object(m.usb.util, "claim_interface",
                             side_effect=m.usb.core.USBError("claim failed")):
            result, failed = m.run()
        self.assertTrue(failed)
        self.assertTrue(app.attached)
        self.assertEqual(app.writes, [])

    def test_wrong_interface_restores_drivers_without_commands(self):
        app, _, _ = self.devices()
        app.interface.bInterfaceClass = 3
        with patch.object(m, "enumerate_target", return_value=[app]):
            result, failed = m.run()
        self.assertTrue(failed)
        self.assertTrue(app.attached)
        self.assertEqual(app.writes, [])

    def test_cleanup_error_after_final_inquiry_is_not_success(self):
        app, rom, returned = self.devices()
        returned.attach_kernel_driver = lambda _: (_ for _ in ()).throw(
            m.usb.core.USBError("reattach failed"))
        with patch.object(m, "enumerate_target", side_effect=[[app], [rom], [returned]]):
            result, failed = m.run()
        self.assertTrue(failed)
        self.assertFalse(result["application_return_confirmed"])
        self.assertIn("cleanup", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
