#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ "$(id -u)" != 0 ]; then
    exec sudo "$0" "$@"
fi

# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"
BOARD="$(< /sys/class/dmi/id/board_name)"
case "$BOARD" in
    TM2119|XMCC2119) ;;
    *) fail "Unsupported board '$BOARD'; this package supports only TM2119 / XMCC2119" ;;
esac
MANAGER="$(detect_package_manager)"
DESKTOP_USER="$(desktop_user)" || fail "Run from the GNOME user's session with sudo ./install.sh"
USER_HOME="$(getent passwd "$DESKTOP_USER" | cut -d: -f6)"
USER_UID="$(id -u "$DESKTOP_USER")"
KERNEL="$(uname -r)"
STATE_DIR=/var/lib/tm2119-power

echo "Installing TM2119 Power Control for $DESKTOP_USER ($MANAGER)"
install_runtime_dependencies "$MANAGER"
"$ROOT/scripts/build-install-power-profiles-daemon.sh" --install-deps
"$ROOT/scripts/build-install-radv-rembrandt.sh" --install-deps

iasl -ve -p "$ROOT/acpi/tm2119-runtime" "$ROOT/acpi/tm2119-runtime.dsl" >/dev/null

install -d /usr/local/lib/tm2119-power /usr/local/share/tm2119 \
    /usr/local/libexec /usr/local/bin \
    /etc/systemd/system/power-profiles-daemon.service.d "$STATE_DIR"
rm -rf /usr/local/lib/tm2119-power/tm2119_power
cp -a "$ROOT/power/tm2119_power" /usr/local/lib/tm2119-power/
install -m 0644 "$ROOT/acpi/tm2119-runtime.aml" /usr/local/share/tm2119/tm2119-runtime.aml
install -m 0755 "$ROOT/scripts/tm2119-power-profile" /usr/local/bin/tm2119-power-profile
install -m 0644 "$ROOT/modules-load/tm2119-power.conf" /etc/modules-load.d/tm2119-power.conf
install -m 0644 "$ROOT/systemd/tm2119-power-profile.service" /etc/systemd/system/tm2119-power-profile.service
install -m 0644 "$ROOT/systemd/power-profiles-daemon.tm2119.conf" \
    /etc/systemd/system/power-profiles-daemon.service.d/90-tm2119-boost.conf

rm -f /usr/local/lib/tm2119-power/acpi_call.ko
if ! modprobe acpi_call >/dev/null 2>&1; then
    [ -d "/lib/modules/$KERNEL/build" ] || fail "Kernel build directory is missing: /lib/modules/$KERNEL/build"
    ACPI_BUILD="$ROOT/.build/acpi-call"
    rm -rf "$ACPI_BUILD"
    install -d "$ACPI_BUILD"
    cp "$ROOT/acpi-call/acpi_call.c" "$ROOT/acpi-call/Makefile" "$ACPI_BUILD/"
    make -C "$ACPI_BUILD" KVER="$KERNEL"
    install -d "/lib/modules/$KERNEL/extra"
    install -m 0644 "$ACPI_BUILD/acpi_call.ko" "/lib/modules/$KERNEL/extra/acpi_call.ko"
    install -m 0644 "$ACPI_BUILD/acpi_call.ko" /usr/local/lib/tm2119-power/acpi_call.ko
    echo "/lib/modules/$KERNEL/extra/acpi_call.ko" > "$STATE_DIR/acpi-call-module"
    depmod -a "$KERNEL"
    modprobe acpi_call
fi
modprobe acpi_configfs

systemctl daemon-reload
systemctl restart power-profiles-daemon.service
systemctl enable tm2119-power-profile.service
systemctl restart tm2119-power-profile.service

runuser -u "$DESKTOP_USER" -- env HOME="$USER_HOME" \
    XDG_RUNTIME_DIR="/run/user/$USER_UID" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_UID/bus" \
    "$ROOT/scripts/install-power-osd.sh"

systemctl --no-pager --full is-active tm2119-power-profile.service power-profiles-daemon.service
echo "Installed. Current profile: $(powerprofilesctl get)"
echo "CLI: tm2119-power-profile status"
