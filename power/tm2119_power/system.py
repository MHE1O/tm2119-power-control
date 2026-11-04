"""Linux system adapter for TM2119 power-profile control."""

from __future__ import annotations

import glob
import logging
import os
from pathlib import Path
import pwd
import re
import subprocess
import time

from . import PROFILE_TO_STNM, PROFILES


LOG = logging.getLogger("tm2119-power")
ACPI_CALL = Path("/proc/acpi/call")
ACPI_TABLE = Path("/sys/kernel/config/acpi/table/tm2119")
DEFAULT_AML = Path("/usr/local/share/tm2119/tm2119-runtime.aml")
DEFAULT_ACPI_CALL_KO = Path("/usr/local/lib/tm2119-power/acpi_call.ko")
CPUFREQ_POLICIES = "/sys/devices/system/cpu/cpufreq/policy*"
PPD_DEST = "org.freedesktop.UPower.PowerProfiles"
PPD_PATH = "/org/freedesktop/UPower/PowerProfiles"
PPD_INTERFACE = "org.freedesktop.UPower.PowerProfiles"

PROFILE_INFO = {
    "power-saver": (
        "Power Saver (Eco)",
        "20 W sustained · 35 W fast",
        "power-profile-power-saver-symbolic",
        ("power", "balance_power", "default"),
    ),
    "balanced": (
        "Balanced",
        "48 W sustained · 60 W fast",
        "power-profile-balanced-symbolic",
        ("balance_performance", "balance_power", "default", "performance"),
    ),
    "performance": (
        "Performance (Turbo)",
        "54 W sustained · 65 W fast",
        "power-profile-performance-symbolic",
        ("performance",),
    ),
}


class SystemBackend:
    def __init__(self, aml_path: Path | None = None):
        self.aml_path = aml_path or Path(os.environ.get("TM2119_AML", DEFAULT_AML))
        self._acpi_ready = False

    def acpi(self, expression: str) -> str:
        """Execute a known, fixed ACPI expression through acpi_call."""
        with ACPI_CALL.open("w", encoding="ascii") as stream:
            stream.write(expression)
        raw = ACPI_CALL.read_bytes().replace(b"\0", b"").decode("utf-8", "replace").strip()
        if "Error" in raw or raw.startswith("AE_"):
            raise RuntimeError(f"ACPI call {expression!r} failed: {raw}")
        return raw

    @staticmethod
    def _acpi_integer(raw: str) -> int:
        match = re.search(r"0x[0-9a-fA-F]+|\b\d+\b", raw)
        if not match:
            raise RuntimeError(f"ACPI returned no integer: {raw!r}")
        return int(match.group(0), 0)

    def ensure_acpi(self) -> None:
        if self._acpi_ready:
            return
        if not self.aml_path.is_file():
            raise RuntimeError(f"runtime SSDT not found: {self.aml_path}")
        subprocess.run(["modprobe", "acpi_configfs"], check=True)
        if not ACPI_CALL.exists():
            subprocess.run(["modprobe", "acpi_call"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not ACPI_CALL.exists():
            module = Path(os.environ.get("TM2119_ACPI_CALL_KO", DEFAULT_ACPI_CALL_KO))
            subprocess.run(["insmod", str(module)], check=True)
        if not ACPI_TABLE.exists():
            ACPI_TABLE.mkdir(parents=True)
            (ACPI_TABLE / "aml").write_bytes(self.aml_path.read_bytes())
        # Resolve all methods before considering the table ready.
        self.acpi(r"\GPTI")
        self._acpi_ready = True

    def get_stnm(self) -> int:
        self.ensure_acpi()
        return self._acpi_integer(self.acpi(r"\GETM"))

    def get_dptc(self) -> int:
        self.ensure_acpi()
        return self._acpi_integer(self.acpi(r"\ADPT"))

    def get_gnome_profile(self) -> str:
        result = subprocess.run(
            [
                "gdbus", "call", "--system", "--dest", PPD_DEST,
                "--object-path", PPD_PATH, "--method",
                "org.freedesktop.DBus.Properties.Get", PPD_INTERFACE, "ActiveProfile",
            ],
            check=True, capture_output=True, text=True, timeout=5,
        )
        match = re.search(r"<['\"]([a-z-]+)['\"]>", result.stdout)
        if not match or match.group(1) not in PROFILES:
            raise RuntimeError(f"could not read GNOME ActiveProfile: {result.stdout.strip()}")
        return match.group(1)

    def set_gnome_profile(self, profile: str) -> None:
        if profile not in PROFILES:
            raise ValueError(f"unsupported power profile: {profile}")
        # powerprofilesctl is the supported command-line client for PPD's D-Bus API.
        subprocess.run(["powerprofilesctl", "set", profile], check=True, timeout=8)

    def sync_epp(self, profile: str) -> None:
        candidates = PROFILE_INFO[profile][3]
        for policy in glob.glob(CPUFREQ_POLICIES):
            policy_path = Path(policy)
            preference = policy_path / "energy_performance_preference"
            available_path = policy_path / "energy_performance_available_preferences"
            if not preference.exists() or not available_path.exists():
                continue
            available = available_path.read_text().split()
            target = next((item for item in candidates if item in available), None)
            if target is None or preference.read_text().strip() == target:
                continue
            try:
                preference.write_text(target)
            except OSError as error:
                LOG.warning("Cannot set EPP on %s to %s: %s", policy_path.name, target, error)

    def apply_profile(self, profile: str) -> None:
        if profile not in PROFILES:
            raise ValueError(f"unsupported power profile: {profile}")
        self.ensure_acpi()
        mode = PROFILE_TO_STNM[profile]
        self.acpi(rf"\APPL {mode:#x}")
        dptc = self.get_dptc()
        if dptc != 0:
            raise RuntimeError(f"DPTC lock failed: expected 0, got {dptc}")
        self.sync_epp(profile)
        LOG.info("Applied %s (HAC1 STNM=%d, DPTC=0)", profile, mode)

    def show_osd(self, profile: str, source: str) -> None:
        command = [
            "gdbus", "call", "--session", "--dest", "org.gnome.Shell",
            "--object-path", "/org/tm2119/PowerProfile", "--method",
            "org.tm2119.PowerProfile.ShowProfile", profile, source,
        ]
        for bus in glob.glob("/run/user/[0-9]*/bus"):
            runtime_dir = str(Path(bus).parent)
            uid = int(Path(runtime_dir).name)
            try:
                user = pwd.getpwuid(uid)
                env = {
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "DBUS_SESSION_BUS_ADDRESS": f"unix:path={bus}",
                    "XDG_RUNTIME_DIR": runtime_dir,
                    "HOME": user.pw_dir,
                }
                if os.geteuid() == uid:
                    child_env = os.environ.copy()
                    child_env.update(env)
                    subprocess.run(command, env=child_env, check=True, timeout=4,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif os.geteuid() == 0:
                    def demote():
                        os.setgroups([])
                        os.setgid(user.pw_gid)
                        os.setuid(uid)
                    subprocess.run(command, env=env, preexec_fn=demote, check=True, timeout=4,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError) as error:
                LOG.warning("Could not display OSD for uid %d: %s", uid, error)

    def daemon(self, poll_interval: float = 0.5) -> None:
        import select

        from . import ProfileController, STNM_TO_PROFILE
        from .acpi_events import AcpiEventListener

        controller = ProfileController(self)
        self.ensure_acpi()
        active = self.get_gnome_profile()
        self.apply_profile(active)
        last_gnome = active
        last_stnm = PROFILE_TO_STNM[active]
        try:
            listener = AcpiEventListener()
            LOG.info("Listening for Fn+K WMI event 0x16 and GNOME ActiveProfile")
        except OSError as error:
            listener = None
            LOG.warning("ACPI events unavailable (%s); using EC state polling", error)

        while True:
            try:
                handled_hotkey = False
                if listener is not None:
                    readable, _, _ = select.select([listener], [], [], poll_interval)
                    if readable:
                        for device_class, _bus_id, kind in listener.next_events():
                            if device_class != "wmi" or kind != 0x20:
                                continue
                            event = self._acpi_integer(self.acpi(r"\_SB.PCI0.WMID.EVFN"))
                            if event != 0x16:
                                continue
                            # _Q24 waits 500 ms before HPTC; apply the safe AC path after it.
                            time.sleep(0.55)
                            stnm = self.get_stnm()
                            controller.handle_hotkey(stnm)
                            last_gnome = STNM_TO_PROFILE[stnm]
                            last_stnm = stnm
                            handled_hotkey = True
                    if handled_hotkey:
                        continue
                else:
                    time.sleep(poll_interval)

                gnome = self.get_gnome_profile()
                stnm = self.get_stnm()
                if gnome != last_gnome:
                    controller.handle_gnome_profile(gnome)
                    last_gnome = gnome
                    last_stnm = PROFILE_TO_STNM[gnome]
                elif stnm != last_stnm:
                    controller.handle_hotkey(stnm)
                    last_gnome = STNM_TO_PROFILE[stnm]
                    last_stnm = stnm
            except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
                LOG.error("Profile synchronization failed: %s", error)
                time.sleep(max(poll_interval, 2.0))

    def status(self) -> str:
        lines = [f"GNOME ActiveProfile: {self.get_gnome_profile()}"]
        lines.append(f"EC STNM: {self.get_stnm():#04x}")
        lines.append(f"DPTC: {self.get_dptc():#04x}")
        preferences = []
        for policy in sorted(glob.glob(CPUFREQ_POLICIES)):
            path = Path(policy) / "energy_performance_preference"
            if path.exists():
                value = path.read_text().strip()
                if value not in preferences:
                    preferences.append(value)
        lines.append("CPU EPP: " + (", ".join(preferences) if preferences else "unavailable"))
        return "\n".join(lines)
