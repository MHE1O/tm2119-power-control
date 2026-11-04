#!/usr/bin/env bash
# Shared distro and desktop-user helpers. This file is sourced, not executed.

fail() {
    echo "Error: $*" >&2
    exit 1
}

detect_package_manager() {
    if command -v pacman >/dev/null 2>&1; then
        echo pacman
    elif command -v dnf >/dev/null 2>&1; then
        echo dnf
    elif command -v apt-get >/dev/null 2>&1; then
        echo apt
    else
        fail "Supported package managers: pacman, dnf, and apt-get"
    fi
}

install_runtime_dependencies() {
    local manager="$1"
    local kernel headers
    kernel="$(uname -r)"
    case "$manager" in
        pacman)
            case "$kernel" in
                *-lts) headers=linux-lts-headers ;;
                *-zen) headers=linux-zen-headers ;;
                *-hardened) headers=linux-hardened-headers ;;
                *) headers=linux-headers ;;
            esac
            pacman -S --needed --noconfirm acpica python power-profiles-daemon \
                "$headers" make gcc
            ;;
        dnf)
            dnf install -y acpica-tools python3 power-profiles-daemon \
                "kernel-devel-$kernel" kernel-headers make gcc
            ;;
        apt)
            apt-get update
            DEBIAN_FRONTEND=noninteractive apt-get install -y \
                acpica-tools python3 power-profiles-daemon \
                "linux-headers-$kernel" make gcc
            ;;
    esac
}

install_ppd_build_dependencies() {
    local manager="$1"
    case "$manager" in
        pacman)
            pacman -S --needed --noconfirm base-devel meson ninja git pkgconf \
                glib2 polkit upower libgudev systemd
            ;;
        dnf)
            dnf install -y meson ninja-build gcc git pkgconf-pkg-config \
                glib2-devel polkit-devel upower-devel libgudev-devel systemd-devel
            ;;
        apt)
            DEBIAN_FRONTEND=noninteractive apt-get install -y \
                build-essential meson ninja-build git pkg-config libglib2.0-dev \
                libpolkit-gobject-1-dev libupower-glib-dev libgudev-1.0-dev \
                libsystemd-dev
            ;;
    esac
}

install_mesa_build_dependencies() {
    local manager="$1"
    case "$manager" in
        pacman)
            pacman -S --needed --noconfirm base-devel meson ninja python \
                pkgconf curl ca-certificates xz patch bison flex glslang spirv-tools \
                libdrm libxcb libxshmfence libxrandr wayland wayland-protocols \
                libdisplay-info expat libelf zlib zstd
            ;;
        dnf)
            dnf install -y gcc gcc-c++ meson ninja-build python3 \
                pkgconf-pkg-config curl ca-certificates xz patch bison flex glslang \
                spirv-tools-devel libdrm-devel libxcb-devel libxshmfence-devel \
                libXrandr-devel wayland-devel wayland-protocols-devel \
                libdisplay-info-devel expat-devel libelf-devel zlib-devel zstd-devel
            ;;
        apt)
            DEBIAN_FRONTEND=noninteractive apt-get install -y \
                build-essential meson ninja-build python3 pkg-config curl \
                ca-certificates xz-utils patch bison flex glslang-tools spirv-tools \
                libdrm-dev libxcb1-dev libxcb-dri3-dev libxcb-present-dev \
                libxcb-shm-dev libxcb-sync-dev libxcb-xfixes0-dev libxcb-randr0-dev \
                libx11-xcb-dev libxshmfence-dev libxrandr-dev libwayland-dev \
                wayland-protocols libdisplay-info-dev libexpat1-dev libelf-dev \
                zlib1g-dev libzstd-dev
            ;;
    esac
}

desktop_user() {
    local user=
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != root ]; then
        user="$SUDO_USER"
    elif command -v logname >/dev/null 2>&1; then
        user="$(logname 2>/dev/null || true)"
    fi
    [ -n "$user" ] && [ "$user" != root ] && id "$user" >/dev/null 2>&1 || return 1
    echo "$user"
}
