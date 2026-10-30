"""PE-S1.51: distinct reviewer vs witness Ed25519 trust signatures.

Real OpenSSH tests use freshly generated disposable keys on Ubuntu.
No native VM, hostile binary, production key, signing service or host
attestation is involved. The Git source fixture is self-reported.
"""
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
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_dual_control_review as dual
import pe_arch_vm_handoff_review as handoff
import pe_arch_vm_witness_review as witness
from test_pe_arch_vm_witness_trust_review import (
    ReviewerTrustPolicyTests, RealOpenSshTrustLifecycleTests, WITNESS_ID,
)

REVIEWER_ID = "policy-approver@example.invalid"


def _test_ssh_ed25519_public(key_bytes: bytes) -> str:
    return base64.b64encode(
        b"\x00\x00\x00\x0bssh-ed25519" +
        b"\x00\x00\x00\x20" + key_bytes).decode("ascii")


class ReviewerDualControlTests(unittest.TestCase):
    trust_case = ReviewerTrustPolicyTests
    real_ssh = False

    def setUp(self):
        self.fixture = self.trust_case(
            "test_s1_50_active_key_and_signature_policy_accepted_not_vm")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.folder = self.fixture.folder
        self.source_root = self.fixture.case.fixture.case.fixture.root
        self.reviewer_allowed = self.folder / dual.REVIEWER_SIGNERS
        self.reviewer_sig = self.folder / dual.REVIEWER_SIGNATURE
        self.reviewer_allowed.write_text(
            REVIEWER_ID + " ssh-ed25519 "
            + _test_ssh_ed25519_public(b"q" * 32) + "\n",
            encoding="ascii")
        self.reviewer_sig.write_bytes(b"synthetic-reviewer-signature")
        self.reviewer_allowed.chmod(0o600)
        self.reviewer_sig.chmod(0o600)

    def options(self):
        return {
            **self.fixture.options(),
            "expected_reviewer_signers_sha256":
                hashlib.sha256(self.reviewer_allowed.read_bytes()).hexdigest(),
            "expected_reviewer_signature_sha256":
                hashlib.sha256(self.reviewer_sig.read_bytes()).hexdigest(),
            "expected_reviewer_id": REVIEWER_ID,
        }

    def run_review(self, *, force_real=False, **overrides):
        args = {**self.options(), **overrides}
        with mock.patch.object(
                handoff, "verify_source_checkout_pin",
                return_value=self.fixture.case.fixture.case.pin) as git:
            if self.real_ssh or force_real:
                result = dual.verify_dual_control(
                    self.folder, self.source_root, **args)
            else:
                with mock.patch.object(witness, "_ssh_verify") as verify:
                    result = dual.verify_dual_control(
                        self.folder, self.source_root, **args)
                self.assertEqual(verify.call_count, 2)
                namespaces = [c.kwargs.get("namespace", witness.NAMESPACE)
                              for c in verify.call_args_list]
                self.assertEqual(
                    namespaces,
                    [dual.NAMESPACE, witness.NAMESPACE])
        self.assertEqual(git.call_count, 2)
        return result

    def test_s1_51_two_distinct_keys_and_pins_pass_without_vm_attestation(self):
        data = self.run_review()
        self.assertEqual(data["status"],
                         "DUAL_CONTROL_CUSTODY_AUTHORIZATION_VERIFIED")
        self.assertTrue(data["reviewer_and_witness_keys_distinct"])
        self.assertTrue(data["reviewer_policy_signature_verified"])
        self.assertTrue(data["witness_custody_signature_verified"])
        self.assertEqual(data["reviewer_id"], REVIEWER_ID)
        self.assertEqual(data["witness_id"], WITNESS_ID)
        self.assertFalse(data["independent_reviewer_identity_verified"])
        self.assertFalse(data["independent_vm_attestation"])
        self.assertFalse(data["native_kernel_execution_independently_verified"])
        self.assertFalse(data["guest_logs_authenticated"])

    def test_s1_51_witness_cannot_authorize_own_key_under_second_identity(self):
        witness_line = self.fixture.case.signers_path.read_text(
            encoding="ascii").split(" ", 1)[1]
        self.reviewer_allowed.write_text(
            REVIEWER_ID + " " + witness_line, encoding="ascii")
        with mock.patch.object(witness, "_ssh_verify") as verifier:
            with self.assertRaisesRegex(
                    dual.DualControlError, "same public key"):
                self.run_review()
        verifier.assert_not_called()

    def test_s1_51_witness_and_reviewer_names_must_differ(self):
        with mock.patch.object(witness, "_ssh_verify") as verifier:
            with self.assertRaisesRegex(
                    dual.DualControlError, "identities must differ"):
                self.run_review(expected_reviewer_id=WITNESS_ID)
        verifier.assert_not_called()

    def test_s1_51_changed_reviewer_signature_rejected_before_crypto(self):
        with mock.patch.object(witness, "_ssh_verify") as verifier:
            with self.assertRaisesRegex(
                    dual.DualControlError, "reviewer signature"):
                self.run_review(expected_reviewer_signature_sha256="f" * 64)
        verifier.assert_not_called()

    def test_s1_51_changed_reviewer_key_rejected_before_crypto(self):
        with mock.patch.object(witness, "_ssh_verify") as verifier:
            with self.assertRaisesRegex(
                    dual.DualControlError, "reviewer key"):
                self.run_review(expected_reviewer_signers_sha256="f" * 64)
        verifier.assert_not_called()

    def test_s1_51_reviewer_namespace_failure_blocks_witness_review(self):
        with (mock.patch.object(
                witness, "_ssh_verify",
                side_effect=witness.WitnessReviewError(
                    "Witness signature rejected by pinned OpenSSH key"))
              as verify, mock.patch.object(
                dual.trust, "verify_trusted_witness") as trust_verify):
            with self.assertRaisesRegex(
                    dual.DualControlError, "signature rejected"):
                self.run_review(force_real=True)
        self.assertEqual(verify.call_count, 1)
        self.assertEqual(verify.call_args.kwargs["namespace"], dual.NAMESPACE)
        trust_verify.assert_not_called()

    def test_s1_51_suspended_policy_still_rejected_after_reviewer_signature(self):
        self.fixture.policy["decision"] = "SUSPENDED"
        self.fixture.write_policy()
        with self.assertRaisesRegex(dual.trust.TrustReviewError,
                                    "suspended or revoked"):
            self.run_review()

    def test_s1_51_policy_revision_rollback_fails_even_if_signed(self):
        with self.assertRaisesRegex(
                dual.trust.TrustReviewError, "revision"):
            self.run_review(expected_policy_revision=2)

    def test_s1_51_duplicate_reviewer_signer_rejected(self):
        old = self.reviewer_allowed.read_bytes()
        self.reviewer_allowed.write_bytes(old + old)
        with mock.patch.object(witness, "_ssh_verify") as crypto:
            with self.assertRaisesRegex(
                    dual.trust.TrustReviewError, "one exact"):
                self.run_review()
        crypto.assert_not_called()

    def test_s1_51_reviewer_file_changed_during_custody_rejected(self):
        original = dual.trust.verify_trusted_witness

        def tamper(*args, **kwargs):
            result = original(*args, **kwargs)
            self.reviewer_sig.write_bytes(
                self.reviewer_sig.read_bytes() + b"late replacement")
            return result
        with mock.patch.object(
                dual.trust, "verify_trusted_witness", side_effect=tamper):
            with self.assertRaisesRegex(
                    dual.DualControlError, "changed during review"):
                self.run_review()

    def test_s1_51_missing_reviewer_pin_fails_before_file_reads(self):
        for field in ("expected_reviewer_id",
                      "expected_reviewer_signers_sha256",
                      "expected_reviewer_signature_sha256",
                      "expected_policy_sha256"):
            with self.subTest(field=field):
                args = self.options()
                args[field] = ""
                with mock.patch.object(
                        dual.receipt_review, "_read_private_receipt") as read:
                    with self.assertRaises(dual.DualControlError):
                        dual.verify_dual_control(
                            self.folder, self.source_root, **args)
                read.assert_not_called()

    def test_s1_51_cli_missing_reviewer_signature_fails_closed(self):
        options = self.options()
        args = [
            "--private-dir", str(self.folder),
            "--source-root", str(self.source_root),
        ]
        for field, value in options.items():
            flag = "--" + field.replace("expected_", "expected-").replace("_", "-")
            args.extend((flag, str(value)))
        self.reviewer_sig.unlink()
        err = StringIO()
        with redirect_stderr(err):
            rc = dual.main(args)
        self.assertEqual(rc, 2)
        self.assertEqual(
            json.loads(err.getvalue())["status"],
            "REJECTED_DUAL_CONTROL_CUSTODY_AUTHORIZATION")


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH unavailable")
class RealDualControlEd25519Tests(ReviewerDualControlTests):
    """Two separate disposable Ed25519 signing keys, verified with OpenSSH."""

    trust_case = RealOpenSshTrustLifecycleTests
    real_ssh = True

    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory(
            prefix="negresco-separate-approver-")
        self.addCleanup(self.temp.cleanup)
        self.approver_key = Path(self.temp.name) / "reviewer-test-only"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "",
             "-f", str(self.approver_key)],
            stdin=subprocess.DEVNULL, capture_output=True,
            check=True, timeout=15)
        contents = self.approver_key.with_suffix(".pub").read_text(
            encoding="ascii").split()
        self.reviewer_allowed.write_text(
            f"{REVIEWER_ID} {contents[0]} {contents[1]}\n",
            encoding="ascii")
        self.reviewer_allowed.chmod(0o600)
        self.sign_policy()

    def sign_policy(self, namespace=None):
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", str(self.approver_key),
             "-n", namespace or dual.NAMESPACE,
             str(self.fixture.policy_path)],
            stdin=subprocess.DEVNULL, capture_output=True,
            timeout=15, check=True)
        signed_file = self.fixture.policy_path.with_suffix(".json.sig")
        signed_file.replace(self.reviewer_sig)
        self.reviewer_sig.chmod(0o600)

    def test_s1_51_real_two_distinct_signatures_accepted(self):
        report = self.run_review()
        self.assertTrue(report["reviewer_policy_signature_verified"])
        self.assertTrue(report["witness_custody_signature_verified"])
        self.assertFalse(report["independent_vm_attestation"])

    def test_s1_51_real_wrong_reviewer_namespace_rejected(self):
        self.sign_policy(namespace=witness.NAMESPACE)
        with self.assertRaisesRegex(
                dual.DualControlError, "signature rejected"):
            self.run_review()

    def test_s1_51_real_reviewer_signature_tampering_rejected(self):
        self.reviewer_sig.write_bytes(
            self.reviewer_sig.read_bytes().replace(
                b"BEGIN", b"FAKED", 1))
        with self.assertRaisesRegex(
                dual.DualControlError, "signature rejected"):
            self.run_review()

    def test_s1_51_real_signed_suspended_policy_still_rejected(self):
        self.fixture.policy["decision"] = "SUSPENDED"
        self.fixture.write_policy()
        self.sign_policy()
        with self.assertRaisesRegex(
                dual.trust.TrustReviewError, "suspended or revoked"):
            self.run_review()

    def test_s1_51_real_witness_key_cannot_sign_reviewer_policy(self):
        # A real witness signature over the policy in its own custody
        # namespace is not a reviewer authorization, even if repinned.
        witness_key = Path(self.fixture.case.secret.name) / "test-only-ed25519"
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", str(witness_key),
             "-n", witness.NAMESPACE, str(self.fixture.policy_path)],
            stdin=subprocess.DEVNULL, capture_output=True,
            timeout=15, check=True)
        self.fixture.policy_path.with_suffix(".json.sig").replace(
            self.reviewer_sig)
        self.reviewer_sig.chmod(0o600)
        with self.assertRaisesRegex(dual.DualControlError, "signature rejected"):
            self.run_review()


if __name__ == "__main__":
    unittest.main()
