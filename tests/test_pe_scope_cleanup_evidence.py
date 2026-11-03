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

    def run_mock(self, report: str, *, stop=False, returncode=0,
                 second_report=None, second_returncode=None):
        # A successful verification must bracket its kernel cgroup check
        # with two independent systemd state queries.
        replies = [
            mock.Mock(returncode=returncode, stdout=report),
            mock.Mock(
                returncode=(returncode if second_returncode is None
                            else second_returncode),
                stdout=(report if second_report is None else second_report)),
        ]
        with mock.patch.object(scope, "stop_scope", return_value=stop) as stopper:
            with mock.patch.object(scope.subprocess, "run",
                                   side_effect=replies) as show:
                result = scope.stop_and_attest_scope(
                    self.UNIT, systemctl_path=str(self.systemctl),
                    mount_root=self.cgroup)
        stopper.assert_called_once_with(self.UNIT,
                                        systemctl_path=str(self.systemctl))
        self.assertEqual(show.call_count, 2)
        for observed in show.call_args_list:
            argv = observed.args[0]
            self.assertIn("--user", argv)
            self.assertIn("--no-pager", argv)
            self.assertIn("--all", argv)  # Never omit ControlGroup.
            self.assertIn("show", argv)
            self.assertFalse(observed.kwargs.get("shell", False))
            self.assertEqual(observed.kwargs["timeout"], 10)
        self.assertEqual(
            show.call_args_list[0].args[0],
            show.call_args_list[1].args[0])
        return result

    def test_collected_scope_may_have_failed_stop_request(self):
        out = self.run_mock(
            self.report(load="not-found"), stop=False)
        self.assertTrue(out["verified"])
        self.assertEqual(out["scope"], self.UNIT)
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
        # A removed transient unit's leaf may be GC'd, but its parent
        # cgroup hierarchy must still be independently traversable.
        (self.cgroup / "user.slice").mkdir()
        out = self.run_mock(self.report(
            control="/user.slice/" + self.UNIT), stop=False)
        self.assertTrue(out["scope_quiescent"])

    def test_missing_cgroup_ancestor_does_not_count_as_scope_cleanup(self):
        # Before S1.80, ENOENT anywhere in the path was interpreted as
        # evidence of an empty transient scope, including missing slices.
        # That can hide forged/stale ControlGroup paths.
        control = "/user.slice/user-1000.slice/" + self.UNIT
        with self.assertRaises(scope.ScopeCleanupUnavailable):
            self.run_mock(self.report(control=control), stop=True)
        (self.cgroup / "user.slice").mkdir()
        with self.assertRaises(scope.ScopeCleanupUnavailable):
            self.run_mock(self.report(control=control), stop=True)

    def test_missing_leaf_only_accepted_with_verified_parent_hierarchy(self):
        parents = self.cgroup / "user.slice" / "user-1000.slice"
        parents.mkdir(parents=True)
        result = self.run_mock(self.report(
            control="/user.slice/user-1000.slice/" + self.UNIT), stop=False)
        self.assertTrue(result["scope_quiescent"])
        self.assertTrue(result["cgroup_unpopulated"])

    def test_kernel_events_reject_forged_or_ambiguous_population(self):
        path = self.cgroup / "user.slice" / self.UNIT
        path.mkdir(parents=True)
        events = path / "cgroup.events"
        for contents in (
                "populated 1\nfrozen 0\n",
                "populated 0\npopulated 0\n",
                "frozen 0\n",
                "populated false\n",
                "populated 0",
                "populated 0\nfrozen nope\n",
                "populated 0\n" + ("x" * 4096) + "\n"):
            with self.subTest(contents=contents[:80]):
                events.write_text(contents, encoding="ascii")
                with self.assertRaises(scope.ScopeCleanupUnavailable):
                    self.run_mock(
                        self.report(control="/user.slice/" + self.UNIT),
                        stop=True)

    def test_kernel_events_allow_valid_additional_cgroup_v2_fields(self):
        path = self.cgroup / "user.slice" / self.UNIT
        path.mkdir(parents=True)
        (path / "cgroup.events").write_text(
            "populated 0\nfrozen 0\nnr_dying_descendants 0\n",
            encoding="ascii")
        result = self.run_mock(
            self.report(control="/user.slice/" + self.UNIT), stop=True)
        self.assertTrue(result["cgroup_unpopulated"])

    def test_cgroup_directory_symlink_cannot_impersonate_empty_scope(self):
        parent = self.cgroup / "user.slice"
        parent.mkdir()
        other = parent / "other-scope"
        other.mkdir()
        (other / "cgroup.events").write_text(
            "populated 0\n", encoding="ascii")
        (parent / self.UNIT).symlink_to(other, target_is_directory=True)
        with self.assertRaises(scope.ScopeCleanupUnavailable):
            self.run_mock(
                self.report(control="/user.slice/" + self.UNIT), stop=True)

    def test_intermediate_cgroup_symlink_cannot_redirect_kernel_probe(self):
        actual = self.cgroup / "real-user.slice" / self.UNIT
        actual.mkdir(parents=True)
        (actual / "cgroup.events").write_text(
            "populated 0\n", encoding="ascii")
        (self.cgroup / "user.slice").symlink_to(
            actual.parent, target_is_directory=True)
        with self.assertRaises(scope.ScopeCleanupUnavailable):
            self.run_mock(
                self.report(control="/user.slice/" + self.UNIT), stop=True)

    def test_kernel_event_file_symlink_is_rejected(self):
        path = self.cgroup / "user.slice" / self.UNIT
        path.mkdir(parents=True)
        target = self.root / "forged-events"
        target.write_text("populated 0\n", encoding="ascii")
        (path / "cgroup.events").symlink_to(target)
        with self.assertRaises(scope.ScopeCleanupUnavailable):
            self.run_mock(
                self.report(control="/user.slice/" + self.UNIT), stop=True)

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

    def test_scope_reactivation_between_kernel_and_systemd_reads_rejected(self):
        # First report says inactive/dead and cgroup.events says empty.
        # A later active/running report invalidates that result.
        path = self.cgroup / "user.slice" / self.UNIT
        path.mkdir(parents=True)
        (path / "cgroup.events").write_text("populated 0\\n", encoding="ascii")
        with self.assertRaises(scope.ScopeCleanupUnavailable):
            self.run_mock(
                self.report(control="/user.slice/" + self.UNIT),
                second_report=self.report(active="active", sub="running",
                                          control="/user.slice/" + self.UNIT),
                stop=True)

    def test_scope_cgroup_path_change_after_kernel_probe_rejected(self):
        # A second *inactive* report can still refer to another cgroup.
        first = self.cgroup / "user.slice" / self.UNIT
        first.mkdir(parents=True)
        (first / "cgroup.events").write_text("populated 0\\n", encoding="ascii")
        with self.assertRaisesRegex(
                scope.ScopeCleanupUnavailable, "changed during"):
            self.run_mock(
                self.report(control="/user.slice/" + self.UNIT),
                second_report=self.report(
                    control="/user.slice/user-1000.slice/" + self.UNIT),
                stop=True)

    def test_scope_gc_between_two_systemd_reads_is_refused(self):
        # Conservative false negative is preferable to an unbound PASS.
        (self.cgroup / "user.slice").mkdir()
        with self.assertRaisesRegex(
                scope.ScopeCleanupUnavailable, "changed during"):
            self.run_mock(
                self.report(control="/user.slice/" + self.UNIT),
                second_report=self.report(load="not-found"),
                stop=False)

    def test_second_systemd_query_failure_never_produces_pass(self):
        with self.assertRaisesRegex(
                scope.ScopeCleanupUnavailable, "systemd could not confirm"):
            self.run_mock(
                self.report(load="not-found"),
                second_returncode=1, stop=False)

    def test_systemd_query_failure_not_interpreted_as_gc(self):
        with self.assertRaises(scope.ScopeCleanupUnavailable):
            self.run_mock(self.report(load="not-found"), returncode=1)

    def test_path_injected_user_owned_systemctl_is_never_trusted(self):
        with mock.patch.object(scope.shutil, "which",
                               return_value=str(self.systemctl)):
            with mock.patch.object(scope.subprocess, "run") as show:
                with self.assertRaisesRegex(
                        scope.ScopeCleanupUnavailable, "Cannot verify scope cleanup"):
                    scope.stop_and_attest_scope(
                        self.UNIT, mount_root=self.cgroup)
                show.assert_not_called()

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
