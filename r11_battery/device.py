"""HID discovery and Nordic52 battery transactions for the R11 Ultra."""

from __future__ import annotations

import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

import hid

from . import protocol as proto

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HidCollection:
    path: bytes
    vendor_id: int
    product_id: int
    product_string: str
    manufacturer_string: str
    usage_page: int
    usage: int
    interface_number: int


@dataclass(frozen=True)
class BatteryReading:
    percent: int
    wired: bool
    charging: bool
    voltage_mv: int | None
    vendor_id: int
    product_id: int
    product_string: str

    @property
    def state_label(self) -> str:
        if self.charging:
            return "charging"
        if self.wired and self.percent >= 100:
            return "full"
        if self.wired:
            return "wired"
        return "discharging"


def _info_to_collection(info: dict[str, Any]) -> HidCollection:
    path = info["path"]
    return HidCollection(
        path=path if isinstance(path, bytes) else str(path).encode("utf-8"),
        vendor_id=int(info["vendor_id"]),
        product_id=int(info["product_id"]),
        product_string=str(info.get("product_string") or ""),
        manufacturer_string=str(info.get("manufacturer_string") or ""),
        usage_page=int(info.get("usage_page") or 0),
        usage=int(info.get("usage") or 0),
        interface_number=(
            int(info["interface_number"])
            if info.get("interface_number") is not None
            else -1
        ),
    )


def enumerate_all() -> list[HidCollection]:
    return [_info_to_collection(info) for info in hid.enumerate()]


def enumerate_compx() -> list[HidCollection]:
    # Vendor filter avoids scanning every HID device on the system each poll.
    return [_info_to_collection(info) for info in hid.enumerate(proto.VID, 0)]


def battery_collections() -> list[HidCollection]:
    """Compx (VID 0x3554) battery collections for the R11 Ultra.

    Same VID for dongle and USB-C; known PIDs are preferred when present.
    """
    matched = [
        c
        for c in enumerate_compx()
        if c.usage_page == proto.USAGE_PAGE and c.usage == proto.USAGE
    ]

    def sort_key(c: HidCollection) -> tuple[int, int]:
        if c.product_id == proto.PID_WIRELESS:
            return (0, c.product_id)
        if c.product_id == proto.PID_WIRED:
            return (1, c.product_id)
        return (2, c.product_id)

    matched.sort(key=sort_key)
    return matched


def _transact(
    path: bytes,
    report: bytes | list[int],
    read_length: int,
    delay: float,
) -> list[int] | None:
    device = hid.device()
    try:
        device.open_path(path)
        for _ in range(8):
            if not device.read(64, timeout_ms=1):
                break

        report_id = report[0]
        for attempt in range(3):
            written = device.write(report)
            if written is None or written < 0:
                log.warning("HID write failed (attempt %s)", attempt + 1)
                time.sleep(delay)
                continue
            time.sleep(delay)
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                res = device.read(max(read_length, 64), timeout_ms=100)
                if not res:
                    continue
                data = list(res)
                if data[0] == report_id:
                    return data[:read_length] if len(data) >= read_length else data
            log.warning("HID read timeout (attempt %s)", attempt + 1)
        return None
    except Exception as exc:
        log.warning("HID transaction failed: %s", exc)
        return None
    finally:
        with suppress(Exception):
            device.close()


def read_battery(collection: HidCollection | None = None) -> BatteryReading | None:
    targets = [collection] if collection is not None else battery_collections()
    request = proto.battery_request()
    for col in targets:
        parsed = proto.parse_battery_response(
            _transact(col.path, request, proto.REPORT_LEN, proto.TRANSACTION_DELAY_SEC)
        )
        if parsed is None:
            continue
        return BatteryReading(
            percent=parsed.percent,
            wired=parsed.wired,
            charging=parsed.charging,
            voltage_mv=parsed.voltage_mv,
            vendor_id=col.vendor_id,
            product_id=col.product_id,
            product_string=col.product_string,
        )
    return None
