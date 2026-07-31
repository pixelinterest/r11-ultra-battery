"""Transparent tray icon with colored percent text."""

from __future__ import annotations

import winreg

from PIL import Image, ImageDraw, ImageFont

from .device import BatteryReading

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
        return (21, 101, 192) if light else (52, 152, 219)
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

    cache_key = (text, color, light, size)
    cached = _ICON_CACHE.get(cache_key)
    if cached is not None:
        return cached

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _font(54 if len(text) <= 2 else 34)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    x = (size - (right - left)) / 2 - left
    y = (size - (bottom - top)) / 2 - top
    draw.text((x, y), text, fill=(*color, 255), font=font)

    if len(_ICON_CACHE) > 40:
        _ICON_CACHE.clear()
    _ICON_CACHE[cache_key] = image
    return image
