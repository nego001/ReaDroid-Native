"""Contract tests for the Arch descendant cleanup diagnostic.

All positive-path systemd actions are mocked; CI cannot validate a native
Arch host's cgroup or real systemd session.
"""
from pathlib import Path
import json
import os
import signal
import subprocess
import sys
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

    def test_active_identity_fails_for_zombies_and_recycled_pid(self):
        with mock.patch.object(smoke, "proc_identity", return_value=("S", "123")):
            self.assertTrue(smoke.active_identity(2345, "123"))
            self.assertFalse(smoke.active_identity(2345, "999"))
        with mock.patch.object(smoke, "proc_identity", return_value=("Z", "123")):
            self.assertFalse(smoke.active_identity(2345, "123"))
        with mock.patch.object(smoke, "proc_identity", return_value=None):
            self.assertFalse(smoke.active_identity(2345, "123"))

    def _synthetic_result(self, *, child_gone=True, proof=True,
                          cleanup_quiescent=True, cleanup_other_scope=False):
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
            kwargs["stdout"].flush()
            return fake_process

        with mock.patch.object(smoke, "verify_arch_vm",
                               return_value={"status": "ARCH_VM_PREFLIGHT_PASSED",
                                             "vm_confirmed": True,
                                             "container": False}):
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
                                                    and not cleanup_other_scope):
                                                result = smoke.run_native_descendant_smoke()
                                                cleanup.assert_called_once_with(self.unit)
                                            else:
                                                with self.assertRaises(smoke.DescendantProbeError):
                                                    smoke.run_native_descendant_smoke()
                                                if proof and child_gone:
                                                    cleanup.assert_called_once_with(self.unit)
                                                else:
                                                    cleanup.assert_not_called()
                                                result = None
        self.assertEqual(wrap.call_args.kwargs["timeout_seconds"], 30)
        self.assertEqual(wrap.call_args.kwargs["unit_name"], self.unit)
        self.assertEqual(wrap.call_args.kwargs["proof_path"].name, "quota.json")
        # Private quotas are checked BEFORE attempting to stop the child,
        # including the negative test where that child deliberately survives.
        if proof:
            quota_read.assert_called_once_with(mock.ANY, self.unit)
        else:
            quota_read.assert_not_called()
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
