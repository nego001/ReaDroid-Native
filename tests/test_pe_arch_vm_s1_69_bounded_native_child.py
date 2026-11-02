"""PE-S1.69: real bounded capture of harmless Python-only children.

No VM, Ghidra, cgroup, Windows executable or network work in this suite.
All child code uses Python -I -B with fixed test-only statements.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_69_bounded_native_child as bounded

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "tools" / "pe_arch_vm_validation.py"


class BoundedNativeChildContracts(unittest.TestCase):
    def python(self, code: str):
        return [sys.executable, "-I", "-B", "-c", code]

    def call(self, code: str, **kwargs):
        return bounded.run_bounded_native(
            self.python(code), env=dict(os.environ),
            timeout=kwargs.pop("timeout", 4), **kwargs)

    def test_both_pipes_drained_without_deadlock(self):
        result = self.call(
            "import os;os.write(1,b'OUTPUT');os.write(2,b'WARNING')",
            max_stdout=6, max_stderr=7)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"OUTPUT")
        self.assertEqual(result.stderr, b"WARNING")

    def test_stdout_at_exact_limit_allowed(self):
        result = self.call(
            "import os;os.write(1,b'A'*1024)", max_stdout=1024)
        self.assertEqual(len(result.stdout), 1024)

    def test_stdout_one_byte_over_limit_fails_closed(self):
        with self.assertRaisesRegex(
                bounded.BoundedNativeChildError, "stdout exceeds limit"):
            self.call("import os;os.write(1,b'A'*65536)",
                      max_stdout=512)

    def test_stderr_one_byte_over_limit_fails_closed(self):
        with self.assertRaisesRegex(
                bounded.BoundedNativeChildError, "stderr exceeds limit"):
            self.call("import os;os.write(2,b'E'*65536)",
                      max_stderr=128)

    def test_stderr_and_stdout_interleaved_both_complete(self):
        result = self.call(
            "import os\n"
            "for _ in range(64):\n"
            " os.write(1,b'A'*128)\n os.write(2,b'B'*64)\n",
            max_stdout=8192, max_stderr=4096)
        self.assertEqual(len(result.stdout), 8192)
        self.assertEqual(len(result.stderr), 4096)

    def test_silent_child_timeout_kills_own_session(self):
        start = time.monotonic()
        with self.assertRaisesRegex(
                bounded.BoundedNativeChildError, "timed out"):
            self.call("import time;time.sleep(5)", timeout=0.2)
        self.assertLess(time.monotonic() - start, 4)

    def test_descendant_keeps_stdout_open_timeout_still_rejected(self):
        start = time.monotonic()
        with self.assertRaisesRegex(
                bounded.BoundedNativeChildError, "timed out"):
            self.call(
                "import subprocess,sys,os\n"
                "subprocess.Popen([sys.executable,'-I','-B','-c',"
                "'import time;time.sleep(5)'],close_fds=True)\n"
                "os.write(1,b'CHILD_SPAWNED')\n",
                timeout=0.3)
        self.assertLess(time.monotonic() - start, 4)

    def test_failed_child_return_code_is_preserved_not_success(self):
        result = self.call("import sys;sys.exit(13)")
        self.assertEqual(result.returncode, 13)

    def test_zero_stdout_is_returned_not_fabricated(self):
        result = self.call("import sys;sys.exit(0)")
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")

    def test_stdin_is_devnull_and_no_shell_used(self):
        result = self.call(
            "import sys; b=sys.stdin.buffer.read();print(len(b))")
        self.assertEqual(result.stdout.strip(), b"0")

    def test_child_session_is_independent(self):
        result = self.call("import os;print(os.getsid(0)==os.getpid())")
        self.assertEqual(result.stdout.strip(), b"True")

    def test_invalid_input_parameters_are_rejected_without_launch(self):
        for changes in (
            {"timeout": 0}, {"timeout": 1801},
            {"max_stdout": -1}, {"max_stdout": True},
            {"max_stderr": 0}, {"max_stderr": 9000},
        ):
            with self.subTest(changes=changes), self.assertRaises(
                    bounded.BoundedNativeChildError):
                self.call("raise RuntimeError('SHOULD NOT RUN')", **changes)
        with self.assertRaises(bounded.BoundedNativeChildError):
            bounded.run_bounded_native(
                ["bad\x00argument"], env=dict(os.environ))

    def test_python_isolated_mode_ignores_pythonpath_injection(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-69-pythonpath-") as tmp:
            marker = Path(tmp) / "injected_test_only_module.py"
            marker.write_text("COMPROMISED=True\n", encoding="ascii")
            env = {**os.environ, "PYTHONPATH": tmp}
            run = bounded.run_bounded_native(
                self.python(
                    "import importlib.util;print("
                    "importlib.util.find_spec('injected_test_only_module') is None)"),
                env=env, timeout=4)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(run.stdout.strip(), b"True")

    def test_pinned_native_entrypoint_imports_under_isolated_python(self):
        # --help must exit during argparse, before the native VM preflight
        # or any Ghidra/scope run. It catches the -I script-directory issue.
        result = bounded.run_bounded_native(
            [sys.executable, "-I", "-B", str(NATIVE), "--help"],
            env=dict(os.environ), timeout=8,
            max_stdout=16384)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertIn(b"--reviewer-pinned-checkout", result.stdout)


if __name__ == "__main__":
    unittest.main()
