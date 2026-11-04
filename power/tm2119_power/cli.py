"""Command-line and systemd entry point for TM2119 power profiles."""

import argparse
import logging
import os

from . import PROFILE_TO_STNM, STNM_TO_PROFILE, next_stnm
from .system import SystemBackend


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tm2119-power-profile")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("daemon", help="synchronize Fn+K and GNOME continuously")
    subparsers.add_parser("status", help="show GNOME, EC, DPTC, and EPP state")
    for name, help_text in (
        ("apply", "apply hardware profile without changing GNOME"),
        ("set", "set both GNOME and hardware profiles"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("profile", choices=PROFILE_TO_STNM)
    subparsers.add_parser("cycle", help="cycle Eco, Balanced, Turbo")
    osd = subparsers.add_parser("osd", help="show a native GNOME Shell profile OSD")
    osd.add_argument("profile", choices=PROFILE_TO_STNM)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    backend = SystemBackend()
    if args.command == "daemon":
        if os.geteuid() != 0:
            parser.error("daemon must run as root")
        backend.daemon()
    elif args.command == "status":
        print(backend.status())
    elif args.command == "apply":
        backend.apply_profile(args.profile)
    elif args.command == "set":
        # The running service is the sole hardware writer; this avoids racing it.
        backend.set_gnome_profile(args.profile)
    elif args.command == "cycle":
        profile = STNM_TO_PROFILE[next_stnm(backend.get_stnm())]
        backend.set_gnome_profile(profile)
    elif args.command == "osd":
        backend.show_osd(args.profile, "Manual")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
