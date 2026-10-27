"""Synthetic contracts for a seccomp filter created inside a systemd scope.

CI never starts systemd user scopes and never attaches the BPF to itself.
"""
from pathlib import Path
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_scoped_seccomp_launcher as bridge


class ScopedSeccompLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.binary = Path(self.temp.name) / "bwrap"
        self.binary.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        self.binary.chmod(self.binary.stat().st_mode | stat.S_IXUSR)
        self.unit = "negresco-pe-0123456789abcdef01234567.scope"
        self.argv = [str(self.binary), "--unshare-all", "--",
                     "/usr/bin/python3", "-c", "print('synthetic')"]

    def tearDown(self):
        self.temp.cleanup()

    def context(self):
        return mock.patch.multiple(
            bridge, verify_cgroup_limits=mock.DEFAULT,
            compile_seccomp_bpf_fd=mock.DEFAULT, attach_seccomp_fd=mock.DEFAULT)

    def test_live_scope_recheck_precedes_filter_creation(self):
        with mock.patch.object(bridge.os, "geteuid", return_value=1000):
            with mock.patch.object(bridge.shutil, "which",
                                   return_value=str(self.binary)):
                with mock.patch.object(
                        bridge, "verify_cgroup_limits",
                        side_effect=bridge.CgroupVerificationError("no quota")):
                    with mock.patch.object(bridge, "compile_seccomp_bpf_fd") as compile_fd:
                        with self.assertRaisesRegex(
                                bridge.ScopedSeccompUnavailable, "not verified"):
                            bridge.launch_scoped_bwrap(self.unit, self.argv)
        compile_fd.assert_not_called()

    def test_compiles_filter_inside_scope_and_only_bwrap_inherits(self):
        fd = os.memfd_create("synthetic-scope-filter", flags=os.MFD_CLOEXEC)
        fake_child = mock.Mock()
        fake_child.wait.return_value = 0
        fake_child.pid = 80001
        with mock.patch.object(bridge.os, "geteuid", return_value=1000):
            with mock.patch.object(bridge.shutil, "which",
                                   return_value=str(self.binary)):
                with mock.patch.object(bridge, "verify_cgroup_limits",
                                       return_value={"verified": True}) as guard:
                    with mock.patch.object(bridge, "compile_seccomp_bpf_fd",
                                           return_value=fd) as compiler:
                        with mock.patch.object(bridge.subprocess, "Popen",
                                               return_value=fake_child) as popen:
                            self.assertEqual(
                                bridge.launch_scoped_bwrap(
                                    self.unit, self.argv, timeout_seconds=30), 0)
        guard.assert_called_once_with(
            bridge.MEMORY_MAX_BYTES, bridge.TASKS_MAX,
            bridge.CPU_QUOTA_PERCENT, expected_scope=self.unit)
        compiler.assert_called_once()
        launched = popen.call_args.args[0]
        self.assertEqual(launched[launched.index("--seccomp") + 1], str(fd))
        self.assertEqual(launched[launched.index("--") + 1:],
                         self.argv[self.argv.index("--") + 1:])
        self.assertEqual(popen.call_args.kwargs["pass_fds"], (fd,))
        self.assertTrue(popen.call_args.kwargs["close_fds"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertEqual(popen.call_args.kwargs["stdin"], bridge.subprocess.DEVNULL)
        with self.assertRaises(OSError):
            os.fstat(fd)

    def test_rejects_untrusted_launcher_before_scope_probe(self):
        with mock.patch.object(bridge.os, "geteuid", return_value=1000):
            with mock.patch.object(bridge.shutil, "which",
                                   return_value=str(self.binary)):
                with mock.patch.object(bridge, "verify_cgroup_limits") as verify:
                    for invalid in (
                            ["/bin/sh", "--", "/usr/bin/python3"],
                            [str(self.binary), "--seccomp", "3", "--", "python"],
                            [str(self.binary), "--", ""],
                            [str(self.binary), "--"]):
                        with self.subTest(argv=invalid):
                            with self.assertRaises(bridge.ScopedSeccompUnavailable):
                                bridge.launch_scoped_bwrap(self.unit, invalid)
                    verify.assert_not_called()

    def test_rejects_root_without_starting_any_process(self):
        with mock.patch.object(bridge.os, "geteuid", return_value=0):
            with mock.patch.object(bridge.subprocess, "Popen") as popen:
                with self.assertRaisesRegex(bridge.ScopedSeccompUnavailable, "root"):
                    bridge.launch_scoped_bwrap(self.unit, self.argv)
        popen.assert_not_called()

    def test_filter_fd_is_closed_after_bwrap_launch_fails(self):
        fd = os.memfd_create("synthetic-fd-close", flags=os.MFD_CLOEXEC)
        with mock.patch.object(bridge.os, "geteuid", return_value=1000):
            with mock.patch.object(bridge.shutil, "which",
                                   return_value=str(self.binary)):
                with mock.patch.object(bridge, "verify_cgroup_limits",
                                       return_value={"verified": True}):
                    with mock.patch.object(bridge, "compile_seccomp_bpf_fd",
                                           return_value=fd):
                        with mock.patch.object(bridge.subprocess, "Popen",
                                               side_effect=OSError("denied")):
                            with self.assertRaises(bridge.ScopedSeccompUnavailable):
                                bridge.launch_scoped_bwrap(self.unit, self.argv)
        with self.assertRaises(OSError):
            os.fstat(fd)

    def test_propagates_bwrap_failure_instead_of_claiming_pass(self):
        fd = os.memfd_create("synthetic-fd-exit", flags=os.MFD_CLOEXEC)
        fake_child = mock.Mock()
        fake_child.wait.return_value = 27
        with mock.patch.object(bridge.os, "geteuid", return_value=1000):
            with mock.patch.object(bridge.shutil, "which",
                                   return_value=str(self.binary)):
                with mock.patch.object(bridge, "verify_cgroup_limits",
                                       return_value={"verified": True}):
                    with mock.patch.object(bridge, "compile_seccomp_bpf_fd",
                                           return_value=fd):
                        with mock.patch.object(bridge.subprocess, "Popen",
                                               return_value=fake_child):
                            result = bridge.launch_scoped_bwrap(self.unit, self.argv)
        self.assertEqual(result, 27)


if __name__ == "__main__":
    unittest.main()
