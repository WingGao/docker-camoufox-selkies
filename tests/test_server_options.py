from __future__ import annotations

import argparse
import os
import tempfile
import unittest
from pathlib import Path

from app.camoufox_server import (
    LAUNCH_SCRIPT,
    PROFILE_ENV,
    build_browser_environment,
    build_child_environment,
    camoufox_build_cache_environment,
    normalize_websocket_path,
    validate_profile_options,
)
from app.server_entrypoint import parse_boolean, resolve_settings


class ProfileOptionTests(unittest.TestCase):
    def test_project_node_launcher_exists(self) -> None:
        self.assertEqual(LAUNCH_SCRIPT.name, "launch_server.js")
        self.assertTrue(LAUNCH_SCRIPT.is_file())

    def test_build_cache_environment_is_scoped(self) -> None:
        sentinel = object()
        previous = os.environ.get("XDG_CACHE_HOME", sentinel)
        try:
            os.environ.pop("XDG_CACHE_HOME", None)
            with camoufox_build_cache_environment():
                self.assertEqual(os.environ["XDG_CACHE_HOME"], "/opt")
            self.assertNotIn("XDG_CACHE_HOME", os.environ)
        finally:
            if previous is sentinel:
                os.environ.pop("XDG_CACHE_HOME", None)
            else:
                os.environ["XDG_CACHE_HOME"] = previous  # type: ignore[assignment]

    def test_ephemeral_mode(self) -> None:
        self.assertIsNone(validate_profile_options(False, None))
        environment, profile = build_child_environment(
            False,
            None,
            base_environment={PROFILE_ENV: "/stale/profile", "DISPLAY": ":1"},
        )
        self.assertIsNone(profile)
        self.assertNotIn(PROFILE_ENV, environment)
        self.assertEqual(environment["DISPLAY"], ":1")

    def test_persistent_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            profile_path = Path(temporary) / "profile"
            environment, profile = build_child_environment(
                True,
                profile_path,
                base_environment={"DISPLAY": ":1"},
            )
            self.assertEqual(profile, profile_path)
            self.assertTrue(profile_path.is_dir())
            self.assertEqual(environment[PROFILE_ENV], str(profile_path))

    def test_persistent_context_requires_user_data_dir(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "persistent_context=True requires user_data_dir",
        ):
            validate_profile_options(True, None)

    def test_user_data_dir_requires_persistent_context(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "user_data_dir requires persistent_context=True",
        ):
            validate_profile_options(False, "/data/profile")

    def test_relative_profile_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be an absolute path"):
            validate_profile_options(True, "relative/profile")

    def test_non_directory_profile_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            profile_path = Path(temporary) / "profile"
            profile_path.write_text("not a directory", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "is not a directory"):
                validate_profile_options(True, profile_path)

    def test_read_only_profile_fails_without_fallback(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root can bypass directory write mode bits")
        with tempfile.TemporaryDirectory() as temporary:
            profile_path = Path(temporary) / "profile"
            profile_path.mkdir(mode=0o500)
            try:
                with self.assertRaisesRegex(PermissionError, "is not writable"):
                    validate_profile_options(True, profile_path)
            finally:
                profile_path.chmod(0o700)

    def test_process_environment_is_not_mutated(self) -> None:
        sentinel = object()
        previous = os.environ.get(PROFILE_ENV, sentinel)
        try:
            os.environ.pop(PROFILE_ENV, None)
            with tempfile.TemporaryDirectory() as temporary:
                build_child_environment(True, Path(temporary) / "profile")
            self.assertNotIn(PROFILE_ENV, os.environ)
        finally:
            if previous is sentinel:
                os.environ.pop(PROFILE_ENV, None)
            else:
                os.environ[PROFILE_ENV] = previous  # type: ignore[assignment]

    def test_browser_environment_forces_x11(self) -> None:
        environment = build_browser_environment(
            {
                "DISPLAY": ":1",
                "GDK_BACKEND": "wayland",
                "MOZ_ENABLE_WAYLAND": "1",
                "WAYLAND_DISPLAY": "wayland-0",
            }
        )
        self.assertEqual(environment["DISPLAY"], ":1")
        self.assertEqual(environment["GDK_BACKEND"], "x11")
        self.assertEqual(environment["MOZ_ENABLE_WAYLAND"], "0")
        self.assertEqual(environment["XDG_CACHE_HOME"], "/config/.cache")
        self.assertNotIn("WAYLAND_DISPLAY", environment)

    def test_browser_environment_merges_launch_overrides(self) -> None:
        environment = build_browser_environment({"CAMOUFOX_TEST_OVERRIDE": "set"})
        self.assertEqual(environment["CAMOUFOX_TEST_OVERRIDE"], "set")
        self.assertIn("PATH", environment)

    def test_websocket_path_is_normalized(self) -> None:
        self.assertEqual(normalize_websocket_path("agents/camoufox"), "/agents/camoufox")
        self.assertEqual(normalize_websocket_path("/fixed"), "/fixed")

    def test_invalid_websocket_paths_are_rejected(self) -> None:
        for value in ("", "ws://localhost/path", "/path?token=value", "/with space"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_websocket_path(value)


class EntrypointOptionTests(unittest.TestCase):
    @staticmethod
    def arguments(**overrides: object) -> argparse.Namespace:
        defaults = {
            "port": None,
            "ws_path": None,
            "persistent_context": None,
            "user_data_dir": None,
            "debug": None,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_environment_defaults_to_ephemeral(self) -> None:
        settings = resolve_settings(self.arguments(), {})
        self.assertEqual(settings, (1234, None, False, None, False))

    def test_environment_enables_persistent_mode(self) -> None:
        settings = resolve_settings(
            self.arguments(),
            {
                "CAMOUFOX_PORT": "4321",
                "CAMOUFOX_WS_PATH": "agents/camoufox",
                "CAMOUFOX_PERSISTENT_CONTEXT": "true",
                "CAMOUFOX_USER_DATA_DIR": "/data/profile",
                "CAMOUFOX_DEBUG": "yes",
            },
        )
        self.assertEqual(settings, (4321, "/agents/camoufox", True, "/data/profile", True))

    def test_cli_overrides_environment(self) -> None:
        settings = resolve_settings(
            self.arguments(
                port=5678,
                ws_path="/cli-path",
                persistent_context=False,
                user_data_dir=None,
                debug=False,
            ),
            {
                "CAMOUFOX_PORT": "4321",
                "CAMOUFOX_PERSISTENT_CONTEXT": "true",
                "CAMOUFOX_USER_DATA_DIR": "/data/profile",
                "CAMOUFOX_DEBUG": "true",
            },
        )
        # An env profile without persistent mode remains visible and is rejected
        # later by the same profile option validator.
        self.assertEqual(settings, (5678, "/cli-path", False, "/data/profile", False))
        with self.assertRaisesRegex(ValueError, "requires persistent_context=True"):
            validate_profile_options(settings[2], settings[3])

    def test_invalid_boolean_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be true or false"):
            parse_boolean("sometimes", "CAMOUFOX_DEBUG")


if __name__ == "__main__":
    unittest.main()
