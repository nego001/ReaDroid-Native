"""PE-S1.60: real local reviewer nonce issuance; synthetic-only custody join.

These tests never create a native VM or claim hardware/kernel attestation.
"""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_60_review_request as request
import pe_arch_vm_evidence as evidence

COMMIT = "a" * 40
REVIEWER = "independent-reviewer@example.invalid"
CUSTODY = "c" * 64


class LocalReviewerRequestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pe-s1-60-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "private"
        self.dir.mkdir(mode=0o700)
        self.file = self.dir / "review-request-001.json"
        self.issued = request.issue_request(
            self.file, expected_source_commit=COMMIT, reviewer_id=REVIEWER)

    def options(self):
        return {
            "expected_request_sha256": self.issued["request_sha256"],
            "expected_source_commit": COMMIT,
            "expected_challenge": self.issued["reviewer_challenge"],
            "expected_reviewer_id": REVIEWER,
        }

    def verify(self, **changes):
        return request.verify_request(
            self.file, **{**self.options(), **changes})

    def patch_record(self, edit):
        obj = json.loads(self.file.read_text(encoding="utf-8"))
        edit(obj)
        raw = request._canonical(obj)
        self.file.write_bytes(raw)
        self.file.chmod(0o600)
        return hashlib.sha256(raw).hexdigest()

    def test_issue_has_crypto_random_challenge_private_file_and_no_vm_claim(self):
        self.assertEqual(self.issued["status"], request.ISSUED)
        self.assertEqual(len(self.issued["reviewer_challenge"]), 64)
        self.assertNotEqual(self.issued["reviewer_challenge"], "0" * 64)
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.issued["request_sha256"],
                         hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assertFalse(self.issued["independent_vm_attestation"])
        self.assertFalse(self.issued["operator_evidence_accepted"])
        self.assertFalse(self.issued["release_authorized"])

    def test_distinct_issuances_have_distinct_challenges(self):
        second = request.issue_request(
            self.dir / "review-request-002.json",
            expected_source_commit=COMMIT, reviewer_id=REVIEWER)
        self.assertNotEqual(second["reviewer_challenge"],
                            self.issued["reviewer_challenge"])
        self.assertNotEqual(second["request_sha256"],
                            self.issued["request_sha256"])

    def test_external_pin_and_format_validated(self):
        answer = self.verify()
        self.assertEqual(answer["status"], request.VERIFIED)
        self.assertTrue(answer["external_request_pin_matched"])
        self.assertFalse(answer["independent_vm_attestation"])
        self.assertFalse(answer["operator_evidence_accepted"])
        self.assertFalse(answer["release_authorized"])

    def test_existing_file_never_overwritten(self):
        prior = self.file.read_bytes()
        with self.assertRaises(request.RequestReviewError):
            request.issue_request(
                self.file, expected_source_commit=COMMIT, reviewer_id=REVIEWER)
        self.assertEqual(self.file.read_bytes(), prior)

    def test_insecure_directory_mode_refuses_creation(self):
        self.dir.chmod(0o755)
        target = self.dir / "review-request-other.json"
        with self.assertRaises(request.RequestReviewError):
            request.issue_request(
                target, expected_source_commit=COMMIT, reviewer_id=REVIEWER)
        self.assertFalse(target.exists())

    def test_symlink_parent_refuses_creation_and_reading(self):
        link = Path(self.tmp.name) / "linked-dir"
        link.symlink_to(self.dir, target_is_directory=True)
        with self.assertRaises(request.RequestReviewError):
            request.issue_request(
                link / "review-request-new.json",
                expected_source_commit=COMMIT, reviewer_id=REVIEWER)
        with self.assertRaises(request.RequestReviewError):
            request.verify_request(link / self.file.name, **self.options())

    def test_symlink_and_hardlink_request_refused(self):
        link = self.dir / "review-request-symlink.json"
        link.symlink_to(self.file)
        with self.assertRaises(request.RequestReviewError):
            request.verify_request(link, **self.options())
        alias = self.dir / "review-request-hardlink.json"
        os.link(self.file, alias)
        with self.assertRaises(request.RequestReviewError):
            self.verify()

    def test_invalid_destination_names_and_relative_paths_refused(self):
        for path in (Path("review-request-foo.json"),
                     self.dir / "other.json",
                     self.dir / "review-request-abc.tmp",
                     self.dir / "review-request-x.json" / "oops",
                     Path(str(self.dir) + "/../private/review-request-new.json")):
            with self.subTest(path=path):
                with self.assertRaises(request.RequestReviewError):
                    request.issue_request(
                        path, expected_source_commit=COMMIT,
                        reviewer_id=REVIEWER)

    def test_wrong_external_hash_refused(self):
        with self.assertRaises(request.RequestReviewError):
            self.verify(expected_request_sha256="f" * 64)

    def test_wrong_commit_challenge_and_reviewer_refused(self):
        for key, value in (
                ("expected_source_commit", "f" * 40),
                ("expected_challenge", "f" * 64),
                ("expected_reviewer_id", "another@example.invalid")):
            with self.subTest(field=key):
                with self.assertRaises(request.RequestReviewError):
                    self.verify(**{key: value})

    def test_false_attestation_even_with_rehashed_request_refused(self):
        sha = self.patch_record(lambda d: d.update(
            independent_vm_attestation=True))
        with self.assertRaises(request.RequestReviewError):
            self.verify(expected_request_sha256=sha)

    def test_extra_field_even_if_rehashed_refused(self):
        sha = self.patch_record(lambda d: d.update(
            windows_binary_execution_authorized=True))
        with self.assertRaises(request.RequestReviewError):
            self.verify(expected_request_sha256=sha)

    def test_local_clock_claim_wrong_timezone_rejected(self):
        sha = self.patch_record(lambda d: d.update(
            reviewer_local_issued_at_utc_not_attested=
                "2026-10-30T19:00:00+02:00"))
        with self.assertRaises(request.RequestReviewError):
            self.verify(expected_request_sha256=sha)

    def test_duplicate_json_keys_even_with_valid_hash_refused(self):
        raw = self.file.read_bytes().rstrip(b"\n")
        fake = raw[:-1] + b',"release_authorized":false}\n'
        self.file.write_bytes(fake)
        sha = hashlib.sha256(fake).hexdigest()
        with self.assertRaises(request.RequestReviewError):
            self.verify(expected_request_sha256=sha)

    def test_invalid_reviewer_identity_rejected(self):
        with self.assertRaises(request.RequestReviewError):
            request.issue_request(
                self.dir / "review-request-new.json",
                expected_source_commit=COMMIT,
                reviewer_id="bad identity with spaces")
        self.assertFalse((self.dir / "review-request-new.json").exists())

    def test_dangling_destination_symlink_refuses_issue(self):
        missing = self.dir / "review-request-dangling.json"
        missing.symlink_to(self.dir / "missing")
        with self.assertRaises(request.RequestReviewError):
            request.issue_request(
                missing, expected_source_commit=COMMIT, reviewer_id=REVIEWER)

    def test_readonly_custody_correlation_contract_mocked_not_vm(self):
        synthetic = {
            "status": "LOCAL_CUSTODY_PACKAGE_CORRELATED",
            "source_files_rechecked": len(evidence.SOURCE_FILES),
            "native_kernel_execution_independently_verified": False,
            "independent_vm_attestation": False,
        }
        with mock.patch.object(request.custody, "verify_custody_index",
                               return_value=synthetic) as cust:
            r = request.correlate_request_custody(
                self.file, self.dir, Path("/review/source"),
                expected_custody_sha256=CUSTODY, **self.options(),
                require_readonly_source_view=True)
        cust.assert_called_once()
        self.assertEqual(r["status"], request.CORRELATED)
        self.assertTrue(r["external_custody_sha256_pin_matched"])
        self.assertFalse(r["independent_vm_attestation"])
        self.assertFalse(r["native_kernel_execution_independently_verified"])
        self.assertFalse(r["unknown_windows_pe_execution_authorized"])
        self.assertFalse(r["apk_or_ota_publication_authorized"])

    def test_wrong_operator_custody_cannot_promote_result(self):
        synthetic = {
            "status": "LOCAL_CUSTODY_PACKAGE_CORRELATED",
            "source_files_rechecked": len(evidence.SOURCE_FILES),
            "native_kernel_execution_independently_verified": True,
            "independent_vm_attestation": False,
        }
        with mock.patch.object(request.custody, "verify_custody_index",
                               return_value=synthetic):
            with self.assertRaises(request.RequestReviewError):
                request.correlate_request_custody(
                    self.file, self.dir, Path("/review/source"),
                    expected_custody_sha256=CUSTODY, **self.options())

    def test_wrong_custody_hash_blocks_custody_reader(self):
        with mock.patch.object(request.custody,
                               "verify_custody_index") as cust:
            with self.assertRaises(request.RequestReviewError):
                request.correlate_request_custody(
                    self.file, self.dir, Path("/review/source"),
                    expected_custody_sha256="NOT_SHA", **self.options())
        cust.assert_not_called()

    def test_change_request_mid_review_fails_and_does_not_authorize(self):
        def tamper(*args, **kwargs):
            self.patch_record(lambda d: d.update(
                reviewer_local_issued_at_utc_not_attested=
                    "2026-10-30T19:00:00+00:00"))
            return {
                "status": "LOCAL_CUSTODY_PACKAGE_CORRELATED",
                "source_files_rechecked": len(evidence.SOURCE_FILES),
                "native_kernel_execution_independently_verified": False,
                "independent_vm_attestation": False,
            }
        with mock.patch.object(request.custody,
                               "verify_custody_index", side_effect=tamper):
            with self.assertRaises(request.RequestReviewError):
                request.correlate_request_custody(
                    self.file, self.dir, Path("/review/source"),
                    expected_custody_sha256=CUSTODY, **self.options())

    def test_cli_issue_and_verify_and_reject(self):
        fresh = self.dir / "review-request-cli.json"
        o, e = StringIO(), StringIO()
        with redirect_stdout(o), redirect_stderr(e):
            self.assertEqual(request.main([
                "issue", "--output", str(fresh),
                "--expected-source-commit", COMMIT,
                "--reviewer-id", REVIEWER]), 0)
        self.assertEqual(e.getvalue(), "")
        response = json.loads(o.getvalue())
        self.assertFalse(response["independent_vm_attestation"])
        expected = [
            "verify", "--request", str(fresh),
            "--expected-request-sha256", response["request_sha256"],
            "--expected-source-commit", COMMIT,
            "--expected-challenge", response["reviewer_challenge"],
            "--expected-reviewer-id", REVIEWER]
        o, e = StringIO(), StringIO()
        with redirect_stdout(o), redirect_stderr(e):
            self.assertEqual(request.main(expected), 0)
        self.assertEqual(e.getvalue(), "")
        self.assertEqual(json.loads(o.getvalue())["status"], request.VERIFIED)
        o, e = StringIO(), StringIO()
        expected[expected.index("--expected-challenge") + 1] = "d" * 64
        with redirect_stdout(o), redirect_stderr(e):
            self.assertEqual(request.main(expected), 2)
        self.assertEqual(o.getvalue(), "")
        self.assertEqual(
            json.loads(e.getvalue())["status"],
            "REJECTED_PE_S1_60_LOCAL_REQUEST_OR_CUSTODY")


if __name__ == "__main__":
    unittest.main()
