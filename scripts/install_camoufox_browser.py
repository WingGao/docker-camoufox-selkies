#!/usr/bin/env python3
"""Expose the fetched Camoufox browser through a stable, read-only path."""

from __future__ import annotations

import json
import os
from pathlib import Path

from camoufox.multiversion import get_active_path
from camoufox.pkgman import Version, launch_path
from camoufox.utils import _generate_fontconfig

INSTALL_ROOT = Path("/opt/camoufox")
STABLE_BROWSER = INSTALL_ROOT / "browser"


def normalize_permissions(root: Path, executable: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_dir():
            path.chmod(0o755)
            continue
        try:
            with path.open("rb") as stream:
                header = stream.read(4)
        except OSError:
            header = b""
        mode = 0o755 if path == executable or header == b"\x7fELF" or header[:2] == b"#!" else 0o644
        path.chmod(mode)
    root.chmod(0o755)


def main() -> int:
    browser = get_active_path()
    if browser is None:
        raise RuntimeError("Camoufox fetch completed without an active browser installation")
    browser = browser.resolve()
    executable = Path(launch_path(browser)).resolve()
    if not executable.is_file():
        raise RuntimeError(f"Camoufox executable was not found: {executable}")

    INSTALL_ROOT.mkdir(mode=0o755, parents=True, exist_ok=True)
    if STABLE_BROWSER.is_symlink() or STABLE_BROWSER.is_file():
        STABLE_BROWSER.unlink()
    elif STABLE_BROWSER.exists():
        raise RuntimeError(f"Stable browser path already exists and is not a symlink: {STABLE_BROWSER}")
    STABLE_BROWSER.symlink_to(browser, target_is_directory=True)

    # Camoufox normally writes this generated file on first launch. Generate it
    # while the image is writable so runtime user abc can use a read-only bundle.
    fontconfigs = sorted(browser.glob("fontconfig/*/fonts.conf"))
    fontconfigs.extend(sorted(browser.glob("fontconfigs/*/fonts.conf")))
    if not fontconfigs:
        raise RuntimeError("Camoufox browser bundle does not contain Linux fonts.conf")
    for fonts_conf in fontconfigs:
        _generate_fontconfig(str(fonts_conf.parent))

    normalize_permissions(browser, executable)
    cache_root = browser.parents[2]
    for directory in (cache_root, cache_root / "fontconfig"):
        if directory.exists():
            directory.chmod(0o755)

    version = Version.from_path(browser)
    manifest = {
        "browser_directory": str(browser),
        "executable": str(STABLE_BROWSER / executable.name),
        "version": version.full_string,
    }
    (INSTALL_ROOT / "browser-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(INSTALL_ROOT / "browser-manifest.json", 0o644)
    print(f"Camoufox browser executable: {manifest['executable']}")
    print(f"Camoufox browser version: {manifest['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
