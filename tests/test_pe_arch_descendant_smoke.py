"""Contract tests for the Arch descendant cleanup diagnostic.

All positive-path systemd actions are mocked; CI cannot validate a native
Arch host's cgroup or real systemd session.
"""
from pathlib import Path
import json
import os
import resource
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_descendant_smoke as smoke


class NativeDescendantTests(unittest.TestCase):
    def setUp(self):
        self.unit = "negresco-pe-0123456789abcdef01234567.scope"

    def test_direct_worker_and_grandchild_cli_refuse_non_vm(self):
        for mode in ("--worker", "--grandchild"):
            with self.subTest(mode=mode):
                argv = ["pe_arch_descendant_smoke.py", mode,
                        "/tmp/synthetic-only", self.unit]
                with mock.patch.object(smoke, "verify_arch_vm",
                                       side_effect=RuntimeError("not VM")):
                    with mock.patch.object(smoke, "_worker") as worker:
                        with mock.patch.object(smoke, "_grandchild") as child:
                            self.assertEqual(smoke.main(argv), 2)
                            worker.assert_not_called()
                            child.assert_not_called()

    def test_direct_worker_cli_refuses_incomplete_vm_claim(self):
        argv = ["pe_arch_descendant_smoke.py", "--worker",
                "/tmp/synthetic-only", self.unit]
        with mock.patch.object(smoke, "verify_arch_vm",
                               return_value={"status": "ARCH_VM_PREFLIGHT_PASSED",
                                             "vm_confirmed": False,
                                             "container": True}):
            with mock.patch.object(smoke, "_worker") as started:
                self.assertEqual(smoke.main(argv), 2)
                started.assert_not_called()

    def test_worker_requires_assigned_scope_before_fork(self):
        with mock.patch.object(smoke, "belongs_to_scope", return_value=False):
            with mock.patch.object(smoke.subprocess, "Popen") as started:
                with self.assertRaisesRegex(smoke.DescendantProbeError, "outside"):
                    smoke._worker(Path("/tmp/synthetic-marker"), self.unit)
        started.assert_not_called()

    def test_grandchild_rejects_outside_scope_before_ignoring_sigterm(self):
        with mock.patch.object(smoke, "belongs_to_scope", return_value=False):
            with mock.patch.object(smoke.signal, "signal") as handler:
                with self.assertRaisesRegex(smoke.DescendantProbeError, "outside"):
                    smoke._grandchild(self.unit, Path("/tmp/no-file-created"))
        handler.assert_not_called()

    def test_scoped_worker_refuses_incorrect_effective_file_limit(self):
        # In a real native VM, prlimit can only be claimed if the worker
        # and detached grandchild actually inherit its hard kernel limit.
        for value in ((-1, -1), (32768, -1), (65536, 65536),
                      (8192, 32768)):
            with self.subTest(value=value):
                with mock.patch.object(
                        resource, "getrlimit", return_value=value):
                    with self.assertRaisesRegex(
                            smoke.DescendantProbeError,
                            "did not inherit hard file-size limit"):
                        smoke._require_inherited_file_limit()
        with mock.patch.object(
                resource, "getrlimit", return_value=(32768, 32768)):
            smoke._require_inherited_file_limit()

    def test_bad_worker_file_limit_prevents_descendant_spawn(self):
        with (mock.patch.object(smoke, "belongs_to_scope",
                                return_value=True),
              mock.patch.object(resource, "getrlimit",
                                return_value=(-1, -1)),
              mock.patch.object(smoke.subprocess, "Popen") as spawn):
            with self.assertRaisesRegex(
                    smoke.DescendantProbeError,
                    "did not inherit hard file-size limit"):
                smoke._worker(Path("/tmp/never-created"), self.unit)
        spawn.assert_not_called()

    def test_bad_grandchild_file_limit_does_not_ignore_sigterm(self):
        with (mock.patch.object(smoke, "belongs_to_scope",
                                return_value=True),
              mock.patch.object(resource, "getrlimit",
                                return_value=(-1, -1)),
              mock.patch.object(smoke.signal, "signal") as handler):
            with self.assertRaisesRegex(
                    smoke.DescendantProbeError,
                    "did not inherit hard file-size limit"):
                smoke._grandchild(self.unit, Path("/tmp/never-created"))
        handler.assert_not_called()

    def test_bounded_proc_record_rejects_oversize_symlink_hardlink_fifo_and_binary(self):
        pid = 24680
        with tempfile.TemporaryDirectory(prefix="pe-s1-95-proc-") as root:
            proc = Path(root)
            (proc / str(pid)).mkdir()
            record = proc / str(pid) / "stat"
            record.write_bytes(b"safe-record")
            read = lambda: smoke._read_bounded_proc_record(
                pid, "stat", 128, proc_root=proc)
            self.assertEqual(read(), "safe-record")
            for bad in (b"", b"\x00record", b"\xff", b"X" * 129):
                with self.subTest(bad=bad[:15]):
                    record.write_bytes(bad)
                    with self.assertRaises(smoke.DescendantProbeError):
                        read()
            record.write_bytes(b"safe-record")
            hardlink = proc / str(pid) / "copy"
            os.link(record, hardlink)
            with self.assertRaises(smoke.DescendantProbeError):
                read()
            hardlink.unlink()
            record.unlink()
            canary = proc / str(pid) / "canary"
            canary.write_bytes(b"do-not-follow")
            record.symlink_to(canary)
            with self.assertRaises(smoke.DescendantProbeError):
                read()
            self.assertEqual(canary.read_bytes(), b"do-not-follow")
            record.unlink()
            os.mkfifo(record)
            with self.assertRaises(smoke.DescendantProbeError):
                read()
            for bad_pid, bad_leaf, bad_limit in (
                    (True, "stat", 128),
                    (1, "stat", 128),
                    (pid, "../cgroup", 128),
                    (pid, "stat", True),
                    (pid, "stat", smoke.MAX_PROC_CGROUP_BYTES + 1)):
                with self.subTest(args=(bad_pid, bad_leaf, bad_limit)):
                    with self.assertRaises(smoke.DescendantProbeError):
                        smoke._read_bounded_proc_record(
                            bad_pid, bad_leaf, bad_limit, proc_root=proc)

    def test_proc_identity_requires_own_pid_and_valid_starttime(self):
        pid = 24680
        fields = " ".join(["S"] + ["0"] * 18 + ["3333"])
        examples = [
            (f"{pid} (harmless) {fields}\n", ("S", "3333")),
            (f"24681 (harmless) {fields}\n", None),
            (f"{pid} (harmless) {fields.replace('3333', '-1')}\n", None),
            (f"{pid} (harmless) S 1 2\n", None),
            ("garbage\n", None),
        ]
        for raw, expected in examples:
            with self.subTest(raw=raw[:25]):
                with mock.patch.object(
                        smoke, "_read_bounded_proc_record", return_value=raw):
                    self.assertEqual(smoke.proc_identity(pid), expected)
        with mock.patch.object(
                smoke, "_read_bounded_proc_record",
                side_effect=smoke.DescendantProbeError("oversized")):
            self.assertIsNone(smoke.proc_identity(pid))

    def test_scope_membership_requires_one_canonical_kernel_v2_record(self):
        raw = f"0::/user.slice/user-1000.slice/{self.unit}\n"
        examples = [
            (raw, True),
            (raw + raw, False),
            ("1:name=systemd:/other.slice\n", False),
            ("0::relative/" + self.unit + "\n", False),
            ("0::/user.slice/another.scope\n", False),
            ("0::/user.slice/" + self.unit + "/nested\n", False),
        ]
        for record, expected in examples:
            with self.subTest(record=record[:60]):
                with mock.patch.object(
                        smoke, "_read_bounded_proc_record",
                        return_value=record):
                    self.assertIs(smoke.belongs_to_scope(24680, self.unit),
                                  expected)
        for invalid_unit in ("../../foo.scope", "nonsense.scope",
                             self.unit.upper(), self.unit + "/x", None):
            with self.subTest(unit=invalid_unit):
                with mock.patch.object(
                        smoke, "_read_bounded_proc_record") as read:
                    self.assertFalse(
                        smoke.belongs_to_scope(24680, invalid_unit))
                    read.assert_not_called()

    @unittest.skipUnless(sys.platform == "linux", "Linux procfs only")
    def test_real_bounded_procfs_reads_current_owned_kernel_process(self):
        pid = os.getpid()
        record = smoke._read_bounded_proc_record(
            pid, "stat", smoke.MAX_PROC_STAT_BYTES)
        self.assertTrue(record.startswith(str(pid) + " ("))
        identity = smoke.proc_identity(pid)
        self.assertIsNotNone(identity)
        self.assertTrue(smoke.active_identity(pid, identity[1]))
        cgroup = smoke._read_bounded_proc_record(
            pid, "cgroup", smoke.MAX_PROC_CGROUP_BYTES)
        self.assertIn("0::", cgroup)

    def test_active_identity_fails_for_zombies_and_recycled_pid(self):
        with mock.patch.object(smoke, "proc_identity", return_value=("S", "123")):
            self.assertTrue(smoke.active_identity(2345, "123"))
            self.assertFalse(smoke.active_identity(2345, "999"))
        with mock.patch.object(smoke, "proc_identity", return_value=("Z", "123")):
            self.assertFalse(smoke.active_identity(2345, "123"))
        with mock.patch.object(smoke, "proc_identity", return_value=None):
            self.assertFalse(smoke.active_identity(2345, "123"))

    def _synthetic_result(self, *, child_gone=True, proof=True,
                          cleanup_quiescent=True, cleanup_other_scope=False,
                          oversized_output=False, unexpected_stderr=False,
                          kernel_witness=True, guard_line=None):
        proof_line = (
            '{"cgroup_verification": "passed", "verified": true,'
            '"memory_max": 4294967296, "pids_max": 128,'
            '"cpu_quota": 200000, "cpu_period": 100000}\n'
            if proof else '{"cgroup_verification": "rejected"}\n')
        fake_process = mock.Mock()
        fake_process.poll.return_value = None
        fake_process.wait.return_value = 0

        def launch(argv, **kwargs):
            marker = Path(argv[argv.index("--worker") + 1])
            marker.write_text(json.dumps({
                "pid": 24680, "starttime": "3333", "unit": self.unit
            }), encoding="utf-8")
            kwargs["stdout"].write((guard_line if guard_line is not None
                                    else proof_line).encode("utf-8"))
            if oversized_output:
                kwargs["stdout"].write(
                    b"X" * (smoke.MAX_GUARD_STDOUT_BYTES + 1))
            kwargs["stdout"].flush()
            if unexpected_stderr:
                kwargs["stderr"].write(b"unexpected guard failure\n")
                kwargs["stderr"].flush()
            return fake_process

        with (mock.patch.object(smoke, "verify_arch_vm",
                                return_value={"status": "ARCH_VM_PREFLIGHT_PASSED",
                                              "vm_confirmed": True,
                                              "container": False}),
              mock.patch.object(
                  smoke, "_native_prlimit_prefix",
                  return_value=["/usr/bin/prlimit",
                                "--fsize=32768:32768", "--"]) as limiter):
            with mock.patch.object(smoke, "new_scope_unit", return_value=self.unit):
                with (
                    mock.patch.object(smoke, "wrap_in_cgroup_scope",
                                      side_effect=lambda cmd, **opts: cmd) as wrap,
                    mock.patch.object(smoke, "read_scope_proof",
                                      return_value={
                                          "verification": "guard_verified_before_bwrap",
                                          "memory_max_bytes": 4294967296,
                                          "tasks_max": 128,
                                          "cpu_quota": 200000, "cpu_period": 100000,
                                      }) as quota_read,
                ):
                    with mock.patch.object(smoke.subprocess, "Popen",
                                           side_effect=launch) as popen:
                        with mock.patch.object(smoke, "belongs_to_scope",
                                               return_value=True):
                            with mock.patch.object(smoke, "active_identity",
                                                   side_effect=[True, True, True]):
                                with mock.patch.object(smoke, "wait_until_dead",
                                                       return_value=child_gone):
                                    with (mock.patch.object(
                                              smoke, "stop_scope",
                                              return_value=True) as stop,
                                          mock.patch.object(
                                              smoke, "_require_pinned_descendant_file_limit",
                                              side_effect=(None if kernel_witness else
                                                           smoke.DescendantProbeError(
                                                               "Kernel limit mismatch"))
                                              ) as external_limit,
                                          mock.patch.object(
                                              smoke.os, "pidfd_open",
                                              side_effect=lambda pid, flags=0:
                                              os.open(os.devnull, os.O_RDONLY)) as pin,
                                          mock.patch.object(
                                              smoke.signal,
                                              "pidfd_send_signal") as send):
                                        with mock.patch.object(
                                                smoke, "stop_and_attest_scope",
                                                return_value={
                                                    "scope": (
                                                        "negresco-pe-ffffffffffffffffffffffff.scope"
                                                        if cleanup_other_scope else self.unit),
                                                    "verified": True,
                                                    "scope_quiescent": cleanup_quiescent,
                                                    "cgroup_unpopulated": cleanup_quiescent,
                                                    "active_state": "inactive",
                                                    "sub_state": "dead",
                                                }) as cleanup:
                                            if (proof and child_gone and cleanup_quiescent
                                                    and kernel_witness
                                                    and guard_line is None
                                                    and not cleanup_other_scope
                                                    and not oversized_output
                                                    and not unexpected_stderr):
                                                result = smoke.run_native_descendant_smoke()
                                                cleanup.assert_called_once_with(self.unit)
                                            else:
                                                with self.assertRaises(smoke.DescendantProbeError):
                                                    smoke.run_native_descendant_smoke()
                                                if (proof and child_gone and kernel_witness
                                                        and guard_line is None
                                                        and not oversized_output
                                                        and not unexpected_stderr):
                                                    cleanup.assert_called_once_with(self.unit)
                                                else:
                                                    cleanup.assert_not_called()
                                                result = None
        self.assertEqual(wrap.call_args.kwargs["timeout_seconds"], 30)
        self.assertEqual(wrap.call_args.kwargs["unit_name"], self.unit)
        self.assertEqual(wrap.call_args.kwargs["proof_path"].name, "quota.json")
        # Private quotas are checked BEFORE attempting to stop the child,
        # including the negative test where that child deliberately survives.
        # Oversized stdout or nonempty stderr is refused before the
        # quota-proof parser. No downstream attestation may run in that case.
        if (proof and kernel_witness and guard_line is None
                and not oversized_output and not unexpected_stderr):
            quota_read.assert_called_once_with(mock.ANY, self.unit)
        else:
            quota_read.assert_not_called()
        limiter.assert_called_once_with()
        self.assertEqual(
            popen.call_args.args[0][:3],
            ["/usr/bin/prlimit", "--fsize=32768:32768", "--"])
        self.assertEqual(popen.call_args.args[0][3], sys.executable)
        self.assertTrue(popen.call_args.kwargs["close_fds"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertGreaterEqual(stop.call_count, 1)
        pin.assert_called_once_with(24680, 0)
        external_limit.assert_called_once_with(24680, "3333", self.unit)
        send.assert_called_once()
        self.assertEqual(send.call_args.args[1:], (signal.SIGKILL, None, 0))
        return result

    def test_accepts_only_scope_killing_live_detached_child(self):
        result = self._synthetic_result()
        self.assertEqual(result["status"], "PASS_NATIVE_ARCH_DESCENDANTS")
        self.assertTrue(result["quota_verified"])
        self.assertEqual(result["quota_private_proof"]["verification"],
                         "guard_verified_before_bwrap")
        self.assertTrue(result["detached_sigterm_ignoring_child_terminated"])
        self.assertTrue(result["descendant_cleanup_evidence"]["cgroup_unpopulated"])
        self.assertFalse(result["windows_binary_executed"])

    def test_guard_stdout_rejects_duplicate_keys_nested_values_and_nonfinite(self):
        valid = (b'{"cgroup_verification":"passed","verified":true,'
                 b'"memory_max":4294967296,"pids_max":128,'
                 b'"cpu_quota":200000,"cpu_period":100000}\n')
        self.assertEqual(
            smoke._parse_scope_guard_stdout(b"systemd-run started\n" + valid)[0]
            ["cgroup_verification"], "passed")
        bad = [
            valid.replace(b'"verified":true,',
                          b'"verified":false,"verified":true,'),
            valid.replace(b'"pids_max":128,',
                          b'"pids_max":1,"pids_max":128,'),
            valid.replace(b'"pids_max":128,',
                          b'"pids_max":NaN,'),
            b'{"noise":{"x":1,"x":2}}\n' + valid,
            b'{"cgroup_verification":"passed"',
            b'\xff' + valid,
            valid + b"X" * smoke.MAX_GUARD_STDOUT_BYTES,
        ]
        for raw in bad:
            with self.subTest(raw=raw[:65]):
                with self.assertRaises(smoke.DescendantProbeError):
                    smoke._parse_scope_guard_stdout(raw)

    def test_ambiguous_guard_stdout_rejects_after_pidfd_pin_and_stops_scope(self):
        for line in (
            '{"cgroup_verification":"passed","verified":false,'
            '"verified":true,"memory_max":4294967296,"pids_max":128,'
            '"cpu_quota":200000,"cpu_period":100000}\n',
            '{"cgroup_verification":"passed","verified":true,'
            '"memory_max":4294967296,"pids_max":NaN,'
            '"cpu_quota":200000,"cpu_period":100000}\n',
        ):
            with self.subTest(line=line):
                with mock.patch.object(smoke.os, "kill") as numeric_kill:
                    self._synthetic_result(guard_line=line)
                numeric_kill.assert_not_called()

    def test_ready_marker_appears_only_after_complete_atomic_publication(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-92-atomic-") as root:
            folder = Path(root)
            ready = folder / "child.ready"
            pending = folder / "child.ready.pending"
            real_replace = os.replace
            observations = []

            def publish(source, destination):
                self.assertEqual(Path(source), pending)
                self.assertEqual(Path(destination), ready)
                self.assertFalse(ready.exists())
                self.assertEqual(pending.read_bytes(), b"sigterm_ignored")
                self.assertEqual(pending.stat().st_mode & 0o777, 0o600)
                observations.append(True)
                real_replace(source, destination)

            with mock.patch.object(smoke.os, "replace", side_effect=publish):
                smoke._publish_ready_marker(ready)
            self.assertEqual(observations, [True])
            self.assertFalse(pending.exists())
            self.assertEqual(ready.read_bytes(), b"sigterm_ignored")
            self.assertEqual(
                smoke._read_bounded_scope_log(
                    ready, smoke.MAX_READY_MARKER_BYTES),
                b"sigterm_ignored")

    def test_ready_marker_rejects_preexisting_destinations_without_clobbering(self):
        for kind in ("regular", "symlink", "dangling_symlink", "fifo"):
            with self.subTest(kind=kind):
                with tempfile.TemporaryDirectory(
                        prefix="pe-s1-92-ready-reject-") as root:
                    folder = Path(root)
                    ready = folder / "child.ready"
                    canary = folder / "canary"
                    canary.write_bytes(b"original")
                    if kind == "regular":
                        ready.write_bytes(b"already-here")
                    elif kind == "symlink":
                        ready.symlink_to(canary)
                    elif kind == "dangling_symlink":
                        ready.symlink_to(folder / "nonexistent")
                    else:
                        os.mkfifo(ready)
                    with self.assertRaisesRegex(
                            smoke.DescendantProbeError,
                            "Readiness marker already exists"):
                        smoke._publish_ready_marker(ready)
                    self.assertEqual(canary.read_bytes(), b"original")
                    if kind == "regular":
                        self.assertEqual(ready.read_bytes(), b"already-here")
                    self.assertTrue(ready.is_symlink()
                                    or ready.exists())

    def test_ready_marker_rejects_pending_link_and_failed_rename(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-92-rename-") as root:
            folder = Path(root)
            ready = folder / "child.ready"
            pending = folder / "child.ready.pending"
            canary = folder / "canary"
            canary.write_bytes(b"unchanged")
            pending.symlink_to(canary)
            with self.assertRaisesRegex(
                    smoke.DescendantProbeError, "exclusively"):
                smoke._publish_ready_marker(ready)
            self.assertFalse(ready.exists())
            self.assertEqual(canary.read_bytes(), b"unchanged")
            pending.unlink()
            with mock.patch.object(
                    smoke.os, "replace",
                    side_effect=OSError("filesystem rejected rename")):
                with self.assertRaisesRegex(
                        smoke.DescendantProbeError,
                        "Cannot atomically publish readiness"):
                    smoke._publish_ready_marker(ready)
            self.assertFalse(ready.exists())
            self.assertEqual(pending.read_bytes(), b"sigterm_ignored")

    def test_proc_limit_parser_requires_exact_single_hard_soft_kernel_record(self):
        good = (b"Limit Soft Limit Hard Limit Units\n"
                b"Max file size   32768 32768 bytes\n"
                b"Max stack size  8388608 unlimited bytes\n")
        smoke._require_proc_fsize_record(good)
        bad = [
            good.replace(b"32768 32768", b"32768 unlimited"),
            good.replace(b"32768 32768", b"8192 32768"),
            good.replace(b"32768 32768", b"32768 8192"),
            good.replace(b"32768 bytes", b"32768 kilobytes"),
            good + b"Max file size 32768 32768 bytes\n",
            b"Max cpu time unlimited unlimited seconds\n",
            good + b"\x00",
            b"\xff" + good,
            b"X" * (smoke.MAX_PROC_LIMITS_BYTES + 1),
            b"",
        ]
        for raw in bad:
            with self.subTest(raw=raw[:64]):
                with self.assertRaises(smoke.DescendantProbeError):
                    smoke._require_proc_fsize_record(raw)

    @unittest.skipUnless(
        sys.platform == "linux"
        and callable(getattr(os, "pidfd_open", None))
        and callable(getattr(signal, "pidfd_send_signal", None)),
        "Linux pidfd kernel test")
    def test_real_proc_limits_corroborates_harmless_pinned_python(self):
        # The process and RLIMIT_FSIZE are real; mocked membership explicitly
        # does NOT prove a user-systemd scope or native independent Arch VM.
        prefix = smoke._native_prlimit_prefix()
        with tempfile.TemporaryDirectory(prefix="pe-s1-93-proc-limits-") as root:
            ready = Path(root) / "ready"
            child = subprocess.Popen(
                [*prefix, sys.executable, "-I", "-c",
                 "import pathlib,sys,time;"
                 "pathlib.Path(sys.argv[1]).write_bytes(b'ready');"
                 "time.sleep(15)", str(ready)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, close_fds=True)
            fd = None
            try:
                deadline = time.monotonic() + 4
                while not ready.exists() and time.monotonic() < deadline:
                    self.assertIsNone(child.poll())
                    time.sleep(0.02)
                self.assertEqual(ready.read_bytes(), b"ready")
                identity = smoke.proc_identity(child.pid)
                self.assertIsNotNone(identity)
                with mock.patch.object(smoke, "belongs_to_scope",
                                       return_value=True):
                    fd = smoke._pin_descendant_pidfd(
                        child.pid, identity[1], self.unit)
                    smoke._require_pinned_descendant_file_limit(
                        child.pid, identity[1], self.unit)
            finally:
                if fd is not None:
                    try:
                        signal.pidfd_send_signal(fd, signal.SIGKILL, None, 0)
                    except ProcessLookupError:
                        pass
                    os.close(fd)
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)

    def test_invalid_external_kernel_witness_fails_and_uses_pidfd_cleanup(self):
        with mock.patch.object(smoke.os, "kill") as numeric_kill:
            self._synthetic_result(kernel_witness=False)
        numeric_kill.assert_not_called()

    def test_private_marker_is_exclusive_owner_only_and_bounded(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-91-exclusive-") as root:
            folder = Path(root)
            marker = folder / "ready"
            payload = b"sigterm_ignored"
            smoke._write_new_private_marker(
                marker, payload, smoke.MAX_READY_MARKER_BYTES)
            self.assertEqual(marker.read_bytes(), payload)
            self.assertEqual(marker.stat().st_mode & 0o777, 0o600)
            with self.assertRaisesRegex(
                    smoke.DescendantProbeError, "exclusively"):
                smoke._write_new_private_marker(
                    marker, b"overwrite", smoke.MAX_READY_MARKER_BYTES)
            self.assertEqual(marker.read_bytes(), payload)
            for data, limit in (
                    (b"", smoke.MAX_READY_MARKER_BYTES),
                    (b"X" * (smoke.MAX_READY_MARKER_BYTES + 1),
                     smoke.MAX_READY_MARKER_BYTES),
                    ("not-bytes", smoke.MAX_READY_MARKER_BYTES),
                    (b"ok", 0), (b"ok", True),
                    (b"ok", smoke.MAX_CHILD_MARKER_BYTES + 1)):
                with self.subTest(data=str(data)[:20], limit=limit):
                    with self.assertRaises(smoke.DescendantProbeError):
                        smoke._write_new_private_marker(
                            folder / "invalid", data, limit)
                    self.assertFalse((folder / "invalid").exists())

    def test_private_marker_refuses_preexisting_links_and_untrusted_parent(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-91-links-") as root:
            folder = Path(root)
            canary = folder / "canary"
            canary.write_bytes(b"do-not-change")
            symlink = folder / "symlink"
            symlink.symlink_to(canary)
            hardlink = folder / "hardlink"
            os.link(canary, hardlink)
            fifo = folder / "fifo"
            os.mkfifo(fifo)
            for target in (symlink, hardlink, fifo, canary):
                with self.subTest(path=target.name):
                    with self.assertRaises(smoke.DescendantProbeError):
                        smoke._write_new_private_marker(target, b"altered", 64)
                    self.assertEqual(canary.read_bytes(), b"do-not-change")
            untrusted = folder / "world-readable"
            untrusted.mkdir(mode=0o755)
            untrusted.chmod(0o755)
            with self.assertRaisesRegex(
                    smoke.DescendantProbeError, "Untrusted private"):
                smoke._write_new_private_marker(
                    untrusted / "marker", b"x", 64)
            self.assertFalse((untrusted / "marker").exists())

    def test_worker_refuses_preplanted_pending_symlink_without_clobbering(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-91-pending-") as root:
            folder = Path(root)
            marker = folder / "child.json"
            pending = marker.with_suffix(".pending")
            canary = folder / "canary"
            canary.write_bytes(b"unchanged")
            pending.symlink_to(canary)
            ready = marker.with_suffix(".ready")
            ready.write_bytes(b"sigterm_ignored")
            child = mock.Mock()
            child.pid = 24680
            child.poll.return_value = None
            with (mock.patch.object(smoke, "belongs_to_scope",
                                    return_value=True),
                  mock.patch.object(resource, "getrlimit",
                                    return_value=(32768, 32768)),
                  mock.patch.object(smoke, "proc_identity",
                                    return_value=("S", "3333")),
                  mock.patch.object(smoke.subprocess, "Popen",
                                    return_value=child) as spawn):
                with self.assertRaisesRegex(
                        smoke.DescendantProbeError, "already occupied"):
                    smoke._worker(marker, self.unit)
                spawn.assert_not_called()
            self.assertEqual(canary.read_bytes(), b"unchanged")
            self.assertFalse(marker.exists())

    def test_worker_fails_before_spawn_when_stale_marker_paths_exist(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-96-preflight-") as root:
            folder = Path(root)
            marker = folder / "child.json"
            ready = marker.with_suffix(".ready")
            paths = (marker, marker.with_suffix(".pending"),
                     ready, ready.with_name(ready.name + ".pending"))
            for path in paths:
                with self.subTest(path=path.name):
                    path.write_bytes(b"preplanted")
                    with (mock.patch.object(smoke, "belongs_to_scope",
                                            return_value=True),
                          mock.patch.object(resource, "getrlimit",
                                            return_value=(32768, 32768)),
                          mock.patch.object(smoke.subprocess, "Popen") as spawn):
                        with self.assertRaisesRegex(
                                smoke.DescendantProbeError, "already occupied"):
                            smoke._worker(marker, self.unit)
                        spawn.assert_not_called()
                    self.assertEqual(path.read_bytes(), b"preplanted")
                    path.unlink()

    def test_failed_worker_ready_check_kills_pinned_child_and_reaps(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-96-pidfd-") as root:
            marker = Path(root) / "child.json"
            ready = marker.with_suffix(".ready")
            child = mock.Mock()
            child.pid = 24680
            child.poll.return_value = None

            def spawn(*args, **kwargs):
                # The marker appears only after the pre-spawn freshness gate.
                ready.write_bytes(b"not-the-expected-ready-marker")
                return child

            with (mock.patch.object(smoke, "belongs_to_scope",
                                    return_value=True),
                  mock.patch.object(resource, "getrlimit",
                                    return_value=(32768, 32768)),
                  mock.patch.object(smoke.subprocess, "Popen",
                                    side_effect=spawn) as launcher,
                  mock.patch.object(smoke.os, "pidfd_open",
                                    side_effect=lambda pid, flags=0:
                                    os.open(os.devnull, os.O_RDONLY)) as pin,
                  mock.patch.object(smoke.signal,
                                    "pidfd_send_signal") as sig,
                  mock.patch.object(smoke.os, "kill") as numeric_kill):
                with self.assertRaisesRegex(
                        smoke.DescendantProbeError,
                        "SIGTERM-resistant child was not ready"):
                    smoke._worker(marker, self.unit)
            launcher.assert_called_once()
            pin.assert_called_once_with(24680, 0)
            sig.assert_called_once()
            self.assertEqual(sig.call_args.args[1:],
                             (signal.SIGKILL, None, 0))
            numeric_kill.assert_not_called()
            child.kill.assert_not_called()
            child.wait.assert_called_once_with(timeout=3)
            self.assertFalse(marker.exists())

    def test_worker_pidfd_pin_failure_terminates_unreaped_direct_child(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-96-no-pidfd-") as root:
            marker = Path(root) / "child.json"
            child = mock.Mock()
            child.pid = 24680
            child.poll.return_value = None
            with (mock.patch.object(smoke, "belongs_to_scope",
                                    return_value=True),
                  mock.patch.object(resource, "getrlimit",
                                    return_value=(32768, 32768)),
                  mock.patch.object(smoke.subprocess, "Popen",
                                    return_value=child) as launcher,
                  mock.patch.object(smoke.os, "pidfd_open",
                                    side_effect=OSError("pidfd unavailable")),
                  mock.patch.object(smoke.signal,
                                    "pidfd_send_signal") as sig):
                with self.assertRaisesRegex(
                        smoke.DescendantProbeError,
                        "Cannot pin worker-owned grandchild"):
                    smoke._worker(marker, self.unit)
            launcher.assert_called_once()
            sig.assert_not_called()
            child.kill.assert_called_once()
            child.wait.assert_called_once_with(timeout=3)
            self.assertFalse(marker.exists())

    @unittest.skipUnless(sys.platform == "linux",
                         "Linux direct child cleanup only")
    def test_real_unreaped_direct_python_child_is_killed_on_setup_error(self):
        # Harmless Python subprocess, never a systemd scope or Windows PE.
        # Its PID is owned by Popen and cannot be reused until reaped.
        with tempfile.TemporaryDirectory(prefix="pe-s1-96-real-child-") as root:
            marker = Path(root) / "child.json"
            process = None
            def spawn(*args, **kwargs):
                nonlocal process
                process = subprocess.Popen(
                    [sys.executable, "-I", "-c",
                     "import time; time.sleep(15)"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
                return process
            with (mock.patch.object(smoke, "belongs_to_scope",
                                    return_value=True),
                  mock.patch.object(resource, "getrlimit",
                                    return_value=(32768, 32768)),
                  mock.patch.object(smoke.subprocess, "Popen",
                                    side_effect=spawn),
                  mock.patch.object(smoke.os, "pidfd_open",
                                    side_effect=OSError("intentional pin failure"))):
                # Use the original Popen in spawn to avoid patched recursion.
                with self.assertRaisesRegex(
                        smoke.DescendantProbeError,
                        "Cannot pin worker-owned grandchild"):
                    smoke._worker(marker, self.unit)
            self.assertIsNotNone(process)
            self.assertIsNotNone(process.returncode)
            self.assertFalse(marker.exists())

    def test_child_marker_requires_exact_bounded_nonduplicate_json(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-90-marker-") as root:
            marker = Path(root) / "child.json"
            valid = {"pid": 24680, "starttime": "3333", "unit": self.unit}
            marker.write_text(json.dumps(valid), encoding="utf-8")
            self.assertEqual(smoke._read_child_marker(marker), valid)
            malformed = [
                b'{"pid":24680,"pid":24680,"starttime":"3333","unit":"x"}',
                b'{"pid":24680,"starttime":"3333","unit":"x","verified":true}',
                b'{"pid":true,"starttime":"3333","unit":"x"}',
                b'{"pid":24680,"starttime":"-3","unit":"x"}',
                b'{"pid":24680,"starttime":"3333","unit":null}',
                b'{"pid":24680,"starttime":"3333"}',
                b'{"pid":NaN,"starttime":"3333","unit":"x"}',
                b'\xff' + b'X' * 8,
                b'X' * (smoke.MAX_CHILD_MARKER_BYTES + 1),
            ]
            for payload in malformed:
                with self.subTest(payload=payload[:55]):
                    marker.write_bytes(payload)
                    with self.assertRaises(smoke.DescendantProbeError):
                        smoke._read_child_marker(marker)

    def test_child_marker_rejects_symlink_hardlink_and_fifo(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-90-marker-") as root:
            folder = Path(root)
            real = folder / "genuine"
            real.write_text(json.dumps({
                "pid": 24680, "starttime": "3333", "unit": self.unit
            }), encoding="utf-8")
            alias = folder / "symlink"
            alias.symlink_to(real)
            hardlink = folder / "hardlink"
            os.link(real, hardlink)
            fifo = folder / "fifo"
            os.mkfifo(fifo)
            for path in (alias, hardlink, fifo, real):
                with self.subTest(path=path.name):
                    with self.assertRaises(smoke.DescendantProbeError):
                        smoke._read_child_marker(path)

    def test_worker_refuses_oversized_or_spoofed_ready_before_pid_marker(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-90-ready-") as root:
            folder = Path(root)
            marker = folder / "child.json"
            ready = marker.with_suffix(".ready")
            canary = folder / "canary"
            canary.write_bytes(b"sigterm_ignored")
            for mode in ("oversized", "symlink", "bad"):
                with self.subTest(mode=mode):
                    if ready.is_symlink() or ready.exists():
                        ready.unlink()
                    if mode == "oversized":
                        ready.write_bytes(b"X" * (smoke.MAX_READY_MARKER_BYTES + 1))
                    elif mode == "symlink":
                        ready.symlink_to(canary)
                    else:
                        ready.write_bytes(b"unexpected")
                    child = mock.Mock()
                    child.poll.return_value = None
                    with (mock.patch.object(smoke, "belongs_to_scope",
                                            return_value=True),
                          mock.patch.object(resource, "getrlimit",
                                            return_value=(32768, 32768)),
                          mock.patch.object(smoke.subprocess, "Popen",
                                            return_value=child) as spawn):
                        with self.assertRaises(smoke.DescendantProbeError):
                            smoke._worker(marker, self.unit)
                    spawn.assert_not_called()
                    self.assertFalse(marker.exists())

    def test_bounded_scope_logs_reject_oversize_without_loading_all(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-88-log-") as root:
            path = Path(root) / "guard.stdout"
            path.write_bytes(b"A" * smoke.MAX_GUARD_STDOUT_BYTES)
            self.assertEqual(
                len(smoke._read_bounded_scope_log(
                    path, smoke.MAX_GUARD_STDOUT_BYTES)),
                smoke.MAX_GUARD_STDOUT_BYTES)
            path.write_bytes(b"B" * (smoke.MAX_GUARD_STDOUT_BYTES + 1))
            with self.assertRaisesRegex(
                    smoke.DescendantProbeError, "read budget"):
                smoke._read_bounded_scope_log(
                    path, smoke.MAX_GUARD_STDOUT_BYTES)

    def test_bounded_scope_logs_refuse_symlink_hardlink_and_fifo(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-88-log-") as root:
            folder = Path(root)
            genuine = folder / "ordinary"
            genuine.write_bytes(b"")
            dangling = folder / "link"
            dangling.symlink_to(genuine)
            with self.assertRaises(smoke.DescendantProbeError):
                smoke._read_bounded_scope_log(dangling, 128)
            fifo = folder / "fifo"
            os.mkfifo(fifo)
            # Opening an untrusted FIFO without O_NONBLOCK would hang.
            with self.assertRaises(smoke.DescendantProbeError):
                smoke._read_bounded_scope_log(fifo, 128)
            alias = folder / "hardlink"
            os.link(genuine, alias)
            with self.assertRaisesRegex(
                    smoke.DescendantProbeError, "regular file"):
                smoke._read_bounded_scope_log(genuine, 128)

    def test_bounded_scope_logs_refuse_invalid_limits(self):
        with tempfile.TemporaryDirectory(prefix="pe-s1-88-log-") as root:
            path = Path(root) / "ordinary"
            path.write_bytes(b"receipt")
            for limit in (0, -1, 2.5, True,
                          smoke.MAX_GUARD_STDOUT_BYTES + 1):
                with self.subTest(limit=limit):
                    with self.assertRaises(smoke.DescendantProbeError):
                        smoke._read_bounded_scope_log(path, limit)

    def test_oversized_or_stderr_guard_logs_fail_and_trigger_pidfd_cleanup(self):
        # These errors occur *after* the descendant is pinned: the
        # finally path must still stop the scope and use pidfd, not kill(pid).
        with mock.patch.object(smoke.os, "kill") as numeric_kill:
            self._synthetic_result(oversized_output=True)
            self._synthetic_result(unexpected_stderr=True)
        numeric_kill.assert_not_called()

    def test_missing_prlimit_refused_before_scope_creation(self):
        vm = {"status": "ARCH_VM_PREFLIGHT_PASSED",
              "vm_confirmed": True, "container": False}
        with (mock.patch.object(smoke, "verify_arch_vm", return_value=vm),
              mock.patch.object(
                  smoke, "PRLIMIT_EXECUTABLE",
                  Path("/definitely-not-installed/pe-s1-89-prlimit")),
              mock.patch.object(smoke, "new_scope_unit") as scope,
              mock.patch.object(smoke.subprocess, "Popen") as spawn):
            with self.assertRaisesRegex(
                    smoke.DescendantProbeError,
                    "Trusted /usr/bin/prlimit is required"):
                smoke.run_native_descendant_smoke()
        scope.assert_not_called()
        spawn.assert_not_called()

    def test_untrusted_prlimit_refused_before_scope_creation(self):
        vm = {"status": "ARCH_VM_PREFLIGHT_PASSED",
              "vm_confirmed": True, "container": False}
        with tempfile.TemporaryDirectory(prefix="pe-s1-89-prlimit-") as root:
            folder = Path(root)
            fake = folder / "prlimit"
            fake.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
            fake.chmod(0o777)
            alias = folder / "alias"
            alias.symlink_to(fake)
            for path in (fake, alias):
                with self.subTest(path=path):
                    with (
                        mock.patch.object(smoke, "verify_arch_vm",
                                          return_value=vm),
                        mock.patch.object(smoke, "PRLIMIT_EXECUTABLE",
                                          path),
                        mock.patch.object(smoke, "new_scope_unit") as scope,
                        mock.patch.object(smoke.subprocess, "Popen") as spawn,
                    ):
                        with self.assertRaisesRegex(
                                smoke.DescendantProbeError,
                                "Untrusted prlimit"):
                            smoke.run_native_descendant_smoke()
                    scope.assert_not_called()
                    spawn.assert_not_called()

    def test_native_prlimit_is_pinned_not_searched_on_path(self):
        with mock.patch.object(smoke, "PRLIMIT_EXECUTABLE",
                               Path("/usr/bin/prlimit")):
            with mock.patch.object(smoke, "shutil", create=True) as fake:
                # The implementation must not consult PATH or invoke
                # a user-writable prlimit lookalike.
                prefix = smoke._native_prlimit_prefix()
        self.assertEqual(prefix[0], "/usr/bin/prlimit")
        fake.which.assert_not_called()

    @unittest.skipUnless(sys.platform == "linux", "Linux-only file limit")
    def test_real_prlimit_enforces_hard_fsize_on_owned_python(self):
        # Harmless local Python fixture, no scope/systemd/PE/VM.
        prefix = smoke._native_prlimit_prefix()
        with tempfile.TemporaryDirectory(prefix="pe-s1-89-real-fsize-") as root:
            output = Path(root) / "oversized"
            # RLIMIT_FSIZE is inherited and enforced by the kernel even
            # if child Python attempts to write beyond it.
            child = subprocess.run(
                [*prefix, sys.executable, "-I", "-c",
                 "import pathlib,resource,sys; "
                 "assert resource.getrlimit(resource.RLIMIT_FSIZE)"
                 " == (32768,32768); "
                 "pathlib.Path(sys.argv[1]).write_bytes(b'X' * 65536)",
                 str(output)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=5, check=False)
            self.assertNotEqual(child.returncode, 0)
            self.assertTrue(output.is_file())
            self.assertLessEqual(
                output.stat().st_size, smoke.MAX_NATIVE_WRITE_FILE_BYTES)

    def test_refuses_platform_without_pidfd_before_spawning(self):
        vm = {"status": "ARCH_VM_PREFLIGHT_PASSED",
              "vm_confirmed": True, "container": False}
        for module, attribute in ((smoke.os, "pidfd_open"),
                                  (smoke.signal, "pidfd_send_signal")):
            with self.subTest(attribute=attribute):
                with (mock.patch.object(smoke, "verify_arch_vm",
                                        return_value=vm),
                      mock.patch.object(module, attribute, None),
                      mock.patch.object(smoke, "new_scope_unit") as scope,
                      mock.patch.object(smoke.subprocess, "Popen") as launch):
                    with self.assertRaisesRegex(
                            smoke.DescendantProbeError, "pidfd cleanup support"):
                        smoke.run_native_descendant_smoke()
                    scope.assert_not_called()
                    launch.assert_not_called()

    def test_pidfd_pin_detects_pid_reuse_after_open_and_closes_fd(self):
        fd = os.open(os.devnull, os.O_RDONLY)
        with (mock.patch.object(smoke, "active_identity",
                                side_effect=[True, False]),
              mock.patch.object(smoke, "belongs_to_scope",
                                return_value=True),
              mock.patch.object(smoke.os, "pidfd_open",
                                return_value=fd) as opened,
              mock.patch.object(smoke.os, "kill") as numeric_kill):
            with self.assertRaisesRegex(
                    smoke.DescendantProbeError, "changed during pidfd pin"):
                smoke._pin_descendant_pidfd(24680, "3333", self.unit)
        opened.assert_called_once_with(24680, 0)
        numeric_kill.assert_not_called()
        with self.assertRaises(OSError):
            os.fstat(fd)

    def test_pidfd_pin_rejects_wrong_cgroup_after_open(self):
        fd = os.open(os.devnull, os.O_RDONLY)
        with (mock.patch.object(smoke, "active_identity",
                                return_value=True),
              mock.patch.object(smoke, "belongs_to_scope",
                                side_effect=[True, False]),
              mock.patch.object(smoke.os, "pidfd_open",
                                return_value=fd)):
            with self.assertRaisesRegex(
                    smoke.DescendantProbeError, "scope changed"):
                smoke._pin_descendant_pidfd(24680, "3333", self.unit)
        with self.assertRaises(OSError):
            os.fstat(fd)

    @unittest.skipUnless(
        sys.platform == "linux"
        and callable(getattr(os, "pidfd_open", None))
        and callable(getattr(signal, "pidfd_send_signal", None)),
        "real Linux pidfd syscalls not available")
    def test_real_pidfd_signal_pins_harmless_python_child(self):
        # Exercise the REAL kernel pidfd API, but only on a harmless
        # Python sleeper created and reaped by this test itself.
        # No cgroup/systemd, unknown PE, guest VM or network is involved.
        child = subprocess.Popen(
            [sys.executable, "-I", "-c",
             "import time; time.sleep(30)"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
            close_fds=True)
        fd = None
        try:
            fd = os.pidfd_open(child.pid, 0)
            signal.pidfd_send_signal(fd, signal.SIGKILL, None, 0)
            self.assertEqual(child.wait(timeout=5), -signal.SIGKILL)
            # The same pinned descriptor can no longer signal another
            # process after the original child has been reaped.
            with self.assertRaises(ProcessLookupError):
                signal.pidfd_send_signal(fd, signal.SIGKILL, None, 0)
        finally:
            if child.poll() is None:
                # Direct, still-unreaped Popen child, not a marker PID.
                child.kill()
                child.wait(timeout=5)
            if fd is not None:
                os.close(fd)

    def test_pidfd_fallback_does_not_use_numeric_kill(self):
        with mock.patch.object(smoke.os, "kill") as numeric_kill:
            self._synthetic_result(child_gone=False)
            self._synthetic_result()
        numeric_kill.assert_not_called()

    def test_direct_descendant_probe_refuses_non_vm_before_spawning(self):
        with mock.patch.object(smoke, "verify_arch_vm",
                               side_effect=RuntimeError("not a disposable VM")):
            with mock.patch.object(smoke, "new_scope_unit") as new_scope:
                with mock.patch.object(smoke.subprocess, "Popen") as launch:
                    with self.assertRaisesRegex(RuntimeError, "disposable VM"):
                        smoke.run_native_descendant_smoke()
                new_scope.assert_not_called()
                launch.assert_not_called()

    def test_false_vm_proof_is_rejected_before_scope(self):
        with mock.patch.object(smoke, "verify_arch_vm", return_value={
            "status": "ARCH_VM_PREFLIGHT_PASSED",
            "vm_confirmed": False, "container": True
        }):
            with mock.patch.object(smoke, "new_scope_unit") as new_scope:
                with self.assertRaisesRegex(
                        smoke.DescendantProbeError, "VM not verified"):
                    smoke.run_native_descendant_smoke()
                new_scope.assert_not_called()

    def test_fails_closed_if_child_survives_or_quota_proof_missing(self):
        self._synthetic_result(child_gone=False)
        self._synthetic_result(proof=False)
        self._synthetic_result(cleanup_quiescent=False)
        self._synthetic_result(cleanup_other_scope=True)


if __name__ == "__main__":
    unittest.main()
