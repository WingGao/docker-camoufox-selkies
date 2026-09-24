#!/usr/bin/env python3
"""Enable Firefox's local password manager in the Camoufox policy file."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_POLICY_FILE = Path("/opt/camoufox/browser/distribution/policies.json")
PASSWORD_MANAGER_ENV = "CAMOUFOX_PASSWORD_MANAGER_ENABLED"
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


class PolicyError(RuntimeError):
    """Raised when the Camoufox policy file has an unexpected structure."""


def parse_boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{PASSWORD_MANAGER_ENV} must be true or false, got {value!r}")


def configure_password_manager(target: Path, enabled: bool) -> None:
    document: Any = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("policies"), dict):
        raise PolicyError(f"Camoufox policy file has no policies object: {target}")

    password_policies = {
        "OfferToSaveLogins": enabled,
        "PasswordManagerEnabled": enabled,
    }
    document["policies"].update(password_policies)
    target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    saved = json.loads(target.read_text(encoding="utf-8"))
    if any(saved["policies"].get(name) is not value for name, value in password_policies.items()):
        raise PolicyError(f"Unable to verify Camoufox password policies: {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, nargs="?", default=DEFAULT_POLICY_FILE)
    parser.add_argument("--enabled")
    args = parser.parse_args()
    try:
        configured = args.enabled
        if configured is None:
            configured = os.environ.get(PASSWORD_MANAGER_ENV, "true")
        enabled = parse_boolean(configured)
        configure_password_manager(args.target, enabled)
    except (OSError, ValueError, json.JSONDecodeError, PolicyError) as error:
        print(f"ERROR: {error}")
        return 1
    state = "enabled" if enabled else "disabled"
    print(f"Camoufox password manager {state}: {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
