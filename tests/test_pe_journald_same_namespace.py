"""PE-S2.27 synthetic contracts; no real host, journald or native Arch VM."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import stat
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_journald_same_namespace as mod

PID = 2468
SIZE = 32 * 1024 * 1024
STAT = (str(PID) + " (systemd-journald) " +
        " ".join(["S"] + ["0"] * 18 + ["123456"] + ["0"] * 4) + "\n")
STAT_CHANGED = STAT.replace("123456", "123457")
MOUNT = {"mount_id": "101", "root": "/", "filesystem": "tmpfs",
         "source": "tmpfs", "mountpoint": "/run/log/journal",
         "mount_options": ["rw"]}


class SameNamespaceContracts(unittest.TestCase):
    def enter(self, **overrides):
        stack = ExitStack()
        self.addCleanup(stack.close)
        defaults = {
            "_service_pid": [PID, PID],
            "_read_bounded": [STAT, STAT],
            "_ns_identity": [(1, 90)] * 4,
            "_root_identity": [(2, 1)] * 4,
            "_pid_mountinfo": [b"mountinfo"] * 2,
        }
        for name, values in {**defaults, **overrides}.items():
            stack.enter_context(mock.patch.object(mod, name, side_effect=values))
        for name, values in {
            "_secure_root_owned_path": [(3, 4), (3, 4)],
            "_kernel_mountinfo": [b"mountinfo"] * 2,
            "_journal_mount": [MOUNT] * 4,
            "_filesystem_size": [SIZE] * 2,
        }.items():
            stack.enter_context(mock.patch.object(mod.mount, name, side_effect=values))
        stack.enter_context(mock.patch.object(mod.os, "geteuid", return_value=1000))
        return stack

    def test_consistent_kernel_local_view_never_homologates(self):
        self.enter()
        r = mod.observe_live_process_mount()
        self.assertEqual(r["status"], mod.OBSERVED)
        self.assertEqual(r["journald_pid_locally_observed"], PID)
        self.assertEqual(r["journald_pid_start_ticks"], 123456)
        self.assertEqual(r["journal_tmpfs_capacity_bytes"], SIZE)
        self.assertTrue(r["same_mount_namespace_locally_observed"])
        self.assertTrue(r["same_process_root_locally_observed"])
        self.assertTrue(r["same_exact_journal_mount_locally_observed"])
        for key in ("journald_writes_to_this_mount_independently_proven",
                    "journald_effective_config_independently_verified",
                    "journald_kernel_storage_cap_independently_attested",
                    "host_or_guest_provenance_verified",
                    "independent_vm_attestation", "release_authorized",
                    "apk_or_ota_publication_authorized",
                    "unknown_windows_pe_execution_authorized"):
            self.assertIs(r[key], False)

    def test_distinct_mount_namespace_rejected(self):
        self.enter(_ns_identity=[(1, 90), (1, 91)])
        with self.assertRaisesRegex(mod.JournalProcessMountError, "distinct"):
            mod.observe_live_process_mount()

    def test_distinct_process_root_rejected(self):
        self.enter(_root_identity=[(2, 1), (2, 2)])
        with self.assertRaisesRegex(mod.JournalProcessMountError, "distinct"):
            mod.observe_live_process_mount()

    def test_pid_reused_mid_observation_rejected(self):
        self.enter(_read_bounded=[STAT, STAT_CHANGED])
        with self.assertRaisesRegex(mod.JournalProcessMountError, "changed"):
            mod.observe_live_process_mount()

    def test_service_pid_replaced_mid_observation_rejected(self):
        self.enter(_service_pid=[PID, PID + 1])
        with self.assertRaisesRegex(mod.JournalProcessMountError, "changed"):
            mod.observe_live_process_mount()

    def test_namespace_change_rejected(self):
        self.enter(_ns_identity=[(1, 90), (1, 90), (1, 99), (1, 90)])
        with self.assertRaisesRegex(mod.JournalProcessMountError, "changed"):
            mod.observe_live_process_mount()

    def test_process_root_change_rejected(self):
        self.enter(_root_identity=[(2, 1), (2, 1), (2, 1), (2, 90)])
        with self.assertRaisesRegex(mod.JournalProcessMountError, "changed"):
            mod.observe_live_process_mount()

    def test_mount_identity_different_between_observer_and_service(self):
        self.enter()
        with mock.patch.object(
                mod.mount, "_journal_mount",
                side_effect=[MOUNT, {**MOUNT, "mount_id": "202"}]):
            with self.assertRaisesRegex(mod.JournalProcessMountError, "differs"):
                mod.observe_live_process_mount()

    def test_journal_mount_switch_during_snapshot_rejected(self):
        self.enter()
        with mock.patch.object(mod.mount, "_journal_mount",
                               side_effect=[MOUNT, MOUNT,
                                            {**MOUNT, "mount_id": "555"}, MOUNT]):
            with self.assertRaisesRegex(mod.JournalProcessMountError, "changed"):
                mod.observe_live_process_mount()

    def test_journal_store_inode_replacement_rejected(self):
        self.enter()
        with mock.patch.object(mod.mount, "_secure_root_owned_path",
                               side_effect=[(3, 4), (3, 5)]):
            with self.assertRaisesRegex(mod.JournalProcessMountError, "replaced"):
                mod.observe_live_process_mount()

    def test_journal_capacity_change_rejected(self):
        self.enter()
        with mock.patch.object(mod.mount, "_filesystem_size",
                               side_effect=[SIZE, SIZE + 4096]):
            with self.assertRaisesRegex(mod.JournalProcessMountError, "changed"):
                mod.observe_live_process_mount()

    def test_invalid_journald_service_report_rejected(self):
        invalid = {"status": "LOCAL_JOURNALD_SERVICE_CGROUP_OBSERVED_ONLY",
                   "journald_pid_observed": PID,
                   "journald_running_observed_locally": True,
                   "journald_cgroup_v2_observed_locally": True,
                   "journal_storage_kernel_quota_verified": True,
                   "effective_journald_configuration_verified": False,
                   "independent_vm_attested": False,
                   "release_authorized": False}
        with (mock.patch.object(mod.runtime, "observe_live_journald",
                                return_value=invalid),
              self.assertRaises(mod.JournalProcessMountError)):
            mod._service_pid()

    def test_root_observer_rejected_before_service_query(self):
        with (mock.patch.object(mod.os, "geteuid", return_value=0),
              mock.patch.object(mod, "_service_pid") as service,
              self.assertRaises(mod.JournalProcessMountError)):
            mod.observe_live_process_mount()
        service.assert_not_called()

    def test_namespace_handle_requires_valid_kernel_inode(self):
        fake = mock.Mock(st_mode=stat.S_IFDIR | 0o755, st_dev=1, st_ino=2)
        with (mock.patch.object(mod.os, "stat", return_value=fake),
              self.assertRaises(mod.JournalProcessMountError)):
            mod._ns_identity(PID)

    def test_default_cli_does_not_read_or_spawn(self):
        out = StringIO()
        with (mock.patch.object(mod, "observe_live_process_mount") as inspect,
              redirect_stdout(out)):
            self.assertEqual(mod.main([]), 0)
        inspect.assert_not_called()
        r = json.loads(out.getvalue())
        self.assertEqual(r["status"], mod.PLAN)
        self.assertIs(r["service_or_kernel_queried"], False)

    def test_explicit_local_observation_returns_hold_exit_two(self):
        out = StringIO()
        with (mock.patch.object(mod, "observe_live_process_mount",
                                return_value={"status": mod.OBSERVED,
                                              "release_authorized": False}),
              redirect_stdout(out)):
            self.assertEqual(mod.main(["--inspect-live-journald-mount"]), 2)
        self.assertEqual(json.loads(out.getvalue())["status"], mod.OBSERVED)

    def test_bad_local_observation_returns_rejection_exit_two(self):
        out, err = StringIO(), StringIO()
        with (mock.patch.object(mod, "observe_live_process_mount",
                                side_effect=mod.JournalProcessMountError("bad")),
              redirect_stdout(out), redirect_stderr(err)):
            self.assertEqual(mod.main(["--inspect-live-journald-mount"]), 2)
        self.assertFalse(out.getvalue())
        r = json.loads(err.getvalue())
        self.assertEqual(r["status"], mod.REJECTED)
        self.assertIs(r["release_authorized"], False)
        self.assertIs(r["independent_vm_attestation"], False)


if __name__ == "__main__":
    unittest.main()
