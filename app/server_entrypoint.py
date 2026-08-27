"""Command-line and Docker environment entrypoint for Camoufox."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import signal
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.camoufox_server import (  # noqa: E402
    CamoufoxServerTerminated,
    DEFAULT_EXECUTABLE,
    launch_camoufox_server,
    normalize_websocket_path,
    validate_profile_options,
)

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off", ""})


def parse_boolean(value: str, variable: str) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{variable} must be true or false, got {value!r}")


def positive_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise ValueError(f"CAMOUFOX_PORT must be an integer, got {value!r}") from error
    if not 1 <= port <= 65535:
        raise ValueError(f"CAMOUFOX_PORT must be between 1 and 65535, got {port}")
    return port


def resolve_settings(
    args: argparse.Namespace,
    environment: dict[str, str] | None = None,
) -> tuple[int, str | None, bool, str | None, bool]:
    env = os.environ if environment is None else environment
    port = args.port
    if port is None:
        port = positive_port(env.get("CAMOUFOX_PORT", "1234"))

    ws_path = args.ws_path
    if ws_path is None:
        configured_path = env.get("CAMOUFOX_WS_PATH", "")
        ws_path = normalize_websocket_path(configured_path) if configured_path else None

    persistent = args.persistent_context
    if persistent is None:
        persistent = parse_boolean(
            env.get("CAMOUFOX_PERSISTENT_CONTEXT", "false"),
            "CAMOUFOX_PERSISTENT_CONTEXT",
        )

    user_data_dir = args.user_data_dir
    if user_data_dir is None:
        user_data_dir = env.get("CAMOUFOX_USER_DATA_DIR") or None

    debug = args.debug
    if debug is None:
        debug = parse_boolean(env.get("CAMOUFOX_DEBUG", "false"), "CAMOUFOX_DEBUG")
    return port, ws_path, persistent, user_data_dir, debug


def find_patched_javascript() -> Path | None:
    try:
        import playwright
    except ImportError:
        return None
    package = Path(playwright.__file__).resolve().parent / "driver" / "package"
    matches = []
    for javascript in package.rglob("*.js"):
        try:
            if "CAMOUFOX_PERSISTENT_SERVER_PROFILE_PATCH" in javascript.read_text(
                encoding="utf-8", errors="ignore"
            ):
                matches.append(javascript)
        except OSError:
            continue
    return matches[0] if len(matches) == 1 else None


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def log_diagnostics(persistent: bool, profile: str | None) -> None:
    version_file = DEFAULT_EXECUTABLE.parent.parent / "browser-manifest.json"
    browser_version = "unknown"
    if version_file.is_file():
        try:
            manifest = json.loads(version_file.read_text(encoding="utf-8"))
            browser_version = str(manifest.get("version", "unknown"))
        except (OSError, json.JSONDecodeError):
            pass
    print(f"[camoufox] debug.camoufox_version={package_version('camoufox')}", flush=True)
    print(f"[camoufox] debug.playwright_version={package_version('playwright')}", flush=True)
    print(f"[camoufox] debug.browser_version={browser_version}", flush=True)
    print(f"[camoufox] debug.executable={DEFAULT_EXECUTABLE}", flush=True)
    print(f"[camoufox] debug.display={os.environ.get('DISPLAY', '')}", flush=True)
    print("[camoufox] debug.gdk_backend=x11", flush=True)
    print(f"[camoufox] debug.persistent={str(persistent).lower()}", flush=True)
    print(f"[camoufox] debug.profile={profile or ''}", flush=True)
    print(f"[camoufox] debug.patch={find_patched_javascript() or 'not-found'}", flush=True)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the Camoufox Playwright server")
    parser.add_argument("--port", type=positive_port, default=None)
    parser.add_argument("--ws-path", type=normalize_websocket_path, default=None)
    parser.add_argument(
        "--persistent-context",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument("--user-data-dir", default=None)
    parser.add_argument("--debug", action=argparse.BooleanOptionalAction, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    def request_shutdown(_signum: int, _frame: object) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, request_shutdown)
    args = create_parser().parse_args(argv)
    try:
        port, ws_path, persistent, user_data_dir, debug = resolve_settings(args)
        profile = validate_profile_options(persistent, user_data_dir)
        print("[camoufox] starting", flush=True)
        print(f"[camoufox] display={os.environ.get('DISPLAY', '')}", flush=True)
        print(f"[camoufox] mode={'persistent' if profile else 'ephemeral'}", flush=True)
        print(f"[camoufox] ws_path={ws_path or 'random'}", flush=True)
        if profile:
            print(f"[camoufox] profile={profile}", flush=True)
        if debug:
            log_diagnostics(persistent, str(profile) if profile else None)
        while True:
            try:
                launch_camoufox_server(
                    headless=False,
                    port=port,
                    ws_path=ws_path,
                    persistent_context=persistent,
                    user_data_dir=str(profile) if profile else None,
                )
            except CamoufoxServerTerminated as error:
                print(f"[camoufox] error: {error}", file=sys.stderr, flush=True)
                print("[camoufox] restarting after unexpected browser exit", flush=True)
                time.sleep(2)
    except (ValueError, OSError, RuntimeError) as error:
        print(f"[camoufox] error: {error}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
