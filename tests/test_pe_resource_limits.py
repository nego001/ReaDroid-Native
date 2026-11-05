"""Contract tests only: no cgroup or systemd scope is created here."""
from pathlib import Path
import os
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_resource_limits as limits
from pe_resource_limits import (wrap_in_cgroup_scope, new_scope_unit, stop_scope,
                                ResourceLimitsUnavailable,
                                MEMORY_MAX_BYTES, TASKS_MAX, CPU_QUOTA_PERCENT)


class CgroupScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.launcher = Path(self.temp.name) / "systemd-run"
        self.launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.launcher.chmod(self.launcher.stat().st_mode | stat.S_IXUSR)
        self.command = ["/usr/bin/bwrap", "--unshare-all", "--", "/usr/bin/java"]
        self.unit_name = "negresco-pe-0123456789abcdef01234567.scope"

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
                argv = wrap_in_cgroup_scope(self.command, timeout_seconds=420,
                                            unit_name=self.unit_name,
                                            systemd_run_path=str(self.launcher))
        self.assertEqual(argv[:13], [
            str(self.launcher), "--user", "--scope", "--quiet",
            "--unit=" + self.unit_name,
            "--property=RuntimeMaxSec=440s",
            "--property=TimeoutStopSec=5s",
            "--property=KillMode=control-group",
            "--property=SendSIGKILL=yes",
            "--property=MemoryMax=" + str(MEMORY_MAX_BYTES),
            "--property=TasksMax=" + str(TASKS_MAX),
            "--property=CPUQuota=" + str(CPU_QUOTA_PERCENT) + "%",
            "--",
        ])
        self.assertEqual(argv[13:15], [sys.executable, "-I"])
        self.assertTrue(argv[15].endswith("/tools/pe_cgroup_guard.py"))
        self.assertEqual(argv[16:22],
                         [str(MEMORY_MAX_BYTES), str(TASKS_MAX),
                          str(CPU_QUOTA_PERCENT), self.unit_name, "-", "--"])
        self.assertEqual(argv[22:], self.command)
        self.assertNotIn("--system", argv)
        self.assertNotIn("--shell", argv)

    def test_accepts_only_private_outside_sandbox_proof_path(self):
        with tempfile.TemporaryDirectory() as evidence:
            path = Path(evidence) / "guard-proof.json"
            with mock.patch("pe_resource_limits.os.geteuid", return_value=os.geteuid()):
                with mock.patch("pe_resource_limits.Path.is_file", return_value=True):
                    argv = wrap_in_cgroup_scope(
                        self.command, timeout_seconds=30, unit_name=self.unit_name,
                        proof_path=path, systemd_run_path=str(self.launcher))
            self.assertEqual(argv[20], str(path))
            path.write_text("existing")
            with self.assertRaisesRegex(ResourceLimitsUnavailable, "inválido"):
                wrap_in_cgroup_scope(self.command, proof_path=path)
            path.unlink()
            link = Path(evidence) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(ResourceLimitsUnavailable):
                wrap_in_cgroup_scope(self.command, proof_path=link)

    def test_unique_scopes_and_bad_names_or_timeouts(self):
        first = new_scope_unit()
        second = new_scope_unit()
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("negresco-pe-"))
        self.assertTrue(first.endswith(".scope"))
        for invalid in ("other.scope", "negresco-pe-abc.scope",
                        "negresco-pe-0123456789abcdef01234567.service",
                        "../negresco-pe-0123456789abcdef01234567.scope"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ResourceLimitsUnavailable, "escopo"):
                    wrap_in_cgroup_scope(self.command, unit_name=invalid)
                with self.assertRaises(ResourceLimitsUnavailable):
                    stop_scope(invalid, systemctl_path=str(self.launcher))
        with self.assertRaisesRegex(ResourceLimitsUnavailable, "Tempo"):
            wrap_in_cgroup_scope(self.command, timeout_seconds=0)

    def test_stop_scope_has_bounded_no_shell_cleanup(self):
        with mock.patch("pe_resource_limits.subprocess.run") as run:
            run.return_value.returncode = 0
            self.assertTrue(stop_scope(self.unit_name,
                                       systemctl_path=str(self.launcher)))
        run.assert_called_once()
        args = run.call_args.args[0]
        self.assertEqual(args, [str(self.launcher), "--user",
                                "--no-ask-password", "stop", self.unit_name])
        self.assertEqual(run.call_args.kwargs["timeout"], 10)
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_path_discovered_user_binary_cannot_launch_scope_or_stop_scope(self):
        # A PATH-injected user script was accepted by the old
        # is_file()+X_OK check. Neither production lookup may execute it.
        for tool_name in ("systemd-run", "systemctl"):
            with self.subTest(tool=tool_name):
                selected = Path(self.temp.name) / tool_name
                selected.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                selected.chmod(0o755)
                with (mock.patch("pe_resource_limits.shutil.which",
                                 return_value=str(selected)),
                      mock.patch("pe_resource_limits.Path.is_file",
                                 return_value=True),
                      mock.patch("pe_resource_limits.os.geteuid",
                                 return_value=1000),
                      mock.patch("pe_resource_limits.subprocess.run") as launched):
                    if tool_name == "systemd-run":
                        with self.assertRaisesRegex(
                                ResourceLimitsUnavailable,
                                "não confiável"):
                            wrap_in_cgroup_scope(self.command,
                                                unit_name=self.unit_name)
                    else:
                        self.assertFalse(stop_scope(self.unit_name))
                    launched.assert_not_called()

    def test_discovered_systemd_binary_rejects_mutable_or_linked_ancestors(self):
        # Mock only inode metadata. The test is neither a root-owned
        # executable nor a real host trust attestation.
        selected = str(self.launcher)
        parent = self.launcher.parent
        root_file = stat.S_IFREG | 0o755
        root_dir = stat.S_IFDIR | 0o755

        for kind in ("trusted_shape", "writable_file", "writable_dir",
                     "user_owned_file", "user_owned_dir", "symlink_dir"):
            with self.subTest(kind=kind):
                def fake_lstat(path):
                    if Path(path) == self.launcher:
                        mode = root_file | (0o022 if kind == "writable_file" else 0)
                        uid = 1000 if kind == "user_owned_file" else 0
                    else:
                        mode = root_dir
                        uid = 0
                        if Path(path) == parent:
                            if kind == "writable_dir":
                                mode |= 0o022
                            if kind == "user_owned_dir":
                                uid = 1000
                            if kind == "symlink_dir":
                                mode = stat.S_IFLNK | 0o777
                    return SimpleNamespace(st_mode=mode, st_uid=uid)

                with mock.patch.object(Path, "lstat",
                                       autospec=True, side_effect=fake_lstat):
                    self.assertIs(
                        limits._trusted_discovered_systemd_binary(selected),
                        kind == "trusted_shape")

    def test_discovered_systemd_run_checks_root_owned_metadata_before_returning_argv(self):
        # Simulated root metadata only: no systemd command is ever invoked.
        root_file = stat.S_IFREG | 0o755
        root_dir = stat.S_IFDIR | 0o755

        def root_lstat(path):
            return SimpleNamespace(
                st_mode=root_file if Path(path) == self.launcher else root_dir,
                st_uid=0)

        with (mock.patch("pe_resource_limits.shutil.which",
                         return_value=str(self.launcher)),
              mock.patch("pe_resource_limits.Path.is_file",
                         return_value=True),
              mock.patch("pe_resource_limits.os.geteuid", return_value=1000),
              mock.patch.object(Path, "lstat",
                                autospec=True, side_effect=root_lstat),
              mock.patch("pe_resource_limits.subprocess.run") as launched):
            result = wrap_in_cgroup_scope(
                self.command, unit_name=self.unit_name)
        self.assertEqual(result[0], str(self.launcher))
        launched.assert_not_called()

    def test_rejects_symlink_launcher(self):
        link = Path(self.temp.name) / "linked-systemd-run"
        link.symlink_to(self.launcher)
        with mock.patch("pe_resource_limits.os.geteuid", return_value=1000):
            with mock.patch("pe_resource_limits.Path.is_file", return_value=True):
                with self.assertRaisesRegex(ResourceLimitsUnavailable, "não confiável"):
                    wrap_in_cgroup_scope(self.command, systemd_run_path=str(link))


if __name__ == "__main__":
    unittest.main()
