"""Compx / Nordic 52840 battery HID protocol constants."""

from __future__ import annotations

from typing import NamedTuple

VID = 0x3554
PID_WIRELESS = 0xFB44
PID_WIRED = 0xFB43

USAGE_PAGE = 0xFF02
USAGE = 0x0002

REPORT_ID = 0x08
SUBCOMMAND_BATTERY = 0x04
REPORT_LEN = 17
CHECKSUM_MOD = 0x55

PERCENT_OFFSET = 6
WIRED_FLAG_OFFSET = 7
VOLTAGE_MSB_OFFSET = 8
VOLTAGE_LSB_OFFSET = 9

POLL_INTERVAL_SEC = 30.0
STALE_READING_SEC = 300.0
TRANSACTION_DELAY_SEC = 0.1

# Fixed request: report id 0x08, subcmd 0x04, checksum 0x49 (bytes sum to 0x55).
_BATTERY_REQUEST = bytes([REPORT_ID, SUBCOMMAND_BATTERY] + [0] * 14 + [0x49])


class BatteryData(NamedTuple):
    percent: int
    wired: bool
    charging: bool
    voltage_mv: int | None


def battery_request() -> bytes:
    return _BATTERY_REQUEST


def checksum_ok(data: list[int] | bytes) -> bool:
    if len(data) < REPORT_LEN:
        return False
    return sum(data[:REPORT_LEN]) % 256 == CHECKSUM_MOD


def parse_battery_response(data: list[int] | bytes | None) -> BatteryData | None:
    if data is None or len(data) < REPORT_LEN:
        return None
    if not checksum_ok(data):
        return None
    if data[0] != REPORT_ID or data[1] != SUBCOMMAND_BATTERY:
        return None
    percent = int(data[PERCENT_OFFSET])
    if percent < 0 or percent > 100:
        return None
    wired = data[WIRED_FLAG_OFFSET] != 0
    voltage_mv = (int(data[VOLTAGE_MSB_OFFSET]) << 8) | int(data[VOLTAGE_LSB_OFFSET])
    return BatteryData(
        percent=percent,
        wired=wired,
        charging=wired and percent < 100,
        voltage_mv=voltage_mv or None,
    )
