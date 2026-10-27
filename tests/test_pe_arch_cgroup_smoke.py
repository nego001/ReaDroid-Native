"""Native Arch diagnostics contract tests, without touching the real host."""
from pathlib import Path
import json
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_cgroup_smoke as native


class NativeArchSmokeTests(unittest.TestCase):
    def test_rejects_root_without_starting_systemd(self):
        with mock.patch.object(native.sys, "platform", "linux"):
            with mock.patch.object(native.os, "geteuid", return_value=0):
                with self.assertRaisesRegex(RuntimeError, "regular user"):
                    native.preflight()

    def test_accepts_only_successful_guard_and_child_proof(self):
        fake = mock.Mock(returncode=0, stderr="",
                         stdout='{"cgroup_verification":"passed",'
                                '"verified":true,"memory_max":4294967296,'
                                '"pids_max":128,"cpu_quota":200000,'
                                '"cpu_period":100000}\n'
                                '{"synthetic_child":"passed"}\n')
        with mock.patch.object(native, "preflight"):
            with mock.patch.object(native, "new_scope_unit",
                                   return_value="negresco-pe-0123456789abcdef01234567.scope"):
                with mock.patch.object(native, "wrap_in_cgroup_scope",
                                       return_value=["synthetic"]):
                    with mock.patch.object(native.subprocess, "run",
                                           return_value=fake) as run:
                        with mock.patch.object(native, "stop_scope") as stop:
                            result = native.run_smoke()
        self.assertEqual(result["status"], "PASS_NATIVE_ARCH_CGROUP")
        self.assertFalse(result["windows_binary_executed"])
        self.assertEqual(result["pids_max"], 128)
        stop.assert_called_once()
        self.assertEqual(run.call_args.kwargs["timeout"], 28)

    def test_cannot_accept_only_child_marker_without_cgroup_proof(self):
        fake = mock.Mock(returncode=0, stderr="",
                         stdout=json.dumps({"synthetic_child": "passed"}))
        with mock.patch.object(native, "preflight"):
            with mock.patch.object(native, "new_scope_unit",
                                   return_value="negresco-pe-0123456789abcdef01234567.scope"):
                with mock.patch.object(native, "wrap_in_cgroup_scope",
                                       return_value=["synthetic"]):
                    with mock.patch.object(native.subprocess, "run",
                                           return_value=fake):
                        with mock.patch.object(native, "stop_scope") as stop:
                            with self.assertRaisesRegex(RuntimeError, "proof"):
                                native.run_smoke()
        stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
