"""PE-S1.54: end-to-end structural, signed policy and receipt-custody review."""
from __future__ import annotations

from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
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
import pe_arch_vm_end_to_end_review as full
import pe_arch_vm_handoff_review as handoff
import pe_arch_vm_witness_review as witness
from test_pe_arch_vm_dual_control_review import (
    ReviewerDualControlTests, RealDualControlEd25519Tests,
)

COMMIT = "a" * 40


class CompletePackageTests(unittest.TestCase):
    case_class = ReviewerDualControlTests
    cryptographic_test = False

    def setUp(self):
        self.case = self.case_class(
            "test_s1_51_two_distinct_keys_and_pins_pass_without_vm_attestation")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.custody = self.case.fixture.case.fixture
        self.folder = self.case.folder
        self.source = self.case.source_root
        self.challenge = self.custody.case.fixture.challenge
        self.commit = self.custody.case.pin["expected_commit"]
        receipt_data = json.loads(
            (self.folder / "acceptance.json").read_text(encoding="utf-8"))
        self.accepted_at = datetime.fromisoformat(
            receipt_data["recorded_at_utc"])
        self.collected_at = self.accepted_at + timedelta(minutes=5)
        self.common = {
            "classification":
                "OPERATOR_SELF_REPORTED_NATIVE_ARCH_OBSERVATION_NOT_ATTESTED",
            "source_commit": self.commit,
            "reviewer_challenge": self.challenge,
            "operator_observed_at_utc_not_attested":
                self.collected_at.isoformat(),
            "native_arch_vm_gate_local_pass": True,
            "independent_vm_attestation": False,
            "native_kernel_execution_independently_verified": False,
            "real_cgroup_limits_or_cleanup_tested_by_this_command": False,
            "windows_binary_executed": False,
        }
        self.kernel = {
            **self.common,
            "artifact": "guest_kernel_observation",
            "kernel_release": "6.15.2-arch1-1",
            "kernel_machine": "x86_64",
            "pid1_comm": "systemd",
            "systemd_version_first_line": "systemd 258",
            "virtualization_reported_by_local_systemd": "kvm",
        }
        self.group = {
            **self.common,
            "artifact": "guest_cgroup_observation",
            "cgroup_v2_controllers_available": [
                "cpu", "io", "memory", "pids"],
            "cgroup_v2_root_subtree_control": ["cpu", "memory", "pids"],
            "systemd_user_control_group_locally_observed":
                "/user.slice/user-1000.slice/user@1000.service",
            "cgroup_quotas_verified_by_this_command": False,
            "cgroup_descendant_cleanup_verified_by_this_command": False,
        }
        self.rehash_logs()
        self.resign_witness_if_real()

    def rehash_logs(self):
        for label, payload in (
                ("guest_kernel_observation", self.kernel),
                ("guest_cgroup_observation", self.group)):
            dest = self.folder / self.custody.index["artifacts"][label]["filename"]
            content = (json.dumps(payload, sort_keys=True,
                                  separators=(",", ":")) + "\n").encode()
            dest.write_bytes(content)
            dest.chmod(0o600)
            self.custody.index["artifacts"][label]["sha256"] = (
                hashlib.sha256(content).hexdigest())
        self.custody.write_index()

    def resign_witness_if_real(self):
        self.case.fixture.case.statement["custody_index_sha256"] = (
            self.custody.index_sha256)
        self.case.fixture.case.write_statement()
        if self.cryptographic_test:
            key = Path(self.case.fixture.case.secret.name) / "test-only-ed25519"
            subprocess.run(
                ["ssh-keygen", "-Y", "sign", "-f", str(key),
                 "-n", witness.NAMESPACE,
                 str(self.case.fixture.case.witness_path)],
                stdin=subprocess.DEVNULL, capture_output=True,
                check=True, timeout=15)
            sig = self.case.fixture.case.witness_path.with_suffix(".json.sig")
            sig.replace(self.case.fixture.case.signature_path)
            self.case.fixture.case.signature_path.chmod(0o600)

    def options(self):
        return {
            **self.case.options(),
            "expected_source_commit": self.commit,
            "expected_challenge": self.challenge,
        }

    def review(self, **overrides):
        kw = {**self.options(), **overrides}
        with mock.patch.object(
                handoff, "verify_source_checkout_pin",
                return_value=self.custody.case.pin) as git:
            if self.cryptographic_test:
                answer = full.verify_complete_review(
                    self.folder, self.source, **kw)
            else:
                with mock.patch.object(witness, "_ssh_verify") as crypto:
                    answer = full.verify_complete_review(
                        self.folder, self.source, **kw)
                self.assertEqual(crypto.call_count, 2)
        self.assertEqual(git.call_count, 4)
        return answer

    def test_s1_54_both_full_checks_reconcile_without_vm_attestation(self):
        verified = self.review()
        self.assertEqual(verified["status"], full.STATUS)
        self.assertTrue(verified["structured_guest_logs_consistent_with_custody"])
        self.assertTrue(verified["separate_reviewer_and_witness_signatures_verified"])
        self.assertTrue(verified["operator_claimed_chronology_consistent"])
        self.assertFalse(verified["operator_clock_independently_verified"])
        self.assertFalse(verified["witness_identity_independently_verified"])
        self.assertFalse(verified["operator_logs_authenticated"])
        self.assertFalse(verified["independent_vm_attestation"])

    def test_s1_54_rejects_claimed_log_before_acceptance_even_when_resigned(self):
        time = self.accepted_at - timedelta(seconds=1)
        self.kernel["operator_observed_at_utc_not_attested"] = time.isoformat()
        self.group["operator_observed_at_utc_not_attested"] = time.isoformat()
        self.rehash_logs()
        self.resign_witness_if_real()
        with self.assertRaisesRegex(
                full.EndToEndReviewError, "predates acceptance"):
            self.review()

    def test_s1_54_rehashed_logs_without_resigned_witness_must_fail(self):
        self.kernel["kernel_release"] = "6.15.3-arch1-1"
        self.rehash_logs()
        # Deliberately do not update or re-sign the PE-S1.49 statement.
        with self.assertRaises(full.EndToEndReviewError):
            self.review()

    def test_s1_54_invalid_source_commit_pin_rejected_before_git(self):
        with mock.patch.object(
                handoff, "verify_source_checkout_pin") as git:
            with self.assertRaisesRegex(
                    full.EndToEndReviewError, "commit/revision"):
                full.verify_complete_review(
                    self.folder, self.source,
                    **{**self.options(), "expected_source_commit": "0"})
        git.assert_not_called()

    def test_s1_54_witness_and_reviewer_must_not_share_identity(self):
        with self.assertRaisesRegex(
                full.EndToEndReviewError, "must be different"):
            self.review(expected_reviewer_id=self.options()["expected_witness_id"])

    def test_s1_54_mismatched_external_policy_hash_fails_closed(self):
        with self.assertRaises(full.EndToEndReviewError):
            self.review(expected_policy_sha256="f" * 64)

    def test_s1_54_suspended_policy_even_when_signed_fails(self):
        self.case.fixture.policy["decision"] = "SUSPENDED"
        self.case.fixture.write_policy()
        if self.cryptographic_test:
            self.case.sign_policy()
        with self.assertRaises(full.EndToEndReviewError):
            self.review()

    def test_s1_54_tampering_private_file_during_second_pass_rejected(self):
        original = full.dual.verify_dual_control

        def tamper(*args, **kwargs):
            result = original(*args, **kwargs)
            target = self.folder / "guest-cgroup-observation.txt"
            target.write_bytes(target.read_bytes() + b"late change\n")
            return result

        with mock.patch.object(
                full.dual, "verify_dual_control", side_effect=tamper):
            with self.assertRaisesRegex(
                    full.EndToEndReviewError, "changed during full review"):
                self.review()

    def test_s1_54_invalid_claimed_time_format_rejected(self):
        self.kernel["operator_observed_at_utc_not_attested"] = "2026-10-30"
        self.group["operator_observed_at_utc_not_attested"] = "2026-10-30"
        self.rehash_logs()
        self.resign_witness_if_real()
        with self.assertRaises(full.EndToEndReviewError):
            self.review()

    def test_s1_54_cli_missing_signature_rejected(self):
        args = ["--private-dir", str(self.folder),
                "--source-root", str(self.source)]
        for k,v in self.options().items():
            args += ["--" + k.replace("_", "-"), str(v)]
        (self.folder / "reviewer-witness-trust-policy.sig").unlink()
        stderr = StringIO()
        with redirect_stderr(stderr):
            rc = full.main(args)
        self.assertEqual(rc, 2)
        self.assertEqual(
            json.loads(stderr.getvalue())["status"],
            "REJECTED_SIGNED_GUEST_CUSTODY_REVIEW")


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH unavailable")
class RealSignedCompletePackageTests(CompletePackageTests):
    """Real dual OpenSSH signers. Source Git pin is a fixture only."""
    case_class = RealDualControlEd25519Tests
    cryptographic_test = True

    def test_s1_54_real_two_ssh_signers_and_structured_logs_accepted(self):
        report = self.review()
        self.assertTrue(report["separate_reviewer_and_witness_signatures_verified"])
        self.assertFalse(report["independent_vm_attestation"])

    def test_s1_54_real_bad_reviewer_signature_rejected(self):
        file = self.case.reviewer_sig
        file.write_bytes(file.read_bytes().replace(b"BEGIN", b"FAKED", 1))
        with self.assertRaises(full.EndToEndReviewError):
            self.review()

    def test_s1_54_real_bad_witness_signature_rejected(self):
        path = self.case.fixture.case.signature_path
        path.write_bytes(path.read_bytes().replace(b"BEGIN", b"FAKED", 1))
        with self.assertRaises(full.EndToEndReviewError):
            self.review()


if __name__ == "__main__":
    unittest.main()
