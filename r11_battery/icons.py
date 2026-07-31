"""Transparent tray icon with colored percent text."""

from __future__ import annotations

import winreg

from PIL import Image, ImageDraw, ImageFont

from .device import BatteryReading

# Tray percent font size (icon is 64x64). Suggested range: 28–40.
# Below ~28 is hard to read; above ~40 clips three-digit values like "100".
ICON_FONT_SIZE = 36

# Charging percent color as RGB 0–255 (used when the mouse reports charging).
# Light / dark track Windows taskbar theme. Examples: cyan (0, 180, 200),
# purple (155, 89, 182), white (240, 240, 240).
CHARGING_COLOR_LIGHT = (21, 101, 192)
CHARGING_COLOR_DARK = (52, 152, 219)

_FONT_CACHE: dict[int, ImageFont.ImageFont] = {}
_ICON_CACHE: dict[tuple, Image.Image] = {}


def _is_light_mode() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            0,
            winreg.KEY_READ,
        ) as key:
            val, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
            return val == 1
    except OSError:
        return False


def _font(size: int) -> ImageFont.ImageFont:
    cached = _FONT_CACHE.get(size)
    if cached is not None:
        return cached
    for name in ("arialbd.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(name, size)
            _FONT_CACHE[size] = font
            return font
        except OSError:
            continue
    font = ImageFont.load_default()
    _FONT_CACHE[size] = font
    return font


def _text_color(percent: int | None, *, charging: bool, light: bool) -> tuple[int, int, int]:
    if percent is None:
        return (70, 70, 70) if light else (170, 170, 170)
    if charging:
        return CHARGING_COLOR_LIGHT if light else CHARGING_COLOR_DARK

    if percent >= 50:
        return (30, 140, 60) if light else (46, 204, 113)
    if percent >= 20:
        return (211, 84, 0) if light else (230, 126, 34)
    return (192, 57, 43) if light else (231, 76, 60)


def make_icon(reading: BatteryReading | None, size: int = 64) -> Image.Image:
    light = _is_light_mode()
    if reading is None:
        text = "??"
        color = _text_color(None, charging=False, light=light)
    else:
        text = str(reading.percent)
        color = _text_color(reading.percent, charging=reading.charging, light=light)

    cache_key = (text, color, light, size, ICON_FONT_SIZE, CHARGING_COLOR_LIGHT, CHARGING_COLOR_DARK)
    cached = _ICON_CACHE.get(cache_key)
    if cached is not None:
        return cached

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _font(ICON_FONT_SIZE)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    x = (size - (right - left)) / 2 - left
    y = (size - (bottom - top)) / 2 - top
    draw.text((x, y), text, fill=(*color, 255), font=font)

    if len(_ICON_CACHE) > 40:
        _ICON_CACHE.clear()
    _ICON_CACHE[cache_key] = image
    return image
