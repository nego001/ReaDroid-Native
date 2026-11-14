"""PE-S1.68: native reviewer stdout JSON ambiguity + parent Git repin tests.

All execution is mocked. No native VM, Ghidra, cgroup or unknown PE runs.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_66_native_reviewer_launcher as launcher
from pe_arch_vm_checkout_pin import CheckoutPinError
import test_pe_arch_vm_s1_66_native_reviewer_launcher as original

COMMIT = original.COMMIT


class ParentGitAndJsonStrictnessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = original.ReviewerNativeLauncherContracts(
            "test_default_plan_does_not_probe_vm_or_launch_subprocess")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.git = {
            "status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED",
            "expected_commit": COMMIT,
            "checked_manifest_entries": len(launcher.SOURCE_FILES),
            "worktree_status_clean": True,
            "git_authorship_or_signature_verified": False,
            "native_vm_or_kernel_verified": False,
        }
        self.strict_status = (
            "LOCAL_PE_S1_67_STRICT_RECEIPT_BINDING_NOT_VM_ATTESTATION")

    def _run(self, *, stdout_mutator=None, git_results=None,
             child_mutator=None, expected_failure=False):
        def child(argv, **kwargs):
            output = self.fixture._fake_run(argv, **kwargs)
            if stdout_mutator is not None:
                payload = stdout_mutator(output.stdout)
                output = subprocess.CompletedProcess(
                    argv, 0, stdout=payload, stderr=b"")
            return output
        def strict_verify(*args, **kwargs):
            return {
                "status": self.strict_status,
                "receipt_sha256": kwargs["expected_receipt_sha256"],
                "source_commit": COMMIT,
                "all_report_fields_matched": True,
                "source_manifest_revalidated": True,
                "independent_vm_attestation": False,
                "release_authorized": False,
                "unknown_windows_pe_execution_authorized": False,
                "apk_or_ota_publication_authorized": False,
            }
        with (
            mock.patch.object(
                launcher.preflight, "native_readiness",
                return_value=self.fixture.ready) as preflight,
            mock.patch.object(
                launcher, "verify_source_checkout_pin",
                side_effect=git_results if git_results is not None
                    else [self.git.copy(), self.git.copy()]) as parent,
            mock.patch.object(
                launcher.bounded, "run_bounded_native", side_effect=child) as process,
            mock.patch.object(
                launcher.binding, "verify_launcher_binding",
                side_effect=strict_verify) as strict,
        ):
            if expected_failure:
                with self.assertRaises(launcher.ReviewerLaunchError):
                    self.fixture.call(
                        execute_synthetic_native_acceptance=True)
                return preflight.call_count, parent.call_count, process.call_count, strict.call_count
            output = self.fixture.call(
                execute_synthetic_native_acceptance=True)
            return output, preflight.call_count, parent.call_count, process.call_count, strict.call_count

    def test_genuine_contract_uses_parent_git_before_and_after_child(self):
        result, preflight_count, parent_count, child_count, strict_count = self._run()
        self.assertEqual(result["status"], launcher.LOCAL_DONE)
        self.assertEqual((preflight_count, parent_count, child_count, strict_count),
                         (1, 2, 1, 1))
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["release_authorized"])

    def test_duplicate_top_level_status_rejected_even_when_last_status_passes(self):
        def duplicate(raw):
            return raw.replace(
                b'"status":', b'"status":"REJECTED","status":', 1)
        _, parent, child, strict = self._run(
            stdout_mutator=duplicate, expected_failure=True)
        self.assertEqual((parent, child, strict), (1, 1, 0))

    def test_duplicate_nested_git_key_rejected(self):
        def duplicate(raw):
            return raw.replace(
                b'"expected_commit":', b'"expected_commit":"faked","expected_commit":', 1)
        _, parent, child, strict = self._run(
            stdout_mutator=duplicate, expected_failure=True)
        self.assertEqual((parent, child, strict), (1, 1, 0))

    def test_nonfinite_json_constant_rejected(self):
        def inject(raw):
            return raw.replace(b'"status":', b'"unsupported":NaN,"status":', 1)
        _, parent, child, strict = self._run(
            stdout_mutator=inject, expected_failure=True)
        self.assertEqual((parent, child, strict), (1, 1, 0))

    def test_invalid_utf8_rejected(self):
        _, parent, child, strict = self._run(
            stdout_mutator=lambda raw: b"\xff"+raw, expected_failure=True)
        self.assertEqual((parent, child, strict), (1, 1, 0))

    def test_two_json_documents_in_stdout_rejected(self):
        _, parent, child, strict = self._run(
            stdout_mutator=lambda raw: raw+b"\n{}\n", expected_failure=True)
        self.assertEqual((parent, child, strict), (1, 1, 0))

    def test_git_commit_changes_after_child_rejected_despite_valid_receipt(self):
        mutated = {**self.git, "expected_commit": "e"*40}
        preflight, parent, child, strict = self._run(
            git_results=[self.git, mutated], expected_failure=True)
        self.assertEqual((preflight, parent, child, strict), (1, 2, 1, 1))

    def test_parent_git_must_not_claim_independent_vm(self):
        forged = {**self.git, "native_vm_or_kernel_verified": True}
        preflight, parent, child, strict = self._run(
            git_results=[forged], expected_failure=True)
        self.assertEqual((preflight, parent, child, strict), (1, 1, 0, 0))

    def test_parent_git_must_not_claim_signed_git_authorship(self):
        forged = {**self.git, "git_authorship_or_signature_verified": True}
        preflight, parent, child, strict = self._run(
            git_results=[forged], expected_failure=True)
        self.assertEqual((preflight, parent, child, strict), (1, 1, 0, 0))

    def test_parent_git_missing_manifests_rejected_pre_child(self):
        forged = {**self.git, "checked_manifest_entries": 2}
        preflight, parent, child, strict = self._run(
            git_results=[forged], expected_failure=True)
        self.assertEqual((preflight, parent, child, strict), (1, 1, 0, 0))

    def test_parent_git_probe_os_error_pre_child_rejected(self):
        preflight, parent, child, strict = self._run(
            git_results=[CheckoutPinError("unavailable")],
            expected_failure=True)
        self.assertEqual((preflight, parent, child, strict), (1, 1, 0, 0))

    def test_parent_git_probe_error_after_child_rejected(self):
        preflight, parent, child, strict = self._run(
            git_results=[self.git, CheckoutPinError("lost checkout")],
            expected_failure=True)
        self.assertEqual((preflight, parent, child, strict), (1, 2, 1, 1))

    def test_child_git_wrapper_differs_from_parent_rejected(self):
        def fake_child_git(raw):
            obj = json.loads(raw)
            obj["local_source_checkout_pin"]["checked_manifest_entries"] = 1
            return json.dumps(obj).encode()
        preflight, parent, child, strict = self._run(
            stdout_mutator=fake_child_git, expected_failure=True)
        self.assertEqual((preflight, parent, child, strict), (1, 2, 1, 1))

    def test_default_no_execute_does_not_consult_parent_git(self):
        with (mock.patch.object(launcher, "verify_source_checkout_pin") as pin,
              mock.patch.object(launcher.bounded, "run_bounded_native") as process):
            result = self.fixture.call()
        self.assertEqual(result["status"], launcher.PLAN)
        pin.assert_not_called()
        process.assert_not_called()

    def test_cli_explicit_error_remains_no_release(self):
        args = [
            "--ghidra-home", str(self.fixture.home),
            "--ghidra-archive", str(self.fixture.zip),
            "--evidence-output", str(self.fixture.receipt),
            "--expected-source-commit", COMMIT,
            "--reviewer-challenge", original.CHALLENGE,
            "--execute-synthetic-native-acceptance",
        ]
        stdout, stderr = StringIO(), StringIO()
        with (
            mock.patch.object(
                launcher.preflight, "native_readiness",
                return_value=self.fixture.ready),
            mock.patch.object(
                launcher, "verify_source_checkout_pin",
                side_effect=CheckoutPinError("mismatch")),
            mock.patch.object(launcher.bounded, "run_bounded_native") as process,
            redirect_stdout(stdout), redirect_stderr(stderr),
        ):
            status = launcher.main(args)
        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        response = json.loads(stderr.getvalue())
        self.assertEqual(response["status"], launcher.REJECTED)
        self.assertFalse(response["release_authorized"])
        self.assertFalse(response["independent_vm_attestation"])
        process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
