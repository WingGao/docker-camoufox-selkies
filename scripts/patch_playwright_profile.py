#!/usr/bin/env python3
"""Safely patch Playwright's Firefox BrowserServer profile selection."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

MARKER = "CAMOUFOX_PERSISTENT_SERVER_PROFILE_PATCH"
DEFAULT_CONTEXT_MARKER = "CAMOUFOX_PERSISTENT_SERVER_DEFAULT_CONTEXT_PATCH"
PROFILE_ENV = "CAMOUFOX_SERVER_USER_DATA_DIR"
TEMP_PROFILE_TOKEN = "dev_profile-"


class PatchError(RuntimeError):
    """Raised when the installed Playwright layout cannot be patched safely."""


def installed_driver_package() -> Path:
    import playwright

    package = Path(playwright.__file__).resolve().parent / "driver" / "package"
    if not package.is_dir():
        raise PatchError(f"Playwright driver package not found: {package}")
    return package


def find_node() -> str:
    from playwright._impl._driver import compute_driver_executable

    executable = compute_driver_executable()
    return str(executable[0] if isinstance(executable, tuple) else executable)


def javascript_files(package: Path) -> list[Path]:
    return sorted(path for path in package.rglob("*.js") if path.is_file())


def verify_patched_source(source: str, target: Path) -> None:
    checks = {
        "patch marker": source.count(MARKER) == 1,
        "default context marker": source.count(DEFAULT_CONTEXT_MARKER) == 1,
        "profile environment variable": source.count(PROFILE_ENV) == 3,
        "temporary profile fallback": TEMP_PROFILE_TOKEN in source,
        "temporary profile cleanup": "tempDirectories.push(userDataDir)" in source,
        "Firefox-only guard": 'this._name === "firefox"' in source,
        "shared BrowserServer mode": (
            "launchServerShared" in source and "_sharedBrowser" in source
        ),
    }
    failed = [name for name, valid in checks.items() if not valid]
    if failed:
        raise PatchError(f"Static patch verification failed for {target}: {', '.join(failed)}")


def locate_insertion(source: str, target: Path) -> tuple[int, str]:
    token_positions = []
    offset = 0
    while (position := source.find(TEMP_PROFILE_TOKEN, offset)) != -1:
        token_positions.append(position)
        offset = position + len(TEMP_PROFILE_TOKEN)
    if len(token_positions) != 1:
        raise PatchError(
            f"Expected exactly one Firefox temporary profile token in {target}, "
            f"found {len(token_positions)}"
        )

    token = token_positions[0]
    window_start = max(0, token - 2500)
    prefix = source[window_start:token]
    relative_if = prefix.rfind("if (userDataDir) {")
    if relative_if == -1:
        raise PatchError(f"Unable to locate userDataDir branch near {TEMP_PROFILE_TOKEN} in {target}")
    insertion = window_start + relative_if
    line_start = source.rfind("\n", 0, insertion) + 1
    indentation = source[line_start:insertion]
    if indentation.strip():
        raise PatchError(f"Unexpected code before userDataDir branch in {target}")

    confirmation = source[insertion : token + 500]
    required = (
        "isAbsolute(userDataDir)",
        "} else {",
        "mkdtemp",
        "tempDirectories.push(userDataDir)",
    )
    missing = [item for item in required if item not in confirmation]
    if missing:
        raise PatchError(
            f"Unable to confirm Playwright profile creation logic in {target}: "
            f"missing {', '.join(missing)}"
        )
    return line_start, indentation


def patch_default_context(source: str, target: Path) -> str:
    needle = "this._innerLaunchWithRetries("
    candidates = []
    offset = 0
    while (position := source.find(needle, offset)) != -1:
        call_end = source.find(").catch", position)
        if call_end != -1:
            call = source[position:call_end]
            if ", void 0, helper.debugProtocolLogger(" in call:
                candidates.append((position, call_end))
        offset = position + len(needle)
    if len(candidates) != 1:
        raise PatchError(
            "Unable to safely locate Playwright BrowserType.launch() context argument "
            f"in {target} (matches: {len(candidates)})."
        )

    start, end = candidates[0]
    original = source[start:end]
    replacement = original.replace(
        ", void 0, helper.debugProtocolLogger(",
        f", (this._name === \"firefox\" && process.env.{PROFILE_ENV} ? {{}} : void 0), "
        "helper.debugProtocolLogger(",
        1,
    )
    line_start = source.rfind("\n", 0, start) + 1
    line_prefix = source[line_start:start]
    indentation = line_prefix[: len(line_prefix) - len(line_prefix.lstrip())]
    marker = f"{indentation}// {DEFAULT_CONTEXT_MARKER}\n"
    return source[:line_start] + marker + line_prefix + replacement + source[end:]


def patch_playwright(
    package_dir: Path | None = None,
    *,
    backup: bool = True,
    check_syntax: bool = True,
    node: str | None = None,
) -> Path:
    package = (package_dir or installed_driver_package()).resolve()
    files = javascript_files(package)
    if not files:
        raise PatchError(f"No JavaScript files found under Playwright driver package: {package}")

    marker_files = []
    profile_files = []
    for javascript in files:
        source = javascript.read_text(encoding="utf-8", errors="ignore")
        if MARKER in source:
            marker_files.append(javascript)
        if TEMP_PROFILE_TOKEN in source and "userDataDir" in source:
            profile_files.append(javascript)

    if marker_files:
        if len(marker_files) != 1:
            raise PatchError(f"Patch marker exists in multiple files: {marker_files}")
        source = marker_files[0].read_text(encoding="utf-8")
        verify_patched_source(source, marker_files[0])
        print(f"Playwright profile patch already present: {marker_files[0]}")
        return marker_files[0]

    if len(profile_files) != 1:
        raise PatchError(
            "Unable to safely locate Playwright Firefox profile creation logic. "
            f"Playwright layout may have changed (candidate files: {len(profile_files)})."
        )

    target = profile_files[0]
    source = target.read_text(encoding="utf-8")
    insertion, indentation = locate_insertion(source, target)
    injected = (
        f"{indentation}// {MARKER}\n"
        f"{indentation}if (!userDataDir && this._name === \"firefox\" && "
        f"process.env.{PROFILE_ENV})\n"
        f"{indentation}  userDataDir = process.env.{PROFILE_ENV};\n"
    )
    patched = source[:insertion] + injected + source[insertion:]
    patched = patch_default_context(patched, target)
    verify_patched_source(patched, target)

    backup_path = target.with_name(target.name + ".pre-camoufox-patch")
    if backup:
        shutil.copy2(target, backup_path)
    target.write_text(patched, encoding="utf-8")

    try:
        if check_syntax:
            subprocess.run(
                [node or find_node(), "--check", str(target)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
    except (OSError, subprocess.CalledProcessError) as error:
        if backup and backup_path.exists():
            shutil.copy2(backup_path, target)
        output = getattr(error, "stdout", "")
        raise PatchError(f"Node syntax check failed for {target}: {output}") from error

    print(f"Patched Playwright Firefox BrowserServer profile selection: {target}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path)
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--no-node-check", action="store_true")
    parser.add_argument("--record-path", type=Path)
    args = parser.parse_args()
    try:
        target = patch_playwright(
            args.package_dir,
            backup=not args.no_backup,
            check_syntax=not args.no_node_check,
        )
        if args.record_path:
            args.record_path.parent.mkdir(parents=True, exist_ok=True)
            args.record_path.write_text(f"{target}\n", encoding="utf-8")
    except PatchError as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
