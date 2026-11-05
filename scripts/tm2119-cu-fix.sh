#!/usr/bin/env bash
set -euo pipefail

VULKANINFO="${TM2119_VULKANINFO:-vulkaninfo}"
PATCHED="${TM2119_RADV_PATCHED:-/usr/local/lib/tm2119-power/mesa/libvulkan_radeon.so}"
BACKUP="${TM2119_RADV_BACKUP:-/var/lib/tm2119-power/backup/libvulkan_radeon.so.stock}"

fail() {
    echo "tm2119-cu-fix: $*" >&2
    exit 2
}

find_driver() {
    if [ -n "${TM2119_RADV_DRIVER:-}" ]; then
        [ -f "$TM2119_RADV_DRIVER" ] || fail "RADV driver not found: $TM2119_RADV_DRIVER"
        DRIVER="$TM2119_RADV_DRIVER"
        return 0
    fi
    for DRIVER in \
        /usr/lib64/libvulkan_radeon.so \
        /usr/lib/libvulkan_radeon.so \
        /usr/lib/x86_64-linux-gnu/libvulkan_radeon.so; do
        [ ! -f "$DRIVER" ] || return 0
    done
    fail "No supported distribution RADV driver found"
}

driver_is_patched() {
    [ -f "$PATCHED" ] && [ -f "$DRIVER" ] &&
        [ "$(sha256sum "$PATCHED" | cut -d' ' -f1)" = "$(sha256sum "$DRIVER" | cut -d' ' -f1)" ]
}

read_topology() {
    command -v "$VULKANINFO" >/dev/null 2>&1 || fail "vulkaninfo is required"
    INFO="$(mktemp)"
    trap 'rm -f "$INFO"' EXIT
    if ! env -u VK_ICD_FILENAMES -u VK_DRIVER_FILES RADV_DEBUG=info \
        "$VULKANINFO" >"$INFO" 2>&1; then
        fail "vulkaninfo could not query the GPU"
    fi

    VENDOR=0
    DEVICE=0
    EMPTY_SA1=0
    TWO_SA=0
    while IFS= read -r line; do
        [[ ! $line =~ vendorID[[:space:]]*=[[:space:]]*0x1002([[:space:]]|$) ]] || VENDOR=1
        [[ ! $line =~ deviceID[[:space:]]*=[[:space:]]*0x1681([[:space:]]|$) ]] || DEVICE=1
        [[ ! $line =~ cu_mask\[SE0\]\[SA1\][[:space:]]*=[[:space:]]*0x0([[:space:]]|$) ]] || EMPTY_SA1=1
        [[ ! $line =~ max_sa_per_se[[:space:]]*=[[:space:]]*2([[:space:]]|$) ]] || TWO_SA=1
    done <"$INFO"
}

affected_topology() {
    [ "$VENDOR" = 1 ] && [ "$DEVICE" = 1 ] && [ "$EMPTY_SA1" = 1 ] && [ "$TWO_SA" = 1 ]
}

check() {
    read_topology
    if ! affected_topology; then
        echo "Healthy: no Rembrandt GPU with an empty SA1 was detected."
        return 0
    fi
    find_driver
    if driver_is_patched; then
        echo "Healthy: patched RADV is installed for the Rembrandt empty-SA1 topology."
        return 0
    fi
    echo "Bug present: Rembrandt has an empty SA1, but $DRIVER is not the patched RADV."
    return 1
}

fix() {
    read_topology
    if ! affected_topology; then
        echo "No affected Rembrandt topology; leaving RADV unchanged."
        return 0
    fi
    find_driver
    if driver_is_patched; then
        echo "Patched RADV is already installed."
        return 0
    fi
    [ -f "$PATCHED" ] || fail "Patched RADV payload not found: $PATCHED"

    # Refresh the rollback copy whenever a distro update supplies a new stock build.
    install -d "$(dirname "$BACKUP")"
    cp -p "$DRIVER" "$BACKUP.tm2119-new"
    mv "$BACKUP.tm2119-new" "$BACKUP"
    install -m 0755 "$PATCHED" "$DRIVER.tm2119-new"
    mv "$DRIVER.tm2119-new" "$DRIVER"
    driver_is_patched || fail "Patched RADV verification failed"
    echo "Installed patched RADV at $DRIVER; stock backup: $BACKUP"
}

restore() {
    find_driver
    if ! driver_is_patched; then
        echo "Distribution RADV is already in place; no rollback needed."
        return 0
    fi
    [ -f "$BACKUP" ] || fail "Stock RADV backup not found: $BACKUP"
    [ "$(sha256sum "$BACKUP" | cut -d' ' -f1)" != "$(sha256sum "$PATCHED" | cut -d' ' -f1)" ] ||
        fail "Refusing to restore a backup that matches the patched driver"
    cp -p "$BACKUP" "$DRIVER.tm2119-new"
    mv "$DRIVER.tm2119-new" "$DRIVER"
    [ "$(sha256sum "$BACKUP" | cut -d' ' -f1)" = "$(sha256sum "$DRIVER" | cut -d' ' -f1)" ] ||
        fail "Stock RADV rollback verification failed"
    echo "Restored stock RADV from $BACKUP"
}

case "${1:-check}" in
    check|--check) check ;;
    fix|--fix) fix ;;
    restore|--restore) restore ;;
    *) fail "Usage: tm2119-cu-fix [check|fix|restore]" ;;
esac
