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

# Check each service independently so a crashed x11vnc/fluxbox is restarted
# even when websockify stayed up.
export DISPLAY=":${DISPLAY_NUM}"

# A container restart can leave a stale X lock/socket behind.
if ! running '^Xvfb'; then
    rm -f "/tmp/.X${DISPLAY_NUM}-lock" "/tmp/.X11-unix/X${DISPLAY_NUM}"
    setsid Xvfb "${DISPLAY}" -screen 0 1920x1080x24 </dev/null >/tmp/xvfb.log 2>&1 &
    for _ in $(seq 1 40); do
        [ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ] && break
        sleep 0.25
    done
fi

if ! running '^fluxbox'; then
    setsid fluxbox </dev/null >/tmp/fluxbox.log 2>&1 &
fi

if ! running '^x11vnc'; then
    setsid x11vnc -display "${DISPLAY}" -rfbport "${VNC_PORT}" -nopw -listen localhost \
        -xkb -forever -shared </dev/null >/tmp/x11vnc.log 2>&1 &
fi

if ! running "websockify.*${NOVNC_PORT}"; then
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

    setsid websockify --web="${WEB_ROOT}" "${NOVNC_PORT}" "localhost:${VNC_PORT}" \
        </dev/null >/tmp/websockify.log 2>&1 &
fi

# Wait until both x11vnc and the noVNC web frontend answer before returning.
for _ in $(seq 1 40); do
    if bash -c "exec 3<>/dev/tcp/localhost/${VNC_PORT}" 2>/dev/null \
        && curl -fsS -o /dev/null "http://localhost:${NOVNC_PORT}/vnc.html" 2>/dev/null; then
        exit 0
    fi
    sleep 0.25
done

echo "noVNC failed to start, see /tmp/websockify.log and /tmp/x11vnc.log" >&2
exit 1
