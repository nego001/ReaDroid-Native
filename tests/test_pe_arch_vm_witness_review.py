"""PE-S1.49: detached witness signatures attest authorship of custody only."""
from __future__ import annotations

from contextlib import redirect_stderr
import hashlib
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_witness_review as witness
import pe_arch_vm_handoff_review as handoff
from test_pe_arch_vm_custody_review import CustodyPackageTests, COMMIT

WITNESS_ID = "independent-reviewer@example.invalid"
STAMP = "2026-10-30T02:00:00Z"


class WitnessAcknowledgementTests(unittest.TestCase):
    def setUp(self):
        self.fixture = CustodyPackageTests(
            "test_s1_48_complete_custody_package_correlates_without_vm_attestation")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.folder = self.fixture.folder
        self.statement = {
            "schema": witness.SCHEMA,
            "security_classification": witness.CLASSIFICATION,
            "witness_id": WITNESS_ID,
            "source_commit": COMMIT,
            "reviewer_challenge": self.fixture.case.fixture.challenge,
            "custody_index_sha256": self.fixture.index_sha256,
            "acknowledgement_utc": STAMP,
            "vm_attestation_claimed": False,
        }
        self.witness_path = self.folder / witness.FILES["statement"]
        self.signature_path = self.folder / witness.FILES["signature"]
        self.signers_path = self.folder / witness.FILES["allowed_signers"]
        self.signature_path.write_bytes(b"synthetic-signature-test-only")
        self.signers_path.write_text(
            WITNESS_ID + " ssh-ed25519 " + "A" * 70 + "\n",
            encoding="ascii")
        self.signature_path.chmod(0o600)
        self.signers_path.chmod(0o600)
        self.write_statement()

    def write_statement(self, raw=None):
        if raw is None:
            raw = (json.dumps(self.statement, sort_keys=True,
                              separators=(",", ":")) + "\n").encode("utf-8")
        self.witness_path.write_bytes(raw)
        self.witness_path.chmod(0o600)
        self.statement_sha = hashlib.sha256(raw).hexdigest()

    def options(self):
        return {
            "expected_custody_sha256": self.fixture.index_sha256,
            "expected_statement_sha256": self.statement_sha,
            "expected_signature_sha256": hashlib.sha256(
                self.signature_path.read_bytes()).hexdigest(),
            "expected_signers_sha256": hashlib.sha256(
                self.signers_path.read_bytes()).hexdigest(),
            "expected_source_commit": COMMIT,
            "expected_challenge": self.fixture.case.fixture.challenge,
            "expected_witness_id": WITNESS_ID,
        }

    def review(self, *, fake_ssh=True, **replacements):
        opts = self.options()
        opts.update(replacements)
        with mock.patch.object(
                handoff, "verify_source_checkout_pin",
                return_value=self.fixture.case.pin) as pin:
            if fake_ssh:
                with mock.patch.object(witness, "_ssh_verify") as check:
                    answer = witness.verify_witness_ack(
                        self.folder, self.fixture.case.fixture.root, **opts)
                check.assert_called_once()
            else:
                answer = witness.verify_witness_ack(
                    self.folder, self.fixture.case.fixture.root, **opts)
        self.assertEqual(pin.call_count, 2)
        return answer

    def test_s1_49_valid_custody_signature_never_claims_vm_attestation(self):
        result = self.review()
        self.assertEqual(
            result["status"], "SIGNED_CUSTODY_ACKNOWLEDGEMENT_VERIFIED")
        self.assertTrue(result["detached_witness_signature_verified"])
        self.assertTrue(result["trusted_witness_key_pin_matched"])
        self.assertTrue(result["custody_package_correlated_locally"])
        self.assertFalse(result["guest_logs_authenticated"])
        self.assertFalse(result["witness_time_independently_verified"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["native_kernel_execution_independently_verified"])
        self.assertFalse(result["host_or_git_authenticity_verified"])

    def test_s1_49_wrong_externally_pinned_signer_key_rejected(self):
        with mock.patch.object(witness, "_ssh_verify") as verifier:
            with self.assertRaisesRegex(
                    witness.WitnessReviewError, "Reviewer-pinned"):
                self.review(expected_signers_sha256="f" * 64)
        verifier.assert_not_called()

    def test_s1_49_wrong_external_signature_hash_rejected(self):
        with mock.patch.object(witness, "_ssh_verify") as verifier:
            with self.assertRaisesRegex(
                    witness.WitnessReviewError, "Reviewer-pinned"):
                self.review(expected_signature_sha256="f" * 64)
        verifier.assert_not_called()

    def test_s1_49_wrong_external_statement_hash_rejected(self):
        with mock.patch.object(witness, "_ssh_verify") as verifier:
            with self.assertRaisesRegex(
                    witness.WitnessReviewError, "Reviewer-pinned"):
                self.review(expected_statement_sha256="f" * 64)
        verifier.assert_not_called()

    def test_s1_49_rejects_claim_to_attest_vm_even_if_statement_repinned(self):
        self.statement["vm_attestation_claimed"] = True
        self.write_statement()
        with self.assertRaisesRegex(
                witness.WitnessReviewError, "claims or pinned values"):
            self.review()

    def test_s1_49_rejects_witness_identity_swap_even_if_repinned(self):
        self.statement["witness_id"] = "another@example.invalid"
        self.write_statement()
        with self.assertRaisesRegex(
                witness.WitnessReviewError, "claims or pinned values"):
            self.review()

    def test_s1_49_rejects_wrong_signature_namespace_or_validity(self):
        with mock.patch.object(
                witness, "_ssh_verify",
                side_effect=witness.WitnessReviewError("bad namespace")):
            with self.assertRaisesRegex(
                    witness.WitnessReviewError, "bad namespace"):
                self.review(fake_ssh=False)

    def test_s1_49_rejects_untrusted_public_key_replacement(self):
        self.signers_path.write_text(
            WITNESS_ID + " ssh-ed25519 " + "B" * 70 + "\n",
            encoding="ascii")
        # Even if the malicious key is re-pinned within the local command,
        # a real signature verified with the original key must be rejected.
        with mock.patch.object(witness, "_ssh_verify",
                               side_effect=witness.WitnessReviewError(
                                   "Witness signature rejected by pinned OpenSSH key")):
            with self.assertRaisesRegex(
                    witness.WitnessReviewError, "signature rejected"):
                self.review(fake_ssh=False)

    def test_s1_49_rejects_allowed_signers_wildcard(self):
        self.signers_path.write_text(
            "* ssh-ed25519 " + "B" * 70 + "\n", encoding="ascii")
        with self.assertRaisesRegex(
                witness.WitnessReviewError, "Only one exact"):
            self.review()

    def test_s1_49_rejects_duplicate_witness_statement_keys(self):
        self.write_statement(
            b'{"schema":"ok","schema":"not-ok"}\n')
        with self.assertRaises(witness.WitnessReviewError):
            self.review()

    def test_s1_49_rejects_missing_external_pins_before_read(self):
        for field in self.options():
            with self.subTest(field=field):
                v = self.options()
                v[field] = ""
                with mock.patch.object(
                        witness.receipt_review, "_read_private_receipt"
                        ) as read:
                    with self.assertRaises(witness.WitnessReviewError):
                        witness.verify_witness_ack(
                            self.folder, self.fixture.case.fixture.root, **v)
                read.assert_not_called()

    def test_s1_49_witness_files_changed_after_signature_rejected(self):
        original = self.signers_path.read_bytes()
        def tamper(*args, **kwargs):
            self.signers_path.write_bytes(original + b"extra\n")
            return self.fixture.review()
        with mock.patch.object(
                witness.custody, "verify_custody_index",
                side_effect=tamper):
            with self.assertRaisesRegex(
                    witness.WitnessReviewError, "Reviewer-pinned"):
                self.review()

    def test_s1_49_cli_rejects_missing_signature_without_execution(self):
        self.signature_path.unlink()
        err = StringIO()
        args = [
            "--private-dir", str(self.folder),
            "--source-root", str(self.fixture.case.fixture.root),
            "--expected-custody-sha256", self.fixture.index_sha256,
            "--expected-statement-sha256", self.statement_sha,
            "--expected-signature-sha256", "e" * 64,
            "--expected-signers-sha256", self.options()["expected_signers_sha256"],
            "--expected-source-commit", COMMIT,
            "--expected-challenge", self.fixture.case.fixture.challenge,
            "--expected-witness-id", WITNESS_ID,
        ]
        with redirect_stderr(err):
            code = witness.main(args)
        self.assertEqual(code, 2)
        self.assertEqual(
            json.loads(err.getvalue())["status"],
            "REJECTED_SIGNED_CUSTODY_ACKNOWLEDGEMENT")


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH not installed here")
class RealOpenSshWitnessSignatureTests(WitnessAcknowledgementTests):
    """Actual Ed25519 signing in a disposable fixture; no production key."""

    def setUp(self):
        super().setUp()
        self.secret = tempfile.TemporaryDirectory()
        self.addCleanup(self.secret.cleanup)
        key = Path(self.secret.name) / "test-only-ed25519"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
            stdin=subprocess.DEVNULL, capture_output=True,
            check=True, timeout=15)
        public = (key.with_suffix(".pub")).read_text(encoding="ascii").split()
        self.signers_path.write_text(
            f"{WITNESS_ID} {public[0]} {public[1]}\n", encoding="ascii")
        self.signers_path.chmod(0o600)
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", str(key),
             "-n", witness.NAMESPACE, str(self.witness_path)],
            stdin=subprocess.DEVNULL, capture_output=True,
            check=True, timeout=15)
        produced = self.witness_path.with_suffix(".json.sig")
        produced.replace(self.signature_path)
        self.signature_path.chmod(0o600)

    def test_s1_49_real_signature_valid_and_tampered_signature_rejected(self):
        verified = self.review(fake_ssh=False)
        self.assertTrue(verified["detached_witness_signature_verified"])
        self.signature_path.write_bytes(
            self.signature_path.read_bytes().replace(b"BEGIN", b"FAKED", 1))
        with self.assertRaisesRegex(
                witness.WitnessReviewError, "signature rejected"):
            self.review(fake_ssh=False)

    def test_s1_49_real_signature_rejected_for_different_namespace(self):
        with mock.patch.object(witness, "NAMESPACE",
                               "different-review-purpose"):
            with self.assertRaisesRegex(
                    witness.WitnessReviewError, "signature rejected"):
                self.review(fake_ssh=False)

    def test_s1_49_real_signature_rejected_after_witness_key_substitution(self):
        self.signers_path.write_text(
            f"{WITNESS_ID} ssh-ed25519 " + "A" * 70 + "\n",
            encoding="ascii")
        with self.assertRaisesRegex(
                witness.WitnessReviewError, "signature rejected"):
            self.review(fake_ssh=False)


if __name__ == "__main__":
    unittest.main()
