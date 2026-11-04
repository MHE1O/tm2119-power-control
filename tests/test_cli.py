import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "power"))

from tm2119_power.cli import main


class CliTests(unittest.TestCase):
    @patch("tm2119_power.cli.SystemBackend")
    def test_set_delegates_hardware_application_to_running_service(self, backend_type):
        backend = backend_type.return_value

        self.assertEqual(main(["set", "balanced"]), 0)

        backend.set_gnome_profile.assert_called_once_with("balanced")
        backend.apply_profile.assert_not_called()

    @patch("tm2119_power.cli.SystemBackend")
    def test_cycle_updates_gnome_without_direct_hardware_write(self, backend_type):
        backend = backend_type.return_value
        backend.get_stnm.return_value = 0x01

        self.assertEqual(main(["cycle"]), 0)

        backend.set_gnome_profile.assert_called_once_with("performance")
        backend.apply_profile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
