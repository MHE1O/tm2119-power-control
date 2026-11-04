import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "power"))

from tm2119_power.acpi_events import parse_events


class AcpiEventTests(unittest.TestCase):
    def test_parse_wmi_notification_from_acpi_generic_netlink(self):
        event = bytearray(44)
        event[:4] = b"wmi\0"
        event[20:31] = b"PNP0C14:00\0"
        struct.pack_into("=I", event, 36, 0x20)
        payload = b"\x03\x01\x00\x00" + struct.pack("=HH", 48, 1) + event
        message = struct.pack("=IHHII", 16 + len(payload), 0x1A, 0, 1, 0) + payload

        self.assertEqual(parse_events(message), [("wmi", "PNP0C14:00", 0x20)])


if __name__ == "__main__":
    unittest.main()
