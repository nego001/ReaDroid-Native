"""PE-S1.64 signed local + third-party observation correlation, ALWAYS HOLD.

Synthetic fixtures use real temporary SSH Ed25519 keys. Local source Git
verification is stubbed; no independent Arch VM is created or attested.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
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
import pe_arch_vm_s1_64_external_correlation_hold as final
import pe_arch_vm_s1_63_external_observer as external
import pe_arch_vm_handoff_review as handoff
from test_pe_arch_vm_s1_62_signed_runtime_hold import (
    SignedRuntimeCombinedReviewTests,
)

OBSERVER_ID = "independent-observer@example.invalid"


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH unavailable")
class ThreeKeySignedHostReviewTests(unittest.TestCase):
    def setUp(self):
        self.case = SignedRuntimeCombinedReviewTests(
            "test_real_two_disposable_signatures_and_runtime_end_in_hold")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.owner = self.case.folder
        self.temporary = tempfile.TemporaryDirectory(prefix="pe-s1-64-host-")
        self.addCleanup(self.temporary.cleanup)
        self.observer_dir = Path(self.temporary.name) / "external"
        self.observer_dir.mkdir(mode=0o700)
        self.key = Path(self.temporary.name) / "test-only-third-key"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)],
            check=True, capture_output=True, timeout=15)
        raw_key = self.key.with_suffix(".pub").read_text("ascii").split()
        allowed = self.observer_dir / external.SIGNERS_FILE
        allowed.write_text(
            f"{OBSERVER_ID} {raw_key[0]} {raw_key[1]}\n", encoding="ascii")
        allowed.chmod(0o600)

        self.manifest = {
            "schema": external.SCHEMA,
            "security_classification": external.CLASSIFICATION,
            "observer_id": OBSERVER_ID,
            "reviewer_id": self.case.kwargs["expected_reviewer_id"],
            "witness_id": self.case.kwargs["expected_witness_id"],
            "source_commit": self.case.commit,
            "reviewer_challenge": self.case.challenge,
            "request_sha256": self.case.kwargs["expected_request_sha256"],
            "custody_index_sha256": self.case.kwargs["expected_custody_sha256"],
            "receipt_sha256": self.case.kwargs["expected_receipt_sha256"],
            "observations": {},
            "observer_local_time_utc_not_attested":
                "2026-10-30T23:40:00+00:00",
            "independent_vm_attestation": False,
            "release_authorized": False,
        }
        for label, name in external.OBS_FILES.items():
            path = self.observer_dir / name
            content = ("TEST ONLY | " + label + " | NO GUEST EXECUTED\n").encode()
            path.write_bytes(content)
            path.chmod(0o600)
            self.manifest["observations"][label] = {
                "filename": name, "sha256": hashlib.sha256(content).hexdigest(),
            }
        self.manifest_file = self.observer_dir / external.MANIFEST_FILE
        self.signature_file = self.observer_dir / external.SIGNATURE_FILE
        self.resign()
        self.pins = {
            **self.case.kwargs,
            "expected_observer_manifest_sha256":
                hashlib.sha256(self.manifest_file.read_bytes()).hexdigest(),
            "expected_observer_signature_sha256":
                hashlib.sha256(self.signature_file.read_bytes()).hexdigest(),
            "expected_observer_signers_sha256":
                hashlib.sha256(allowed.read_bytes()).hexdigest(),
            "expected_observer_id": OBSERVER_ID,
        }

    def resign(self):
        self.manifest_file.write_bytes(
            (json.dumps(self.manifest, sort_keys=True,
                        separators=(",", ":")) + "\n").encode("utf-8"))
        self.manifest_file.chmod(0o600)
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", str(self.key),
             "-n", external.NAMESPACE, str(self.manifest_file)],
            check=True, capture_output=True, timeout=15)
        signed = self.manifest_file.with_suffix(".json.sig")
        signed.replace(self.signature_file)
        self.signature_file.chmod(0o600)

    def opts(self):
        return self.pins.copy()

    def run_review(self, **overrides):
        with mock.patch.object(
            handoff, "verify_source_checkout_pin",
            return_value=self.case.fixture.custody.case.pin) as git:
            result = final.review_three_signed_packages(
                self.owner, self.observer_dir, self.case.source,
                self.case.request, **{**self.opts(), **overrides})
        self.assertEqual(git.call_count, 6)
        return result

    def test_all_three_real_signed_keys_correlate_but_still_hold(self):
        result = self.run_review()
        self.assertEqual(result["status"], final.STATUS)
        self.assertTrue(result["three_distinct_signing_keys_locally_verified"])
        self.assertTrue(result["signed_local_custody_and_runtime_correlated"])
        self.assertTrue(result["external_host_log_hashes_and_signature_correlated"])
        self.assertFalse(result["observer_capture_independently_authenticated"])
        self.assertFalse(result["hypervisor_provenance_independently_verified"])
        self.assertFalse(result["native_kernel_execution_independently_verified"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])

    def test_external_manifest_pin_mismatch_rejected(self):
        with self.assertRaises(final.ThreeWayReviewError):
            self.run_review(expected_observer_manifest_sha256="f" * 64)

    def test_wrong_external_receipt_pin_rejected(self):
        self.manifest["receipt_sha256"] = "f" * 64
        self.resign()
        with self.assertRaises(final.ThreeWayReviewError):
            self.run_review()

    def test_observer_manifest_false_attestation_refused_even_when_signed(self):
        self.manifest["independent_vm_attestation"] = True
        self.resign()
        with self.assertRaises(final.ThreeWayReviewError):
            self.run_review()

    def test_external_log_tampering_rejected(self):
        target = self.observer_dir / external.OBS_FILES["host_guest_kernel"]
        target.write_bytes(b"CHANGED KERNEL LOG\n")
        with self.assertRaises(final.ThreeWayReviewError):
            self.run_review()

    def test_local_ssh_signature_tampered_rejected(self):
        file = self.case.fixture.case.reviewer_sig
        file.write_bytes(file.read_bytes().replace(b"BEGIN", b"FAKED", 1))
        with self.assertRaises(final.ThreeWayReviewError):
            self.run_review()

    def test_external_ssh_signature_tampered_even_with_hash_repin(self):
        self.signature_file.write_bytes(
            self.signature_file.read_bytes().replace(b"BEGIN", b"FAKED", 1))
        sha = hashlib.sha256(self.signature_file.read_bytes()).hexdigest()
        with self.assertRaises(final.ThreeWayReviewError):
            self.run_review(expected_observer_signature_sha256=sha)

    def test_changed_local_receipt_after_signed_stage_rejected(self):
        real = final.external.verify_external_observer
        def tamper(*args, **kwargs):
            answer = real(*args, **kwargs)
            path = self.owner / "acceptance.json"
            path.write_bytes(path.read_bytes() + b"post-review tamper\n")
            return answer
        with mock.patch.object(final.external, "verify_external_observer",
                               side_effect=tamper):
            with self.assertRaisesRegex(
                final.ThreeWayReviewError, "changed during combined review"):
                self.run_review()

    def test_fake_local_attestation_result_refused(self):
        actual = None
        with mock.patch.object(
                handoff, "verify_source_checkout_pin",
                return_value=self.case.fixture.custody.case.pin):
            actual = final.local.review_signed_runtime(
                self.owner, self.case.source, self.case.request,
                **self.case.kwargs)
        with mock.patch.object(
                final.local, "review_signed_runtime",
                return_value={**actual, "independent_vm_attestation": True}):
            with self.assertRaises(final.ThreeWayReviewError):
                self.run_review()

    def test_fake_external_authenticated_host_result_refused(self):
        actual = final.external.verify_external_observer(
            self.observer_dir, self.owner,
            expected_manifest_sha256=self.pins[
                "expected_observer_manifest_sha256"],
            expected_signature_sha256=self.pins[
                "expected_observer_signature_sha256"],
            expected_observer_signers_sha256=self.pins[
                "expected_observer_signers_sha256"],
            expected_reviewer_signers_sha256=self.pins[
                "expected_reviewer_signers_sha256"],
            expected_witness_signers_sha256=self.pins[
                "expected_signers_sha256"],
            expected_observer_id=OBSERVER_ID,
            expected_reviewer_id=self.pins["expected_reviewer_id"],
            expected_witness_id=self.pins["expected_witness_id"],
            expected_source_commit=self.case.commit,
            expected_challenge=self.case.challenge,
            expected_request_sha256=self.pins["expected_request_sha256"],
            expected_custody_sha256=self.pins["expected_custody_sha256"],
            expected_receipt_sha256=self.pins["expected_receipt_sha256"])
        with mock.patch.object(
                final.external, "verify_external_observer",
                return_value={
                    **actual, "observer_host_independently_authenticated": True
                }):
            with self.assertRaises(final.ThreeWayReviewError):
                self.run_review()

    def test_invalid_observer_directory_same_as_operator_refuses_early(self):
        with mock.patch.object(
                final.local, "review_signed_runtime") as local_review:
            with self.assertRaises(final.ThreeWayReviewError):
                final.review_three_signed_packages(
                    self.owner, self.owner, self.case.source,
                    self.case.request, **self.pins)
        local_review.assert_not_called()

    def test_wrong_original_challenge_fails_closed(self):
        with self.assertRaises(final.ThreeWayReviewError):
            self.run_review(expected_challenge="e" * 64)

    def test_bad_policy_revision_fails_closed(self):
        with self.assertRaises(final.ThreeWayReviewError):
            self.run_review(expected_policy_revision=0)

    def _args(self):
        args = [
            "--custody-dir", str(self.owner),
            "--observer-dir", str(self.observer_dir),
            "--source-root", str(self.case.source),
            "--reviewer-request", str(self.case.request),
        ]
        for name, value in self.pins.items():
            args.extend(["--" + name.replace("_", "-"), str(value)])
        return args

    def test_cli_all_real_signatures_exit_two_even_if_valid(self):
        out, err = StringIO(), StringIO()
        with (
            redirect_stdout(out), redirect_stderr(err),
            mock.patch.object(
                handoff, "verify_source_checkout_pin",
                return_value=self.case.fixture.custody.case.pin),
        ):
            status = final.main(self._args())
        self.assertEqual(status, 2)
        self.assertEqual(err.getvalue(), "")
        result = json.loads(out.getvalue())
        self.assertEqual(result["status"], final.STATUS)
        self.assertFalse(result["release_authorized"])

    def test_cli_false_external_pin_exit_two_and_reject(self):
        args = self._args()
        args[args.index("--expected-observer-manifest-sha256") + 1] = "f" * 64
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = final.main(args)
        self.assertEqual(status, 2)
        self.assertEqual(out.getvalue(), "")
        result = json.loads(err.getvalue())
        self.assertEqual(result["status"], final.REJECTED)
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])


if __name__ == "__main__":
    unittest.main()
