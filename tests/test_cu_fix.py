import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tm2119-cu-fix.sh"

AFFECTED_GPU = """GPU0:
    vendorID = 0x1002
    deviceID = 0x1681
Shader core info:
    cu_mask[SE0][SA0] = 0x3f (6) CU_EN = 0x3f
    cu_mask[SE0][SA1] = 0x0 (0) CU_EN = 0x0
    min_good_cu_per_sa = 2
    max_sa_per_se = 2
"""


class CuFixTests(unittest.TestCase):
    def fixture(self, temporary, gpu_info=AFFECTED_GPU):
        root = Path(temporary)
        driver = root / "usr/lib64/libvulkan_radeon.so"
        patched = root / "patched/libvulkan_radeon.so"
        backup = root / "backup/libvulkan_radeon.so.stock"
        driver.parent.mkdir(parents=True)
        patched.parent.mkdir(parents=True)
        driver.write_text("stock driver\n")
        patched.write_text("patched driver\n")
        vulkaninfo = root / "bin/vulkaninfo"
        vulkaninfo.parent.mkdir()
        vulkaninfo.write_text(
            f"#!/bin/sh\n[ \"${{RADV_DEBUG:-}}\" = info ] || exit 0\ncat >&2 <<'EOF'\n{gpu_info}EOF\n"
        )
        vulkaninfo.chmod(0o755)
        env = os.environ.copy()
        env.update({
            "TM2119_RADV_DRIVER": str(driver),
            "TM2119_RADV_PATCHED": str(patched),
            "TM2119_RADV_BACKUP": str(backup),
            "TM2119_VULKANINFO": str(vulkaninfo),
        })
        return driver, patched, backup, env

    def test_check_reports_affected_stock_driver_as_unhealthy(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, env = self.fixture(temporary)
            result = subprocess.run(
                ["bash", str(SCRIPT), "check"], env=env, text=True, capture_output=True
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("empty SA1", result.stdout)

    def test_fix_backs_up_stock_and_installs_patched_driver(self):
        with tempfile.TemporaryDirectory() as temporary:
            driver, patched, backup, env = self.fixture(temporary)
            result = subprocess.run(
                ["bash", str(SCRIPT), "fix"], env=env, text=True, capture_output=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(driver.read_bytes(), patched.read_bytes())
            self.assertEqual(backup.read_text(), "stock driver\n")
            check = subprocess.run(
                ["bash", str(SCRIPT), "check"], env=env, text=True, capture_output=True
            )
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_restore_returns_to_the_latest_stock_driver(self):
        with tempfile.TemporaryDirectory() as temporary:
            driver, _, backup, env = self.fixture(temporary)
            subprocess.run(["bash", str(SCRIPT), "fix"], env=env, check=True, capture_output=True)
            driver.write_text("updated stock driver\n")
            subprocess.run(["bash", str(SCRIPT), "fix"], env=env, check=True, capture_output=True)
            self.assertEqual(backup.read_text(), "updated stock driver\n")

            result = subprocess.run(
                ["bash", str(SCRIPT), "restore"], env=env, text=True, capture_output=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(driver.read_text(), "updated stock driver\n")

    def test_service_repairs_updates_and_uninstall_restores_stock(self):
        service = (ROOT / "systemd/tm2119-power-profile.service").read_text()
        uninstall = (ROOT / "uninstall.sh").read_text()
        self.assertIn("ExecStartPre=/usr/local/bin/tm2119-cu-fix fix", service)
        self.assertIn("/usr/local/bin/tm2119-cu-fix restore", uninstall)


if __name__ == "__main__":
    unittest.main()
