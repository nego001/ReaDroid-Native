"""PE-S1.57: signed local evidence never upgrades to native VM authorization."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import os
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_end_to_end_review as signed
import pe_arch_vm_evidence as evidence
import pe_arch_vm_s1_57_release_guard as guard

SHA = "a" * 64
COMMIT = "b" * 40
CUSTODY = "c" * 64


class ArchIndependenceReleaseGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="s1-57-review-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.review = self.root / "local-signed-result.json"
        self.record = {
            "status": signed.STATUS,
            "source_commit": COMMIT,
            "custody_index_sha256": CUSTODY,
            "policy_revision": 2,
            "reviewer_id": "approver@example.invalid",
            "witness_id": "witness@example.invalid",
            "source_files_rechecked": len(evidence.SOURCE_FILES),
            "readonly_source_view_verified": True,
            "structured_guest_logs_consistent_with_custody": True,
            "separate_reviewer_and_witness_signatures_verified": True,
            "operator_claimed_chronology_consistent": True,
            "operator_clock_independently_verified": False,
            "witness_identity_independently_verified": False,
            "operator_logs_authenticated": False,
            "independent_vm_attestation": False,
            "native_kernel_execution_independently_verified": False,
            "host_or_git_authenticity_verified": False,
            "windows_binary_executed_by_reviewer": False,
        }
        self.publish()

    def publish(self, raw=None):
        if raw is None:
            raw = (json.dumps(self.record, sort_keys=True,
                              separators=(",", ":")) + "\n").encode("utf-8")
        self.review.write_bytes(raw)
        self.review.chmod(0o600)
        self.sha = hashlib.sha256(raw).hexdigest()

    def options(self):
        return {
            "expected_review_sha256": self.sha,
            "expected_source_commit": COMMIT,
            "expected_custody_sha256": CUSTODY,
            "expected_policy_revision": 2,
            "expected_reviewer_id": "approver@example.invalid",
            "expected_witness_id": "witness@example.invalid",
        }

    def inspect(self, **overrides):
        return guard.evaluate_signed_review(
            self.review, **{**self.options(), **overrides})

    def test_pinned_valid_signature_claim_is_still_blocked_for_vm_release(self):
        hold = self.inspect()
        self.assertEqual(hold["status"], guard.STATUS)
        self.assertTrue(hold["local_signed_review_pin_matched"])
        self.assertFalse(hold["independent_vm_attestation"])
        self.assertFalse(hold["unknown_windows_pe_execution_authorized"])
        self.assertFalse(hold["apk_or_ota_publication_authorized"])
        self.assertEqual(len(hold["required_external_evidence"]), 5)

    def test_cli_returns_nonzero_even_when_local_signed_result_valid(self):
        args = ["--review-result", str(self.review)]
        for name, value in self.options().items():
            args.extend(["--" + name.replace("_", "-"), str(value)])
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = guard.main(args)
        self.assertEqual(rc, 2)
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(json.loads(out.getvalue())["status"], guard.STATUS)

    def test_tamper_without_external_repin_rejected(self):
        pin = self.sha
        self.record["source_commit"] = "d" * 40
        self.publish()
        with self.assertRaises(guard.ReleaseGuardError):
            self.inspect(expected_review_sha256=pin)

    def test_elevating_vm_claim_with_rehashed_local_file_rejected(self):
        self.record["independent_vm_attestation"] = True
        self.publish()
        with self.assertRaisesRegex(guard.ReleaseGuardError, "contradicts"):
            self.inspect()

    def test_elevating_operator_clock_claim_rejected(self):
        self.record["operator_clock_independently_verified"] = True
        self.publish()
        with self.assertRaises(guard.ReleaseGuardError):
            self.inspect()

    def test_extra_release_authorization_field_rejected(self):
        self.record["release_authorized"] = True
        self.publish()
        with self.assertRaisesRegex(guard.ReleaseGuardError, "schema"):
            self.inspect()

    def test_missing_readonly_source_proof_rejected(self):
        self.record["readonly_source_view_verified"] = False
        self.publish()
        with self.assertRaises(guard.ReleaseGuardError):
            self.inspect()

    def test_report_claiming_ubuntu_synthetic_as_vm_rejected(self):
        self.record["status"] = "PASS_PE_S1_56_READONLY_ROLES_AND_SECRET_BOUNDARY"
        self.publish()
        with self.assertRaises(guard.ReleaseGuardError):
            self.inspect()

    def test_external_custody_pin_mismatch_rejected(self):
        with self.assertRaises(guard.ReleaseGuardError):
            self.inspect(expected_custody_sha256="e" * 64)

    def test_bool_policy_revision_not_treated_as_integer(self):
        self.record["policy_revision"] = True
        self.publish()
        with self.assertRaises(guard.ReleaseGuardError):
            self.inspect()

    def test_duplicate_keys_json_rejected(self):
        raw = self.review.read_bytes().rstrip(b"\n")
        bad = raw[:-1] + b',"independent_vm_attestation":false}\n'
        self.publish(bad)
        with self.assertRaises(guard.ReleaseGuardError):
            self.inspect()

    def test_nonfinite_json_rejected(self):
        raw = self.review.read_bytes().rstrip(b"\n")
        self.publish(raw[:-1] + b',"extra":NaN}\n')
        with self.assertRaises(guard.ReleaseGuardError):
            self.inspect()

    def test_symlink_to_local_review_rejected(self):
        link = self.root / "indirect-review.json"
        link.symlink_to(self.review)
        with self.assertRaises(guard.ReleaseGuardError):
            guard.evaluate_signed_review(link, **self.options())

    def test_hardlinked_local_review_rejected(self):
        alias = self.root / "hardlinked-review.json"
        os.link(self.review, alias)
        with self.assertRaises(guard.ReleaseGuardError):
            self.inspect()

    def test_wrong_file_mode_rejected(self):
        self.review.chmod(0o644)
        with self.assertRaises(guard.ReleaseGuardError):
            self.inspect()

    def test_missing_review_rejected(self):
        self.review.unlink()
        with self.assertRaises(guard.ReleaseGuardError):
            self.inspect()

    def test_same_reviewer_and_witness_identity_rejected(self):
        with self.assertRaises(guard.ReleaseGuardError):
            self.inspect(expected_witness_id="approver@example.invalid")


if __name__ == "__main__":
    unittest.main()
