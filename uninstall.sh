#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ "$(id -u)" != 0 ]; then
    exec sudo "$0" "$@"
fi

# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"
UUID=xiaomi-power-osd@mhe10
STATE_DIR=/var/lib/tm2119-power

systemctl disable --now tm2119-power-profile.service 2>/dev/null || true
rm -f /etc/systemd/system/tm2119-power-profile.service
rm -f /etc/systemd/system/power-profiles-daemon.service.d/90-tm2119-boost.conf
rm -f /usr/local/libexec/power-profiles-daemon-tm2119
rm -f /usr/local/bin/tm2119-power-profile
rm -f /etc/modules-load.d/tm2119-power.conf
rm -rf /usr/local/lib/tm2119-power /usr/local/share/tm2119

if [ -f "$STATE_DIR/acpi-call-module" ]; then
    MODULE="$(< "$STATE_DIR/acpi-call-module")"
    case "$MODULE" in
        /lib/modules/*/extra/acpi_call.ko)
            rm -f "$MODULE"
            KERNEL="$(basename "$(dirname "$(dirname "$MODULE")")")"
            depmod -a "$KERNEL"
            ;;
    esac
fi
rm -rf "$STATE_DIR"

if [ -d /sys/kernel/config/acpi/table/tm2119 ]; then
    rmdir /sys/kernel/config/acpi/table/tm2119 || true
fi

if DESKTOP_USER="$(desktop_user)"; then
    USER_HOME="$(getent passwd "$DESKTOP_USER" | cut -d: -f6)"
    USER_UID="$(id -u "$DESKTOP_USER")"
    runuser -u "$DESKTOP_USER" -- env HOME="$USER_HOME" \
        XDG_RUNTIME_DIR="/run/user/$USER_UID" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_UID/bus" \
        gnome-extensions disable "$UUID" 2>/dev/null || true
    rm -rf "$USER_HOME/.local/share/gnome-shell/extensions/$UUID"
fi

systemctl daemon-reload
systemctl restart power-profiles-daemon.service
systemctl --no-pager --full is-active power-profiles-daemon.service
echo "Removed TM2119 Power Control and restored the distribution power-profiles-daemon."
