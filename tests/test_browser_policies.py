from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.configure_camoufox_policies import (
    PolicyError,
    configure_password_manager,
    parse_boolean,
)


class BrowserPolicyTests(unittest.TestCase):
    def test_enables_password_manager_and_preserves_other_policies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "policies.json"
            target.write_text(
                json.dumps(
                    {
                        "policies": {
                            "DisableTelemetry": True,
                            "OfferToSaveLogins": False,
                            "PasswordManagerEnabled": False,
                        }
                    }
                ),
                encoding="utf-8",
            )

            configure_password_manager(target, True)
            policies = json.loads(target.read_text(encoding="utf-8"))["policies"]

            self.assertIs(policies["OfferToSaveLogins"], True)
            self.assertIs(policies["PasswordManagerEnabled"], True)
            self.assertIs(policies["DisableTelemetry"], True)

    def test_disables_password_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "policies.json"
            target.write_text('{"policies": {}}\n', encoding="utf-8")

            configure_password_manager(target, False)
            policies = json.loads(target.read_text(encoding="utf-8"))["policies"]

            self.assertIs(policies["OfferToSaveLogins"], False)
            self.assertIs(policies["PasswordManagerEnabled"], False)

    def test_missing_policies_object_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "policies.json"
            target.write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(PolicyError, "no policies object"):
                configure_password_manager(target, True)

    def test_boolean_values(self) -> None:
        for value in ("1", "true", "YES", "on"):
            self.assertIs(parse_boolean(value), True)
        for value in ("0", "false", "NO", "off"):
            self.assertIs(parse_boolean(value), False)
        with self.assertRaisesRegex(ValueError, "must be true or false"):
            parse_boolean("sometimes")


if __name__ == "__main__":
    unittest.main()
