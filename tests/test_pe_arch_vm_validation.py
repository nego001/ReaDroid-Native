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
                        validation.run_acceptance(Path("/sample/ghidra"), Path("/sample/zip"))
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
                            validation.run_acceptance(Path("/sample/ghidra"), Path("/sample/zip"))
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
                        result = validation.run_acceptance(Path("/sample/ghidra"), Path("/sample/zip"))
        self.assertEqual(result["status"], "PASS_PE_S1_5_ARCH_VM")
        self.assertFalse(result["windows_binary_executed"])

    def test_rejects_unsupported_ghidra_release_even_with_launch_script(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / "Ghidra").mkdir()
            meta = home / "Ghidra/application.properties"
            meta.write_text("application.name=Ghidra\napplication.version=12.3\n")
            with self.assertRaisesRegex(
                    validation.ArchVmValidationError, "exactly 12.2"):
                validation.validate_ghidra_122_install(home)
            meta.write_text("application.name=Ghidra\napplication.version=12.2\n")
            validation.validate_ghidra_122_install(home)
            meta.write_text("application.name=Ghidra\napplication.version=12.2\napplication.version=12.2\n")
            with self.assertRaisesRegex(validation.ArchVmValidationError,
                                        "Duplicate"):
                validation.validate_ghidra_122_install(home)

    def test_arch_bwrap_probe_rejects_unverified_filesystem_or_network(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pe = root / "synthetic.exe"
            pe.write_bytes(b"MZsynthetic-pe-not-executed")
            cmd = ["/usr/bin/bwrap", "--unshare-all", "--",
                   "/usr/bin/placeholder"]
            incomplete = {
                "isolation_probe": "passed", "host_home_canary_hidden": True,
                "network_namespace_separate": False, "host_etc_hidden": True,
                "usr_runtime_read_only": True, "private_work_writable": True,
                "inherited_host_fd_hidden": True}
            with mock.patch.object(validation, "build_command", return_value=cmd):
                with mock.patch.object(
                        validation.subprocess, "run",
                        return_value=mock.Mock(returncode=0,
                                               stdout=json.dumps(incomplete))) as run:
                    with self.assertRaisesRegex(
                            validation.ArchVmValidationError, "incomplete"):
                        validation.native_bwrap_probe(Path("/unused-ghidra"), pe, root)
            argv = run.call_args.args[0]
            self.assertEqual(argv[argv.index("--") + 1], "/usr/bin/python3")
            self.assertIn("/work/pe_sandbox_probe.py", argv)
            self.assertIn("network_namespace_separate", incomplete)
            incomplete["network_namespace_separate"] = True
            second = root / "second-attempt"
            second.mkdir()
            with mock.patch.object(validation, "build_command", return_value=cmd):
                with mock.patch.object(
                        validation.subprocess, "run",
                        return_value=mock.Mock(returncode=0,
                                               stdout=json.dumps(incomplete))):
                    result = validation.native_bwrap_probe(
                        Path("/unused-ghidra"), pe, second)
            self.assertEqual(result["status"], "PASS_NATIVE_ARCH_BWRAP_PROBE")
            self.assertTrue(result["inherited_host_fd_hidden"])
            self.assertTrue(run.call_args.kwargs["close_fds"])

    def test_arch_vm_rejects_unproven_scoped_seccomp_before_ghidra(self):
        with tempfile.TemporaryDirectory() as tmp:
            ghidra = Path(tmp) / "ghidra"
            (ghidra / "support").mkdir(parents=True)
            (ghidra / "support/analyzeHeadless").write_text("synthetic")
            (ghidra / "Ghidra").mkdir()
            (ghidra / "Ghidra/application.properties").write_text(
                "application.name=Ghidra\napplication.version=12.2\n",
                encoding="utf-8")
            with mock.patch.object(validation, "verify_pinned_ghidra_tree",
                                   return_value={"verified": True}):
                with mock.patch.object(validation, "java25_preflight"):
                    with mock.patch.object(validation.subprocess, "run",
                                           return_value=mock.Mock(returncode=0)):
                        with mock.patch.object(validation, "native_bwrap_probe",
                                               return_value={"status": "PASS_NATIVE_ARCH_BWRAP_PROBE"}):
                            with mock.patch.object(validation, "run_scoped_seccomp_probe",
                                                   return_value={
                                                       "status": "REJECTED_NOT_HOMOLOGATED",
                                                       "filter_compiled_after_guard": False
                                                   }):
                                with mock.patch.object(validation, "inspect_functions") as inspect:
                                    with self.assertRaisesRegex(
                                            validation.ArchVmValidationError,
                                            "joint native attestation incomplete"):
                                        validation.validate_real_ghidra(
                                            ghidra, Path(tmp) / "synthetic.zip")
                                inspect.assert_not_called()

    def test_real_ghidra_requires_private_quota_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "ghidra"
            (home / "support").mkdir(parents=True)
            (home / "support" / "analyzeHeadless").write_text("mock")
            (home / "Ghidra").mkdir()
            (home / "Ghidra" / "application.properties").write_text(
                "application.name=Ghidra\napplication.version=12.2\n",
                encoding="utf-8")
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

            with mock.patch.object(validation, "verify_pinned_ghidra_tree",
                                   return_value={"verified": True}):
                with mock.patch.object(validation, "java25_preflight"):
                    with mock.patch.object(validation.subprocess, "run",
                                       return_value=mock.Mock(returncode=0)):
                        with mock.patch.object(validation, "native_bwrap_probe",
                                               return_value={"status": "PASS_NATIVE_ARCH_BWRAP_PROBE"}):
                            with mock.patch.object(
                                    validation, "run_scoped_seccomp_probe",
                                    return_value={
                                        "status": "PASS_NATIVE_ARCH_VM_SCOPED_SECCOMP",
                                        "filter_compiled_after_guard": True,
                                        "cgroup_verification": {"verification": "guard_verified_before_bwrap"},
                                        "scope_cleanup_evidence": {
                                            "verified": True, "scope_quiescent": True,
                                            "cgroup_unpopulated": True}
                                    }):
                                with (mock.patch.object(validation, "inspect_functions",
                                                       side_effect=fake_inspect),
                                      mock.patch.object(validation,
                                          "run_native_scoped_ghidra", return_value={
                                              "status": "PASS_NATIVE_ARCH_REAL_GHIDRA_WITH_CGROUP_AND_SECCOMP",
                                              "scope_cleanup_verified": True,
                                              "scope_cleanup_evidence": {
                                                  "verified": True,
                                                  "scope_quiescent": True,
                                                  "cgroup_unpopulated": True,
                                                  "active_state": "inactive",
                                                  "sub_state": "dead"},
                                              "filter_compiled_inside_scope": True,
                                              "quotas_verified_before_bwrap": {
                                                  "verification": "guard_verified_before_bwrap"},
                                              "decompiled_functions": 2,
                                              "ghidra_jvm_seccomp_evidence": {
                                                  "verified": True, "seccomp_mode": 2,
                                                  "filters_before_bwrap": 1,
                                                  "filters_in_ghidra": 2},
                                              "windows_binary_executed": False})):
                                    with self.assertRaisesRegex(
                                            validation.ArchVmValidationError, "incomplete"):
                                        validation.validate_real_ghidra(
                                            home, Path("/fake/release.zip"),
                                            timeout_seconds=420)


if __name__ == "__main__":
    unittest.main()
