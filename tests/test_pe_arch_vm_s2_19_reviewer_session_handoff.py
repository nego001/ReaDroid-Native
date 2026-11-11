"""PE-S2.19 joint V3+native receipt test: real V1/V2/V3 test signatures.

Ghidra, libvirt host counters, local kernel and Git source verification are
not executed. Native receipt and Git verdict are mocked intentionally.
"""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_evidence as evidence
import pe_arch_vm_s2_18_signed_host_pair as v3
import pe_arch_vm_s2_19_reviewer_session_handoff as handoff
from test_pe_arch_vm_s2_18_signed_host_pair import SignedHostPairV3Contracts


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH required")
class JointSessionHandoffContracts(unittest.TestCase):
    def setUp(self):
        self.fixture = SignedHostPairV3Contracts(
            "test_three_valid_signatures_and_pair_still_hold")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture
        self.observer = self.f.owner
        self.custody = self.f.custody
        self.checkout = self.f.old.f.root / "separate-checkout"
        self.checkout.mkdir(mode=0o700)
        self.receipt = self.custody / "acceptance.json"
        self.payload = b"TEST-ONLY-UNAUTHENTICATED-LOCAL-RECEIPT\n"
        self.receipt.write_bytes(self.payload)
        self.receipt.chmod(0o600)
        digest = hashlib.sha256(self.payload).hexdigest()
        self.digest = digest

        # Resign each of the 3 manifests with the same *real* disposable
        # observer key. The signed V1 chain must pin THIS receipt SHA.
        old = self.f.old
        old.f.record["receipt_sha256"] = digest
        old.f.sign()
        v1_pins = old.f.options()
        old.pins["expected_receipt_sha256"] = digest
        old.pins["expected_v1_manifest_sha256"] = v1_pins[
            "expected_manifest_sha256"]
        old.pins["expected_v1_signature_sha256"] = v1_pins[
            "expected_signature_sha256"]
        old.v2_manifest.unlink()
        old.v2_signature.unlink()
        old.prepare()
        old.sign()
        self.f.pins.update(old.pins)
        self.f.pins["expected_v2_manifest_sha256"] = hashlib.sha256(
            old.v2_manifest.read_bytes()).hexdigest()
        self.f.pins["expected_v2_signature_sha256"] = hashlib.sha256(
            old.v2_signature.read_bytes()).hexdigest()
        self.f.prepare()
        self.f.sign()
        self.pins = dict(self.f.pins)
        self.extras = {
            "expected_v3_manifest_sha256": hashlib.sha256(
                self.f.file.read_bytes()).hexdigest(),
            "expected_v3_signature_sha256": hashlib.sha256(
                self.f.sig.read_bytes()).hexdigest(),
            "expected_native_receipt_sha256": digest,
        }

    def local_result(self, **changed):
        return {
            "status": "LOCAL_RECEIPT_CONSISTENCY_VALIDATED",
            "security_classification": "UNSIGNED_NOT_INDEPENDENT_VM_ATTESTATION",
            "receipt_sha256": self.digest,
            "source_files_rechecked": len(evidence.SOURCE_FILES),
            "external_receipt_sha256_pin_matched": True,
            "readonly_source_view_verified": True,
            "reviewer_challenge_correlated": True,
            "native_kernel_execution_independently_verified": False,
            "windows_binary_executed_by_reviewer": False,
            "independent_vm_attestation": False,
            **changed,
        }

    def git_result(self, **changed):
        return {
            "status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED",
            "expected_commit": self.pins["expected_source_commit"],
            "checked_manifest_entries": len(evidence.SOURCE_FILES),
            "worktree_status_clean": True,
            "git_authorship_or_signature_verified": False,
            "native_vm_or_kernel_verified": False,
            **changed,
        }

    def verify(self, *, local=None, git=None, **overrides):
        with (mock.patch.object(
                handoff.receipt, "verify_local_receipt",
                return_value=self.local_result() if local is None else local)
              as receipt_review,
              mock.patch.object(
                handoff.checkout, "verify_source_checkout_pin",
                return_value=self.git_result() if git is None else git)
              as checkout_review):
            result = handoff.verify_reviewer_session(
                self.observer, self.custody, self.receipt, self.checkout,
                **{**self.pins, **self.extras, **overrides})
        return result, receipt_review, checkout_review

    def test_three_real_signatures_and_matching_receipt_still_hold(self):
        result, local, git = self.verify()
        self.assertEqual(result["status"], handoff.STATUS)
        self.assertTrue(result[
            "native_receipt_sha256_equals_v1_signed_receipt_pin"])
        self.assertTrue(result["v1_v2_v3_detached_signatures_verified"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["guest_kernel_execution_independently_attested"])
        local.assert_called_once_with(
            self.receipt, self.checkout,
            expected_challenge=self.pins["expected_challenge"],
            expected_receipt_sha256=self.digest,
            require_readonly_source_view=True)
        git.assert_called_once_with(
            self.checkout, self.pins["expected_source_commit"],
            evidence.SOURCE_FILES)

    def test_receipt_digest_from_unsigned_input_cannot_override_signed_v1(self):
        with (mock.patch.object(handoff.v3,
                                "verify_signed_domstats_extension") as signed,
              self.assertRaises(handoff.SessionHandoffError)):
            self.verify(expected_native_receipt_sha256="f"*64)
        signed.assert_not_called()

    def test_missing_receipt_refused_before_signed_review(self):
        self.receipt.unlink()
        with (mock.patch.object(handoff.v3,
                                "verify_signed_domstats_extension") as signed,
              self.assertRaises(handoff.SessionHandoffError)):
            self.verify()
        signed.assert_not_called()

    def test_symlink_receipt_refused_before_signed_review(self):
        backup=self.custody/"saved-receipt"
        self.receipt.rename(backup)
        self.receipt.symlink_to(backup)
        with (mock.patch.object(handoff.v3,
                                "verify_signed_domstats_extension") as signed,
              self.assertRaises(handoff.SessionHandoffError)):
            self.verify()
        signed.assert_not_called()

    def test_rewritten_native_receipt_blocked_even_if_new_hash_supplied(self):
        self.receipt.write_bytes(b"REPLACED-RECEIPT\n")
        with self.assertRaises(handoff.SessionHandoffError):
            self.verify(expected_native_receipt_sha256=hashlib.sha256(
                self.receipt.read_bytes()).hexdigest())

    def test_host_v3_signature_altered_refused(self):
        self.f.sig.write_bytes(self.f.old.v2_signature.read_bytes())
        self.f.sig.chmod(0o600)
        with self.assertRaises(handoff.SessionHandoffError):
            self.verify(expected_v3_signature_sha256=hashlib.sha256(
                self.f.sig.read_bytes()).hexdigest())

    def test_host_v3_manifest_wrong_signed_digest_refused(self):
        with self.assertRaises(handoff.SessionHandoffError):
            self.verify(expected_v3_manifest_sha256="f"*64)

    def test_unsupported_receipt_attestation_flag_refused(self):
        with self.assertRaises(handoff.SessionHandoffError):
            self.verify(local=self.local_result(
                native_kernel_execution_independently_verified=True))

    def test_readonly_source_not_reported_refused(self):
        with self.assertRaises(handoff.SessionHandoffError):
            self.verify(local=self.local_result(
                readonly_source_view_verified=False))

    def test_git_source_commit_mismatch_refused(self):
        with self.assertRaises(handoff.SessionHandoffError):
            self.verify(git=self.git_result(expected_commit="f"*40))

    def test_git_dirty_checkout_refused(self):
        with self.assertRaises(handoff.SessionHandoffError):
            self.verify(git=self.git_result(worktree_status_clean=False))

    def test_reviewer_receipt_must_remain_in_separate_custody(self):
        other=self.checkout/"acceptance.json"
        other.write_bytes(self.payload)
        other.chmod(0o600)
        with self.assertRaises(handoff.SessionHandoffError):
            handoff.verify_reviewer_session(
                self.observer, self.custody, other, self.checkout,
                **self.pins, **self.extras)

    def test_invalid_release_claim_in_signature_result_refused(self):
        with (mock.patch.object(handoff.v3, "verify_signed_domstats_extension",
                                return_value={
                                    "status": v3.VERIFIED,
                                    "v3_detached_ed25519_signature_verified": True,
                                    "v2_detached_signature_rechecked": True,
                                    "v1_detached_signature_rechecked": True,
                                    "two_phase_hashes_bound_to_signed_v3_only": True,
                                    "independent_vm_attestation": False,
                                    "release_authorized": True}),
              self.assertRaises(handoff.SessionHandoffError)):
            self.verify()

    def test_cli_valid_joint_review_returns_hold_code_two(self):
        args=[
            "--observer-dir",str(self.observer),
            "--custody-dir",str(self.custody),
            "--native-receipt",str(self.receipt),
            "--source-root",str(self.checkout)]
        for key,val in {**self.pins, **self.extras}.items():
            args.extend(["--"+key.replace("_","-"),val])
        output=StringIO()
        with (mock.patch.object(
                handoff.receipt, "verify_local_receipt",
                return_value=self.local_result()),
              mock.patch.object(
                handoff.checkout, "verify_source_checkout_pin",
                return_value=self.git_result()),
              redirect_stdout(output)):
            status=handoff.main(args)
        self.assertEqual(status,2)
        self.assertEqual(json.loads(output.getvalue())["status"],handoff.STATUS)


if __name__ == "__main__":
    unittest.main()
