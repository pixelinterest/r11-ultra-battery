"""Windows system-tray battery monitor for Attack Shark R11 Ultra."""

from __future__ import annotations

import logging
import sys
import threading
import time
from logging.handlers import RotatingFileHandler

import pystray

from . import protocol as proto
from .device import BatteryReading, read_battery
from .icons import make_icon
from .startup import (
    acquire_single_instance,
    clear_stale_startup,
    is_startup_enabled,
    log_file_path,
    set_startup,
)

log = logging.getLogger(__name__)


class TrayApp:
    def __init__(self, poll_interval: float = proto.POLL_INTERVAL_SEC) -> None:
        self.poll_interval = poll_interval
        self._reading: BatteryReading | None = None
        self._reading_at: float | None = None
        self._showing_stale = False
        self._icon_key: tuple | None = None
        self._title_key: tuple | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._poll_lock = threading.Lock()
        # One stable menu with callables — avoids recreating Win32 HMENU churn.
        self.icon = pystray.Icon(
            "r11-ultra-battery",
            make_icon(None),
            "R11 Ultra Battery Tracker",
            menu=self._build_menu(),
        )
        self._icon_key = self._icon_key_for(None)
        self._title_key = self._title_key_for(None, stale=False)

    def _status_text(self) -> str:
        with self._lock:
            reading = self._reading
            stale = self._showing_stale
        if reading is None:
            return "Attack Shark R11 Ultra: disconnected"
        label = f"Attack Shark R11 Ultra: {reading.percent}%"
        if reading.charging:
            label += " (charging)"
        elif stale:
            label += " (last reading)"
        return label

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(lambda _item: self._status_text(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Refresh", self._on_refresh),
            pystray.MenuItem(
                "Start with Windows",
                self._on_toggle_startup,
                checked=lambda _item: is_startup_enabled(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )

    @staticmethod
    def _icon_key_for(reading: BatteryReading | None) -> tuple:
        if reading is None:
            return (None, False)
        return (reading.percent, reading.charging)

    @staticmethod
    def _title_key_for(reading: BatteryReading | None, *, stale: bool) -> tuple:
        if reading is None:
            return (None, False, False)
        return (reading.percent, reading.charging, stale)

    def _apply_display(self, reading: BatteryReading | None, *, stale: bool) -> None:
        icon_key = self._icon_key_for(reading)
        title_key = self._title_key_for(reading, stale=stale)
        with self._lock:
            self._reading = reading
            self._showing_stale = stale
            icon_changed = icon_key != self._icon_key
            title_changed = title_key != self._title_key
            if icon_changed:
                self._icon_key = icon_key
            if title_changed:
                self._title_key = title_key

        # Icon assignment recreates a Win32 HICON; skip when pixels would match.
        if icon_changed:
            self.icon.icon = make_icon(reading)
        if title_changed:
            self.icon.title = self._status_text()
            # Menu texts are callables; refresh the native menu once (DestroyMenu
            # + recreate). Do not reassign icon.menu — that would rebuild twice.
            self.icon.update_menu()

    def _poll_once(self) -> None:
        if not self._poll_lock.acquire(blocking=False):
            return
        try:
            self._poll_once_unlocked()
        finally:
            self._poll_lock.release()

    def _poll_once_unlocked(self) -> None:
        try:
            reading = read_battery()
        except Exception:
            log.exception("Battery poll failed")
            reading = None

        now = time.monotonic()
        try:
            if reading is not None:
                with self._lock:
                    self._reading_at = now
                self._apply_display(reading, stale=False)
                log.debug(
                    "Battery %s%% (%s) pid=0x%04x",
                    reading.percent,
                    reading.state_label,
                    reading.product_id,
                )
                return

            with self._lock:
                cached = self._reading
                cached_at = self._reading_at
            if (
                cached is not None
                and cached_at is not None
                and (now - cached_at) <= proto.STALE_READING_SEC
            ):
                self._apply_display(cached, stale=True)
                log.debug(
                    "Poll missed; keeping last reading %s%% (%.0fs old)",
                    cached.percent,
                    now - cached_at,
                )
                return

            with self._lock:
                self._reading_at = None
            self._apply_display(None, stale=False)
            log.debug("Mouse not found / no battery reply")
        except Exception:
            log.exception("Failed to update tray display")

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            self._poll_once()
            self._stop.wait(self.poll_interval)

    def _on_refresh(self, _icon=None, _item=None) -> None:
        # Reuse the poll lock; skip if a poll is already in flight.
        threading.Thread(target=self._poll_once, daemon=True, name="r11-refresh").start()

    def _on_toggle_startup(self, _icon=None, _item=None) -> None:
        enabled = not is_startup_enabled()
        if set_startup(enabled):
            log.info("Start with Windows: %s", "on" if enabled else "off")
        self.icon.update_menu()

    def _on_quit(self, _icon=None, _item=None) -> None:
        self._stop.set()
        self.icon.stop()

    def run(self) -> None:
        threading.Thread(target=self._poll_loop, daemon=True, name="r11-poll").start()
        self.icon.run()


def _configure_logging() -> None:
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            log_file_path(),
            maxBytes=256 * 1024,
            backupCount=2,
            encoding="utf-8",
        ),
    ]
    if sys.stderr is not None and getattr(sys.stderr, "isatty", lambda: False)():
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def main() -> None:
    try:
        _configure_logging()
    except OSError:
        logging.basicConfig(level=logging.INFO)
        log.exception("Could not open log file; continuing with basic logging")
    if not acquire_single_instance():
        log.info("Another instance is already running; exiting")
        return
    clear_stale_startup()
    TrayApp().run()


if __name__ == "__main__":
    main()
