"""TM2119 hardware and GNOME power-profile synchronization."""


PROFILES = ("power-saver", "balanced", "performance")
STNM_TO_PROFILE = {0x02: "power-saver", 0x01: "balanced", 0x03: "performance"}
PROFILE_TO_STNM = {profile: stnm for stnm, profile in STNM_TO_PROFILE.items()}
STNM_CYCLE = {0x02: 0x01, 0x01: 0x03, 0x03: 0x02}


def next_stnm(stnm):
    try:
        return STNM_CYCLE[stnm]
    except KeyError as error:
        raise ValueError(f"unsupported EC profile state: {stnm}") from error


class ProfileController:
    def __init__(self, backend):
        self.backend = backend

    def handle_gnome_profile(self, profile):
        if profile not in PROFILES:
            raise ValueError(f"unsupported power profile: {profile}")
        self.backend.apply_profile(profile)
        self.backend.show_osd(profile, "GNOME")

    def handle_hotkey(self, stnm):
        try:
            profile = STNM_TO_PROFILE[stnm]
        except KeyError as error:
            raise ValueError(f"unsupported EC profile state: {stnm}") from error
        self.backend.set_gnome_profile(profile)
        self.backend.apply_profile(profile)
        self.backend.show_osd(profile, "Fn+K")
