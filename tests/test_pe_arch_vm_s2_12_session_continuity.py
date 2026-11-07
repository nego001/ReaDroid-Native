"""PE-S2.12 continuity contracts: mocked native state, no VM mount or daemon."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s2_12_session_continuity as state

WORK = {
    "work_mount_type": "tmpfs",
    "mounted_size_bytes": 64 * 1024 * 1024,
    "mount_source_kind": "dedicated_reviewer_prepared",
    "kernel_storage_limit_observed_locally": True,
    "journald_budget_verified": False,
    "independent_vm_attested": False,
}
JOURNAL = {
    "status": "LOCAL_JOURNALD_DECLARED_POLICY_ONLY",
    "storage": "volatile",
    "runtime_max_use_bytes": 8 * 1024 * 1024,
    "runtime_max_file_bytes": 4 * 1024 * 1024,
    "runtime_keep_free_bytes": 32 * 1024 * 1024,
    "rate_limit_interval_seconds": 15,
    "rate_limit_burst": 100,
    "journal_daemon_effective_runtime_verified": False,
    "journal_kernel_quota_verified": False,
    "independent_vm_attested": False,
    "release_authorized": False,
}
SERVICE = {
    "status": "LOCAL_JOURNALD_SERVICE_CGROUP_OBSERVED_ONLY",
    "journald_pid_observed": 321,
    "journald_cgroup_v2_observed_locally": True,
    "journald_running_observed_locally": True,
    "effective_journald_configuration_verified": False,
    "journal_storage_kernel_quota_verified": False,
    "independent_vm_attested": False,
    "release_authorized": False,
}


class NativeSessionContinuityContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pe-s2-12-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)

    def capture(self, *, work=None, policy=None, service=None):
        use_work = WORK if work is None else work
        use_policy = JOURNAL if policy is None else policy
        use_service = SERVICE if service is None else service
        real = self.root.lstat()
        fs = mock.Mock(
            f_frsize=4096, f_blocks=WORK["mounted_size_bytes"] // 4096,
        )
        with (mock.patch.object(state.storage, "require_bounded_work_mount",
                                return_value=use_work),
              mock.patch.object(state.policy, "require_journald_declared_policy",
                                return_value=use_policy),
              mock.patch.object(state.runtime, "observe_live_journald",
                                return_value=use_service),
              mock.patch.object(state.os, "statvfs", return_value=fs),
              mock.patch.object(state.Path, "lstat", return_value=real)):
            return state.capture_local_snapshot(self.root)

    def test_valid_local_snapshot_has_explicit_hold(self):
        measured = self.capture()
        self.assertEqual(set(measured), state.SNAPSHOT_FIELDS)
        self.assertEqual(measured["work_filesystem_capacity_bytes"],
                         WORK["mounted_size_bytes"])
        self.assertFalse(measured["independent_vm_attested"])

    def test_matching_pre_and_post_passes_without_external_claim(self):
        before = self.capture()
        with mock.patch.object(state, "capture_local_snapshot", return_value=before):
            receipt = state.require_unchanged_after_work(self.root, before)
        self.assertTrue(receipt["work_and_journald_pre_post_equal"])
        self.assertFalse(receipt["release_authorized"])
        self.assertFalse(receipt["independent_vm_attested"])

    def test_changed_service_pid_or_declared_journal_policy_refused(self):
        before = self.capture()
        for after in (
                self.capture(service={**SERVICE, "journald_pid_observed": 322}),
                self.capture(policy={**JOURNAL, "runtime_max_use_bytes": 16*1024*1024}),
                {**before, "work_filesystem_capacity_bytes": 128*1024*1024}):
            with self.subTest(after=after):
                with (mock.patch.object(state, "capture_local_snapshot",
                                        return_value=after),
                      self.assertRaisesRegex(state.NativeContinuityError, "changed")):
                    state.require_unchanged_after_work(self.root, before)

    def test_replaced_root_inode_is_refused(self):
        earlier = self.capture()
        after = {**earlier, "work_inode_number": earlier["work_inode_number"]+1}
        with (mock.patch.object(state, "capture_local_snapshot",
                                return_value=after),
              self.assertRaises(state.NativeContinuityError)):
            state.require_unchanged_after_work(self.root, earlier)

    def test_unsafe_journal_status_refused(self):
        with self.assertRaisesRegex(state.NativeContinuityError, "policy"):
            self.capture(policy={**JOURNAL,
                                 "journal_kernel_quota_verified": True})

    def test_unsafe_runtime_status_refused(self):
        with self.assertRaisesRegex(state.NativeContinuityError, "service"):
            self.capture(service={**SERVICE,
                                  "independent_vm_attested": True})

    def test_untrusted_mount_status_refused(self):
        with self.assertRaisesRegex(state.NativeContinuityError, "mount"):
            self.capture(work={**WORK, "kernel_storage_limit_observed_locally": False})

    def test_incomplete_or_extra_snapshot_refused_before_observation(self):
        before = self.capture()
        for forged in ({}, {**before, "release_authorized": True},
                       {**before, "proof": "invented"}, {
                           k: v for k, v in before.items()
                           if k != "journald_runtime_state"}):
            with (mock.patch.object(state, "capture_local_snapshot") as after,
                  self.assertRaises(state.NativeContinuityError)):
                state.require_unchanged_after_work(self.root, forged)
            after.assert_not_called()

    def test_root_does_not_run_state_queries(self):
        with (mock.patch.object(state.os, "geteuid", return_value=0),
              mock.patch.object(state.storage,
                                "require_bounded_work_mount") as mount):
            with self.assertRaises(state.NativeContinuityError):
                state.capture_local_snapshot(self.root)
            mount.assert_not_called()

    def test_query_error_refused(self):
        with mock.patch.object(state.storage, "require_bounded_work_mount",
                               side_effect=state.storage.NativeStorageBudgetError("missing")):
            with self.assertRaisesRegex(
                    state.NativeContinuityError, "unavailable"):
                state.capture_local_snapshot(self.root)


if __name__ == "__main__":
    unittest.main()
