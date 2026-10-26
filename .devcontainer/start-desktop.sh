#!/usr/bin/env bash
# Start the OpenSesame GUI stack (Xvfb + fluxbox + x11vnc + noVNC) in the
# background. Safe to run repeatedly: services that are already up are left
# alone, so this can be used as the devcontainer postStartCommand.
set -u

DISPLAY_NUM="${DISPLAY_NUM:-0}"
NOVNC_PORT="${NOVNC_PORT:-8080}"
VNC_PORT="${VNC_PORT:-5900}"

running() {
    pgrep -f "$1" >/dev/null 2>&1
}

# noVNC/websockify is the last service to come up, so if it is running the
# rest of the stack is already up as well.
if running "websockify.*${NOVNC_PORT}"; then
    exit 0
fi

export DISPLAY=":${DISPLAY_NUM}"

# A container restart can leave a stale X lock/socket behind.
if ! running '^Xvfb'; then
    rm -f "/tmp/.X${DISPLAY_NUM}-lock" "/tmp/.X11-unix/X${DISPLAY_NUM}"
    nohup Xvfb "${DISPLAY}" -screen 0 1920x1080x24 >/tmp/xvfb.log 2>&1 &
    for _ in $(seq 1 40); do
        [ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ] && break
        sleep 0.25
    done
fi

running '^fluxbox' || nohup fluxbox >/tmp/fluxbox.log 2>&1 &
running '^x11vnc' || nohup x11vnc -display "${DISPLAY}" -nopw -listen localhost \
    -xkb -forever -shared >/tmp/x11vnc.log 2>&1 &

# Serve noVNC from a directory whose index.html points at vnc.html, so both
# http://localhost:8080/ and http://localhost:8080/vnc.html work.
WEB_ROOT="${HOME}/.novnc-web"
mkdir -p "${WEB_ROOT}"
for entry in /usr/share/novnc/*; do
    name="$(basename "${entry}")"
    [ "${name}" = "index.html" ] && continue
    ln -sfn "${entry}" "${WEB_ROOT}/${name}"
done
ln -sfn vnc.html "${WEB_ROOT}/index.html"

nohup websockify --web="${WEB_ROOT}" "${NOVNC_PORT}" "localhost:${VNC_PORT}" \
    >/tmp/websockify.log 2>&1 &

# Wait until the web frontend answers before returning.
for _ in $(seq 1 40); do
    if curl -fsS -o /dev/null "http://localhost:${NOVNC_PORT}/vnc.html" 2>/dev/null; then
        exit 0
    fi
    sleep 0.25
done

echo "noVNC failed to start, see /tmp/websockify.log and /tmp/x11vnc.log" >&2
exit 1
