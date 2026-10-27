"""Contracts for PE-S1.5. CI NEVER performs the native VM/cgroup smoke."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_gate as gate
import pe_arch_vm_validation as validation


class ArchVmGateTests(unittest.TestCase):
    def test_container_is_rejected_even_when_running_above_a_vm(self):
        with mock.patch.object(gate, "preflight"):
            with mock.patch.object(gate.shutil, "which", return_value="/usr/bin/tool"):
                with mock.patch.object(gate.subprocess, "run",
                                       return_value=mock.Mock(returncode=0)):
                    with self.assertRaisesRegex(gate.ArchVmUnavailable, "container"):
                        gate.verify_arch_vm()

    def test_vm_probe_failure_blocks_acceptance(self):
        with mock.patch.object(gate, "preflight"):
            with mock.patch.object(gate.shutil, "which", return_value="/usr/bin/tool"):
                with mock.patch.object(gate.subprocess, "run",
                                       return_value=mock.Mock(returncode=1)):
                    with mock.patch.object(gate, "_system_command",
                                           side_effect=gate.ArchVmUnavailable("not vm")):
                        with self.assertRaisesRegex(gate.ArchVmUnavailable, "not vm"):
                            gate.verify_arch_vm()

    def test_missing_user_bus_is_rejected(self):
        with mock.patch.object(gate, "preflight"):
            with mock.patch.object(gate.shutil, "which", return_value="/usr/bin/tool"):
                with mock.patch.object(gate.subprocess, "run",
                                       return_value=mock.Mock(returncode=1)):
                    with mock.patch.object(gate, "_system_command"):
                        with mock.patch.object(gate.os, "getuid", return_value=1000):
                            with mock.patch.object(gate.os, "geteuid", return_value=1000):
                                with mock.patch.dict(gate.os.environ,
                                                     {"XDG_RUNTIME_DIR": "/fake/run"}):
                                    with self.assertRaisesRegex(
                                            gate.ArchVmUnavailable, "runtime"):
                                        gate.verify_arch_vm()


class ArchVmAcceptanceTests(unittest.TestCase):
    def test_vm_gate_refuses_before_any_resource_or_ghidra_test(self):
        with mock.patch.object(validation, "verify_arch_vm",
                               side_effect=gate.ArchVmUnavailable("not a VM")):
            with mock.patch.object(validation, "run_smoke") as quotas:
                with mock.patch.object(validation, "validate_real_ghidra") as ghidra:
                    with self.assertRaises(gate.ArchVmUnavailable):
                        validation.run_acceptance(Path("/sample/ghidra"))
        quotas.assert_not_called()
        ghidra.assert_not_called()

    def test_missing_descendant_proof_blocks_ghidra(self):
        with mock.patch.object(validation, "verify_arch_vm", return_value={"status": "VM"}):
            with mock.patch.object(validation, "run_smoke",
                                   return_value={"status": "PASS_NATIVE_ARCH_CGROUP"}):
                with mock.patch.object(validation, "run_native_descendant_smoke",
                                       return_value={"status": "REJECTED_NOT_HOMOLOGATED"}):
                    with mock.patch.object(validation, "validate_real_ghidra") as ghidra:
                        with self.assertRaisesRegex(
                                validation.ArchVmValidationError, "not approved"):
                            validation.run_acceptance(Path("/sample/ghidra"))
        ghidra.assert_not_called()

    def test_acceptance_requires_ghidra_and_two_real_smokes(self):
        quotas = {"status": "PASS_NATIVE_ARCH_CGROUP", "memory_max": 4294967296,
                  "pids_max": 128, "cpu_quota": 200000, "cpu_period": 100000}
        descendant = {"status": "PASS_NATIVE_ARCH_DESCENDANTS",
                      "detached_sigterm_ignoring_child_terminated": True}
        with mock.patch.object(validation, "verify_arch_vm",
                               return_value={"status": "ARCH_VM_PREFLIGHT_PASSED"}):
            with mock.patch.object(validation, "run_smoke", return_value=quotas):
                with mock.patch.object(validation, "run_native_descendant_smoke",
                                       return_value=descendant):
                    with mock.patch.object(validation, "validate_real_ghidra",
                                           return_value={"status": "PASS_REAL_ARCH_VM_GHIDRA"}):
                        result = validation.run_acceptance(Path("/sample/ghidra"))
        self.assertEqual(result["status"], "PASS_PE_S1_5_ARCH_VM")
        self.assertFalse(result["windows_binary_executed"])

    def test_real_ghidra_requires_private_quota_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "ghidra"
            (home / "support").mkdir(parents=True)
            (home / "support" / "analyzeHeadless").write_text("mock")
            incomplete = {"evidence": {"total_discovered": 2},
                          "deep_preview": {"functions": [{"decompile_status": "ok"}]},
                          "limitations": {"os_sandbox": "bubblewrap_profile",
                                          "executable_launched": False,
                                          "resource_scope": "not_enforced"}}

            def fake_inspect(pe, ghidra, report_path, **opts):
                report_path.write_text("{}")
                self.assertEqual(opts["sandbox_mode"], "bwrap")
                self.assertTrue(opts["require_cgroup_limits"])
                self.assertTrue(opts["deep_preview"])
                return incomplete

            with mock.patch.object(validation, "java25_preflight"):
                with mock.patch.object(validation.subprocess, "run",
                                       return_value=mock.Mock(returncode=0)):
                    with mock.patch.object(validation, "inspect_functions",
                                           side_effect=fake_inspect):
                        with self.assertRaisesRegex(
                                validation.ArchVmValidationError, "incomplete"):
                            validation.validate_real_ghidra(home, timeout_seconds=420)


if __name__ == "__main__":
    unittest.main()
