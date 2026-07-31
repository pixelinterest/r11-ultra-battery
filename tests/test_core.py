"""Unit tests for protocol parsing, icons, and startup path safety."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from r11_battery import protocol as proto
from r11_battery.device import BatteryReading
from r11_battery.icons import (
    CHARGING_COLOR_DARK,
    ICON_FONT_SIZE,
    make_icon,
)
from r11_battery.startup import (
    clear_stale_startup,
    launch_command,
    project_root,
)
from r11_battery.tray import TrayApp


def _frame(
    percent: int,
    wired: int = 0,
    voltage_mv: int = 0,
    *,
    bad_checksum: bool = False,
) -> list[int]:
    buf = [0] * proto.REPORT_LEN
    buf[0] = proto.REPORT_ID
    buf[1] = proto.SUBCOMMAND_BATTERY
    buf[proto.PERCENT_OFFSET] = percent
    buf[proto.WIRED_FLAG_OFFSET] = wired
    buf[proto.VOLTAGE_MSB_OFFSET] = (voltage_mv >> 8) & 0xFF
    buf[proto.VOLTAGE_LSB_OFFSET] = voltage_mv & 0xFF
    buf[16] = (proto.CHECKSUM_MOD - (sum(buf[:16]) % 256)) % 256
    if bad_checksum:
        buf[16] = (buf[16] + 1) % 256
    assert len(buf) == proto.REPORT_LEN
    return buf


class ProtocolTests(unittest.TestCase):
    def test_request_checksum(self) -> None:
        req = proto.battery_request()
        self.assertIsInstance(req, bytes)
        self.assertEqual(len(req), proto.REPORT_LEN)
        self.assertTrue(proto.checksum_ok(req))
        self.assertEqual(req, proto.battery_request())  # stable singleton

    def test_parse_wireless_full(self) -> None:
        data = proto.parse_battery_response(_frame(100, wired=0, voltage_mv=4193))
        self.assertIsNotNone(data)
        assert data is not None
        self.assertEqual(data.percent, 100)
        self.assertFalse(data.wired)
        self.assertFalse(data.charging)
        self.assertEqual(data.voltage_mv, 4193)

    def test_parse_charging(self) -> None:
        data = proto.parse_battery_response(_frame(95, wired=1, voltage_mv=4100))
        self.assertIsNotNone(data)
        assert data is not None
        self.assertEqual(data.percent, 95)
        self.assertTrue(data.wired)
        self.assertTrue(data.charging)

    def test_parse_wired_full_not_charging(self) -> None:
        data = proto.parse_battery_response(_frame(100, wired=1))
        self.assertIsNotNone(data)
        assert data is not None
        self.assertFalse(data.charging)

    def test_rejects_bad_checksum(self) -> None:
        self.assertIsNone(proto.parse_battery_response(_frame(80, bad_checksum=True)))

    def test_rejects_bad_percent(self) -> None:
        buf = _frame(50)
        buf[proto.PERCENT_OFFSET] = 150
        buf[16] = (proto.CHECKSUM_MOD - (sum(buf[:16]) % 256)) % 256
        self.assertIsNone(proto.parse_battery_response(buf))

    def test_rejects_wrong_report(self) -> None:
        buf = _frame(50)
        buf[0] = 0x09
        buf[16] = (proto.CHECKSUM_MOD - (sum(buf[:16]) % 256)) % 256
        self.assertIsNone(proto.parse_battery_response(buf))

    def test_rejects_short_and_none(self) -> None:
        self.assertIsNone(proto.parse_battery_response(None))
        self.assertIsNone(proto.parse_battery_response([1, 2, 3]))


class IconTests(unittest.TestCase):
    def test_font_size_constant_in_range(self) -> None:
        self.assertGreaterEqual(ICON_FONT_SIZE, 28)
        self.assertLessEqual(ICON_FONT_SIZE, 40)

    def test_make_icon_sizes_consistent(self) -> None:
        a = BatteryReading(95, True, True, 4100, 0x3554, 0xFB43, "x")
        b = BatteryReading(100, False, False, 4193, 0x3554, 0xFB44, "y")
        img_a = make_icon(a)
        img_b = make_icon(b)
        img_none = make_icon(None)
        self.assertEqual(img_a.size, (64, 64))
        self.assertEqual(img_b.size, (64, 64))
        self.assertEqual(img_none.size, (64, 64))
        self.assertEqual(img_a.mode, "RGBA")

    def test_charging_uses_configured_color(self) -> None:
        reading = BatteryReading(95, True, True, None, 0x3554, 0xFB43, "")
        with mock.patch("r11_battery.icons._is_light_mode", return_value=False):
            img = make_icon(reading)
        # Spot-check that some opaque pixel matches the dark charging color.
        found = False
        for y in range(img.height):
            for x in range(img.width):
                r, g, b, a = img.getpixel((x, y))
                if a > 200 and (r, g, b) == CHARGING_COLOR_DARK:
                    found = True
                    break
            if found:
                break
        self.assertTrue(found)


class StartupSafetyTests(unittest.TestCase):
    def test_project_root_is_repo(self) -> None:
        root = project_root()
        self.assertTrue((root / "main.py").is_file() or (root / "main.pyw").is_file())

    def test_launch_command_quotes_and_stays_in_root(self) -> None:
        if getattr(sys, "frozen", False):
            self.skipTest("frozen")
        cmd = launch_command()
        self.assertTrue(cmd.startswith('"'))
        self.assertIn("main.py", cmd)
        root = str(project_root().resolve())
        self.assertIn(root, cmd.replace("/", "\\"))
        # No shell metacharacters that would expand outside quotes.
        self.assertNotIn("&", cmd)
        self.assertNotIn("|", cmd)
        self.assertNotIn(";", cmd)

    def test_clear_stale_startup_removes_other_install(self) -> None:
        with mock.patch(
            "r11_battery.startup.get_startup_command",
            return_value=r'"C:\Old\R11UltraBattery.exe"',
        ):
            with mock.patch(
                "r11_battery.startup.launch_command",
                return_value=r'"C:\New\R11UltraBattery.exe"',
            ):
                with mock.patch(
                    "r11_battery.startup.set_startup",
                    return_value=True,
                ) as set_startup:
                    self.assertTrue(clear_stale_startup())
                    set_startup.assert_called_once_with(False)

    def test_clear_stale_startup_keeps_matching_install(self) -> None:
        cmd = r'"C:\Apps\R11UltraBattery.exe"'
        with mock.patch("r11_battery.startup.get_startup_command", return_value=cmd):
            with mock.patch("r11_battery.startup.launch_command", return_value=cmd):
                with mock.patch("r11_battery.startup.set_startup") as set_startup:
                    self.assertFalse(clear_stale_startup())
                    set_startup.assert_not_called()


class TrayDisplayTests(unittest.TestCase):
    def test_skip_redundant_ui_updates(self) -> None:
        reading = BatteryReading(100, False, False, None, 0x3554, 0xFB44, "")
        with mock.patch("r11_battery.tray.make_icon", return_value=mock.Mock()) as make:
            with mock.patch("r11_battery.tray.pystray.Icon") as icon_cls:
                icon = mock.Mock()
                icon_cls.return_value = icon
                app = TrayApp(poll_interval=999)
                after_init = make.call_count
                app._apply_display(reading, stale=False)
                self.assertEqual(make.call_count, after_init + 1)
                app._apply_display(reading, stale=False)
                self.assertEqual(make.call_count, after_init + 1)
                # Stale only changes title/menu text, not icon pixels.
                app._apply_display(reading, stale=True)
                self.assertEqual(make.call_count, after_init + 1)
                self.assertEqual(icon.update_menu.call_count, 2)

    def test_menu_not_reassigned_on_update(self) -> None:
        reading = BatteryReading(50, False, False, None, 0x3554, 0xFB44, "")
        with mock.patch("r11_battery.tray.make_icon", return_value=mock.Mock()):
            with mock.patch("r11_battery.tray.pystray.Icon") as icon_cls:
                icon = mock.Mock()
                icon_cls.return_value = icon
                app = TrayApp(poll_interval=999)
                icon.reset_mock()
                app._apply_display(reading, stale=False)
                self.assertTrue(icon.update_menu.called)
                # Reassigning .menu rebuilds HMENU twice; we only call update_menu.
                self.assertEqual(
                    [c for c in icon.mock_calls if c[0] == "menu"],
                    [],
                )


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
