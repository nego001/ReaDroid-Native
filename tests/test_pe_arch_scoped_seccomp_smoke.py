"""Contract-only coverage for native scoped-seccomp/Bubblewrap acceptance.

This file does not create systemd scopes and does not run Windows executables.
"""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_scoped_seccomp_smoke as scoped


class ArchScopedSeccompSmokeTests(unittest.TestCase):
    UNIT = "negresco-pe-0123456789abcdef01234567.scope"

    def run_fixture(self, *, valid_seccomp: bool,
                    include_guard: bool = True, include_scope: bool = True,
                    include_private_proof: bool = True, stop_accepted: bool = True):
        with tempfile.TemporaryDirectory(prefix="negresco-scope-contract-") as temp:
            root = Path(temp)
            pe = root / "synthetic.exe"
            pe.write_bytes(b"MZ synthetic not executed")
            scope_receipt = {
                "scope_seccomp_guard": "passed", "scope": self.UNIT,
                "filters_compiled_inside_scope": True,
            }
            kernel_receipt = {
                "cgroup_verification": "passed", "verified": True,
                "memory_max": 4294967296, "pids_max": 128,
                "cpu_quota": 200000, "cpu_period": 100000}
            fields = (
                "host_home_canary_hidden", "network_namespace_separate",
                "host_etc_hidden", "usr_runtime_read_only",
                "private_work_writable", "inherited_host_fd_hidden",
                "seccomp_enforced")
            sandbox_receipt = {"isolation_probe": "passed",
                               **{field: True for field in fields}}
            sandbox_receipt["seccomp_enforced"] = valid_seccomp
            payload = []
            if include_scope:
                payload.append(scope_receipt)
            if include_guard:
                payload.append(kernel_receipt)
            payload.append(sandbox_receipt)

            def scope_argv(command, **options):
                self.assertEqual(options["unit_name"], self.UNIT)
                self.assertEqual(options["timeout_seconds"], 70)
                self.assertFalse(options["proof_path"].exists())
                self.assertNotIn(str(options["proof_path"]), command)
                self.assertEqual(command[0], sys.executable)
                self.assertEqual(command[1], "-I")
                self.assertEqual(Path(command[2]).name,
                                 "pe_scoped_seccomp_launcher.py")
                return ["systemd-run-synthetic", *command]

            with ExitStack() as stack:
                vm = stack.enter_context(mock.patch.object(
                    scoped, "verify_arch_vm", return_value={
                        "status": "ARCH_VM_PREFLIGHT_PASSED",
                        "vm_confirmed": True, "container": False}))
                stack.enter_context(mock.patch.object(
                    scoped, "new_scope_unit", return_value=self.UNIT))
                stack.enter_context(mock.patch.object(
                    scoped, "seccomp_filter_count", return_value=1))
                stack.enter_context(mock.patch.object(
                    scoped, "build_command",
                    side_effect=lambda home, work, secs: [
                        "/usr/bin/bwrap", "--unshare-all", "--",
                        "/usr/bin/placeholder"]))
                wrap = stack.enter_context(mock.patch.object(
                    scoped, "wrap_in_cgroup_scope", side_effect=scope_argv))
                process = stack.enter_context(mock.patch.object(
                    scoped.subprocess, "run",
                    return_value=mock.Mock(
                        returncode=0,
                        stdout="\n".join(json.dumps(x) for x in payload))))
                quota = stack.enter_context(mock.patch.object(
                    scoped, "read_scope_proof",
                    side_effect=(
                        lambda path, unit: {"verification": "guard_verified_before_bwrap"}
                        if include_private_proof
                        else (_ for _ in ()).throw(
                            scoped.InvalidResourceEvidence("absent")))))
                stop = stack.enter_context(mock.patch.object(
                    scoped, "stop_and_attest_scope",
                    side_effect=(
                        lambda unit: {
                            "scope": self.UNIT,
                            "verified": True, "scope_quiescent": True,
                            "cgroup_unpopulated": True,
                            "stop_request_accepted": True,
                            "load_state": "loaded",
                            "active_state": "inactive",
                            "sub_state": "dead",
                            "scope_collected": False
                        }
                    ) if stop_accepted else scoped.ScopeCleanupUnavailable(
                        "scope still active")))
                if (valid_seccomp and include_guard and include_scope
                        and include_private_proof and stop_accepted):
                    result = scoped.run_scoped_seccomp_probe(
                        Path("/trusted-ghidra"), pe, root)
                    self.assertEqual(
                        result["status"], "PASS_NATIVE_ARCH_VM_SCOPED_SECCOMP")
                    self.assertTrue(result["filter_compiled_after_guard"])
                    quota.assert_called_once()
                else:
                    with self.assertRaises(scoped.ScopedSeccompSmokeError):
                        scoped.run_scoped_seccomp_probe(
                            Path("/trusted-ghidra"), pe, root)
                vm.assert_called_once()
                wrap.assert_called_once()
                process.assert_called_once()
                self.assertTrue(process.call_args.kwargs["close_fds"])
                self.assertEqual(process.call_args.kwargs["stdin"],
                                 scoped.subprocess.DEVNULL)
                stop.assert_called_once_with(self.UNIT)

    def test_accepts_only_all_joint_proofs(self):
        self.run_fixture(valid_seccomp=True)

    def test_rejects_disabled_seccomp_even_with_good_scope(self):
        self.run_fixture(valid_seccomp=False)

    def test_rejects_missing_guard_or_launcher_confirmation(self):
        self.run_fixture(valid_seccomp=True, include_guard=False)
        self.run_fixture(valid_seccomp=True, include_scope=False)

    def test_rejects_missing_private_cgroup_proof(self):
        self.run_fixture(valid_seccomp=True, include_private_proof=False)

    def test_rejects_scope_stop_refusal_even_with_all_other_proofs(self):
        self.run_fixture(valid_seccomp=True, stop_accepted=False)

    def test_direct_probe_refuses_to_run_outside_real_arch_vm(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pe = root / "synthetic.exe"
            pe.write_bytes(b"MZ synthetic test")
            with mock.patch.object(scoped, "verify_arch_vm",
                                   side_effect=scoped.ArchVmUnavailable("not native")):
                with mock.patch.object(scoped, "new_scope_unit") as unit:
                    with mock.patch.object(scoped.subprocess, "run") as launch:
                        with self.assertRaises(scoped.ArchVmUnavailable):
                            scoped.run_scoped_seccomp_probe(
                                Path("/trusted-ghidra"), pe, root)
                    unit.assert_not_called()
                    launch.assert_not_called()

    def test_mocked_vm_claim_without_real_confirmation_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pe = root / "synthetic.exe"
            pe.write_bytes(b"MZ synthetic")
            with mock.patch.object(scoped, "verify_arch_vm",
                                   return_value={
                                       "status": "ARCH_VM_PREFLIGHT_PASSED",
                                       "vm_confirmed": False, "container": True}):
                with mock.patch.object(scoped, "new_scope_unit") as unit:
                    with self.assertRaisesRegex(
                            scoped.ScopedSeccompSmokeError, "gate not attested"):
                        scoped.run_scoped_seccomp_probe(
                            Path("/trusted-ghidra"), pe, root)
                    unit.assert_not_called()

    def test_requires_private_absolute_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            synthetic = Path(temp) / "synthetic.exe"
            synthetic.write_bytes(b"MZ synthetic fixture")
            with self.assertRaisesRegex(
                    scoped.ScopedSeccompSmokeError, "absolute"):
                scoped.run_scoped_seccomp_probe(
                    Path("/trusted-ghidra"), synthetic,
                    Path("relative/path"))


if __name__ == "__main__":
    unittest.main()
