"""Contracts for the reproducible, privacy-safe manual test package."""

from __future__ import annotations

import hashlib
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build_test_zip.py"
TESTING_GUIDE = ROOT / "TESTING.md"
COMPONENT_PREFIX = "custom_components/mobility_forecast/"
REQUIRED_PACKAGE_FILES = {
    f"{COMPONENT_PREFIX}brand/icon.png",
    f"{COMPONENT_PREFIX}brand/icon@2x.png",
    f"{COMPONENT_PREFIX}manifest.json",
    f"{COMPONENT_PREFIX}strings.json",
    f"{COMPONENT_PREFIX}translations/en.json",
}
REQUIRED_BRAND_SIZES = {
    f"{COMPONENT_PREFIX}brand/icon.png": (256, 256),
    f"{COMPONENT_PREFIX}brand/icon@2x.png": (512, 512),
}
FORBIDDEN_PARTS = {
    "__pycache__",
    ".storage",
    ".env",
    "secrets.yaml",
}


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _png_header(payload: bytes) -> tuple[int, int, int, int]:
    """Return width, height, bit depth and color type from a PNG IHDR."""

    if payload[:8] != b"\x89PNG\r\n\x1a\n" or payload[12:16] != b"IHDR":
        raise ValueError("brand asset is not a PNG with an IHDR header")
    return struct.unpack(">IIBB", payload[16:26])


class TestPackageTests(unittest.TestCase):
    """Prove archive scope, reproducibility, checksum, and independent checking."""

    def test_build_is_reproducible_and_contains_only_tracked_integration_files(
        self,
    ) -> None:
        tracked = subprocess.run(
            ["git", "ls-files", COMPONENT_PREFIX],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()

        with (
            tempfile.TemporaryDirectory() as first,
            tempfile.TemporaryDirectory() as second,
        ):
            first_result = _run("--output-dir", first)
            second_result = _run("--output-dir", second)
            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            self.assertEqual(second_result.returncode, 0, second_result.stderr)

            first_archive = next(Path(first).glob("*.zip"))
            second_archive = next(Path(second).glob("*.zip"))
            first_bytes = first_archive.read_bytes()
            self.assertEqual(first_bytes, second_archive.read_bytes())

            with zipfile.ZipFile(first_archive) as package:
                infos = package.infolist()
                names = [info.filename for info in infos]
                self.assertEqual(names, sorted(tracked))
                self.assertTrue(set(names) >= REQUIRED_PACKAGE_FILES)
                for asset, expected_size in REQUIRED_BRAND_SIZES.items():
                    width, height, bit_depth, color_type = _png_header(
                        package.read(asset)
                    )
                    self.assertEqual((width, height), expected_size)
                    self.assertEqual(bit_depth, 8)
                    self.assertEqual(color_type, 6)  # RGBA
                self.assertTrue(
                    all(name.startswith(COMPONENT_PREFIX) for name in names)
                )
                self.assertTrue(all(not name.endswith("/") for name in names))
                self.assertTrue(
                    all(
                        not FORBIDDEN_PARTS.intersection(Path(name).parts)
                        for name in names
                    )
                )
                self.assertTrue(
                    all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in infos)
                )
                self.assertTrue(
                    all(info.compress_type == zipfile.ZIP_STORED for info in infos)
                )
                self.assertTrue(
                    all((info.external_attr >> 16) == 0o100644 for info in infos)
                )

            checksum = hashlib.sha256(first_bytes).hexdigest()
            sidecar = first_archive.with_suffix(first_archive.suffix + ".sha256")
            self.assertEqual(
                sidecar.read_text(encoding="ascii"),
                f"{checksum}  {first_archive.name}\n",
            )

    def test_testing_guide_covers_safe_install_and_rollback(self) -> None:
        guide = TESTING_GUIDE.read_text(encoding="utf-8")
        required_sections = (
            "## Safety and current limitations",
            "## 1. Back up Home Assistant",
            "## 2. Verify the package",
            "## 3. Install the files",
            "## 4. Restart and check logs",
            "## 5. Run the config-flow smoke test",
            "## 6. Verify the expected entity state",
            "## 7. Uninstall or roll back",
        )
        self.assertTrue(all(section in guide for section in required_sections))
        self.assertIn("pre-alpha", guide.casefold())
        self.assertIn("read-only", guide.casefold())
        self.assertIn("synthetic", guide.casefold())
        self.assertIn("unavailable", guide.casefold())
        self.assertIn("sha256sum --check", guide)
        self.assertNotIn("forecasting works", guide.casefold())

    def test_check_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            result = _run("--output-dir", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            archive = next(Path(output).glob("*.zip"))

            checked = _run("--check", str(archive))
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertIn("package check: PASS", checked.stdout)

            archive.write_bytes(archive.read_bytes() + b"tampered")
            rejected = _run("--check", str(archive))
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("checksum mismatch", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
