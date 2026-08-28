from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = SKILL_ROOT / "assets" / "pyside6-serial-console"
sys.path.insert(0, str(APP_ROOT))

from virtual_ports import (  # noqa: E402
    VirtualPortError,
    build_install_arguments,
    find_setupc,
    normalize_com_name,
)


class VirtualPortTests(unittest.TestCase):
    def test_normalize_com_name(self) -> None:
        self.assertEqual(normalize_com_name(" com10 "), "COM10")
        self.assertEqual(normalize_com_name(256), "COM256")

    def test_invalid_com_name(self) -> None:
        for value in ("COM0", "COM257", "CNCA0", "10"):
            with self.subTest(value=value), self.assertRaises(VirtualPortError):
                normalize_com_name(value)

    def test_install_arguments(self) -> None:
        self.assertEqual(
            build_install_arguments("COM10", "COM11"),
            [
                "install",
                "PortName=COM#,RealPortName=COM10",
                "PortName=COM#,RealPortName=COM11",
            ],
        )
        with self.assertRaises(VirtualPortError):
            build_install_arguments("COM10", "COM10")

    def test_find_explicit_setupc(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            setupc = Path(directory) / "setupc.exe"
            setupc.touch()
            self.assertEqual(find_setupc(setupc), setupc.resolve())


if __name__ == "__main__":
    unittest.main()
