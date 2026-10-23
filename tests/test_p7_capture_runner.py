"""Regression tests for P7 populated-Explorer capture script.

ADB is stubbed; these tests cover orchestration and fail-closed behavior,
not Android visual fidelity or physical-device acceptance.
"""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "p7_capture_populated.sh"


def chunk(tag, data=b""):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))


def png():
    header = struct.pack(">IIBBBBB", 3, 2, 8, 6, 0, 0, 0)
    row = b"\x00" + b"\x10\x20\x30\xff" * 3
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(row * 2)) + chunk(b"IEND"))


class P7CaptureRunnerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.cwd = Path(temp.name)
        for item in (
            "app/build/outputs/apk/debug/app-debug.apk",
            "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk",
        ):
            path = self.cwd / item
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test-only")
        image = self.cwd / "fixture.png"
        image.write_bytes(png())
        bin_dir = self.cwd / "bin"
        bin_dir.mkdir()
        fake_adb = bin_dir / "adb"
        fake_adb.write_text(
            "#!" + sys.executable + "\n"
            "import os,sys,pathlib\n"
            "args=sys.argv[1:]\n"
            "with open(os.environ['P7_ADB_LOG'],'a') as f:\n"
            "  f.write(' '.join(args)+'\\n')\n"
            "if args[0]=='install':\n"
            "  print('Success')\n"
            "elif args[:3]==['shell','am','instrument']:\n"
            "  print(os.environ.get('P7_INSTRUMENT_RESULT','OK (1 test)'))\n"
            "elif args[:4]==['exec-out','run-as','com.readroid.app','cat']:\n"
            "  sys.stdout.buffer.write(pathlib.Path(os.environ['P7_PNG']).read_bytes())\n"
            "else:\n"
            "  sys.exit(9)\n",
            encoding="utf-8")
        fake_adb.chmod(0o755)
        self.log = self.cwd / "calls.txt"
        self.env = dict(os.environ)
        self.env.update({
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "PYTHONPATH": str(ROOT),
            "P7_ADB_LOG": str(self.log),
            "P7_PNG": str(image),
        })

    def execute(self, api="29"):
        return subprocess.run(["bash", str(RUNNER), api], cwd=self.cwd,
                              env=self.env, capture_output=True, text=True,
                              timeout=20)

    def test_valid_real_png_and_shell_state(self):
        result = self.execute()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("P7_POPULATED_PNG_OK", result.stdout)
        self.assertTrue((self.cwd /
                         "p7-explorer-populated-android-29.png").is_file())
        commands = self.log.read_text()
        self.assertEqual(2, commands.count("install -r "))
        self.assertIn("shell am instrument -w -r", commands)
        self.assertIn("exec-out run-as com.readroid.app cat", commands)

    def test_invalid_api_rejected_without_adb(self):
        result = self.execute("33")
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.log.exists())

    def test_corrupt_png_fails_closed(self):
        (self.cwd / "fixture.png").write_bytes(b"not PNG")
        result = self.execute()
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("P7_POPULATED_PNG_OK", result.stdout)

    def test_instrumentation_failure_cannot_pass(self):
        self.env["P7_INSTRUMENT_RESULT"] = "FAILURES!!!"
        result = self.execute()
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.cwd /
                          "p7-explorer-populated-android-29.png").exists())

    def test_missing_android_test_package_cannot_pass(self):
        (self.cwd /
         "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk").unlink()
        result = self.execute()
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
