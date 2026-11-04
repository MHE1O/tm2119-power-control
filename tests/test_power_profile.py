import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "power"))

from tm2119_power import ProfileController, next_stnm


class FakeBackend:
    def __init__(self):
        self.applied = []
        self.osd_events = []
        self.gnome_sets = []
        self.stnm = 0x01

    def apply_profile(self, profile):
        self.applied.append(profile)
        self.stnm = {"power-saver": 0x02, "balanced": 0x01, "performance": 0x03}[profile]

    def set_gnome_profile(self, profile):
        self.gnome_sets.append(profile)

    def show_osd(self, profile, source):
        self.osd_events.append((profile, source))


class ProfileControllerTests(unittest.TestCase):
    def test_gnome_selection_applies_matching_hardware_profile_and_osd(self):
        backend = FakeBackend()
        controller = ProfileController(backend)

        controller.handle_gnome_profile("power-saver")

        self.assertEqual(backend.applied, ["power-saver"])
        self.assertEqual(backend.gnome_sets, [])
        self.assertEqual(backend.osd_events, [("power-saver", "GNOME")])

    def test_fn_k_ec_change_updates_gnome_reapplies_hac1_and_shows_osd(self):
        backend = FakeBackend()
        backend.stnm = 0x03
        controller = ProfileController(backend)

        controller.handle_hotkey(0x03)

        self.assertEqual(backend.gnome_sets, ["performance"])
        self.assertEqual(backend.applied, ["performance"])
        self.assertEqual(backend.osd_events, [("performance", "Fn+K")])

    def test_profile_cycle_follows_eco_balanced_turbo_order(self):
        self.assertEqual(next_stnm(0x02), 0x01)
        self.assertEqual(next_stnm(0x01), 0x03)
        self.assertEqual(next_stnm(0x03), 0x02)


if __name__ == "__main__":
    unittest.main()
