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
                     guard=True, decompiled=True, limit_proof=True):
        with tempfile.TemporaryDirectory(prefix="negresco-combined-contract-") as temp:
            base = Path(temp)
            pe = base / "synthetic.exe"
            pe.write_bytes(b"MZ harmless synthetic fixture")
            records = []
            if guard:
                records.append({"cgroup_verification": "passed", "verified": True})
            if scope:
                records.append({
                    "scope_seccomp_guard": "passed", "scope": self.UNIT,
                    "filters_compiled_inside_scope": True})
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
                return ["systemd-run-mocked", *argv]

            good_proof = {"verification": "guard_verified_before_bwrap",
                          "memory_max_bytes": 4294967296,
                          "tasks_max": 128, "cpu_quota": 200000,
                          "cpu_period": 100000}
            with ExitStack() as stack:
                stack.enter_context(mock.patch.object(
                    native.os, "geteuid", return_value=1000))
                stack.enter_context(mock.patch.object(
                    native, "new_scope_unit", return_value=self.UNIT))
                stack.enter_context(mock.patch.object(
                    native, "build_command", side_effect=lambda home, work, timeout,
                    deep_preview: [
                        "/usr/bin/bwrap", "--unshare-all", "--",
                        "/usr/bin/ghidra-fixture",
                        "NegrescoFunctionInventory.java",
                        "NegrescoDeepPreview.java"]))
                wrap = stack.enter_context(mock.patch.object(
                    native, "wrap_in_cgroup_scope", side_effect=intercept_wrap))
                run = stack.enter_context(mock.patch.object(
                    native.subprocess, "run",
                    return_value=mock.Mock(returncode=code, stdout=report)))
                stop = stack.enter_context(mock.patch.object(
                    native, "stop_scope", return_value=stop_accepted))
                read = stack.enter_context(mock.patch.object(
                    native, "read_scope_proof",
                    side_effect=(lambda path, unit: good_proof)
                    if limit_proof else native.InvalidResourceEvidence("missing")))
                inventory = stack.enter_context(mock.patch.object(
                    native, "_validated_function_evidence",
                    return_value={"total_discovered": 2}))
                preview = stack.enter_context(mock.patch.object(
                    native, "_validated_deep_evidence", return_value={
                        "functions": [{"decompile_status": "ok" if decompiled
                                       else "unavailable"}]}))
                approved = (stop_accepted and code == 0 and scope and guard
                            and decompiled and limit_proof)
                if approved:
                    report_value = native.run_native_scoped_ghidra(
                        Path("/synthetic-ghidra"), pe, base)
                    self.assertEqual(
                        report_value["status"],
                        "PASS_NATIVE_ARCH_REAL_GHIDRA_WITH_CGROUP_AND_SECCOMP")
                    self.assertEqual(report_value["decompiled_functions"], 1)
                    self.assertTrue(report_value["scope_stop_accepted"])
                    self.assertFalse(report_value["windows_binary_executed"])
                    inventory.assert_called_once()
                    preview.assert_called_once()
                    read.assert_called_once_with(mock.ANY, self.UNIT)
                else:
                    with self.assertRaises(native.ScopedGhidraError):
                        native.run_native_scoped_ghidra(
                            Path("/synthetic-ghidra"), pe, base)
                wrap.assert_called_once()
                run.assert_called_once()
                self.assertTrue(run.call_args.kwargs["close_fds"])
                self.assertEqual(run.call_args.kwargs["stdin"],
                                 native.subprocess.DEVNULL)
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

    def test_refuses_to_run_as_root(self):
        with mock.patch.object(native.os, "geteuid", return_value=0):
            with mock.patch.object(native.subprocess, "run") as started:
                with self.assertRaisesRegex(native.ScopedGhidraError, "unprivileged"):
                    native.run_native_scoped_ghidra(
                        Path("/ghidra"), Path("/input.exe"), Path("/tmp"))
        started.assert_not_called()


if __name__ == "__main__":
    unittest.main()
