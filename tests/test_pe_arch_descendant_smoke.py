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
                          oversized_output=False, unexpected_stderr=False):
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
            kwargs["stdout"].write(proof_line.encode("utf-8"))
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
                                                    and not cleanup_other_scope
                                                    and not oversized_output
                                                    and not unexpected_stderr):
                                                result = smoke.run_native_descendant_smoke()
                                                cleanup.assert_called_once_with(self.unit)
                                            else:
                                                with self.assertRaises(smoke.DescendantProbeError):
                                                    smoke.run_native_descendant_smoke()
                                                if (proof and child_gone
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
        if proof and not oversized_output and not unexpected_stderr:
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
                                    return_value=child)):
                with self.assertRaisesRegex(
                        smoke.DescendantProbeError, "exclusively"):
                    smoke._worker(marker, self.unit)
            self.assertEqual(canary.read_bytes(), b"unchanged")
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
                    spawn.assert_called_once()
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
