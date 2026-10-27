"""Native scope lifecycle contracts: systemd GC and kernel cgroup events.

Tests use only a dummy systemctl and disposable synthetic cgroup files.
No real scope or systemd service is started in Ubuntu/Arch container CI.
"""
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_scope_cleanup_evidence as scope


class ScopeCleanupEvidenceTests(unittest.TestCase):
    UNIT = "negresco-pe-0123456789abcdef01234567.scope"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.systemctl = self.root / "systemctl"
        self.systemctl.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        self.systemctl.chmod(0o700)
        self.cgroup = self.root / "cgroup"
        self.cgroup.mkdir()

    def report(self, *, load="loaded", active="inactive", sub="dead",
               control=""):
        return (f"LoadState={load}\nActiveState={active}\n"
                f"SubState={sub}\nControlGroup={control}\n")

    def run_mock(self, report: str, *, stop=False, returncode=0):
        with mock.patch.object(scope, "stop_scope", return_value=stop) as stopper:
            with mock.patch.object(scope.subprocess, "run",
                                   return_value=mock.Mock(
                                       returncode=returncode,
                                       stdout=report)) as show:
                result = scope.stop_and_attest_scope(
                    self.UNIT, systemctl_path=str(self.systemctl),
                    mount_root=self.cgroup)
        stopper.assert_called_once_with(self.UNIT,
                                        systemctl_path=str(self.systemctl))
        argv = show.call_args.args[0]
        self.assertIn("--user", argv)
        self.assertIn("--no-pager", argv)
        self.assertIn("show", argv)
        self.assertFalse(show.call_args.kwargs.get("shell", False))
        self.assertEqual(show.call_args.kwargs["timeout"], 10)
        return result

    def test_collected_scope_may_have_failed_stop_request(self):
        out = self.run_mock(
            self.report(load="not-found"), stop=False)
        self.assertTrue(out["verified"])
        self.assertTrue(out["scope_quiescent"])
        self.assertTrue(out["scope_collected"])
        self.assertFalse(out["stop_request_accepted"])
        self.assertTrue(out["cgroup_unpopulated"])

    def test_active_scope_refused_even_if_stop_exits_zero(self):
        for active, sub in (("active", "running"),
                            ("deactivating", "stop-sigterm"),
                            ("failed", "failed")):
            with self.subTest(active=active):
                with self.assertRaises(scope.ScopeCleanupUnavailable):
                    self.run_mock(self.report(active=active, sub=sub), stop=True)

    def test_live_cgroup_processes_are_refused(self):
        path = self.cgroup / "user.slice" / self.UNIT
        path.mkdir(parents=True)
        (path / "cgroup.events").write_text(
            "populated 1\nfrozen 0\n", encoding="ascii")
        with self.assertRaisesRegex(scope.ScopeCleanupUnavailable,
                                    "contains processes"):
            self.run_mock(self.report(
                control="/user.slice/" + self.UNIT), stop=True)

    def test_unpopulated_cgroup_is_confirmed(self):
        path = self.cgroup / "user.slice" / self.UNIT
        path.mkdir(parents=True)
        (path / "cgroup.events").write_text(
            "populated 0\nfrozen 0\n", encoding="ascii")
        out = self.run_mock(self.report(
            control="/user.slice/" + self.UNIT), stop=True)
        self.assertTrue(out["verified"])
        self.assertFalse(out["scope_collected"])
        self.assertTrue(out["cgroup_unpopulated"])

    def test_disappeared_kernel_cgroup_is_valid_when_unit_inactive(self):
        out = self.run_mock(self.report(
            control="/user.slice/" + self.UNIT), stop=False)
        self.assertTrue(out["scope_quiescent"])

    def test_unreadable_kernel_cgroup_events_rejected(self):
        path = self.cgroup / "user.slice" / self.UNIT
        path.mkdir(parents=True)
        with self.assertRaises(scope.ScopeCleanupUnavailable):
            self.run_mock(self.report(
                control="/user.slice/" + self.UNIT), stop=True)

    def test_malformed_or_ambiguous_systemd_state_rejected(self):
        for report in (
            "", self.report(load="masked"),
            self.report(load="not-found",
                        control="/user.slice/" + self.UNIT),
            self.report() + "ActiveState=inactive\n",
            self.report().replace("SubState=dead\n", ""),
            self.report(control="/other.slice/other.scope"),
            self.report(control="/user.slice/../" + self.UNIT),
        ):
            with self.subTest(report=report[:100]):
                with self.assertRaises(scope.ScopeCleanupUnavailable):
                    self.run_mock(report)

    def test_systemd_query_failure_not_interpreted_as_gc(self):
        with self.assertRaises(scope.ScopeCleanupUnavailable):
            self.run_mock(self.report(load="not-found"), returncode=1)

    def test_symlinked_systemctl_refused_without_calling_systemd(self):
        alias = self.root / "alias"
        alias.symlink_to(self.systemctl)
        with mock.patch.object(scope.subprocess, "run") as show:
            with self.assertRaises(scope.ScopeCleanupUnavailable):
                scope.stop_and_attest_scope(self.UNIT,
                                            systemctl_path=str(alias),
                                            mount_root=self.cgroup)
            show.assert_not_called()


if __name__ == "__main__":
    unittest.main()
