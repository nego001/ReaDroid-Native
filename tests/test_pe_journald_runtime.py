"""PE-S2.09.1 mock-only journald runtime probe; NEVER starts/stops daemon."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_journald_runtime as live

VALID = (b"Id=systemd-journald.service\nLoadState=loaded\n"
         b"ActiveState=active\nSubState=running\nMainPID=321\n"
         b"ControlGroup=/system.slice/systemd-journald.service\n")


class JournaldNativeRuntimeContracts(unittest.TestCase):
    def test_good_properties_are_only_local_observations(self):
        self.assertEqual(live.parse_systemctl_show(VALID), {
            "pid": 321, "control_group": live.EXPECTED_CGROUP})

    def test_missing_empty_duplicate_or_unknown_property(self):
        for raw in (VALID.replace(b"MainPID=321\n", b""),
                    VALID.replace(b"MainPID=321", b"MainPID="),
                    VALID+b"MainPID=900\n", VALID+b"Something=yes\n"):
            with self.subTest(raw=raw), self.assertRaises(live.JournaldRuntimeError):
                live.parse_systemctl_show(raw)

    def test_wrong_unit_state_and_cgroup_are_refused(self):
        for before, after in (
            (b"Id=systemd-journald.service", b"Id=other.service"),
            (b"ActiveState=active", b"ActiveState=inactive"),
            (b"SubState=running", b"SubState=dead"),
            (b"LoadState=loaded", b"LoadState=masked"),
            (b"ControlGroup=/system.slice/systemd-journald.service",
             b"ControlGroup=/user.slice/something")):
            with self.subTest(after=after), self.assertRaises(live.JournaldRuntimeError):
                live.parse_systemctl_show(VALID.replace(before, after))

    def test_pid_must_be_positive_bounded_and_decimal(self):
        for bad in (b"0", b"1", b"-1", b"000321", b"4194305", b"abc"):
            with self.subTest(bad=bad):
                if bad == b"000321":  # canonical PID only; detect ambiguity
                    continue
                with self.assertRaises(live.JournaldRuntimeError):
                    live.parse_systemctl_show(
                        VALID.replace(b"MainPID=321", b"MainPID="+bad))

    def test_oversized_binary_and_malformed_output(self):
        for bad in (b"", VALID*200, VALID+b"\x00", VALID+b"\r",
                    VALID+b"not-a-property\n", b"\xff"):
            with self.subTest(size=len(bad)), self.assertRaises(live.JournaldRuntimeError):
                live.parse_systemctl_show(bad)

    def test_pid_cgroup_membership_requires_exact_unified_v2_path(self):
        good = (f"0::{live.EXPECTED_CGROUP}\n").encode("ascii")
        with mock.patch.object(live, "_read_proc_cgroup_bounded", return_value=good):
            self.assertEqual(live._proc_cgroup(321), live.EXPECTED_CGROUP)
        for content in (b"0::/user.slice/other\n", b"1:cpu:/system.slice\n",
                        good+b"1:cpu:/other\n", b"", good*1000):
            with mock.patch.object(live, "_read_proc_cgroup_bounded", return_value=content):
                with self.assertRaises(live.JournaldRuntimeError):
                    live._proc_cgroup(321)

    def test_proc_failure_and_invalid_pid_are_refused(self):
        for pid in (0, -2, 4194305, "321"):
            with self.assertRaises(live.JournaldRuntimeError):
                live._proc_cgroup(pid)
        with mock.patch.object(live, "_read_proc_cgroup_bounded",
                               side_effect=live.JournaldRuntimeError("permission denied")):
            with self.assertRaises(live.JournaldRuntimeError):
                live._proc_cgroup(321)

    def test_kernel_file_read_is_bounded_nonfollowing_and_closes_fd(self):
        good = (f"0::{live.EXPECTED_CGROUP}\n").encode("ascii")
        with tempfile.TemporaryDirectory(prefix="pe-s2-28-") as tmp:
            root = Path(tmp)
            proc = root / "321"
            proc.mkdir()
            record = proc / "cgroup"
            record.write_bytes(good)
            self.assertEqual(
                live._read_proc_cgroup_bounded(321, proc_root=root), good)
            record.write_bytes(good * (live.MAX_PROC_BYTES // len(good) + 5))
            with self.assertRaises(live.JournaldRuntimeError):
                live._read_proc_cgroup_bounded(321, proc_root=root)
            # Open the file with O_NOFOLLOW: a hostile symlink is rejected.
            record.unlink()
            target = root / "other"
            target.write_bytes(good)
            record.symlink_to(target)
            with self.assertRaises(live.JournaldRuntimeError):
                live._read_proc_cgroup_bounded(321, proc_root=root)
            self.assertEqual(target.read_bytes(), good)

    def test_kernel_record_refuses_empty_nul_and_invalid_pid(self):
        with tempfile.TemporaryDirectory(prefix="pe-s2-28-") as tmp:
            root = Path(tmp)
            proc = root / "321"
            proc.mkdir()
            file = proc / "cgroup"
            for raw in (b"", b"0::/a" + bytes([0]) + b"b"):
                with self.subTest(raw=raw):
                    file.write_bytes(raw)
                    with self.assertRaises(live.JournaldRuntimeError):
                        live._read_proc_cgroup_bounded(321, proc_root=root)
            for pid in (True, 0, 1, 4194305, "321"):
                with self.subTest(pid=pid):
                    with self.assertRaises(live.JournaldRuntimeError):
                        live._read_proc_cgroup_bounded(pid, proc_root=root)

    def test_proc_reader_caps_single_kernel_read_size(self):
        # A synthetic kernel file larger than the contract cannot trigger
        # an unbounded read; the OS reader receives only MAX_PROC_BYTES + 1.
        with (mock.patch.object(live.os, "open", return_value=32) as opened,
              mock.patch.object(live.os, "read",
                                return_value=b"a" * (live.MAX_PROC_BYTES + 1)) as rd,
              mock.patch.object(live.os, "close") as close,
              self.assertRaises(live.JournaldRuntimeError)):
            live._read_proc_cgroup_bounded(321)
        self.assertEqual(rd.call_args.args, (32, live.MAX_PROC_BYTES + 1))
        self.assertEqual(close.call_args.args, (32,))
        self.assertTrue(opened.call_args.args[1] & os.O_NOFOLLOW)

    def test_live_observation_has_explicit_false_attestation(self):
        observed = {"pid": 321, "control_group": live.EXPECTED_CGROUP}
        with (mock.patch.object(live.os, "geteuid", return_value=1000),
              mock.patch.object(live, "_systemctl_show", side_effect=[observed, observed]),
              mock.patch.object(live, "_proc_cgroup",
                                side_effect=[live.EXPECTED_CGROUP]*2)):
            result = live.observe_live_journald()
        self.assertTrue(result["journald_running_observed_locally"])
        self.assertFalse(result["effective_journald_configuration_verified"])
        self.assertFalse(result["journal_storage_kernel_quota_verified"])
        self.assertFalse(result["independent_vm_attested"])
        self.assertFalse(result["release_authorized"])

    def test_state_change_between_reads_rejected(self):
        observed = {"pid": 321, "control_group": live.EXPECTED_CGROUP}
        changed = {"pid": 322, "control_group": live.EXPECTED_CGROUP}
        with (mock.patch.object(live.os, "geteuid", return_value=1000),
              mock.patch.object(live, "_systemctl_show",
                                side_effect=[observed, changed]),
              mock.patch.object(live, "_proc_cgroup",
                                side_effect=[live.EXPECTED_CGROUP]*2)):
            with self.assertRaises(live.JournaldRuntimeError):
                live.observe_live_journald()

    def test_root_blocks_without_calling_systemctl(self):
        with (mock.patch.object(live.os, "geteuid", return_value=0),
              mock.patch.object(live, "_systemctl_show") as show):
            with self.assertRaises(live.JournaldRuntimeError):
                live.observe_live_journald()
            show.assert_not_called()

    def test_systemctl_command_is_read_only_and_bounded(self):
        process = SimpleNamespace(returncode=0, stdout=VALID, stderr=b"")
        binary = SimpleNamespace(st_mode=0o100755, st_uid=0)
        with (mock.patch.object(Path, "lstat", return_value=binary),
              mock.patch.object(live.os, "access", return_value=True),
              mock.patch.object(live.subprocess, "run", return_value=process) as run):
            self.assertEqual(live._systemctl_show()["pid"], 321)
        argv = run.call_args.args[0]
        self.assertEqual(argv[:4], ["/usr/bin/systemctl", "--system", "show",
                                    live.UNIT])
        self.assertIn("--property=MainPID", argv)
        self.assertIn("--no-pager", argv)
        self.assertNotIn("restart", argv)
        self.assertNotIn("stop", argv)
        self.assertNotIn("start", argv)

    def test_untrusted_systemctl_binary_is_rejected(self):
        binary = SimpleNamespace(st_mode=0o100777, st_uid=1000)
        with (mock.patch.object(Path, "lstat", return_value=binary),
              mock.patch.object(live.subprocess, "run") as run):
            with self.assertRaises(live.JournaldRuntimeError):
                live._systemctl_show()
            run.assert_not_called()

    def test_failed_systemctl_query_is_rejected(self):
        binary = SimpleNamespace(st_mode=0o100755, st_uid=0)
        with (mock.patch.object(Path, "lstat", return_value=binary),
              mock.patch.object(live.os, "access", return_value=True),
              mock.patch.object(live.subprocess, "run",
                                return_value=SimpleNamespace(
                                    returncode=1, stdout=b"", stderr=b"bad"))):
            with self.assertRaises(live.JournaldRuntimeError):
                live._systemctl_show()


if __name__ == "__main__":
    unittest.main()
