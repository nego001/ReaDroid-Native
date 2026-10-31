"""PE-S1.61 local evidence matrix: NO real/native VM or Windows PE execution."""
from __future__ import annotations

import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_61_runtime_matrix as matrix
import pe_arch_vm_s1_60_review_request as request
import pe_arch_vm_handoff_review as handoff
from test_pe_arch_vm_observation_review import (
    ObservationCustodyCorrelationTests, COMMIT,
)

REVIEWER = "external-reviewer@example.invalid"


class NativeRuntimeSelfReportMatrixTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ObservationCustodyCorrelationTests(
            "test_s1_53_coherent_full_receipt_custody_and_batch_is_not_vm_proof")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.folder = self.fixture.folder
        self.source = self.fixture.source
        self.request = self.folder / "review-request-runtime.json"
        self.challenge = self.fixture.fixture.case.fixture.challenge
        # A test fixture already generated its receipt. Align the
        # otherwise randomly-issued request to its TEST challenge only.
        # Production issue_request uses real secrets.token_hex(32).
        with mock.patch.object(
                request.secrets, "token_hex", return_value=self.challenge):
            self.request_ack = request.issue_request(
                self.request, expected_source_commit=COMMIT,
                reviewer_id=REVIEWER)
        self.receipt_sha256 = self.fixture.fixture.case.receipt_sha256

    def options(self):
        return {
            "expected_request_sha256": self.request_ack["request_sha256"],
            "expected_custody_sha256": self.fixture.fixture.index_sha256,
            "expected_receipt_sha256": self.receipt_sha256,
            "expected_source_commit": COMMIT,
            "expected_challenge": self.challenge,
            "expected_reviewer_id": REVIEWER,
        }

    def evaluate(self, **changes):
        with mock.patch.object(
                handoff, "verify_source_checkout_pin",
                return_value=self.fixture.fixture.case.pin) as git:
            result = matrix.verify_runtime_claims(
                self.folder, self.source, self.request,
                **{**self.options(), **changes})
        self.assertEqual(git.call_count, 2)
        return result

    def test_real_local_synthetic_chain_reports_only_unattested_claims(self):
        result = self.evaluate()
        self.assertEqual(result["status"], matrix.STATUS)
        self.assertEqual(result["distinct_operator_reported_scopes"], 4)
        self.assertTrue(result["operator_reported_scopes_locally_unique"])
        self.assertTrue(result["operator_reported_scope_cleanup_locally_validated"])
        self.assertTrue(result["operator_reported_seccomp_and_cgroups_locally_correlated"])
        self.assertEqual(result["operator_reported_ghidra_seccomp_mode"], 2)
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["native_arch_kernel_independently_verified"])
        self.assertFalse(result["real_seccomp_and_cgroups_independently_witnessed"])
        self.assertFalse(result["scope_cleanup_independently_witnessed"])
        self.assertFalse(result["unknown_windows_pe_execution_authorized"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])

    def test_wrong_external_receipt_pin_fails_closed(self):
        with self.assertRaises(matrix.RuntimeMatrixError):
            self.evaluate(expected_receipt_sha256="f" * 64)

    def test_wrong_external_request_digest_blocks_observation_reader(self):
        with (
            mock.patch.object(matrix.observations,
                              "verify_observation_custody") as observer,
            self.assertRaises(request.RequestReviewError),
        ):
            # This lower-level verifier is also tested separately;
            # the matrix wraps its refusal into RuntimeMatrixError.
            request.verify_request(
                self.request,
                expected_request_sha256="f" * 64,
                expected_source_commit=COMMIT,
                expected_challenge=self.challenge,
                expected_reviewer_id=REVIEWER)
        observer.assert_not_called()
        with mock.patch.object(matrix.observations,
                               "verify_observation_custody") as observer:
            with self.assertRaises(matrix.RuntimeMatrixError):
                self.evaluate(expected_request_sha256="f" * 64)
        observer.assert_not_called()

    def test_wrong_challenge_commit_and_reviewer_refuse(self):
        for key, value in (
            ("expected_challenge", "e" * 64),
            ("expected_source_commit", "e" * 40),
            ("expected_reviewer_id", "stranger@example.invalid"),
        ):
            with self.subTest(field=key):
                with self.assertRaises(matrix.RuntimeMatrixError):
                    self.evaluate(**{key: value})

    def test_operator_kernel_or_cgroup_changed_even_if_rehashed_rejected(self):
        for label in ("kernel", "cgroup"):
            with self.subTest(kind=label):
                path = self.folder / ("guest-" + label + "-observation.txt")
                original = path.read_bytes()
                path.write_bytes(original + b"false attestations\n")
                try:
                    with self.assertRaises(matrix.RuntimeMatrixError):
                        self.evaluate()
                finally:
                    path.write_bytes(original)
                    path.chmod(0o600)

    def test_guest_observation_missing_after_request_refused(self):
        path = self.folder / "guest-kernel-observation.txt"
        path.unlink()
        with self.assertRaises(matrix.RuntimeMatrixError):
            self.evaluate()

    def test_duplicate_scope_ids_rejected_before_promotion(self):
        report = copy.deepcopy(self.fixture.fixture.case.fixture.report)
        first = report["cgroup_lifecycle"]["scope"]
        descendant = report["descendant_lifecycle"]
        descendant["scope"] = first
        descendant["descendant_cleanup_evidence"]["scope"] = first
        with self.assertRaisesRegex(matrix.RuntimeMatrixError,
                                    "reused a systemd scope"):
            matrix._scopes(report)

    def test_scope_cleanup_missing_or_unpopulated_false_refused(self):
        report = copy.deepcopy(self.fixture.fixture.case.fixture.report)
        with self.subTest(case="unpopulated"):
            report["ghidra"]["arch_real_ghidra_with_both"][
                "scope_cleanup_evidence"]["cgroup_unpopulated"] = False
            with self.assertRaises(matrix.RuntimeMatrixError):
                matrix._scopes(report)
        with self.subTest(case="wrong scope"):
            report = copy.deepcopy(self.fixture.fixture.case.fixture.report)
            report["ghidra"]["arch_scoped_seccomp_probe"][
                "scope_cleanup_evidence"]["scope"] = (
                    "negresco-pe-ffffffffffffffffffffffff.scope")
            with self.assertRaises(matrix.RuntimeMatrixError):
                matrix._scopes(report)

    def test_guest_review_extra_claim_cannot_enter_matrix(self):
        real = self.fixture.verify()
        fake = {**real, "operator_claims_hypervisor_verified": True}
        with mock.patch.object(matrix.observations,
                               "verify_observation_custody", return_value=fake):
            with self.assertRaisesRegex(matrix.RuntimeMatrixError,
                                        "incomplete claims"):
                self.evaluate()

    def test_guest_review_authentication_forgery_rejected(self):
        real = self.fixture.verify()
        for name in (
            "operator_logs_authenticated",
            "native_kernel_execution_independently_verified",
            "independent_vm_attestation",
            "host_or_git_authenticity_verified",
        ):
            with self.subTest(flag=name):
                fake = {**real, name: True}
                with mock.patch.object(
                        matrix.observations,
                        "verify_observation_custody", return_value=fake):
                    with self.assertRaises(matrix.RuntimeMatrixError):
                        self.evaluate()

    def test_bogus_seccomp_false_mode_rejected_before_result(self):
        data = json.loads((self.folder / "acceptance.json").read_text("utf-8"))
        data["native_acceptance_report"]["ghidra"][
            "arch_real_ghidra_with_both"]["ghidra_jvm_seccomp_evidence"][
                "seccomp_mode"] = 0
        raw = (json.dumps(data, sort_keys=True) + "\n").encode()
        (self.folder / "acceptance.json").write_bytes(raw)
        with self.assertRaises(matrix.RuntimeMatrixError):
            self.evaluate()

    def test_receipt_removed_after_observation_refused(self):
        (self.folder / "acceptance.json").unlink()
        with self.assertRaises(matrix.RuntimeMatrixError):
            self.evaluate()

    def test_wrong_readonly_policy_is_not_promoted_to_true(self):
        with self.assertRaises(matrix.RuntimeMatrixError):
            self.evaluate(require_readonly_source_view=True)

    def test_bool_policy_and_malformed_pins_refuse_before_open(self):
        for field, bad in (
                ("require_readonly_source_view", "false"),
                ("expected_receipt_sha256", True),
                ("expected_custody_sha256", "bad")):
            with self.subTest(field=field):
                with mock.patch.object(matrix.request, "verify_request") as req:
                    with self.assertRaises(matrix.RuntimeMatrixError):
                        self.evaluate(**{field: bad})
                req.assert_not_called()

    def test_cli_bad_receipt_pin_exit_two_and_never_approves(self):
        args = ["--private-dir", str(self.folder),
                "--source-root", str(self.source),
                "--reviewer-request", str(self.request)]
        for key, value in self.options().items():
            args.extend(["--" + key.replace("_", "-"), value])
        ix = args.index("--expected-receipt-sha256") + 1
        args[ix] = "f" * 64
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(matrix.main(args), 2)
        self.assertEqual(stdout.getvalue(), "")
        result = json.loads(stderr.getvalue())
        self.assertEqual(result["status"], matrix.FAILURE)
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["unknown_windows_pe_execution_authorized"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])


if __name__ == "__main__":
    unittest.main()
