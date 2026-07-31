# R11 Ultra Battery

[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?logo=windows&logoColor=white)](https://github.com/pixelinterest/r11-ultra-battery)
[![Release](https://img.shields.io/github/v/release/pixelinterest/r11-ultra-battery?color=28a745)](https://github.com/pixelinterest/r11-ultra-battery/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/pixelinterest/r11-ultra-battery/total?color=7952b3)](https://github.com/pixelinterest/r11-ultra-battery/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

Windows system tray battery monitor for the **Attack Shark R11 Ultra**.

**[Download latest release](https://github.com/pixelinterest/r11-ultra-battery/releases/latest)**

---

## Features

- Colored battery percent in the tray (green / orange / red; blue while charging)
- Runs in the background with no console window
- **Start with Windows** toggle (no admin required)
- Polls every 30s; keeps the last reading up to 5 minutes on a missed poll
- Supports 2.4 GHz dongle and USB-C charging

## Supported modes

| Mode | VID | PID |
|------|-----|-----|
| 2.4 GHz dongle | `0x3554` | `0xFB44` |
| USB-C wired | `0x3554` | `0xFB43` |

Bluetooth is not supported. Older Attack Shark X11 tools use a different protocol and will not work with this mouse.

---

## Install

### Release build (recommended)

1. Download `R11UltraBattery-windows.zip` from the [latest release](https://github.com/pixelinterest/r11-ultra-battery/releases/latest).
2. Extract the folder and run `R11UltraBattery.exe`.
3. Right-click the tray icon → **Start with Windows** if you want it at login.

### From source

```powershell
git clone https://github.com/pixelinterest/r11-ultra-battery.git
cd r11-ultra-battery
pip install -r requirements.txt
pythonw main.pyw
```

Debug console: `python main.py`  
HID probe: `python tools/probe_hid.py`  
Logs: `%LOCALAPPDATA%\R11UltraBattery\tray.log`

---

## Troubleshooting

- **Icon shows `??`** — Wake the mouse, confirm the dongle or USB-C cable is connected, and close the official Attack Shark software if it has locked the device.
- Unsigned release builds may trigger antivirus heuristics. Prefer the SHA256 on the release page, or run from source.

## Protocol

See [`protocol.md`](protocol.md). Compx / Nordic 52840 report id `0x08`, sub-command `0x04`, percent at byte 6 (usage page `0xFF02` / usage `0x02`).
