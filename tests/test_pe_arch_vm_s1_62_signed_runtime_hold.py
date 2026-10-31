"""PE-S1.62: real dual Ed25519 local custody review + runtime HOLD contracts.

The signed test fixture is synthetic and signed with temporary disposable
OpenSSH Ed25519 keys. It proves signature verification only, NEVER VM proof.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_62_signed_runtime_hold as gate
import pe_arch_vm_s1_60_review_request as request
import pe_arch_vm_handoff_review as handoff
from test_pe_arch_vm_end_to_end_review import RealSignedCompletePackageTests


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH unavailable")
class SignedRuntimeCombinedReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = RealSignedCompletePackageTests(
            "test_s1_54_real_two_ssh_signers_and_structured_logs_accepted")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.folder = self.fixture.folder
        self.source = self.fixture.source
        self.challenge = self.fixture.challenge
        self.commit = self.fixture.commit
        self.options_signed = self.fixture.options()
        self.reviewer = self.options_signed["expected_reviewer_id"]
        self.request = self.folder / "review-request-62.json"
        with mock.patch.object(
                request.secrets, "token_hex", return_value=self.challenge):
            self.issued = request.issue_request(
                self.request, expected_source_commit=self.commit,
                reviewer_id=self.reviewer)
        self.kwargs = {
            **self.options_signed,
            "expected_request_sha256": self.issued["request_sha256"],
            "expected_receipt_sha256": self.fixture.custody.case.receipt_sha256,
        }

    def check(self, **changed):
        with mock.patch.object(
                handoff, "verify_source_checkout_pin",
                return_value=self.fixture.custody.case.pin) as git:
            outcome = gate.review_signed_runtime(
                self.folder, self.source, self.request,
                **{**self.kwargs, **changed})
        self.assertEqual(git.call_count, 6)
        return outcome

    def test_real_two_disposable_signatures_and_runtime_end_in_hold(self):
        result = self.check()
        self.assertEqual(result["status"], gate.STATUS)
        self.assertTrue(result["dual_ssh_custody_signatures_locally_verified"])
        self.assertTrue(result["operator_runtime_report_locally_correlated"])
        self.assertTrue(result["operator_reported_scopes_locally_unique"])
        self.assertFalse(result["readonly_source_view_verified"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["native_kernel_execution_independently_verified"])
        self.assertFalse(result["operator_logs_authenticated"])
        self.assertFalse(result["hypervisor_identity_independently_verified"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["unknown_windows_pe_execution_authorized"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])
        self.assertEqual(result["required_external_evidence"], gate.hold.MISSING)

    def test_bad_reviewer_ssh_signature_refused_even_with_runtime_valid(self):
        self.fixture.case.reviewer_sig.write_bytes(
            self.fixture.case.reviewer_sig.read_bytes().replace(
                b"BEGIN", b"FORGED", 1))
        with self.assertRaises(gate.SignedRuntimeReviewError):
            self.check()

    def test_bad_witness_ssh_signature_refused_even_with_runtime_valid(self):
        path = self.fixture.case.fixture.case.signature_path
        path.write_bytes(path.read_bytes().replace(b"BEGIN", b"FORGED", 1))
        with self.assertRaises(gate.SignedRuntimeReviewError):
            self.check()

    def test_wrong_external_policy_sha_blocks_full_review(self):
        with self.assertRaises(gate.SignedRuntimeReviewError):
            self.check(expected_policy_sha256="e" * 64)

    def test_wrong_external_request_sha_blocks_runtime(self):
        with self.assertRaises(gate.SignedRuntimeReviewError):
            self.check(expected_request_sha256="e" * 64)

    def test_wrong_receipt_sha_blocks_even_valid_signatures(self):
        with self.assertRaises(gate.SignedRuntimeReviewError):
            self.check(expected_receipt_sha256="e" * 64)

    def test_reviewer_witness_identity_collision_refuses(self):
        with mock.patch.object(gate.signed, "verify_complete_review") as call:
            with self.assertRaises(gate.SignedRuntimeReviewError):
                self.check(expected_witness_id=self.reviewer)
        call.assert_not_called()

    def test_invalid_source_pin_rejected_before_read(self):
        with mock.patch.object(gate.receipts, "_read_private_receipt") as reader:
            with self.assertRaises(gate.SignedRuntimeReviewError):
                self.check(expected_source_commit="G" * 40)
        reader.assert_not_called()

    def test_false_vm_attestation_in_runtime_result_refused(self):
        good = {
            "status": gate.runtime.STATUS,
            "source_commit": self.commit,
            "custody_index_sha256": self.kwargs["expected_custody_sha256"],
            "receipt_sha256": self.kwargs["expected_receipt_sha256"],
            "reviewer_request_sha256": self.kwargs["expected_request_sha256"],
            "distinct_operator_reported_scopes": 4,
            "operator_reported_scopes_locally_unique": True,
            "operator_reported_scope_cleanup_locally_validated": True,
            "operator_reported_ghidra_seccomp_mode": 2,
            "operator_reported_seccomp_and_cgroups_locally_correlated": True,
            "operator_guest_kernel_and_cgroup_logs_structurally_correlated": True,
            "readonly_source_view_verified": False,
            "independent_vm_attestation": False,
            "native_arch_kernel_independently_verified": False,
            "operator_logs_authenticated": False,
            "real_seccomp_and_cgroups_independently_witnessed": False,
            "scope_cleanup_independently_witnessed": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }
        for key, value in (
            ("independent_vm_attestation", True),
            ("operator_logs_authenticated", True),
            ("real_seccomp_and_cgroups_independently_witnessed", True),
            ("distinct_operator_reported_scopes", 3),
            ("operator_reported_ghidra_seccomp_mode", True),
            ("source_commit", "e" * 40),
        ):
            with self.subTest(field=key):
                altered = {**good, key: value}
                with mock.patch.object(gate.runtime, "verify_runtime_claims",
                                       return_value=altered):
                    with self.assertRaises(gate.SignedRuntimeReviewError):
                        self.check()

    def test_tamper_after_signatures_before_runtime_rejected(self):
        real = gate.runtime.verify_runtime_claims
        def mutate_after_signed(*args, **kwargs):
            target = self.folder / "guest-kernel-observation.txt"
            target.write_bytes(target.read_bytes() + b"late tampering\n")
            return real(*args, **kwargs)
        with mock.patch.object(gate.runtime, "verify_runtime_claims",
                               side_effect=mutate_after_signed):
            with self.assertRaises(gate.SignedRuntimeReviewError):
                self.check()

    def test_cli_valid_signed_fixture_must_exit_two_with_hold(self):
        arguments = [
            "--private-dir", str(self.folder),
            "--source-root", str(self.source),
            "--reviewer-request", str(self.request),
        ]
        for key, val in self.kwargs.items():
            arguments.extend(["--" + key.replace("_", "-"), str(val)])
        stdout, stderr = StringIO(), StringIO()
        with (
            mock.patch.object(
                handoff, "verify_source_checkout_pin",
                return_value=self.fixture.custody.case.pin),
            redirect_stdout(stdout), redirect_stderr(stderr),
        ):
            status = gate.main(arguments)
        self.assertEqual(status, 2)
        self.assertEqual(stderr.getvalue(), "")
        data = json.loads(stdout.getvalue())
        self.assertEqual(data["status"], gate.STATUS)
        self.assertFalse(data["release_authorized"])

    def test_cli_wrong_pin_exit_two_rejects_not_hold(self):
        arguments = [
            "--private-dir", str(self.folder),
            "--source-root", str(self.source),
            "--reviewer-request", str(self.request),
        ]
        for key, val in self.kwargs.items():
            arguments.extend(["--" + key.replace("_", "-"), str(val)])
        arguments[arguments.index("--expected-request-sha256") + 1] = "e" * 64
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = gate.main(arguments)
        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        data = json.loads(stderr.getvalue())
        self.assertEqual(data["status"], gate.REJECTED)
        self.assertFalse(data["release_authorized"])
        self.assertFalse(data["apk_or_ota_publication_authorized"])


if __name__ == "__main__":
    unittest.main()
