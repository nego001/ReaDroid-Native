"""Fail-closed behavior checks for the real Android 15 reboot gate.

ADB and sleep are stubbed, so these tests do not require an emulator. They
prove orchestration/failure propagation, not actual hardware stability.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "p7_api35_reboot.sh"


class P7Api35RebootTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        binaries = self.work / "bin"
        binaries.mkdir()
        adb = binaries / "adb"
        adb.write_text(
            "#!" + sys.executable + "\n"
            "import os,sys\n"
            "args=' '.join(sys.argv[1:])\n"
            "with open(os.environ['P7_MOCK_ADB_LOG'],'a') as log:\n"
            "  log.write(args+'\\n')\n"
            "if args == 'reboot':\n"
            "  sys.exit(1 if os.environ.get('P7_FAIL_REBOOT') else 0)\n"
            "if args == 'wait-for-device':\n"
            "  sys.exit(1 if os.environ.get('P7_FAIL_WAIT') else 0)\n"
            "if args == 'shell getprop sys.boot_completed':\n"
            "  print(os.environ.get('P7_BOOT_COMPLETED','1'))\n"
            "elif args == 'shell pm path com.readroid.app':\n"
            "  print('' if os.environ.get('P7_MISSING_PACKAGE') else\n"
            "        'package:/data/app/com.readroid.app/base.apk')\n"
            "elif args == 'shell wm size':\n"
            "  print('' if os.environ.get('P7_BAD_SIZE') else 'Physical size: 1080x2220')\n"
            "elif args == 'shell wm density':\n"
            "  print('' if os.environ.get('P7_BAD_DENSITY') else 'Physical density: 440')\n"
            "elif args not in ('reboot','wait-for-device'):\n"
            "  sys.exit(42)\n",
            encoding="utf-8",
        )
        adb.chmod(0o755)
        quick_sleep = binaries / "sleep"
        quick_sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        quick_sleep.chmod(0o755)
        fast_seq = binaries / "seq"
        fast_seq.write_text(
            "#!/bin/sh\n"
            "if [ -n \"$P7_LIMIT_BOOT_PROBES\" ]; then\n"
            "  printf '1\\n2\\n3\\n'\n"
            "else\n  /usr/bin/seq \"$@\"\nfi\n",
            encoding="utf-8")
        fast_seq.chmod(0o755)
        self.log = self.work / "adb_calls.txt"
        self.env = dict(os.environ)
        self.env.update({
            "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
            "P7_MOCK_ADB_LOG": str(self.log),
        })

    def run_gate(self, api):
        return subprocess.run(
            ["bash", str(SCRIPT), api],
            env=self.env, cwd=self.work,
            text=True, capture_output=True, timeout=25,
        )

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_api29_skips_reboot_without_contacting_adb(self):
        result = self.run_gate("29")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("P7_API29_NO_REBOOT", result.stdout)
        self.assertEqual([], self.calls())

    def test_unknown_api_rejected_before_any_adb_call(self):
        self.assertNotEqual(0, self.run_gate("34").returncode)
        self.assertEqual([], self.calls())

    def test_api35_success_requires_all_checks_in_order(self):
        result = self.run_gate("35")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("P7_API35_REBOOT_VERIFIED", result.stdout)
        self.assertEqual([
            "reboot", "wait-for-device", "shell getprop sys.boot_completed",
            "shell pm path com.readroid.app", "shell wm size", "shell wm density",
        ], self.calls())
        self.assertFalse(any("install" in call for call in self.calls()))

    def test_reboot_failure_blocks_followup_checks(self):
        self.env["P7_FAIL_REBOOT"] = "1"
        self.assertNotEqual(0, self.run_gate("35").returncode)
        self.assertEqual(["reboot"], self.calls())

    def test_adb_wait_failure_blocks_capture(self):
        self.env["P7_FAIL_WAIT"] = "1"
        self.assertNotEqual(0, self.run_gate("35").returncode)
        self.assertEqual(["reboot", "wait-for-device"], self.calls())

    def test_incomplete_boot_never_checks_app_or_display(self):
        self.env["P7_BOOT_COMPLETED"] = "0"
        self.env["P7_LIMIT_BOOT_PROBES"] = "1"
        result = self.run_gate("35")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("did not finish boot", result.stderr)
        self.assertEqual(3, self.calls().count("shell getprop sys.boot_completed"))
        self.assertNotIn("shell pm path com.readroid.app", self.calls())

    def test_missing_app_blocks_screenshots(self):
        self.env["P7_MISSING_PACKAGE"] = "1"
        self.assertNotEqual(0, self.run_gate("35").returncode)
        self.assertNotIn("shell wm size", self.calls())

    def test_invalid_dimensions_block_screenshots(self):
        self.env["P7_BAD_SIZE"] = "1"
        self.assertNotEqual(0, self.run_gate("35").returncode)
        self.assertNotIn("shell wm density", self.calls())

    def test_invalid_density_blocks_screenshots(self):
        self.env["P7_BAD_DENSITY"] = "1"
        self.assertNotEqual(0, self.run_gate("35").returncode)
        self.assertEqual("shell wm density", self.calls()[-1])


if __name__ == "__main__":
    unittest.main()
