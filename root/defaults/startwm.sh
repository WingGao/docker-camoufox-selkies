#!/usr/bin/env bash

set -u

DISABLE_ZINK_VALUE="${DISABLE_ZINK:-false}"

if which nvidia-smi > /dev/null 2>&1 && ls -A /dev/dri 2>/dev/null && [ "${DISABLE_ZINK_VALUE,,}" == "false" ]; then
  export LIBGL_KOPPER_DRI2=1
  export MESA_LOADER_DRIVER_OVERRIDE=zink
  export GALLIUM_DRIVER=zink
fi

AUTOSTART="${XDG_CONFIG_HOME:-${HOME}/.config}/openbox/autostart"
if [ ! -x "${AUTOSTART}" ]; then
  AUTOSTART=/defaults/autostart
fi

exec dbus-launch --exit-with-session /bin/bash -s -- "${AUTOSTART}" <<'SESSION'
set -u

AUTOSTART="$1"

# Start the window manager before applications so the first browser window is
# decorated and registered in the task list.
/usr/bin/xfwm4 &
WM_PID=$!
/usr/bin/xfce4-panel --sm-client-disable &
PANEL_PID=$!

# The stock panel layout includes a task list and workspace pager. Make the
# task list behave like a conventional desktop taskbar: show every window,
# including windows on other workspaces, without grouping separate windows.
for _ in $(seq 1 20); do
  TASKLIST_PATH="$(xfconf-query -c xfce4-panel -lv 2>/dev/null \
    | awk '$2 == "tasklist" { print $1; exit }')"
  if [ -n "${TASKLIST_PATH}" ]; then
    xfconf-query --channel xfce4-panel --property "${TASKLIST_PATH}/grouping" \
      --create --type uint --set 0
    xfconf-query --channel xfce4-panel --property "${TASKLIST_PATH}/include-all-workspaces" \
      --create --type bool --set true

    # Debian's default layout puts the task list on a top panel and adds a
    # second launcher panel at the bottom. Keep one Windows-like bottom bar.
    xfconf-query --channel xfce4-panel --property /panels/panel-1/position \
      --create --type string --set 'p=10;x=0;y=0'
    xfconf-query --channel xfce4-panel --property /panels/panel-2/autohide-behavior \
      --create --type uint --set 2
    break
  fi
  sleep 0.1
done

# Selkies stores the application launcher in the Openbox config path for
# compatibility. Keep that stable path even though xfwm4 now owns the session.
"${AUTOSTART}" &
APP_PID=$!

cleanup() {
  kill "${APP_PID}" "${PANEL_PID}" "${WM_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# The desktop session remains alive as long as the window manager does.
wait "${WM_PID}"
SESSION
