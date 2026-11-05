import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "mesa-rembrandt-empty-sa-ps-cu-mask.patch"
SCRIPT = ROOT / "scripts" / "build-install-radv-rembrandt.sh"


class RadvPackageTests(unittest.TestCase):
    def test_patch_is_limited_to_the_tested_cu_mask_function(self):
        content = PATCH.read_text()
        self.assertEqual(content.count("--- a/"), 1)
        self.assertIn("--- a/src/amd/common/ac_gpu_info.c", content)
        self.assertIn("if (!info->cu_mask[se][sa])", content)
        self.assertIn("return ~0u;", content)
        self.assertIn("return BITFIELD_MASK(info->min_good_cu_per_sa);", content)
        for forbidden in ("PPSMC", "RSMU", "0x03B1", "cg_mask", "pg_mask"):
            self.assertNotIn(forbidden, content)

    def test_staging_applies_patch_and_installs_only_tm2119_assets(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        content = SCRIPT.read_text()
        self.assertIn("b9436b3e1a8be76fbd4823dc884f90596ab7c6ac5e1867a305e66ffccfb31a92", content)
        self.assertIn("-Dvulkan-drivers=amd", content)
        self.assertIn("-Dgallium-drivers=", content)
        self.assertNotIn("/usr/lib64/libvulkan_radeon.so", content)

        (ROOT / ".build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".build") as temporary:
            temp = Path(temporary)
            source_file = temp / "source/src/amd/common/ac_gpu_info.c"
            source_file.parent.mkdir(parents=True)
            source_file.write_text(
                "    * Disable the extra CUs for PS in other shader arrays to save power and thus\n"
                "    * increase clocks for busy CUs. In the future, we might disable or enable this\n"
                "    * tweak only for certain apps.\n"
                "    */\n"
                "   return BITFIELD_MASK(info->min_good_cu_per_sa);\n"
                "}\n"
            )
            driver = temp / "build/src/amd/vulkan/libvulkan_radeon.so"
            driver.parent.mkdir(parents=True)
            driver.write_text("test driver\n")
            generated_manifest = driver.parent / "radeon_devenv_icd.x86_64.json"
            generated_manifest.write_text(json.dumps({
                "ICD": {"api_version": "1.4.test", "library_path": str(driver)},
                "file_format_version": "1.0.1",
            }))
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            for tool in ("meson", "ninja"):
                path = fake_bin / tool
                path.write_text("#!/bin/sh\nexit 0\n")
                path.chmod(0o755)
            stage = temp / "stage"
            env = os.environ.copy()
            env.update({
                "PATH": f"{fake_bin}:{env['PATH']}",
                "TM2119_MESA_SOURCE": str(temp / "source"),
                "TM2119_MESA_BUILD": str(temp / "build"),
                "DESTDIR": str(stage),
            })
            result = subprocess.run([str(SCRIPT)], env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("return ~0u;", source_file.read_text())
            self.assertEqual(
                (stage / "usr/local/lib/tm2119-power/mesa/libvulkan_radeon.so").read_text(),
                "test driver\n",
            )
            self.assertTrue((stage / "usr/local/bin/tm2119-cu-fix").is_file())
            self.assertFalse((stage / "etc/environment.d/90-tm2119-radv.conf").exists())
            self.assertFalse((stage / "etc/profile.d/tm2119-radv.sh").exists())
            self.assertFalse(
                (stage / "usr/local/share/vulkan/icd.d/tm2119_radeon_icd.x86_64.json").exists()
            )


if __name__ == "__main__":
    unittest.main()
