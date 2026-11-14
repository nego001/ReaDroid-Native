"""Contracts for the synthetic-only Ghidra/Bubblewrap/libseccomp harness."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_seccomp_ghidra_smoke as smoke


class GhidraSeccompSmokeTests(unittest.TestCase):
    def test_fail_closed_if_root_or_untrusted_cross_compiler_absent(self):
        with mock.patch.object(smoke.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(smoke.GhidraSeccompSmokeError, "root"):
                smoke.run_ghidra_seccomp_smoke(Path("/ghidra"), Path("/release.zip"))
        with mock.patch.object(smoke.os, "geteuid", return_value=1000):
            with mock.patch.object(smoke.shutil, "which", return_value=None):
                with self.assertRaisesRegex(
                        smoke.GhidraSeccompSmokeError, "compiler"):
                    smoke.run_ghidra_seccomp_smoke(
                        Path("/ghidra"), Path("/release.zip"))

    def test_fail_closed_on_release_mismatch_before_launch(self):
        with mock.patch.object(smoke.os, "geteuid", return_value=1000):
            with mock.patch.object(smoke.shutil, "which", return_value="/bin/gcc"):
                with mock.patch.object(smoke, "verify_pinned_ghidra_tree",
                                       side_effect=smoke.GhidraIntegrityError("bad zip")):
                    with mock.patch.object(smoke.subprocess, "run") as launched:
                        with self.assertRaises(smoke.GhidraIntegrityError):
                            smoke.run_ghidra_seccomp_smoke(
                                Path("/ghidra"), Path("/bad-release.zip"))
        launched.assert_not_called()

    def _run_with_synthetic_child(self, exit_code=0, inventory=True):
        fd = os.memfd_create("synthetic-bpf-fd", flags=os.MFD_CLOEXEC)
        calls = []

        def fake_subprocess(argv, **kwargs):
            calls.append((list(argv), dict(kwargs)))
            if argv[0] == "x86_64-w64-mingw32-gcc":
                Path(argv[-1]).write_bytes(b"MZ-test-fixture-never-executed")
                return mock.Mock(returncode=0)
            self.assertIn("--seccomp", argv)
            self.assertEqual(kwargs["pass_fds"], (fd,))
            self.assertTrue(kwargs["close_fds"])
            workspace = Path(argv[argv.index("--bind") + 1])
            if inventory:
                evidence = {
                    "schema": "ghidra_function_preview_v1",
                    "total_discovered": 1, "preview_truncated": False,
                    "name_provenance": "original_or_generated_not_verified",
                    "functions": [{"entry_point": "00401000",
                                   "name": "SyntheticFunction", "is_thunk": False}],
                }
                (workspace / "ghidra-functions.json").write_text(json.dumps(evidence))
            return mock.Mock(returncode=exit_code)

        with mock.patch.object(smoke.os, "geteuid", return_value=1000):
            with mock.patch.object(smoke.shutil, "which", return_value="/bin/gcc"):
                with mock.patch.object(smoke, "verify_pinned_ghidra_tree",
                                       return_value={"verified": True,
                                                     "matched_files": 4000}):
                    with mock.patch.object(
                            smoke, "build_command",
                            side_effect=lambda home, workspace, timeout: [
                                "/usr/bin/bwrap", "--bind", str(workspace),
                                "/work", "--", "/bin/echo"]):
                        with mock.patch.object(
                                smoke, "compile_seccomp_bpf_fd", return_value=fd):
                            with mock.patch.object(
                                    smoke.subprocess, "run",
                                    side_effect=fake_subprocess):
                                if exit_code == 0 and inventory:
                                    result = smoke.run_ghidra_seccomp_smoke(
                                        Path("/ghidra"), Path("/release.zip"))
                                else:
                                    with self.assertRaises(
                                            (smoke.GhidraSeccompSmokeError,
                                             smoke.HeadlessError)):
                                        smoke.run_ghidra_seccomp_smoke(
                                            Path("/ghidra"), Path("/release.zip"))
                                    result = None
        with self.assertRaises(OSError):
            os.fstat(fd)
        self.assertEqual(len(calls), 2)
        self.assertFalse(calls[0][1].get("shell", False))
        self.assertFalse(calls[1][1].get("shell", False))
        return result

    @unittest.skipUnless(hasattr(os, "memfd_create"), "Linux memfd required")
    def test_success_requires_pinned_release_filter_fd_and_bounded_inventory(self):
        report = self._run_with_synthetic_child()
        self.assertEqual(report["status"], "PASS_REAL_GHIDRA_SECCOMP_SMOKE")
        self.assertEqual(report["ghidra_functions_discovered"], 1)
        self.assertFalse(report["windows_binary_executed"])
        self.assertFalse(report["cgroup_limits_tested"])

    @unittest.skipUnless(hasattr(os, "memfd_create"), "Linux memfd required")
    def test_rejects_nonzero_exit_or_missing_inventory(self):
        self._run_with_synthetic_child(exit_code=1)
        self._run_with_synthetic_child(inventory=False)


if __name__ == "__main__":
    unittest.main()
