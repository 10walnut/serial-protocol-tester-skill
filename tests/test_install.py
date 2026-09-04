from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallationTests(unittest.TestCase):
    def assert_installed(self, directory: Path) -> None:
        installed = directory / "skills" / "serial-protocol-assistant"
        for relative in (
            "SKILL.md", "LICENSE", "agents/openai.yaml",
            "references/protocol-script-format.md", "scripts/protocol_core.py",
            "scripts/validate_protocol.py", "examples/sample_protocol.json",
        ):
            self.assertEqual((installed / relative).read_bytes(), (ROOT / relative).read_bytes())
        self.assertFalse((directory / "skills" / "serial-protocol-tester").exists())

    def test_powershell_installs_new_name_and_display_metadata(self) -> None:
        executable = shutil.which("pwsh") or shutil.which("powershell")
        if not executable:
            self.skipTest("PowerShell is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(
                [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(ROOT / "install.ps1"), "-Target", "harness"],
                cwd=directory, check=True, capture_output=True, timeout=30,
            )
            self.assert_installed(Path(directory))

    @unittest.skipIf(os.name == "nt", "POSIX installation is checked by Linux CI")
    def test_shell_installs_new_name_and_display_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(
                ["sh", str(ROOT / "install.sh"), "harness"],
                cwd=directory, check=True, capture_output=True, timeout=30,
            )
            self.assert_installed(Path(directory))


if __name__ == "__main__":
    unittest.main()
