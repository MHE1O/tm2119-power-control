#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

VERSION=26.2.6
ARCHIVE_SHA256=b9436b3e1a8be76fbd4823dc884f90596ab7c6ac5e1867a305e66ffccfb31a92
UPSTREAM="https://archive.mesa3d.org/mesa-$VERSION.tar.xz"
PATCH="$ROOT/patches/mesa-rembrandt-empty-sa-ps-cu-mask.patch"
ARCHIVE="$ROOT/.build/mesa-$VERSION.tar.xz"
SOURCE="${TM2119_MESA_SOURCE:-$ROOT/.build/mesa-$VERSION}"
BUILD="${TM2119_MESA_BUILD:-$ROOT/.build/mesa-$VERSION-radv}"
JOBS="${TM2119_JOBS:-4}"
DESTDIR="${DESTDIR:-}"
BUILD_ONLY=0
INSTALL_DEPS=0

for arg in "$@"; do
    case "$arg" in
        --build-only) BUILD_ONLY=1 ;;
        --install-deps) INSTALL_DEPS=1 ;;
        *) fail "Unknown argument: $arg" ;;
    esac
done

if [ "$INSTALL_DEPS" = 1 ]; then
    [ "$(id -u)" = 0 ] || fail "Dependency installation requires root"
    install_mesa_build_dependencies "$(detect_package_manager)"
fi
if [ "$BUILD_ONLY" = 0 ] && [ -z "$DESTDIR" ]; then
    [ "$(id -u)" = 0 ] || fail "Run this script as root, use --build-only, or set DESTDIR for staging"
fi

install -d "$ROOT/.build"
if [ ! -f "$SOURCE/src/amd/common/ac_gpu_info.c" ]; then
    [ "$SOURCE" = "$ROOT/.build/mesa-$VERSION" ] || \
        fail "Custom TM2119_MESA_SOURCE does not contain Mesa sources: $SOURCE"
    if [ ! -f "$ARCHIVE" ]; then
        curl -fL --retry 3 "$UPSTREAM" -o "$ARCHIVE"
    fi
    echo "$ARCHIVE_SHA256  $ARCHIVE" | sha256sum -c -
    tar -xJf "$ARCHIVE" -C "$ROOT/.build"
fi

if patch -s -d "$SOURCE" -p1 --dry-run < "$PATCH" >/dev/null 2>&1; then
    patch -s -d "$SOURCE" -p1 < "$PATCH"
elif patch -s -d "$SOURCE" -p1 --reverse --dry-run < "$PATCH" >/dev/null 2>&1; then
    : # The requested patch is already applied.
else
    fail "Mesa source is neither compatible with nor already patched by $PATCH"
fi

MESON_OPTIONS=(
    --buildtype=release
    -Dgallium-drivers=
    -Dvulkan-drivers=amd
    -Dplatforms=x11,wayland
    -Dllvm=disabled
    -Dvalgrind=disabled
    -Dlibunwind=disabled
    -Dbuild-tests=false
    -Dtools=
)
if [ -f "$BUILD/meson-private/coredata.dat" ]; then
    meson setup --reconfigure "$BUILD" "$SOURCE" "${MESON_OPTIONS[@]}"
else
    meson setup "$BUILD" "$SOURCE" "${MESON_OPTIONS[@]}"
fi
ninja -C "$BUILD" -j "$JOBS"

DRIVER="$BUILD/src/amd/vulkan/libvulkan_radeon.so"
[ -f "$DRIVER" ] || fail "Mesa build did not produce $DRIVER"
if [ "$BUILD_ONLY" = 1 ]; then
    echo "Built patched RADV: $DRIVER"
    exit 0
fi

LIB_DIR="$DESTDIR/usr/local/lib/tm2119-power/mesa"
BIN_DIR="$DESTDIR/usr/local/bin"
install -d "$LIB_DIR" "$BIN_DIR"
install -m 0755 "$DRIVER" "$LIB_DIR/libvulkan_radeon.so"
install -m 0755 "$ROOT/scripts/tm2119-cu-fix.sh" "$BIN_DIR/tm2119-cu-fix"

if [ -z "$DESTDIR" ]; then
    rm -f /etc/environment.d/90-tm2119-radv.conf /etc/profile.d/tm2119-radv.sh \
        /usr/local/share/vulkan/icd.d/tm2119_radeon_icd.x86_64.json
    unset VK_ICD_FILENAMES VK_DRIVER_FILES
    "$BIN_DIR/tm2119-cu-fix" fix
    echo "Installed patched RADV in place; restart running games to load it."
else
    echo "Staged patched RADV and tm2119-cu-fix under $DESTDIR"
fi
