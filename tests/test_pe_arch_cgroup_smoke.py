"""Native Arch cgroup contracts; synthetic receipts, NEVER a live host scope."""
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_cgroup_smoke as native
import pe_arch_vm_gate as gate


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



class NativeVmGateTrustTests(unittest.TestCase):
    """S2.02: never treat user-controlled PATH scripts as VM witnesses.

    These tests simulate command results and guest state only. They do not
    create cgroups, detect an actual VM, execute systemd or start a child.
    """

    def environment(self, *, untrusted=None, container_rc=1):
        untrusted = set(untrusted or ())
        def lookup(name):
            return "/usr/bin/" + name

        def trusted(path):
            return Path(path).name not in untrusted

        def command(argv, **kwargs):
            # The container checker uses exit=1 when not in a container.
            return SimpleNamespace(
                returncode=container_rc if "--container" in argv else 0)

        return (
            mock.patch.object(gate, "preflight"),
            mock.patch.object(gate.os, "geteuid", return_value=1000),
            mock.patch.object(gate.os, "getuid", return_value=1000),
            mock.patch.object(gate.shutil, "which", side_effect=lookup),
            mock.patch.object(gate, "_trusted_discovered_systemd_binary",
                              side_effect=trusted),
            mock.patch.object(gate.subprocess, "run", side_effect=command),
            mock.patch.dict(gate.os.environ,
                            {"XDG_RUNTIME_DIR": "/run/user/1000"}),
            mock.patch.object(gate.Path, "is_dir", return_value=True),
            mock.patch.object(gate.Path, "is_symlink", return_value=False),
            mock.patch.object(gate.Path, "stat",
                              return_value=SimpleNamespace(st_uid=1000)),
        )

    def test_path_injected_virtualization_witness_refuses_before_any_subprocess(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            patches = self.environment(untrusted={"systemd-detect-virt"})
            entered = [stack.enter_context(p) for p in patches]
            with self.assertRaisesRegex(gate.ArchVmUnavailable,
                                        "systemd-detect-virt.*trusted"):
                gate.verify_arch_vm()
        entered[5].assert_not_called()

    def test_path_injected_user_bus_witness_refuses_without_executing_script(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            patches = self.environment(untrusted={"systemctl"})
            entered = [stack.enter_context(p) for p in patches]
            with self.assertRaisesRegex(gate.ArchVmUnavailable,
                                        "systemctl.*trusted"):
                gate.verify_arch_vm()
        invocations = [call.args[0] for call in entered[5].call_args_list]
        self.assertEqual(invocations, [
            ["/usr/bin/systemd-detect-virt", "--container", "--quiet"],
            ["/usr/bin/systemd-detect-virt", "--vm", "--quiet"],
        ])
        self.assertNotIn("/usr/bin/systemctl", [x[0] for x in invocations])

    def test_path_injected_runtime_tools_cannot_pass_vm_gate(self):
        from contextlib import ExitStack
        for name in ("bwrap", "systemd-run", "python3",
                     "x86_64-w64-mingw32-gcc"):
            with self.subTest(name=name), ExitStack() as stack:
                patches = self.environment(untrusted={name})
                entered = [stack.enter_context(p) for p in patches]
                with self.assertRaisesRegex(gate.ArchVmUnavailable,
                                            name + ".*trusted"):
                    gate.verify_arch_vm()
                commands = [call.args[0][0]
                            for call in entered[5].call_args_list]
                self.assertNotIn("/usr/bin/" + name, commands)

    def test_mocked_trusted_vm_checker_calls_absolute_commands_and_stays_local(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            patches = self.environment()
            entered = [stack.enter_context(p) for p in patches]
            result = gate.verify_arch_vm()
        self.assertEqual(result["status"], "ARCH_VM_PREFLIGHT_PASSED")
        self.assertIs(result["vm_confirmed"], True)
        self.assertIs(result["real_cgroup_test_executed"], False)
        self.assertEqual(
            [x.args[0] for x in entered[5].call_args_list],
            [
                ["/usr/bin/systemd-detect-virt", "--container", "--quiet"],
                ["/usr/bin/systemd-detect-virt", "--vm", "--quiet"],
                ["/usr/bin/systemctl", "--user", "--no-ask-password",
                 "show-environment"],
            ],
        )

    def test_inconclusive_container_result_refuses_even_with_trusted_paths(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            patches = self.environment(container_rc=2)
            entered = [stack.enter_context(p) for p in patches]
            with self.assertRaisesRegex(gate.ArchVmUnavailable,
                                        "inconclusive"):
                gate.verify_arch_vm()
        self.assertEqual(entered[5].call_count, 1)


if __name__ == "__main__":
    unittest.main()
