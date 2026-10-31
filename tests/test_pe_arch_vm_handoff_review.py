"""PE-S1.47 offline handoff: no attested VM claims and no live PE execution."""
from __future__ import annotations

from contextlib import redirect_stderr
import copy
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_handoff_review as handoff
from test_pe_arch_vm_evidence import PrivateNativeArchReceiptTests

COMMIT = "abcdef01" * 5


class ReviewerHandoffTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PrivateNativeArchReceiptTests(
            "test_s1_42_default_mode_preserves_legacy_success")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.receipt_ack = self.fixture.write()
        self.pin = {
            "status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED",
            "expected_commit": COMMIT,
            "checked_manifest_entries": 1,
            "worktree_status_clean": True,
            "git_authorship_or_signature_verified": False,
            "native_vm_or_kernel_verified": False,
        }
        self.operator = {
            **copy.deepcopy(self.fixture.report),
            "local_receipt": copy.deepcopy(self.receipt_ack),
            "local_source_checkout_pin": copy.deepcopy(self.pin),
        }
        self.operator_path = self.fixture.private / "operator.json"
        self.write_operator()
        self.receipt_sha256 = self.receipt_ack["receipt_sha256"]

    def write_operator(self, blob: bytes | None = None):
        if blob is None:
            blob = (json.dumps(
                self.operator, sort_keys=True, separators=(",", ":"))
                + "\n").encode("utf-8")
        self.operator_path.write_bytes(blob)
        self.operator_path.chmod(0o600)
        self.operator_sha256 = hashlib.sha256(blob).hexdigest()

    def check(self, **kwargs):
        pins = {
            "expected_source_commit": COMMIT,
            "expected_challenge": self.fixture.challenge,
            "expected_receipt_sha256": self.receipt_sha256,
            "expected_operator_sha256": self.operator_sha256,
        }
        pins.update(kwargs)
        with mock.patch.object(
                handoff, "verify_source_checkout_pin",
                return_value=copy.deepcopy(self.pin)) as git:
            output = handoff.verify_operator_handoff(
                self.operator_path, self.fixture.dest, self.fixture.root,
                **pins)
        self.assertEqual(git.call_count, 2)
        return output

    def test_s1_47_complete_correlated_handoff_never_attests_vm(self):
        result = self.check()
        self.assertEqual(result["status"], "LOCAL_OPERATOR_HANDOFF_CORRELATED")
        self.assertEqual(result["source_files_rechecked"], 1)
        self.assertTrue(result["external_operator_sha256_pin_matched"])
        self.assertTrue(result["external_receipt_sha256_pin_matched"])
        self.assertTrue(result["operator_report_matches_receipt"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["native_kernel_execution_independently_verified"])
        self.assertFalse(result["host_or_git_authenticity_verified"])

    def test_s1_47_wrong_external_operator_digest_rejected(self):
        with self.assertRaisesRegex(
                handoff.HandoffReviewError, "externally retained SHA-256"):
            self.check(expected_operator_sha256="f" * 64)

    def test_s1_47_wrong_external_receipt_digest_rejected(self):
        with self.assertRaises(handoff.HandoffReviewError):
            self.check(expected_receipt_sha256="f" * 64)

    def test_s1_47_operator_report_mismatch_rejected_with_new_valid_pin(self):
        self.operator["ghidra"]["ghidra_functions"] = 12
        self.write_operator()
        with self.assertRaisesRegex(
                handoff.HandoffReviewError, "does not match"):
            self.check()

    def test_s1_47_operator_receipt_acknowledgement_mismatch_rejected(self):
        self.operator["local_receipt"]["receipt_sha256"] = "f" * 64
        self.write_operator()
        with self.assertRaisesRegex(
                handoff.HandoffReviewError, "acknowledgement"):
            self.check()

    def test_s1_47_operator_pin_forgery_rejected(self):
        self.operator["local_source_checkout_pin"]["native_vm_or_kernel_verified"] = True
        self.write_operator()
        with self.assertRaisesRegex(
                handoff.HandoffReviewError, "local Git pin"):
            self.check()

    def test_s1_47_rejects_extra_operator_attestation_field(self):
        self.operator["independent_vm_attestation"] = True
        self.write_operator()
        with self.assertRaisesRegex(
                handoff.HandoffReviewError, "unsupported evidence fields"):
            self.check()

    def test_s1_47_rejects_duplicate_json_keys_with_recomputed_hash(self):
        self.write_operator(
            b'{"status":"PASS","status":"FAKE"}\n')
        with self.assertRaises(handoff.HandoffReviewError):
            self.check()

    def test_s1_47_checkout_swap_during_review_refuses(self):
        mismatched = {**self.pin, "checked_manifest_entries": 99}
        with mock.patch.object(
                handoff, "verify_source_checkout_pin",
                side_effect=[self.pin, mismatched]):
            with self.assertRaisesRegex(
                    handoff.HandoffReviewError, "changed during"):
                handoff.verify_operator_handoff(
                    self.operator_path, self.fixture.dest, self.fixture.root,
                    expected_source_commit=COMMIT,
                    expected_challenge=self.fixture.challenge,
                    expected_receipt_sha256=self.receipt_sha256,
                    expected_operator_sha256=self.operator_sha256)

    def test_s1_47_rejects_missing_external_pin_before_source_reads(self):
        for field in ("expected_source_commit", "expected_challenge",
                      "expected_receipt_sha256", "expected_operator_sha256"):
            with self.subTest(field=field), mock.patch.object(
                    handoff.receipt_review, "_read_private_receipt"
                    ) as read, mock.patch.object(
                    handoff, "verify_source_checkout_pin") as git:
                bad = {
                    "expected_source_commit": COMMIT,
                    "expected_challenge": self.fixture.challenge,
                    "expected_receipt_sha256": self.receipt_sha256,
                    "expected_operator_sha256": self.operator_sha256,
                }
                bad[field] = ""
                with self.assertRaises(handoff.HandoffReviewError):
                    handoff.verify_operator_handoff(
                        self.operator_path, self.fixture.dest,
                        self.fixture.root, **bad)
                read.assert_not_called()
                git.assert_not_called()

    def test_s1_47_receipt_and_operator_cannot_be_same_file(self):
        with self.assertRaisesRegex(
                handoff.HandoffReviewError, "separate private"):
            handoff.verify_operator_handoff(
                self.fixture.dest, self.fixture.dest, self.fixture.root,
                expected_source_commit=COMMIT,
                expected_challenge=self.fixture.challenge,
                expected_receipt_sha256=self.receipt_sha256,
                expected_operator_sha256=self.operator_sha256)

    def test_s1_47_cli_refuses_without_operator_output(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            result = handoff.main([
                "--operator-output", str(self.fixture.private / "not-here.json"),
                "--receipt", str(self.fixture.dest),
                "--source-root", str(self.fixture.root),
                "--expected-source-commit", COMMIT,
                "--expected-challenge", self.fixture.challenge,
                "--expected-receipt-sha256", self.receipt_sha256,
                "--expected-operator-sha256", self.operator_sha256,
            ])
        self.assertEqual(result, 2)
        self.assertEqual(
            json.loads(stderr.getvalue())["status"],
            "REJECTED_LOCAL_OPERATOR_HANDOFF")


if __name__ == "__main__":
    unittest.main()
