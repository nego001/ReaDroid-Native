"""Native Arch cgroup contracts; synthetic receipts, NEVER a live host scope."""
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_cgroup_smoke as native


UNIT = "negresco-pe-0123456789abcdef01234567.scope"
GUARD = {
    "cgroup_verification": "passed", "verified": True,
    "memory_max": 4294967296, "pids_max": 128,
    "cpu_quota": 200000, "cpu_period": 100000,
}
CHILD = {"synthetic_child": "passed"}
CLEANUP = {
    "scope": UNIT, "verified": True,
    "scope_quiescent": True, "cgroup_unpopulated": True,
    "active_state": "inactive", "sub_state": "dead",
    "load_state": "not-found", "stop_request_accepted": False,
    "scope_collected": True,
}


class NativeArchSmokeTests(unittest.TestCase):
    def test_rejects_root_without_starting_systemd(self):
        with mock.patch.object(native.sys, "platform", "linux"):
            with mock.patch.object(native.os, "geteuid", return_value=0):
                with self.assertRaisesRegex(RuntimeError, "regular user"):
                    native.preflight()

    def run_synthetic(self, records=None, *, write_proof=True, cleanup=None,
                      failure=None, status=0):
        stdout = "\n".join(json.dumps(x) for x in
                           ([GUARD, CHILD] if records is None else records)) + "\n"
        result = mock.Mock(returncode=status, stderr="synthetic", stdout=stdout)

        def wrap(command, **kwargs):
            if write_proof:
                record = {
                    "schema": "negresco_cgroup_v2_proof_v1",
                    "scope": kwargs["unit_name"],
                    "verified": True,
                    "memory_max": 4294967296,
                    "pids_max": 128,
                    "cpu_quota": 200000,
                    "cpu_period": 100000,
                }
                kwargs["proof_path"].write_text(json.dumps(record),
                                                encoding="utf-8")
                kwargs["proof_path"].chmod(0o600)
            return ["synthetic"]

        with (
            mock.patch.object(native, "preflight") as preflight,
            mock.patch.object(native, "new_scope_unit", return_value=UNIT),
            mock.patch.object(native, "wrap_in_cgroup_scope",
                              side_effect=wrap) as wrapped,
            mock.patch.object(native.subprocess, "run",
                              side_effect=failure if failure else None,
                              return_value=result) as launched,
            mock.patch.object(native, "stop_and_attest_scope",
                              return_value=CLEANUP if cleanup is None else cleanup) as stopped,
        ):
            try:
                return native.run_smoke()
            finally:
                preflight.assert_called_once()
                wrapped.assert_called_once()
                self.assertEqual(wrapped.call_args.kwargs["unit_name"], UNIT)
                self.assertEqual(wrapped.call_args.kwargs["proof_path"].name,
                                 "quota.json")
                stopped.assert_called_once_with(UNIT)
                launched.assert_called_once()
                self.assertEqual(launched.call_args.kwargs["timeout"], 28)
                self.assertEqual(launched.call_args.kwargs["stdin"],
                                 native.subprocess.DEVNULL)

    def test_success_requires_private_quota_and_quiescent_scope(self):
        result = self.run_synthetic()
        self.assertEqual(result["status"], "PASS_NATIVE_ARCH_CGROUP")
        self.assertEqual(result["scope"], UNIT)
        self.assertEqual(result["pids_max"], 128)
        self.assertEqual(result["quota_private_proof"]["memory_max_bytes"],
                         4294967296)
        self.assertTrue(result["scope_cleanup_evidence"]["cgroup_unpopulated"])
        self.assertFalse(result["scope_cleanup_evidence"]["stop_request_accepted"])
        self.assertFalse(result["windows_binary_executed"])

    def test_missing_or_forged_private_quota_never_passes(self):
        with self.assertRaisesRegex(RuntimeError, "Private native cgroup"):
            self.run_synthetic(write_proof=False)
        with self.assertRaisesRegex(RuntimeError, "Private native cgroup"):
            self.run_synthetic(records=[
                {**GUARD, "memory_max": 2147483648}, CHILD])

    def test_status_messages_cannot_replace_guard_or_child(self):
        for records in (
                [CHILD], [GUARD], [GUARD, GUARD, CHILD],
                [GUARD, CHILD, CHILD],
                [GUARD, CHILD, {"synthetic_child": "passed"}]):
            with self.subTest(records=records):
                with self.assertRaises(RuntimeError):
                    self.run_synthetic(records=records)

    def test_malformed_or_unbounded_stdout_refused(self):
        for records in (
                [{**GUARD, "cpu_period": "max"}, CHILD],
                [{"synthetic_child": "passed", "cgroup_verification": "passed"}],
                [{**GUARD, "pids_max": True}, CHILD]):
            with self.subTest(records=records):
                with self.assertRaises(RuntimeError):
                    self.run_synthetic(records=records)
        with self.assertRaisesRegex(RuntimeError, "stdout exceeded bound"):
            self.run_synthetic(records=[GUARD, CHILD,
                                        {"extra": "X" * 32768}])

    def test_scope_cleanup_must_match_original_scope_and_be_empty(self):
        for replacement in (
                {"scope": UNIT, "verified": True,
                 "scope_quiescent": False, "cgroup_unpopulated": False,
                 "active_state": "active", "sub_state": "running"},
                {**CLEANUP, "scope": "negresco-pe-ffffffffffffffffffffffff.scope"},
                {**CLEANUP, "cgroup_unpopulated": False},
                {**CLEANUP, "active_state": "active"},
        ):
            with self.subTest(replacement=replacement):
                with self.assertRaisesRegex(RuntimeError, "still active"):
                    self.run_synthetic(cleanup=replacement)

    def test_timeout_also_attempts_scope_cleanup(self):
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            self.run_synthetic(failure=native.subprocess.TimeoutExpired(
                cmd=["synthetic"], timeout=28))

    def test_nonzero_child_exit_never_approves(self):
        with self.assertRaisesRegex(RuntimeError, "Native scope refused"):
            self.run_synthetic(status=2)


if __name__ == "__main__":
    unittest.main()
