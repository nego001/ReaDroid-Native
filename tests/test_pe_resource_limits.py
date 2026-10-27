"""Contract tests only: no cgroup or systemd scope is created here."""
from pathlib import Path
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from pe_resource_limits import (wrap_in_cgroup_scope,
                                ResourceLimitsUnavailable,
                                MEMORY_MAX_BYTES, TASKS_MAX, CPU_QUOTA_PERCENT)


class CgroupScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.launcher = Path(self.temp.name) / "systemd-run"
        self.launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.launcher.chmod(self.launcher.stat().st_mode | stat.S_IXUSR)
        self.command = ["/usr/bin/bwrap", "--unshare-all", "--", "/usr/bin/java"]

    def tearDown(self):
        self.temp.cleanup()

    def test_rejects_invalid_commands(self):
        for invalid in ([], [""], ["bwrap", ""], ["bwrap", None], "bwrap"):
            with self.subTest(value=invalid):
                with self.assertRaises(ResourceLimitsUnavailable):
                    wrap_in_cgroup_scope(invalid)

    def test_rejects_root(self):
        with mock.patch("pe_resource_limits.os.geteuid", return_value=0):
            with self.assertRaisesRegex(ResourceLimitsUnavailable, "root"):
                wrap_in_cgroup_scope(self.command, systemd_run_path=str(self.launcher))

    def test_rejects_missing_cgroup_or_systemd_without_fallback(self):
        with mock.patch("pe_resource_limits.os.geteuid", return_value=1000):
            with mock.patch("pe_resource_limits.Path.is_file", return_value=False):
                with self.assertRaisesRegex(ResourceLimitsUnavailable, "cgroup v2"):
                    wrap_in_cgroup_scope(self.command, systemd_run_path=str(self.launcher))
            with mock.patch("pe_resource_limits.Path.is_file", return_value=True):
                with mock.patch("pe_resource_limits.shutil.which", return_value=None):
                    with self.assertRaisesRegex(ResourceLimitsUnavailable, "ausente"):
                        wrap_in_cgroup_scope(self.command)

    def test_scoped_command_has_exact_budgets_and_original_argv(self):
        with mock.patch("pe_resource_limits.os.geteuid", return_value=1000):
            with mock.patch("pe_resource_limits.Path.is_file", return_value=True):
                argv = wrap_in_cgroup_scope(self.command,
                                            systemd_run_path=str(self.launcher))
        self.assertEqual(argv[:8], [
            str(self.launcher), "--user", "--scope", "--quiet",
            "--property=MemoryMax=" + str(MEMORY_MAX_BYTES),
            "--property=TasksMax=" + str(TASKS_MAX),
            "--property=CPUQuota=" + str(CPU_QUOTA_PERCENT) + "%",
            "--",
        ])
        self.assertEqual(argv[8:10], [sys.executable, "-I"])
        self.assertTrue(argv[10].endswith("/tools/pe_cgroup_guard.py"))
        self.assertEqual(argv[11:15],
                         [str(MEMORY_MAX_BYTES), str(TASKS_MAX),
                          str(CPU_QUOTA_PERCENT), "--"])
        self.assertEqual(argv[15:], self.command)
        self.assertNotIn("--system", argv)
        self.assertNotIn("--shell", argv)

    def test_rejects_symlink_launcher(self):
        link = Path(self.temp.name) / "linked-systemd-run"
        link.symlink_to(self.launcher)
        with mock.patch("pe_resource_limits.os.geteuid", return_value=1000):
            with mock.patch("pe_resource_limits.Path.is_file", return_value=True):
                with self.assertRaisesRegex(ResourceLimitsUnavailable, "não confiável"):
                    wrap_in_cgroup_scope(self.command, systemd_run_path=str(link))


if __name__ == "__main__":
    unittest.main()
