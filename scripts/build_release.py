#!/usr/bin/env python3
"""Build the Windows onedir zip for GitHub Releases."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
APP_NAME = "R11UltraBattery"
ZIP_NAME = "R11UltraBattery-windows"


def file_version(version: str) -> tuple[str, tuple[int, int, int, int]]:
    parts = [int(p) for p in version.split(".")]
    while len(parts) < 4:
        parts.append(0)
    parts = parts[:4]
    return ".".join(str(p) for p in parts), tuple(parts)  # type: ignore[return-value]


def write_version_info(path: Path, version: str) -> None:
    dotted, (a, b, c, d) = file_version(version)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({a}, {b}, {c}, {d}),
    prodvers=({a}, {b}, {c}, {d}),
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable(
        "040904B0",
        [
          StringStruct("CompanyName", "pixelinterest"),
          StringStruct("FileDescription", "Attack Shark R11 Ultra battery tracker"),
          StringStruct("FileVersion", "{dotted}"),
          StringStruct("InternalName", "{APP_NAME}"),
          StringStruct("LegalCopyright", "Copyright (c) pixelinterest"),
          StringStruct("OriginalFilename", "{APP_NAME}.exe"),
          StringStruct("ProductName", "R11 Ultra Battery Tracker"),
          StringStruct("ProductVersion", "{dotted}"),
        ],
      )
    ]),
    VarFileInfo([VarStruct("Translation", [1033, 1200])]),
  ],
)
""",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="0.1.4")
    args = parser.parse_args()

    version_file = ROOT / "packaging" / "file_version_info.txt"
    write_version_info(version_file, args.version)

    app_dir = DIST / APP_NAME
    zip_path = DIST / ZIP_NAME
    if app_dir.exists():
        shutil.rmtree(app_dir)
    for leftover in DIST.glob(f"{ZIP_NAME}.*"):
        leftover.unlink()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        f"--name={APP_NAME}",
        f"--version-file={version_file}",
        "--collect-all=pystray",
        "--collect-all=hidapi",
        str(ROOT / "main.py"),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)

    exe = app_dir / f"{APP_NAME}.exe"
    if not exe.is_file():
        raise SystemExit(f"Build failed: {exe} not found")

    archive = shutil.make_archive(str(zip_path), "zip", root_dir=DIST, base_dir=APP_NAME)
    archive_path = Path(archive)
    print(f"Built {archive_path}")
    print(f"SHA256: {sha256(archive_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
