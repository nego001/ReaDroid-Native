"""PE-S1.50: reviewer-held witness trust, suspension, revocation, rotation."""
from __future__ import annotations

import base64
from contextlib import redirect_stderr
import hashlib
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_witness_trust_review as trust
import pe_arch_vm_handoff_review as handoff
import pe_arch_vm_witness_review as witness
from test_pe_arch_vm_witness_review import (
    WitnessAcknowledgementTests, RealOpenSshWitnessSignatureTests,
    WITNESS_ID, COMMIT,
)


class ReviewerTrustPolicyTests(unittest.TestCase):
    case_factory = WitnessAcknowledgementTests
    real_crypto = False

    def setUp(self):
        self.case = self.case_factory(
            "test_s1_49_valid_custody_signature_never_claims_vm_attestation")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.folder = self.case.folder
        if not self.real_crypto:
            # A well-formed SSH Ed25519 public blob for parser tests only.
            blob = (b"\x00\x00\x00\x0bssh-ed25519"
                    + b"\x00\x00\x00\x20" + bytes(range(32)))
            self.case.signers_path.write_text(
                WITNESS_ID + " ssh-ed25519 "
                + base64.b64encode(blob).decode("ascii") + "\n",
                encoding="ascii")
            self.case.signers_path.chmod(0o600)
        self.key_hash = self.current_key_sha()
        self.policy = {
            "schema": trust.SCHEMA,
            "security_classification": trust.CLASSIFICATION,
            "witness_id": WITNESS_ID,
            "signature_namespace": witness.NAMESPACE,
            "policy_revision": 1,
            "decision": "ACTIVE",
            "active_public_key_sha256": self.key_hash,
            "revoked_public_key_sha256": [],
        }
        self.policy_path = self.folder / trust.TRUST_FILENAME
        self.write_policy()

    def current_key_sha(self):
        data = self.case.signers_path.read_bytes()
        return hashlib.sha256(
            trust._public_key_blob(data, WITNESS_ID)).hexdigest()

    def write_policy(self, raw=None):
        if raw is None:
            raw = (json.dumps(self.policy, sort_keys=True,
                              separators=(",", ":")) + "\n").encode("utf-8")
        self.policy_path.write_bytes(raw)
        self.policy_path.chmod(0o600)
        self.policy_sha = hashlib.sha256(raw).hexdigest()

    def options(self):
        return {
            **self.case.options(),
            "expected_policy_sha256": self.policy_sha,
            "expected_policy_revision": self.policy["policy_revision"],
        }

    def review(self, **extra):
        options = self.options()
        options.update(extra)
        with mock.patch.object(
                handoff, "verify_source_checkout_pin",
                return_value=self.case.fixture.case.pin) as git:
            if self.real_crypto:
                report = trust.verify_trusted_witness(
                    self.folder, self.case.fixture.case.fixture.root,
                    **options)
            else:
                with mock.patch.object(witness, "_ssh_verify") as crypto:
                    report = trust.verify_trusted_witness(
                        self.folder, self.case.fixture.case.fixture.root,
                        **options)
                crypto.assert_called_once()
        self.assertEqual(git.call_count, 2)
        return report

    def test_s1_50_active_key_and_signature_policy_accepted_not_vm(self):
        report = self.review()
        self.assertEqual(report["status"], "REVIEWER_PINNED_WITNESS_KEY_ACTIVE")
        self.assertEqual(report["policy_revision"], 1)
        self.assertEqual(report["active_public_key_sha256"], self.key_hash)
        self.assertTrue(report["witness_signature_verified"])
        self.assertFalse(report["independent_vm_attestation"])
        self.assertFalse(report["native_kernel_execution_independently_verified"])
        self.assertFalse(report["revocation_status_independently_fetched"])
        self.assertFalse(report["policy_time_independently_verified"])

    def test_s1_50_suspension_and_revocation_block_even_valid_signature(self):
        for status in ("SUSPENDED", "REVOKED"):
            with self.subTest(status=status):
                self.policy["decision"] = status
                self.write_policy()
                with self.assertRaisesRegex(
                        trust.TrustReviewError, "suspended or revoked"):
                    self.review()

    def test_s1_50_key_on_revocation_list_is_rejected(self):
        self.policy["revoked_public_key_sha256"] = [self.key_hash]
        self.write_policy()
        with self.assertRaisesRegex(trust.TrustReviewError, "revoked"):
            self.review()

    def test_s1_50_reviewer_revision_rollback_rejected(self):
        with self.assertRaisesRegex(trust.TrustReviewError, "revision"):
            self.review(expected_policy_revision=2)

    def test_s1_50_wrong_externally_pinned_policy_hash_rejected(self):
        with self.assertRaisesRegex(trust.TrustReviewError, "external SHA-256"):
            self.review(expected_policy_sha256="f" * 64)

    def test_s1_50_key_substitution_rejected_even_if_file_hash_repinned(self):
        replacement = (b"\x00\x00\x00\x0bssh-ed25519"
                       + b"\x00\x00\x00\x20" + b"z" * 32)
        self.case.signers_path.write_text(
            WITNESS_ID + " ssh-ed25519 "
            + base64.b64encode(replacement).decode("ascii") + "\n",
            encoding="ascii")
        with self.assertRaisesRegex(trust.TrustReviewError, "key do not match"):
            self.review()

    def test_s1_50_duplicate_keys_bad_policy_revision_rejected(self):
        self.write_policy(b'{"schema":"X","schema":"Y"}\n')
        with self.assertRaises(trust.TrustReviewError):
            self.review()
        self.policy["policy_revision"] = True
        self.write_policy()
        with self.assertRaisesRegex(trust.TrustReviewError, "revision"):
            self.review(expected_policy_revision=1)

    def test_s1_50_unsorted_duplicate_or_invalid_revocation_hashes_rejected(self):
        for revoked in (["a" * 64, "a" * 64],
                        ["b" * 64, "a" * 64],
                        ["bad"], ["a" * 64] * 65):
            with self.subTest(revoked=revoked[:2]):
                self.policy["revoked_public_key_sha256"] = revoked
                self.write_policy()
                with self.assertRaisesRegex(
                        trust.TrustReviewError, "sorted, unique"):
                    self.review()

    def test_s1_50_changed_policy_during_review_rejected(self):
        original_verify = witness.verify_witness_ack

        def tamper(*args, **kwargs):
            result = original_verify(*args, **kwargs)
            self.policy_path.write_bytes(
                self.policy_path.read_bytes() + b"changed\n")
            return result

        with mock.patch.object(
                witness, "verify_witness_ack", side_effect=tamper):
            with self.assertRaisesRegex(
                    trust.TrustReviewError, "changed during review|external SHA-256"):
                self.review()

    def test_s1_50_missing_external_trust_pin_rejected_before_reading(self):
        for field, wrong in (
                ("expected_policy_sha256", ""),
                ("expected_policy_revision", 0),
                ("expected_witness_id", "*"),
                ("expected_signers_sha256", "")):
            with self.subTest(field=field):
                options = self.options()
                options[field] = wrong
                with mock.patch.object(
                        trust.receipt_review, "_read_private_receipt"
                        ) as read:
                    with self.assertRaises(trust.TrustReviewError):
                        trust.verify_trusted_witness(
                            self.folder, self.case.fixture.case.fixture.root,
                            **options)
                read.assert_not_called()

    def test_s1_50_cli_missing_policy_rejected(self):
        args = [
            "--private-dir", str(self.folder),
            "--source-root", str(self.case.fixture.case.fixture.root),
            "--expected-policy-sha256", self.policy_sha,
            "--expected-policy-revision", "1",
            "--expected-custody-sha256", self.case.fixture.index_sha256,
            "--expected-statement-sha256", self.case.statement_sha,
            "--expected-signature-sha256",
            self.case.options()["expected_signature_sha256"],
            "--expected-signers-sha256",
            self.case.options()["expected_signers_sha256"],
            "--expected-source-commit", COMMIT,
            "--expected-challenge", self.case.fixture.case.fixture.challenge,
            "--expected-witness-id", WITNESS_ID,
        ]
        self.policy_path.unlink()
        errors = StringIO()
        with redirect_stderr(errors):
            result = trust.main(args)
        self.assertEqual(result, 2)
        self.assertEqual(
            json.loads(errors.getvalue())["status"],
            "REJECTED_WITNESS_KEY_TRUST")


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH missing on this runner")
class RealOpenSshTrustLifecycleTests(ReviewerTrustPolicyTests):
    """Cryptographic key retirement and rotation using disposable SSH keys."""
    case_factory = RealOpenSshWitnessSignatureTests
    real_crypto = True

    def test_s1_50_real_rotation_accepts_new_key_only_with_new_reviewer_pin(self):
        previous_key = self.key_hash
        original_policy = self.policy_path.read_bytes()
        # Generate an entirely new disposable key and sign the *same*
        # statement. The old private key is never copied into the checkout.
        secret = Path(self.case.secret.name)
        key = secret / "rotated-ed25519"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
            timeout=15)
        fields = key.with_suffix(".pub").read_text(encoding="ascii").split()
        self.case.signers_path.write_text(
            f"{WITNESS_ID} {fields[0]} {fields[1]}\n", encoding="ascii")
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", str(key), "-n",
             witness.NAMESPACE, str(self.case.witness_path)],
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
            timeout=15)
        self.case.witness_path.with_suffix(".json.sig").replace(
            self.case.signature_path)
        self.case.signature_path.chmod(0o600)
        rotated_key = self.current_key_sha()
        self.assertNotEqual(previous_key, rotated_key)
        # Old externally pinned policy rejects new key, regardless of the
        # newly valid Ed25519 signature.
        with self.assertRaisesRegex(trust.TrustReviewError, "key do not match"):
            self.review()
        self.policy["policy_revision"] = 2
        self.policy["active_public_key_sha256"] = rotated_key
        self.policy["revoked_public_key_sha256"] = [previous_key]
        self.write_policy()
        report = self.review()
        self.assertEqual(report["policy_revision"], 2)
        self.assertEqual(report["active_public_key_sha256"], rotated_key)
        self.assertEqual(report["revoked_key_count"], 1)
        # Old policy bytes cannot satisfy the new external revision/pin.
        self.policy_path.write_bytes(original_policy)
        with self.assertRaises(trust.TrustReviewError):
            self.review()


if __name__ == "__main__":
    unittest.main()
