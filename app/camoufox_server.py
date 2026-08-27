"""Camoufox BrowserServer wrapper with optional fixed Firefox profiles."""

from __future__ import annotations

import base64
import os
import re
import selectors
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping, NoReturn

PROFILE_ENV = "CAMOUFOX_SERVER_USER_DATA_DIR"
DEFAULT_EXECUTABLE = Path("/opt/camoufox/browser/camoufox-bin")
LAUNCH_SCRIPT = Path(__file__).with_name("launch_server.js")
WEBSOCKET_RE = re.compile(r"wss?://[^\s\x1b]+")
DEFAULT_STARTUP_TIMEOUT = 120.0
ENDPOINT_FILE = Path("/config/.cache/camoufox-server/ws_endpoint")
CAMOUFOX_BUILD_CACHE = "/opt"
_CAMOUFOX_IMPORT_LOCK = threading.Lock()


class CamoufoxServerTerminated(RuntimeError):
    """Raised when a previously ready BrowserServer exits unexpectedly."""


@contextmanager
def camoufox_build_cache_environment():
    """Point Camoufox package discovery at the immutable build cache briefly."""
    with _CAMOUFOX_IMPORT_LOCK:
        previous = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = CAMOUFOX_BUILD_CACHE
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("XDG_CACHE_HOME", None)
            else:
                os.environ["XDG_CACHE_HOME"] = previous


def validate_profile_options(
    persistent_context: bool = False,
    user_data_dir: str | os.PathLike[str] | None = None,
    *,
    check_writable: bool = True,
) -> Path | None:
    """Validate profile mode and prepare a persistent profile directory."""
    if persistent_context and not user_data_dir:
        raise ValueError("persistent_context=True requires user_data_dir")
    if user_data_dir and not persistent_context:
        raise ValueError("user_data_dir requires persistent_context=True")
    if not persistent_context:
        return None

    path = Path(user_data_dir)  # type: ignore[arg-type]
    if not path.is_absolute():
        raise ValueError("user_data_dir must be an absolute path")

    if path.exists() and not path.is_dir():
        raise ValueError(f"Camoufox profile path is not a directory: {path}")
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as error:
        raise OSError(f"Unable to create Camoufox profile directory: {path}") from error

    if check_writable:
        probe = path / f".camoufox-write-test-{os.getpid()}"
        try:
            descriptor = os.open(probe, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            probe.unlink()
        except OSError as error:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass
            raise PermissionError(
                f"Camoufox profile directory is not writable: {path}"
            ) from error
    return path


def normalize_websocket_path(value: str) -> str:
    """Validate and normalize a BrowserServer WebSocket URL path."""
    if not value:
        raise ValueError("WebSocket path must not be empty")
    if len(value) > 2048:
        raise ValueError("WebSocket path must not exceed 2048 characters")
    if "://" in value or any(character.isspace() for character in value):
        raise ValueError("WebSocket path must be a URL path, not a URL")
    if any(character in value for character in ("?", "#", "\\")):
        raise ValueError("WebSocket path must not contain ?, #, or backslash")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ValueError("WebSocket path must not contain control characters")
    return value if value.startswith("/") else f"/{value}"


def build_child_environment(
    persistent_context: bool,
    user_data_dir: str | os.PathLike[str] | None,
    *,
    base_environment: Mapping[str, str] | None = None,
    check_writable: bool = True,
) -> tuple[dict[str, str], Path | None]:
    """Build an isolated Node environment without mutating ``os.environ``."""
    profile = validate_profile_options(
        persistent_context,
        user_data_dir,
        check_writable=check_writable,
    )
    child_env = dict(os.environ if base_environment is None else base_environment)
    child_env.pop(PROFILE_ENV, None)
    if profile is not None:
        child_env[PROFILE_ENV] = str(profile)
    return child_env, profile


def build_browser_environment(
    environment: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Force Camoufox onto Selkies' X11 display for this launch only."""
    browser_env = {str(key): str(value) for key, value in os.environ.items()}
    if environment is not None:
        browser_env.update({str(key): str(value) for key, value in environment.items()})
    browser_env["GDK_BACKEND"] = "x11"
    browser_env["MOZ_ENABLE_WAYLAND"] = "0"
    browser_env["XDG_CACHE_HOME"] = "/config/.cache"
    browser_env.pop("WAYLAND_DISPLAY", None)
    return browser_env


def launch_camoufox_server(
    *,
    persistent_context: bool = False,
    user_data_dir: str | os.PathLike[str] | None = None,
    ws_path: str | None = None,
    **kwargs: Any,
) -> NoReturn:
    """Launch Camoufox through Playwright ``BrowserType.launchServer``.

    The arguments accepted by Camoufox's ``launch_options`` are supported. The
    two profile arguments are consumed here and never forwarded upstream.
    """
    child_env, profile = build_child_environment(
        persistent_context,
        user_data_dir,
    )
    try:
        ENDPOINT_FILE.unlink(missing_ok=True)
    except OSError as error:
        raise OSError(f"Unable to clear WebSocket endpoint file: {ENDPOINT_FILE}") from error
    try:
        startup_timeout = float(
            child_env.get("CAMOUFOX_STARTUP_TIMEOUT", DEFAULT_STARTUP_TIMEOUT)
        )
    except ValueError as error:
        raise ValueError("CAMOUFOX_STARTUP_TIMEOUT must be a number") from error
    if startup_timeout <= 0:
        raise ValueError("CAMOUFOX_STARTUP_TIMEOUT must be greater than zero")

    supplied_browser_env = kwargs.pop("env", None)
    kwargs["env"] = build_browser_environment(supplied_browser_env)
    kwargs.setdefault("headless", False)
    kwargs.setdefault("host", "0.0.0.0")
    if ws_path is not None:
        kwargs["ws_path"] = normalize_websocket_path(ws_path)
    if kwargs.get("executable_path") is None:
        kwargs["executable_path"] = str(DEFAULT_EXECUTABLE)

    executable = Path(kwargs["executable_path"])
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise FileNotFoundError(
            f"Camoufox browser executable not found: {kwargs['executable_path']}"
        )
    if not LAUNCH_SCRIPT.is_file():
        raise FileNotFoundError(f"Camoufox Node launcher not found: {LAUNCH_SCRIPT}")

    # Camoufox computes package paths at import time. Scope XDG_CACHE_HOME to
    # the immutable build cache while importing and building launch options;
    # Firefox itself receives the writable cache from build_browser_environment.
    with camoufox_build_cache_environment():
        import orjson
        from camoufox.addons import DefaultAddons
        from camoufox.server import get_nodejs, to_camel_case_dict
        from camoufox.utils import launch_options

        kwargs.setdefault("exclude_addons", list(DefaultAddons))
        config = launch_options(**kwargs)
    data = orjson.dumps(to_camel_case_dict(config))
    nodejs = get_nodejs()
    driver_package = Path(nodejs).parent / "package"

    process = subprocess.Popen(  # nosec B603
        [nodejs, str(LAUNCH_SCRIPT), str(driver_package)],
        cwd=driver_package,
        env=child_env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdin is not None
    assert process.stdout is not None

    encoded_config = base64.b64encode(data).decode("ascii") + "\n"
    endpoint_logged = False
    startup_deadline = time.monotonic() + startup_timeout

    def close_stdin() -> None:
        if not process.stdin or process.stdin.closed:
            return
        try:
            process.stdin.close()
        except OSError:
            pass

    def shutdown_process() -> None:
        close_stdin()
        if process.poll() is not None:
            process.wait()
            return
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    try:
        process.stdin.write(encoded_config)
        process.stdin.flush()
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        while process.poll() is None:
            events = selector.select(timeout=1)
            if not events:
                if not endpoint_logged and time.monotonic() >= startup_deadline:
                    raise RuntimeError(
                        "Camoufox server did not report a WebSocket endpoint within "
                        f"{startup_timeout:g} seconds"
                    )
                continue
            line = process.stdout.readline()
            if not line:
                continue
            print(line, end="", flush=True)
            if not endpoint_logged and (match := WEBSOCKET_RE.search(line)):
                endpoint = match.group(0)
                try:
                    ENDPOINT_FILE.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                    ENDPOINT_FILE.write_text(f"{endpoint}\n", encoding="utf-8")
                except OSError as error:
                    raise RuntimeError(
                        f"Unable to write WebSocket endpoint file: {ENDPOINT_FILE}"
                    ) from error
                print(f"[camoufox] websocket={endpoint}", flush=True)
                endpoint_logged = True
        for line in process.stdout:
            print(line, end="", flush=True)
        return_code = process.wait()
    except BaseException:
        shutdown_process()
        raise
    finally:
        close_stdin()
        try:
            ENDPOINT_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    mode = "persistent" if profile else "ephemeral"
    error = RuntimeError
    if endpoint_logged:
        error = CamoufoxServerTerminated
    raise error(f"Camoufox {mode} server terminated unexpectedly with exit code {return_code}")


# Common compatibility spelling for consumers expecting launch_server().
launch_server = launch_camoufox_server
