"""PE-A2.1 checks for the intended Bubblewrap Linux isolation argv.

The tests never execute Bubblewrap; this is command construction evidence,
not proof that kernel user namespaces or filesystem/network isolation work.
"""
from pathlib import Path
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from pe_ghidra_sandbox import build_command, SandboxUnavailable


class SandboxProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        parent = Path(self.temp.name)
        self.ghidra = parent / "ghidra"
        (self.ghidra / "support").mkdir(parents=True)
        (self.ghidra / "support" / "analyzeHeadless").write_text("dummy", encoding="utf-8")
        self.working = parent / "workspace"
        (self.working / "scripts").mkdir(parents=True)
        (self.working / "scripts" / "NegrescoFunctionInventory.java").write_text(
            "// fixture", encoding="utf-8")
        self.fake = parent / "bwrap"
        self.fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IXUSR)

    def tearDown(self):
        self.temp.cleanup()

    def test_requires_real_program_path_and_unprivileged_user(self):
        with mock.patch("pe_ghidra_sandbox.shutil.which", return_value=None):
            with self.assertRaisesRegex(SandboxUnavailable, "ausente"):
                build_command(self.ghidra, self.working, 420)
        if os.geteuid() == 0:
            with self.assertRaisesRegex(SandboxUnavailable, "root"):
                build_command(self.ghidra, self.working, 420, bwrap_path=str(self.fake))

    @unittest.skipIf(os.geteuid() == 0, "profile intentionally refuses root")
    def test_only_private_workdir_ghidra_and_system_runtime_are_mounted(self):
        command = build_command(
            self.ghidra, self.working, 420, bwrap_path=str(self.fake))
        self.assertIn("--unshare-all", command)
        self.assertIn("--die-with-parent", command)
        self.assertIn("--clearenv", command)
        self.assertIn("--ro-bind", command)
        self.assertIn("--bind", command)
        self.assertIn("--tmpfs", command)
        self.assertEqual(command[command.index("--bind") + 2], "/work")
        self.assertIn("/usr", command)
        self.assertIn("/opt/negresco-ghidra", command)
        self.assertIn("-import", command)
        self.assertIn("/work/input.exe", command)
        self.assertNotIn(str(self.working / "input.exe"), command)
        self.assertNotIn("-noanalysis", command)
        self.assertIn("/work/ghidra-functions.json", command)
        self.assertIn("-analysisTimeoutPerFile", command)
        self.assertEqual(command[command.index("-analysisTimeoutPerFile") + 1], "390")
        self.assertNotIn("--share-net", command)
        self.assertNotIn("/home", [command[i+1] for i,v in enumerate(command[:-1])
                                    if v in ("--bind", "--ro-bind")])

    @unittest.skipIf(os.geteuid() == 0, "profile intentionally refuses root")
    def test_missing_export_script_is_rejected(self):
        (self.working / "scripts" / "NegrescoFunctionInventory.java").unlink()
        with self.assertRaisesRegex(SandboxUnavailable, "Exportador"):
            build_command(self.ghidra, self.working, 420, bwrap_path=str(self.fake))

    @unittest.skipIf(os.geteuid() == 0, "profile intentionally refuses root")
    def test_runtime_missing_and_invalid_parameters_are_rejected(self):
        with self.assertRaises(SandboxUnavailable):
            build_command(self.ghidra, self.working, 0, bwrap_path=str(self.fake))
        self.fake.unlink()
        with self.assertRaisesRegex(SandboxUnavailable, "indisponível"):
            build_command(self.ghidra, self.working, 60, bwrap_path=str(self.fake))


if __name__ == "__main__":
    unittest.main()
