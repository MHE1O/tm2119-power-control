# TM2119 Power Control

Native Linux power-profile control for the **Xiaomi Book Pro 14 2022 (TM2119 / XMCC2119)** with a Ryzen 6000 Rembrandt APU.

It connects Xiaomi's firmware profile table to GNOME: **Fn+K**, GNOME Quick Settings, hardware power limits, CPU energy-performance preference, and a native GNOME Shell OSD stay synchronized in both directions.

> **Model-specific software:** use only on TM2119 / XMCC2119. The ACPI methods and profile values are not generic Xiaomi laptop controls.

## Features

- **Eco / Power Saver:** 20 W slow PPT, 35 W fast PPT, `power` EPP.
- **Balanced:** 48 W slow PPT, 60 W fast PPT, `balance_performance` EPP.
- **Turbo / Performance:** 54 W slow PPT, 65 W fast PPT, `performance` EPP.
- Fn+K cycling through Xiaomi WMI event `0x16`, with EC state polling as fallback.
- Two-way synchronization with `power-profiles-daemon` and GNOME Quick Settings.
- Native GNOME Shell OSD on GNOME **45, 46, 47, 48, 49, and 50**—no notification daemon required.
- Automatic dependencies, patched PPD build, `acpi_call` setup, CLI, systemd service, and user extension installation.
- A minimal, source-verified Mesa RADV correction for Rembrandt systems whose empty second shader array incorrectly restricts pixel shaders to two of six CUs.
- Arch Linux, Fedora / Nobara, and Ubuntu / Debian package-manager support.

## Installation

Run from a logged-in GNOME desktop session. The installer requests root privileges with `sudo` when necessary.

**Arch Linux**

```sh
git clone https://github.com/MHE1O/tm2119-power-control.git && cd tm2119-power-control && ./install.sh
```

**Fedora / Nobara**

```sh
git clone https://github.com/MHE1O/tm2119-power-control.git && cd tm2119-power-control && ./install.sh
```

**Ubuntu / Debian**

```sh
git clone https://github.com/MHE1O/tm2119-power-control.git && cd tm2119-power-control && ./install.sh
```

The installer:

1. Installs ACPI, Python, PPD, compiler, and current-kernel header dependencies.
2. Compiles `tm2119-runtime.dsl` with `iasl` and installs the resulting AML.
3. Builds the pinned, TM2119-patched `power-profiles-daemon` and installs its systemd override.
4. Downloads checksum-verified Mesa 26.2.6, applies only the Rembrandt empty-shader-array correction, and builds RADV without the other graphics drivers.
5. Installs `tm2119-cu-fix`, backs up the distribution RADV library, and atomically installs the corrected driver at the distribution path so Steam and pressure-vessel use it without environment overrides.
6. Uses an existing `acpi_call` module or builds the bundled GPL source against the running kernel.
7. Installs and enables the root synchronization service, `/usr/local/bin/tm2119-power-profile`, and a service hook that reapplies the RADV correction after distribution Mesa updates.
8. Installs and enables the OSD extension for `$SUDO_USER` (or the user reported by `logname`).

An internet connection is required for package installation and the pinned PPD and Mesa source downloads. Secure Boot may require signing the locally built `acpi_call` module; use your distribution's module-signing process if unsigned module loading is blocked.

Restart games and other running Vulkan applications after installation. No custom Vulkan ICD, `VK_ICD_FILENAMES`, login-cycle, or desktop environment change is required.

After a kernel update, rerun `./install.sh` if `acpi_call` is unavailable for the new kernel. To build the RADV correction without installing it, run `scripts/build-install-radv-rembrandt.sh --build-only`; `DESTDIR=/path/to/stage` stages an installation without root privileges.

## Usage

Use **Fn+K**, GNOME Quick Settings, or:

```sh
tm2119-power-profile status
tm2119-power-profile set power-saver
tm2119-power-profile set balanced
tm2119-power-profile set performance
tm2119-power-profile cycle
tm2119-power-profile osd balanced
```

Check service health with:

```sh
systemctl status tm2119-power-profile.service
journalctl -u tm2119-power-profile.service
```

### Rembrandt CU diagnostic and rollback

```sh
tm2119-cu-fix check       # 0 = healthy/unaffected, 1 = affected driver is unpatched
sudo tm2119-cu-fix fix    # back up stock RADV and install the correction
sudo tm2119-cu-fix restore # roll back to the latest backed-up stock RADV
```

The checker reads the RADV topology reported by `vulkaninfo` and looks for AMD `0x1002:0x1681`, two shader arrays per SE, and an empty `SE0/SA1`. It detects `/usr/lib64/libvulkan_radeon.so` on Fedora/RHEL, `/usr/lib/libvulkan_radeon.so` on Arch, and `/usr/lib/x86_64-linux-gnu/libvulkan_radeon.so` on Ubuntu/Debian. Stock backups live in `/var/lib/tm2119-power/backup/`; a distro update is backed up before the patched payload is reapplied. `tm2119-power-profile.service` runs the repair automatically whenever the service starts.

## Uninstallation

```sh
cd tm2119-power-control && ./uninstall.sh
```

This disables and removes the TM2119 service, CLI, runtime ACPI assets, boot module configuration, and OSD extension. It removes the custom PPD binary and systemd override, then restarts the distribution's stock `power-profiles-daemon`. Before removing the RADV payload and repair hook, it restores the latest stock driver from the backup. Distribution packages are left installed.

## Architecture

### Xiaomi firmware path

The runtime SSDT exposes a narrow wrapper around the firmware's **HAC1** AC profile table. `\APPL` selects the EC `STNM` mode and submits the correctly padded `SVRF` / ALIB `0x0C` payload. After every transition the service verifies **`\DPTC=0`**, preventing the broken dynamic thermal-query path from reaching the malformed `SVRP` buffer and its associated errors or unsafe thermal limit.

### Hotkey and GNOME synchronization

A root Python service joins the ACPI generic-netlink multicast group and accepts Xiaomi WMI notification `0x16`. It reads `\_SB.PCI0.WMID.EVFN`, allows `_Q24`'s HPTC path to finish, reapplies the safe HAC1 route, and updates GNOME through `powerprofilesctl`. GNOME ActiveProfile changes take the reverse path. If generic netlink is unavailable, the service polls EC STNM instead.

### PPD compatibility

The included patch is against PPD commit `1a151ccd8bb42c050960f65ca3dee31effde6b36`. It skips per-policy boost writes when global CPU boost is disabled and disables the generic `platform_profile` driver on this model; TM2119's service owns that firmware path instead.

### Rembrandt RADV correction

On the affected TM2119, Rembrandt reports six active CUs in SE0/SA0 and an empty SA1. Mesa's generic GFX10.3 pixel-shader heuristic interpreted that topology as asymmetric and returned a two-CU mask, restricting pixel shaders to one of three WGPs. The patch returns the full CU mask when an SE/SA slot is empty; it preserves the original heuristic when all populated arrays are genuinely asymmetric.

Validation through the unmodified Valheim capture harness showed repeatable default-present improvement from **22.297 FPS / 7.176 W GFX** to **44.948 and 44.962 FPS / 14.599 and 15.343 W GFX**. SQTT wave-cycle attribution changed from **97.46% / 1.27% / 1.26%** across WGP0/1/2 to **33.32% / 33.34% / 33.34%**. Immediate presentation measured **50.722 FPS** by elapsed time. These are sustained main-menu results, not a claim of identical playable-world Windows parity or a raw harness GREEN verdict.

The correction changes no firmware, ACPI, SMU, kernel, clock-gating, or power-limit state. Only RADV is replaced, using an atomic in-place install with a verified stock backup for rollback.

### Native OSD

The `xiaomi-power-osd@mhe10` extension exports `org.tm2119.PowerProfile.ShowProfile` on the GNOME Shell session bus. It uses `osdWindowManager.showOne()` on newer Shell releases and `osdWindowManager.show()` on GNOME 45–48.

## License

GPL-3.0-or-later. The bundled `acpi_call` source retains its original copyright and license; see `acpi-call/acpi_call.c` and `LICENSE`.
