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
5. Installs the corrected RADV library and Vulkan ICD under `/usr/local` without replacing distribution Mesa files, then selects it through `/etc/environment.d` and `/etc/profile.d`.
6. Uses an existing `acpi_call` module or builds the bundled GPL source against the running kernel.
7. Installs and enables the root synchronization service and `/usr/local/bin/tm2119-power-profile`.
8. Installs and enables the OSD extension for `$SUDO_USER` (or the user reported by `logname`).

An internet connection is required for package installation and the pinned PPD and Mesa source downloads. Secure Boot may require signing the locally built `acpi_call` module; use your distribution's module-signing process if unsigned module loading is blocked.

**Log out and back in after installation** so desktop applications inherit `VK_ICD_FILENAMES=/usr/local/share/vulkan/icd.d/tm2119_radeon_icd.x86_64.json`. For the current shell only, run `source /etc/profile.d/tm2119-radv.sh`. Applications already running must be restarted.

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

## Uninstallation

```sh
cd tm2119-power-control && ./uninstall.sh
```

This disables and removes the TM2119 service, CLI, runtime ACPI assets, boot module configuration, and OSD extension. It removes the custom PPD binary and systemd override, then restarts the distribution's stock `power-profiles-daemon`. Distribution packages are left installed.

## Architecture

### Xiaomi firmware path

The runtime SSDT exposes a narrow wrapper around the firmware's **HAC1** AC profile table. `\APPL` selects the EC `STNM` mode and submits the correctly padded `SVRF` / ALIB `0x0C` payload. After every transition the service verifies **`\DPTC=0`**, preventing the broken dynamic thermal-query path from reaching the malformed `SVRP` buffer and its associated errors or unsafe thermal limit.

### Hotkey and GNOME synchronization

A root Python service joins the ACPI generic-netlink multicast group and accepts Xiaomi WMI notification `0x16`. It reads `\_SB.PCI0.WMID.EVFN`, allows `_Q24`'s HPTC path to finish, reapplies the safe HAC1 route, and updates GNOME through `powerprofilesctl`. GNOME ActiveProfile changes take the reverse path. If generic netlink is unavailable, the service polls EC STNM instead.

### PPD compatibility

The included patch is against PPD commit `1a151ccd8bb42c050960f65ca3dee31effde6b36`. It skips per-policy boost writes when global CPU boost is disabled and disables the generic `platform_profile` driver on this model; TM2119's service owns that firmware path instead.

### Native OSD

The `xiaomi-power-osd@mhe10` extension exports `org.tm2119.PowerProfile.ShowProfile` on the GNOME Shell session bus. It uses `osdWindowManager.showOne()` on newer Shell releases and `osdWindowManager.show()` on GNOME 45–48.

## License

GPL-3.0-or-later. The bundled `acpi_call` source retains its original copyright and license; see `acpi-call/acpi_call.c` and `LICENSE`.
