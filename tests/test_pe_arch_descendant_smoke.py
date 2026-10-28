"""Contract tests for the Arch descendant cleanup diagnostic.

All positive-path systemd actions are mocked; CI cannot validate a native
Arch host's cgroup or real systemd session.
"""
from pathlib import Path
import json
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_descendant_smoke as smoke


class NativeDescendantTests(unittest.TestCase):
    def setUp(self):
        self.unit = "negresco-pe-0123456789abcdef01234567.scope"

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

    def _synthetic_result(self, *, child_gone=True, proof=True):
        proof_line = (
            '{"cgroup_verification": "passed", "verified": true}\n'
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
                with mock.patch.object(smoke, "wrap_in_cgroup_scope",
                                       side_effect=lambda cmd, **opts: cmd) as wrap:
                    with mock.patch.object(smoke.subprocess, "Popen",
                                           side_effect=launch) as popen:
                        with mock.patch.object(smoke, "belongs_to_scope",
                                               return_value=True):
                            with mock.patch.object(smoke, "active_identity",
                                                   side_effect=[True, False]):
                                with mock.patch.object(smoke, "wait_until_dead",
                                                       return_value=child_gone):
                                    with mock.patch.object(smoke, "stop_scope",
                                                           return_value=True) as stop:
                                        with mock.patch.object(
                                                smoke, "stop_and_attest_scope",
                                                return_value={
                                                    "scope": self.unit,
                                                    "verified": True,
                                                    "scope_quiescent": True,
                                                    "cgroup_unpopulated": True,
                                                    "active_state": "inactive",
                                                    "sub_state": "dead",
                                                }) as cleanup:
                                            if proof and child_gone:
                                                result = smoke.run_native_descendant_smoke()
                                                cleanup.assert_called_once_with(self.unit)
                                            else:
                                                with self.assertRaises(smoke.DescendantProbeError):
                                                    smoke.run_native_descendant_smoke()
                                                cleanup.assert_not_called()
                                                result = None
        self.assertEqual(wrap.call_args.kwargs["timeout_seconds"], 30)
        self.assertEqual(wrap.call_args.kwargs["unit_name"], self.unit)
        self.assertTrue(popen.call_args.kwargs["close_fds"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertGreaterEqual(stop.call_count, 1)
        return result

    def test_accepts_only_scope_killing_live_detached_child(self):
        result = self._synthetic_result()
        self.assertEqual(result["status"], "PASS_NATIVE_ARCH_DESCENDANTS")
        self.assertTrue(result["quota_verified"])
        self.assertTrue(result["detached_sigterm_ignoring_child_terminated"])
        self.assertTrue(result["descendant_cleanup_evidence"]["cgroup_unpopulated"])
        self.assertFalse(result["windows_binary_executed"])

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


if __name__ == "__main__":
    unittest.main()
