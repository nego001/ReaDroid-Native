"""PE-S2.25 local read-only PID snapshot contracts, no native Arch VM."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s2_25_pid_kernel_snapshot as diag

PID = 2468
SCOPE = "negresco-pe-" + "a1" * 12 + ".scope"
GROUP = "/user.slice/user-1000.slice/user@1000.service/app.slice/" + SCOPE


class PidKernelSnapshotContracts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="pe-s2-25-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.proc = root / "proc"
        self.cg = root / "sys" / "fs" / "cgroup"
        self.process = self.proc / str(PID)
        self.scope = self.cg / GROUP.lstrip("/")
        self.process.mkdir(parents=True)
        self.scope.mkdir(parents=True)
        self.write_kernel()

    def write_kernel(self, *, seccomp=2, filters=1, uid=1000,
                     memory="4294967296\n", tasks="128\n",
                     cpu="200000 100000\n", start=123456,
                     group=GROUP):
        # /proc/PID/stat: fields 3.., where starttime (field 22) is index 19.
        fields = ["S"] + ["0"] * 18 + [str(start)] + ["0"] * 24
        (self.process / "stat").write_text(
            f"{PID} (java headless) " + " ".join(fields) + "\n", encoding="ascii")
        (self.process / "status").write_text(
            f"Name:\tjava\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
            f"Seccomp:\t{seccomp}\nSeccomp_filters:\t{filters}\n",
            encoding="ascii")
        (self.process / "cgroup").write_text("0::" + group + "\n",
                                              encoding="ascii")
        (self.scope / "memory.max").write_text(memory, encoding="ascii")
        (self.scope / "pids.max").write_text(tasks, encoding="ascii")
        (self.scope / "cpu.max").write_text(cpu, encoding="ascii")

    def snap(self, **kwargs):
        return diag.snapshot_pid(
            PID, SCOPE, proc_root=self.proc, cgroup_root=self.cg,
            expected_uid=1000, **kwargs)

    def test_short_kernel_reads_cannot_hide_contradictory_cgroup_tail(self):
        prefix = ("0::" + GROUP + "\n").encode("ascii")
        extra = b"1:cpu:/hostile\n"
        with (mock.patch.object(diag, "open_absolute_directory_nofollow",
                                return_value=101) as parent,
              mock.patch.object(diag.os, "open", return_value=41) as opened,
              mock.patch.object(diag.os, "read",
                                side_effect=[prefix, extra, b""]) as read,
              mock.patch.object(diag.os, "close") as closed):
            complete = diag._read_bounded(self.process / "cgroup")
        self.assertEqual(complete, (prefix + extra).decode("ascii"))
        self.assertEqual(read.call_count, 3)
        closed.assert_called_once_with(41)
        self.assertTrue(opened.call_args.args[1] & os.O_NOFOLLOW)
        self.assertEqual(opened.call_args.kwargs["dir_fd"], 101)
        parent.assert_called_once()
        with self.assertRaises(diag.PidSnapshotError):
            diag._cgroup_path(complete, SCOPE)

    def test_short_quota_read_cannot_hide_relaxed_tail(self):
        with (mock.patch.object(diag, "open_absolute_directory_nofollow",
                                return_value=101),
              mock.patch.object(diag.os, "open", return_value=42),
              mock.patch.object(diag.os, "read",
                                side_effect=[b"128\n", b"999\n", b""]),
              mock.patch.object(diag.os, "close") as closed):
            result = diag._read_bounded(self.scope / "pids.max")
        self.assertEqual(result, "128\n999\n")
        with self.assertRaises(diag.PidSnapshotError):
            diag._finite_number(result, 128)
        closed.assert_called_once_with(42)

    def test_kernel_reader_enforces_cap_even_when_data_is_chunked(self):
        with (mock.patch.object(diag, "open_absolute_directory_nofollow",
                                return_value=101),
              mock.patch.object(diag.os, "open", return_value=43),
              mock.patch.object(diag.os, "read",
                                side_effect=[b"x" * diag.MAX_BYTES, b"y"]) as read,
              mock.patch.object(diag.os, "close") as closed,
              self.assertRaises(diag.PidSnapshotError)):
            diag._read_bounded(self.process / "status")
        self.assertEqual(read.call_args.args, (43, 1))
        closed.assert_called_once_with(43)

    def test_kernel_reader_closes_fd_after_read_failure(self):
        with (mock.patch.object(diag, "open_absolute_directory_nofollow",
                                return_value=101),
              mock.patch.object(diag.os, "open", return_value=44),
              mock.patch.object(diag.os, "read",
                                side_effect=OSError("simulated procfs failure")),
              mock.patch.object(diag.os, "close") as closed,
              self.assertRaises(diag.PidSnapshotError)):
            diag._read_bounded(self.process / "stat")
        closed.assert_called_once_with(44)

    def test_kernel_reader_rejects_final_symlink_and_nul(self):
        path = self.process / "stat"
        old = path.read_bytes()
        path.write_bytes(old + bytes([0]))
        with self.assertRaises(diag.PidSnapshotError):
            diag._read_bounded(path)
        path.unlink()
        target = self.process / "outside-stat"
        target.write_bytes(old)
        path.symlink_to(target)
        with self.assertRaises(diag.PidSnapshotError):
            diag._read_bounded(path)
        self.assertEqual(target.read_bytes(), old)

    def test_intermediate_symlink_in_pid_path_is_refused(self):
        # O_NOFOLLOW on the final stat file alone does not protect /proc/PID.
        real = self.proc / "real-process"
        self.process.rename(real)
        self.process.symlink_to(real, target_is_directory=True)
        with self.assertRaises(diag.PidSnapshotError):
            self.snap()
        self.assertTrue((real / "stat").is_file())

    def test_intermediate_symlink_in_cgroup_path_is_refused(self):
        # Parent cgroup symlinks must not redirect quota observations.
        user_slice = self.cg / "user.slice"
        real = self.cg / "real-user.slice"
        user_slice.rename(real)
        user_slice.symlink_to(real, target_is_directory=True)
        with self.assertRaises(diag.PidSnapshotError):
            self.snap()
        self.assertTrue((real / "user-1000.slice").is_dir())

    def test_noncanonical_or_relative_kernel_paths_are_refused(self):
        for bad in (Path("relative/status"),
                    self.proc / ".." / str(PID) / "stat"):
            with self.subTest(path=str(bad)):
                with self.assertRaises(diag.PidSnapshotError):
                    diag._read_bounded(bad)

    def test_consistent_local_kernel_values_never_attest_vm(self):
        x = self.snap()
        self.assertEqual(x["status"], diag.OBSERVED)
        self.assertEqual(x["security_classification"], diag.UNTRUSTED)
        self.assertEqual(x["proc_start_ticks"], 123456)
        self.assertEqual(x["seccomp_mode"], 2)
        self.assertEqual(x["seccomp_filters"], 1)
        self.assertEqual(x["memory_max_bytes"], 4294967296)
        self.assertEqual(x["tasks_max"], 128)
        self.assertEqual(x["cpu_quota_us"], 200000)
        self.assertTrue(x["same_pid_local_kernel_snapshot"])
        for key in ("ghidra_process_identity_independently_verified",
                    "native_arch_kernel_provenance_verified",
                    "independent_vm_attestation", "release_authorized",
                    "apk_or_ota_publication_authorized",
                    "unknown_windows_pe_execution_authorized"):
            self.assertIs(x[key], False, key)

    def test_unchanged_kernel_quotas_are_observed_twice(self):
        real = diag._read_bounded
        touched = []
        def measure(path):
            touched.append(path.name)
            return real(path)
        with mock.patch.object(diag, "_read_bounded", side_effect=measure):
            report = self.snap()
        self.assertEqual(report["status"], diag.OBSERVED)
        for name in ("memory.max", "pids.max", "cpu.max"):
            self.assertEqual(touched.count(name), 2, name)

    def test_zombie_dead_stopped_and_unknown_stat_states_rejected(self):
        stat = self.process / "stat"
        for state in ("Z", "X", "x", "T", "t", "I", "W", "K", "P", "?", "ZZ"):
            with self.subTest(state=state):
                self.write_kernel()
                original = stat.read_text("ascii")
                changed = original.replace(") S ", f") {state} ", 1)
                self.assertNotEqual(changed, original)
                stat.write_text(changed, encoding="ascii")
                with self.assertRaisesRegex(diag.PidSnapshotError,
                                             "not live"):
                    self.snap()

    def test_runnable_and_sleeping_kernel_states_accepted_locally_only(self):
        stat = self.process / "stat"
        for state in ("R", "S", "D"):
            with self.subTest(state=state):
                self.write_kernel()
                original = stat.read_text("ascii")
                stat.write_text(original.replace(") S ", f") {state} ", 1),
                                encoding="ascii")
                result = self.snap()
                self.assertEqual(result["proc_start_ticks"], 123456)
                self.assertEqual(result["status"], diag.OBSERVED)
                self.assertIs(result["independent_vm_attestation"], False)
                self.assertIs(result["release_authorized"], False)

    def test_process_zombifies_during_final_pid_check_rejected(self):
        self.write_kernel()
        original = diag._read_bounded
        stat_reads = [0]
        def zombify_during_final_read(path):
            if path.name == "stat":
                stat_reads[0] += 1
                if stat_reads[0] == 3:
                    stat = self.process / "stat"
                    original_stat = stat.read_text("ascii")
                    stat.write_text(original_stat.replace(") S ", ") Z ", 1),
                                    encoding="ascii")
            return original(path)
        with (mock.patch.object(diag, "_read_bounded",
                                side_effect=zombify_during_final_read),
              self.assertRaisesRegex(diag.PidSnapshotError, "not live")):
            self.snap()
        self.assertEqual(stat_reads[0], 3)

    def test_pid_identity_checked_after_second_quota_pass(self):
        real = diag._read_bounded
        touched = []
        def observe(path):
            touched.append(path.name)
            return real(path)
        with mock.patch.object(diag, "_read_bounded", side_effect=observe):
            report = self.snap()
        self.assertEqual(report["status"], diag.OBSERVED)
        for name in ("stat", "status", "cgroup"):
            self.assertEqual(touched.count(name), 3, name)
        for name in ("memory.max", "pids.max", "cpu.max"):
            self.assertEqual(touched.count(name), 2, name)
        self.assertEqual(touched[-3:], ["stat", "status", "cgroup"])
        self.assertIs(report["independent_vm_attestation"], False)
        self.assertIs(report["release_authorized"], False)

    def test_pid_or_seccomp_or_cgroup_change_during_final_quota_read_rejected(self):
        # Each mutation occurs AFTER the earlier identity comparison and
        # DURING the second quota pass, when old code stopped reading /proc.
        for target in ("stat", "status", "cgroup"):
            with self.subTest(target=target):
                self.write_kernel()
                original = diag._read_bounded
                quota_reads = [0]
                def mutate_after_last_quota(path):
                    value = original(path)
                    if path.name == "cpu.max":
                        quota_reads[0] += 1
                        if quota_reads[0] == 2:
                            evidence = self.process / target
                            old_text = evidence.read_text("ascii")
                            if target == "stat":
                                new_text = old_text.replace("123456", "123457")
                            elif target == "status":
                                new_text = old_text.replace(
                                    "Seccomp:\t2\n", "Seccomp:\t0\n")
                            else:
                                new_text = old_text.replace(
                                    "0::" + GROUP + "\n", "0::" + GROUP + "/child\n")
                            self.assertNotEqual(new_text, old_text)
                            evidence.write_text(new_text, encoding="ascii")
                    return value
                with (mock.patch.object(diag, "_read_bounded",
                                        side_effect=mutate_after_last_quota),
                      self.assertRaisesRegex(diag.PidSnapshotError,
                                             "final quota verification")):
                    self.snap()
                self.assertEqual(quota_reads[0], 2)

    def test_bounded_quota_drift_during_pid_snapshot_rejected(self):
        cases = (
            ("memory.max", "2147483648\n"),
            ("pids.max", "64\n"),
            ("cpu.max", "100000 100000\n"),
        )
        for target, updated in cases:
            with self.subTest(target=target):
                self.write_kernel()
                old = diag._read_bounded
                count = [0]
                def change_on_second_quota_read(path):
                    if path.name == target:
                        count[0] += 1
                        if count[0] == 2:
                            (self.scope / target).write_text(updated, encoding="ascii")
                    return old(path)
                with (mock.patch.object(diag, "_read_bounded",
                                        side_effect=change_on_second_quota_read),
                      self.assertRaisesRegex(diag.PidSnapshotError,
                                             "quotas changed")):
                    self.snap()
                self.assertEqual(count[0], 2)

    def test_relaxed_quota_on_second_read_rejected(self):
        self.write_kernel()
        old = diag._read_bounded
        count = [0]
        def relax_memory(path):
            if path.name == "memory.max":
                count[0] += 1
                if count[0] == 2:
                    (self.scope / "memory.max").write_text("max\n", encoding="ascii")
            return old(path)
        with (mock.patch.object(diag, "_read_bounded", side_effect=relax_memory),
              self.assertRaisesRegex(diag.PidSnapshotError,
                                     "Missing finite kernel quota")):
            self.snap()
        self.assertEqual(count[0], 2)

    def test_process_change_rejects_before_second_quota_pass(self):
        old = diag._read_bounded
        count = []
        def mutate_stat(path):
            count.append(path.name)
            value = old(path)
            if path.name == "stat" and count.count("stat") == 2:
                return value.replace("123456", "123457")
            return value
        with (mock.patch.object(diag, "_read_bounded", side_effect=mutate_stat),
              self.assertRaisesRegex(diag.PidSnapshotError, "reused")):
            self.snap()
        for name in ("memory.max", "pids.max", "cpu.max"):
            self.assertEqual(count.count(name), 1, name)

    def test_wrong_process_or_scope_rejected_before_files(self):
        for pid, scope in ((0, SCOPE), (1, SCOPE), (True, SCOPE),
                           (PID, "other.scope"), (PID, "../" + SCOPE),
                           (PID, "negresco-pe-" + "f" * 23 + ".scope")):
            with self.subTest(pid=pid, scope=scope):
                with (mock.patch.object(diag, "_read_bounded") as read,
                      self.assertRaises(diag.PidSnapshotError)):
                    diag.snapshot_pid(pid, scope, proc_root=self.proc,
                                      cgroup_root=self.cg, expected_uid=1000)
                read.assert_not_called()

    def test_seccomp_absent_or_filtered_wrong_uid_rejected(self):
        for values in ({"seccomp": 0}, {"seccomp": 1}, {"filters": 0},
                       {"uid": 999}):
            with self.subTest(values=values):
                self.write_kernel(**values)
                with self.assertRaises(diag.PidSnapshotError):
                    self.snap()

    def test_quota_values_must_be_finite_and_bounded(self):
        for values in ({"memory": "max\n"}, {"memory": "4294967297\n"},
                       {"memory": "0\n"}, {"tasks": "max\n"},
                       {"tasks": "129\n"}, {"cpu": "max 100000\n"},
                       {"cpu": "300000 100000\n"},
                       {"cpu": "0 100000\n"}, {"cpu": "200000 0\n"},
                       {"cpu": "100000 100000 extra\n"}):
            with self.subTest(values=values):
                self.write_kernel(**values)
                with self.assertRaises(diag.PidSnapshotError):
                    self.snap()

    def test_cgroup_v1_or_path_traversal_and_wrong_unit_rejected(self):
        for group in ("2:cpu:/a\n3:memory:/b", "/wrong.scope",
                      "/user.slice/../" + SCOPE,
                      "/user.slice//" + SCOPE):
            with self.subTest(group=group):
                self.write_kernel(group=group)
                with self.assertRaises(diag.PidSnapshotError):
                    self.snap()

    def test_pid_reuse_during_snapshot_rejected(self):
        original = diag._read_bounded
        reads = [0]
        def change(path):
            value = original(path)
            if path.name == "stat":
                reads[0] += 1
                if reads[0] == 2:
                    return value.replace("123456", "999999")
            return value
        with (mock.patch.object(diag, "_read_bounded", side_effect=change),
              self.assertRaisesRegex(diag.PidSnapshotError, "reused")):
            self.snap()
        self.assertEqual(reads[0], 2)

    def test_duplicate_status_field_rejected(self):
        status = self.process / "status"
        status.write_text(status.read_text("ascii") + "Seccomp:\t2\n",
                          encoding="ascii")
        with self.assertRaises(diag.PidSnapshotError):
            self.snap()

    def test_symlink_quota_refused(self):
        (self.scope / "memory.max").unlink()
        (self.scope / "memory.max").symlink_to(self.scope / "pids.max")
        with self.assertRaises(diag.PidSnapshotError):
            self.snap()

    def test_plan_mode_does_not_read_any_process_or_write_files(self):
        output = StringIO()
        with (mock.patch.object(diag, "_read_bounded") as read,
              mock.patch.object(diag, "snapshot_pid") as snapshot,
              redirect_stdout(output)):
            code = diag.main(["--pid", str(PID),
                              "--expected-scope", SCOPE])
        self.assertEqual(code, 0)
        read.assert_not_called()
        snapshot.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"], diag.PLAN)
        self.assertEqual(json.loads(output.getvalue())["kernel_files_read"], False)

    def test_active_cli_rejects_root_or_wrong_kernel_without_release(self):
        output, err = StringIO(), StringIO()
        with (mock.patch.object(diag.os, "geteuid", return_value=0),
              redirect_stdout(output), redirect_stderr(err)):
            code = diag.main(["--pid", str(PID),
                              "--expected-scope", SCOPE,
                              "--snapshot-local-pid"])
        self.assertEqual(code, 2)
        self.assertFalse(output.getvalue())
        result = json.loads(err.getvalue())
        self.assertEqual(result["status"], diag.REJECTED)
        self.assertIs(result["release_authorized"], False)
        self.assertIs(result["independent_vm_attestation"], False)


if __name__ == "__main__":
    unittest.main()
