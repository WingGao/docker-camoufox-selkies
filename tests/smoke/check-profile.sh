#!/bin/sh
set -eu

processes="$(ps auxww)"
case "${CAMOUFOX_PERSISTENT_CONTEXT:-false}" in
  true|TRUE|1|yes|YES)
    printf '%s\n' "$processes" | grep -- "-profile ${CAMOUFOX_USER_DATA_DIR:?}"
    if printf '%s\n' "$processes" | grep -q -- '/tmp/playwright_firefoxdev_profile-'; then
      echo "persistent mode unexpectedly uses a temporary profile" >&2
      exit 1
    fi
    ;;
  *)
    printf '%s\n' "$processes" | grep -- '/tmp/playwright_firefoxdev_profile-'
    if [ -n "${CAMOUFOX_USER_DATA_DIR:-}" ] && printf '%s\n' "$processes" | grep -q -- "-profile ${CAMOUFOX_USER_DATA_DIR}"; then
      echo "ephemeral mode unexpectedly uses the persistent profile" >&2
      exit 1
    fi
    ;;
esac
