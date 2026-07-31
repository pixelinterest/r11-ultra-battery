#!/usr/bin/env python3
"""List Compx / R11 Ultra HID collections and try the Nordic52 battery query."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from r11_battery import protocol as proto
from r11_battery.device import (
    BatteryReading,
    battery_collections,
    enumerate_all,
    enumerate_compx,
    read_battery,
)


def _fmt_ids(vid: int, pid: int) -> str:
    return f"VID=0x{vid:04x} PID=0x{pid:04x}"


def _print_reading(reading: BatteryReading) -> None:
    print(
        f"OK  {_fmt_ids(reading.vendor_id, reading.product_id)}  "
        f"{reading.product_string!r}"
    )
    print(f"  percent     = {reading.percent}%")
    print(f"  state       = {reading.state_label}")
    print(f"  wired_flag  = {reading.wired}")
    if reading.voltage_mv:
        print(f"  voltage     = {reading.voltage_mv} mV")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all",
        action="store_true",
        help="List every HID device on the system, not just Compx",
    )
    parser.add_argument(
        "--no-query",
        action="store_true",
        help="Only enumerate; skip battery query",
    )
    args = parser.parse_args()

    print("=== HID enumeration ===")
    devices = enumerate_all() if args.all else enumerate_compx()
    if not devices:
        print("No matching HID devices found.")
        if not args.all:
            print("Tip: run with --all, or plug in the 2.4 GHz dongle / USB-C cable.")
        return 1

    for c in devices:
        marker = ""
        if c.vendor_id == proto.VID and c.product_id == proto.PID_WIRELESS:
            marker = "  [wireless R11 Ultra]"
        elif c.vendor_id == proto.VID and c.product_id == proto.PID_WIRED:
            marker = "  [wired R11 Ultra]"
        elif (
            c.vendor_id == proto.VID
            and c.usage_page == proto.USAGE_PAGE
            and c.usage == proto.USAGE
        ):
            marker = "  [battery collection]"
        print(
            f"{_fmt_ids(c.vendor_id, c.product_id)}  "
            f"iface={c.interface_number}  "
            f"usage_page=0x{c.usage_page:04x} usage=0x{c.usage:04x}  "
            f"{c.manufacturer_string!r} / {c.product_string!r}{marker}"
        )

    print()
    print("=== Compx (0x3554) product IDs seen ===")
    for pid in sorted({c.product_id for c in enumerate_compx()}):
        if pid == proto.PID_WIRELESS:
            role = "wireless"
        elif pid == proto.PID_WIRED:
            role = "wired"
        else:
            role = "other"
        print(f"  0x{pid:04x} ({role})")

    if args.no_query:
        return 0

    print()
    print("=== Nordic52 battery query ===")
    cols = battery_collections()
    if not cols:
        print("No R11 Ultra battery collection found (usage page 0xFF02 / usage 0x02).")
        return 2

    for c in cols:
        print(
            f"Trying {_fmt_ids(c.vendor_id, c.product_id)} "
            f"usage_page=0x{c.usage_page:04x} usage=0x{c.usage:04x}..."
        )
        reading = read_battery(c)
        if reading:
            _print_reading(reading)
            return 0
        print("  no valid battery reply")

    print("Battery query failed on all candidates.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
