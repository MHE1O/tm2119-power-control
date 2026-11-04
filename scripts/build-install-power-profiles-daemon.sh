#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

UPSTREAM=https://gitlab.freedesktop.org/upower/power-profiles-daemon.git
VERSION=1a151ccd8bb42c050960f65ca3dee31effde6b36
SOURCE="${TM2119_PPD_SOURCE:-$ROOT/.build/power-profiles-daemon}"
BUILD="$SOURCE/_build"
PATCH="$ROOT/patches/power-profiles-daemon-tm2119.patch"
BINARY=/usr/local/libexec/power-profiles-daemon-tm2119

[ "$(id -u)" = 0 ] || fail "Run this script as root"
if [ "${1:-}" = --install-deps ]; then
    install_ppd_build_dependencies "$(detect_package_manager)"
fi

if [ ! -d "$SOURCE/.git" ]; then
    git clone --no-checkout "$UPSTREAM" "$SOURCE"
    git -C "$SOURCE" checkout --detach "$VERSION"
fi

if [ "$(git -C "$SOURCE" rev-parse HEAD)" != "$VERSION" ]; then
    fail "Unexpected power-profiles-daemon revision in $SOURCE"
fi

if git -C "$SOURCE" diff --quiet && git -C "$SOURCE" diff --cached --quiet; then
    git -C "$SOURCE" apply "$PATCH"
elif ! git -C "$SOURCE" apply --reverse --check "$PATCH" >/dev/null 2>&1; then
    fail "Source contains changes other than the TM2119 patch: $SOURCE"
fi

if [ -f "$BUILD/meson-private/coredata.dat" ]; then
    meson setup --wipe "$BUILD" "$SOURCE" -Dprefix=/usr -Dtests=false -Dmanpage=disabled
else
    meson setup "$BUILD" "$SOURCE" -Dprefix=/usr -Dtests=false -Dmanpage=disabled
fi
ninja -C "$BUILD"
install -d /usr/local/libexec
install -m 0755 "$BUILD/src/power-profiles-daemon" "$BINARY"
