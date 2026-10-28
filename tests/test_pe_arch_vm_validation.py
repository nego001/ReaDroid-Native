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
    def test_s1_24_missing_or_invalid_challenge_blocks_vm_run(self):
        from contextlib import redirect_stderr
        from io import StringIO
        for challenge in (None, "0" * 64, "Z" * 64, "a" * 63):
            with self.subTest(challenge=challenge):
                argv = ["pe_arch_vm_validation.py",
                        "--ghidra-home", "/tmp/ghidra",
                        "--ghidra-archive", "/tmp/official.zip",
                        "--evidence-output", "/tmp/private/proof.json"]
                if challenge is not None:
                    argv.extend(["--reviewer-challenge", challenge])
                with (mock.patch.object(validation.sys, "argv", argv),
                      mock.patch.object(validation, "run_acceptance") as native,
                      redirect_stderr(StringIO())):
                    self.assertEqual(validation.main(), 2)
                native.assert_not_called()

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

    def test_unproven_initial_scope_blocks_descendant_experiment(self):
        for rejected in (
                {"status": "PASS_NATIVE_ARCH_CGROUP"},
                {"status": "PASS_NATIVE_ARCH_CGROUP",
                 "scope": "negresco-pe-cccccccccccccccccccccccc.scope",
                 "quota_private_proof": {
                     "verification": "guard_verified_before_bwrap"},
                 "scope_cleanup_evidence": {
                     "scope": "negresco-pe-cccccccccccccccccccccccc.scope",
                     "verified": True, "scope_quiescent": False,
                     "cgroup_unpopulated": False,
                     "active_state": "active", "sub_state": "running"}},
        ):
            with self.subTest(rejected=rejected):
                with (
                    mock.patch.object(validation, "verify_arch_vm",
                                      return_value={"status": "ARCH_VM_PREFLIGHT_PASSED"}),
                    mock.patch.object(validation, "run_smoke",
                                      return_value=rejected),
                    mock.patch.object(validation, "run_native_descendant_smoke") as descendant,
                    mock.patch.object(validation, "validate_real_ghidra") as ghidra,
                ):
                    with self.assertRaisesRegex(
                            validation.ArchVmValidationError,
                            "Initial native cgroup"):
                        validation.run_acceptance(
                            Path("/sample/ghidra"), Path("/sample/zip"))
                descendant.assert_not_called()
                ghidra.assert_not_called()

    def test_acceptance_requires_ghidra_and_two_real_smokes(self):
        quotas = {
            "status": "PASS_NATIVE_ARCH_CGROUP",
            "scope": "negresco-pe-cccccccccccccccccccccccc.scope",
            "memory_max": 4294967296, "pids_max": 128,
            "cpu_quota": 200000, "cpu_period": 100000,
            "quota_private_proof": {
                "verification": "guard_verified_before_bwrap",
                "memory_max_bytes": 4294967296, "tasks_max": 128,
                "cpu_quota": 200000, "cpu_period": 100000},
            "scope_cleanup_evidence": {
                "scope": "negresco-pe-cccccccccccccccccccccccc.scope",
                "verified": True, "scope_quiescent": True,
                "cgroup_unpopulated": True,
                "active_state": "inactive", "sub_state": "dead"},
            "ghidra_executed": False, "windows_binary_executed": False,
        }
        descendant = {"status": "PASS_NATIVE_ARCH_DESCENDANTS",
                      "scope": "negresco-pe-0123456789abcdef01234567.scope",
                      "detached_sigterm_ignoring_child_terminated": True,
                      "systemd_stop_succeeded": True,
                      "quota_verified": True,
                      "quota_private_proof": {
                          "verification": "guard_verified_before_bwrap",
                          "memory_max_bytes": 4294967296,
                          "tasks_max": 128,
                          "cpu_quota": 200000, "cpu_period": 100000},
                      "descendant_cleanup_evidence": {
                          "scope": "negresco-pe-0123456789abcdef01234567.scope",
                          "verified": True, "scope_quiescent": True,
                          "cgroup_unpopulated": True,
                          "active_state": "inactive", "sub_state": "dead"}}
        with mock.patch.object(validation, "verify_arch_vm",
                               return_value={"status": "ARCH_VM_PREFLIGHT_PASSED"}):
            with mock.patch.object(validation, "run_smoke", return_value=quotas):
                with mock.patch.object(validation, "run_native_descendant_smoke",
                                       return_value=descendant):
                    with mock.patch.object(validation, "validate_real_ghidra",
                                           return_value={"status": "PASS_REAL_ARCH_VM_GHIDRA"}):
                        with mock.patch.object(
                                validation, "validate_native_acceptance_report") as policy:
                            result = validation.run_acceptance(
                                Path("/sample/ghidra"), Path("/sample/zip"))
        policy.assert_called_once_with(result)
        self.assertEqual(result["status"], "PASS_PE_S1_5_ARCH_VM")
        self.assertFalse(result["windows_binary_executed"])
        self.assertEqual(result["cgroup_lifecycle"], quotas)
        self.assertTrue(result["cgroup_lifecycle"][
            "scope_cleanup_evidence"]["cgroup_unpopulated"])
        self.assertTrue(result["descendant_lifecycle"][
            "descendant_cleanup_evidence"]["cgroup_unpopulated"])

    def test_stdout_pass_without_valid_private_receipt_policy_is_refused(self):
        # A forged-looking PASS from internal stages cannot reach stdout just
        # because --evidence-output was omitted. The final gate still runs.
        quotas = {
            "status": "PASS_NATIVE_ARCH_CGROUP",
            "scope": "negresco-pe-cccccccccccccccccccccccc.scope",
            "memory_max": 4294967296, "pids_max": 128,
            "cpu_quota": 200000, "cpu_period": 100000,
            "quota_private_proof": {
                "verification": "guard_verified_before_bwrap",
                "memory_max_bytes": 4294967296, "tasks_max": 128,
                "cpu_quota": 200000, "cpu_period": 100000},
            "scope_cleanup_evidence": {
                "scope": "negresco-pe-cccccccccccccccccccccccc.scope",
                "verified": True, "scope_quiescent": True,
                "cgroup_unpopulated": True,
                "active_state": "inactive", "sub_state": "dead"},
            "ghidra_executed": False, "windows_binary_executed": False,
        }
        descendant = {
            "status": "PASS_NATIVE_ARCH_DESCENDANTS",
            "scope": "negresco-pe-0123456789abcdef01234567.scope",
            "detached_sigterm_ignoring_child_terminated": True,
            "systemd_stop_succeeded": True, "quota_verified": True,
            "quota_private_proof": {
                "verification": "guard_verified_before_bwrap",
                "memory_max_bytes": 8 * 1024 ** 3,
                "tasks_max": 128, "cpu_quota": 200000,
                "cpu_period": 100000},
            "descendant_cleanup_evidence": {
                "scope": "negresco-pe-0123456789abcdef01234567.scope",
                "verified": True, "scope_quiescent": True,
                "cgroup_unpopulated": True, "active_state": "inactive",
                "sub_state": "dead"},
        }
        with (
            mock.patch.object(validation, "verify_arch_vm", return_value={
                "status": "ARCH_VM_PREFLIGHT_PASSED",
                "vm_confirmed": True, "container": False}),
            mock.patch.object(validation, "run_smoke", return_value=quotas),
            mock.patch.object(validation, "run_native_descendant_smoke",
                              return_value=descendant),
            mock.patch.object(validation, "validate_real_ghidra",
                              return_value={"status": "PASS_REAL_ARCH_VM_GHIDRA"}),
        ):
            with self.assertRaisesRegex(
                    validation.ArchVmValidationError, "PASS refused"):
                validation.run_acceptance(
                    Path("/sample/ghidra"), Path("/sample/zip"))

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
                                        "scope": "negresco-pe-0123456789abcdef01234567.scope",
                                        "filter_compiled_after_guard": True,
                                        "cgroup_verification": {"verification": "guard_verified_before_bwrap"},
                                        "scope_cleanup_evidence": {
                                            "scope": "negresco-pe-0123456789abcdef01234567.scope",
                                            "verified": True, "scope_quiescent": True,
                                            "cgroup_unpopulated": True}
                                    }):
                                with (mock.patch.object(validation, "inspect_functions",
                                                       side_effect=fake_inspect),
                                      mock.patch.object(validation,
                                          "run_native_scoped_ghidra", return_value={
                                              "status": "PASS_NATIVE_ARCH_REAL_GHIDRA_WITH_CGROUP_AND_SECCOMP",
                                              "scope": "negresco-pe-0123456789abcdef01234567.scope",
                                              "scope_cleanup_verified": True,
                                              "scope_cleanup_evidence": {
                                                  "scope": "negresco-pe-0123456789abcdef01234567.scope",
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
