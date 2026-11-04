#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UUID=xiaomi-power-osd@mhe10
TARGET="$HOME/.local/share/gnome-shell/extensions/$UUID"

[ "$(id -u)" != 0 ] || { echo "Run this installer as the GNOME user, without sudo" >&2; exit 1; }
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"
gnome-extensions disable xiaomi-profile-osd@mhe10 2>/dev/null || true
gnome-extensions disable "$UUID" 2>/dev/null || true
mkdir -p "$(dirname "$TARGET")"
rm -rf "$TARGET"
cp -a "$ROOT/gnome-extension/$UUID" "$TARGET"
gnome-extensions enable "$UUID"
if [ -S "$XDG_RUNTIME_DIR/bus" ]; then
    sleep 1
    if ! gdbus call --session --dest org.gnome.Shell --object-path /org/tm2119/PowerProfile \
        --method org.tm2119.PowerProfile.ShowProfile balanced Installer; then
        echo "OSD installed; log out and back in if GNOME Shell has not loaded it yet"
    fi
else
    echo "OSD installed; it will activate at the next GNOME login"
fi
