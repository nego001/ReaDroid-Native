"""Contracts for Ghidra actually running under seccomp AND cgroups on Arch VM.

CI never invokes systemd-run. All external processes and native scope probes
are mocked, while the real code constructs its complete fail-closed launch.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_scoped_ghidra_smoke as native


class ArchRealCombinedSmokeContracts(unittest.TestCase):
    UNIT = "negresco-pe-0123456789abcdef01234567.scope"

    def run_contract(self, *, stop_accepted=True, code=0, scope=True,
                     guard=True, decompiled=True, limit_proof=True,
                     cleanup_changes=None, cleanup_remove=(),
                     capture_error=False):
        with tempfile.TemporaryDirectory(prefix="negresco-combined-contract-") as temp:
            base = Path(temp)
            pe = base / "synthetic.exe"
            pe.write_bytes(b"MZ harmless synthetic fixture")
            records = []
            if guard:
                records.append({
                    "cgroup_verification": "passed", "verified": True,
                    "memory_max": 4294967296, "pids_max": 128,
                    "cpu_quota": 200000, "cpu_period": 100000})
            if scope:
                records.append({
                    "scope_seccomp_guard": "passed", "scope": self.UNIT,
                    "filters_compiled_inside_scope": True,
                    "seccomp_filters_before_bwrap": 1})
            report = "\n".join(json.dumps(rec) for rec in records)

            def intercept_wrap(argv, **kwargs):
                self.assertEqual(kwargs["unit_name"], self.UNIT)
                self.assertEqual(kwargs["timeout_seconds"], 420)
                self.assertFalse(kwargs["proof_path"].exists())
                self.assertEqual(argv[:3], [
                    sys.executable, "-I", str(native.BRIDGE)])
                self.assertEqual(argv[3:8], [
                    "--scope", self.UNIT, "--timeout", "420", "--"])
                self.assertIn("--unshare-all", argv)
                self.assertIn("NegrescoDeepPreview.java", argv)
                self.assertIn("NegrescoSeccompRuntimeProof.java", argv)
                return ["systemd-run-mocked", *argv]

            cleanup_evidence = {
                "scope": self.UNIT,
                "verified": True,
                "scope_quiescent": True,
                "cgroup_unpopulated": True,
                "stop_request_accepted": True,
                "load_state": "loaded",
                "active_state": "inactive",
                "sub_state": "dead",
                "scope_collected": False,
            }
            if cleanup_changes is not None:
                cleanup_evidence.update(cleanup_changes)
            for field in cleanup_remove:
                cleanup_evidence.pop(field, None)
            good_proof = {"verification": "guard_verified_before_bwrap",
                          "memory_max_bytes": 4294967296,
                          "tasks_max": 128, "cpu_quota": 200000,
                          "cpu_period": 100000}
            with ExitStack() as stack:
                stack.enter_context(mock.patch.object(
                    native.os, "geteuid", return_value=1000))
                gate = stack.enter_context(mock.patch.object(
                    native, "verify_arch_vm", return_value={
                        "status": "ARCH_VM_PREFLIGHT_PASSED",
                        "vm_confirmed": True, "container": False}))
                stack.enter_context(mock.patch.object(
                    native, "new_scope_unit", return_value=self.UNIT))
                stack.enter_context(mock.patch.object(
                    native, "build_command", side_effect=lambda home, work, timeout,
                    deep_preview: [
                        "/usr/bin/bwrap", "--unshare-all", "--",
                        "/usr/bin/ghidra-fixture",
                        "NegrescoFunctionInventory.java",
                        "NegrescoDeepPreview.java",
                        "-analysisTimeoutPerFile", "390"]))
                wrap = stack.enter_context(mock.patch.object(
                    native, "wrap_in_cgroup_scope", side_effect=intercept_wrap))
                run = stack.enter_context(mock.patch.object(
                    native.bounded, "run_bounded_native",
                    side_effect=(native.bounded.BoundedNativeChildError(
                        "stdout exceeded limit") if capture_error else None),
                    return_value=mock.Mock(
                        returncode=code, stdout=report.encode("utf-8"),
                        stderr=b"")))
                stop = stack.enter_context(mock.patch.object(
                    native, "stop_and_attest_scope",
                    side_effect=(
                        (lambda unit: cleanup_evidence)
                        if stop_accepted else native.ScopeCleanupUnavailable(
                            "scope still active"))))
                read = stack.enter_context(mock.patch.object(
                    native, "read_scope_proof",
                    side_effect=(lambda path, unit: good_proof)
                    if limit_proof else native.InvalidResourceEvidence("missing")))
                runtime = stack.enter_context(mock.patch.object(
                    native, "read_ghidra_seccomp_proof",
                    return_value={
                        "verified": True, "seccomp_mode": 2,
                        "filters_before_bwrap": 1, "filters_in_ghidra": 2}))
                inventory = stack.enter_context(mock.patch.object(
                    native, "_validated_function_evidence",
                    return_value={"total_discovered": 2}))
                preview = stack.enter_context(mock.patch.object(
                    native, "_validated_deep_evidence", return_value={
                        "functions": [{"decompile_status": "ok" if decompiled
                                       else "unavailable"}]}))
                approved = (stop_accepted and code == 0 and scope and guard
                            and decompiled and limit_proof
                            and native._verified_scope_cleanup(
                                self.UNIT, cleanup_evidence)
                            and not capture_error)
                if approved:
                    report_value = native.run_native_scoped_ghidra(
                        Path("/synthetic-ghidra"), pe, base)
                    self.assertEqual(
                        report_value["status"],
                        "PASS_NATIVE_ARCH_REAL_GHIDRA_WITH_CGROUP_AND_SECCOMP")
                    self.assertEqual(report_value["decompiled_functions"], 1)
                    self.assertTrue(report_value["scope_cleanup_verified"])
                    self.assertTrue(report_value["scope_cleanup_evidence"]["cgroup_unpopulated"])
                    self.assertTrue(report_value["ghidra_jvm_seccomp_evidence"]["verified"])
                    runtime.assert_called_once()
                    self.assertFalse(report_value["windows_binary_executed"])
                    inventory.assert_called_once()
                    preview.assert_called_once()
                    read.assert_called_once_with(mock.ANY, self.UNIT)
                else:
                    with self.assertRaises(native.ScopedGhidraError):
                        native.run_native_scoped_ghidra(
                            Path("/synthetic-ghidra"), pe, base)
                gate.assert_called_once()
                wrap.assert_called_once()
                run.assert_called_once()
                self.assertEqual(run.call_args.kwargs["max_stdout"],
                                 native.MAX_SCOPE_STDOUT_BYTES)
                self.assertEqual(run.call_args.kwargs["max_stderr"],
                                 native.MAX_SCOPE_STDERR_BYTES)
                self.assertEqual(run.call_args.kwargs["timeout"], 450)
                self.assertIsInstance(run.call_args.kwargs["env"], dict)
                stop.assert_called_once_with(self.UNIT)

    def test_pass_only_with_genuine_joint_receipts_and_decompilation(self):
        self.run_contract()

    def test_refuses_failed_scope_stop_even_if_ghidra_exited_zero(self):
        self.run_contract(stop_accepted=False)

    def test_refuses_nonzero_ghidra_exit(self):
        self.run_contract(code=23)

    def test_refuses_missing_scope_or_guard(self):
        self.run_contract(scope=False)
        self.run_contract(guard=False)

    def test_refuses_missing_private_quota_proof(self):
        self.run_contract(limit_proof=False)

    def test_refuses_zero_successful_decompilations(self):
        self.run_contract(decompiled=False)

    def test_real_ghidra_intermediate_pass_rejects_malformed_cleanup_receipt(self):
        # Pure mocks: no Ghidra, cgroup or Windows execution occurs here.
        for changed in (
            {"active_state": "active"},
            {"sub_state": "running"},
            {"load_state": "not-found"},
            {"scope_collected": True},
            {"stop_request_accepted": 1},
            {"verified": 1},
            {"reviewer_approved_release": True},
        ):
            with self.subTest(changed=changed):
                self.run_contract(cleanup_changes=changed)
        for missing in ("scope", "load_state", "active_state",
                        "scope_collected", "stop_request_accepted"):
            with self.subTest(missing=missing):
                self.run_contract(cleanup_remove=(missing,))
        self.run_contract(cleanup_changes={
            "load_state": "not-found", "scope_collected": True,
            "stop_request_accepted": False})

    def test_bounded_output_overflow_refuses_pass_and_attests_cleanup(self):
        # Contract mock for oversized output; no real Ghidra is launched.
        self.run_contract(capture_error=True)

    def test_direct_call_outside_arch_vm_never_creates_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pe = root / "synthetic.exe"
            pe.write_bytes(b"MZ synthetic-only")
            with mock.patch.object(native.os, "geteuid", return_value=1000):
                with mock.patch.object(
                        native, "verify_arch_vm",
                        side_effect=native.ArchVmUnavailable("not a VM")):
                    with mock.patch.object(native, "new_scope_unit") as scope:
                        with mock.patch.object(native.bounded, "run_bounded_native") as run:
                            with self.assertRaises(native.ArchVmUnavailable):
                                native.run_native_scoped_ghidra(
                                    Path("/ghidra"), pe, root)
                        scope.assert_not_called()
                        run.assert_not_called()

    def test_false_vm_claim_cannot_pass_native_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pe = root / "synthetic.exe"
            pe.write_bytes(b"MZ synthetic-only")
            with mock.patch.object(native.os, "geteuid", return_value=1000):
                with mock.patch.object(native, "verify_arch_vm",
                                       return_value={
                                           "status": "ARCH_VM_PREFLIGHT_PASSED",
                                           "vm_confirmed": False,
                                           "container": True}):
                    with mock.patch.object(native, "new_scope_unit") as scope:
                        with self.assertRaisesRegex(
                                native.ScopedGhidraError, "VM safety gate"):
                            native.run_native_scoped_ghidra(
                                Path("/ghidra"), pe, root)
                        scope.assert_not_called()

    def test_refuses_to_run_as_root(self):
        with mock.patch.object(native.os, "geteuid", return_value=0):
            with mock.patch.object(native.bounded, "run_bounded_native") as started:
                with self.assertRaisesRegex(native.ScopedGhidraError, "unprivileged"):
                    native.run_native_scoped_ghidra(
                        Path("/ghidra"), Path("/input.exe"), Path("/tmp"))
        started.assert_not_called()


if __name__ == "__main__":
    unittest.main()
