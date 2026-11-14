"""PE-S1.53: full custody+structured guest observations, never VM proof."""
from __future__ import annotations

from contextlib import redirect_stderr
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_observation_review as correlate
import pe_arch_vm_handoff_review as handoff
from test_pe_arch_vm_custody_review import CustodyPackageTests, COMMIT


class ObservationCustodyCorrelationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = CustodyPackageTests(
            "test_s1_48_complete_custody_package_correlates_without_vm_attestation")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.folder = self.fixture.folder
        self.source = self.fixture.case.fixture.root
        self.stamp = "2026-10-30T04:00:00+00:00"
        self.common = {
            "classification":
                "OPERATOR_SELF_REPORTED_NATIVE_ARCH_OBSERVATION_NOT_ATTESTED",
            "source_commit": COMMIT,
            "reviewer_challenge": self.fixture.case.fixture.challenge,
            "operator_observed_at_utc_not_attested": self.stamp,
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
        self.cgroup = {
            **self.common,
            "artifact": "guest_cgroup_observation",
            "cgroup_v2_controllers_available": ["cpu", "io", "memory", "pids"],
            "cgroup_v2_root_subtree_control": ["cpu", "memory", "pids"],
            "systemd_user_control_group_locally_observed":
                "/user.slice/user-1000.slice/user@1000.service",
            "cgroup_quotas_verified_by_this_command": False,
            "cgroup_descendant_cleanup_verified_by_this_command": False,
        }
        self.write_observations()

    def write_observations(self):
        for label, record in (
                ("guest_kernel_observation", self.kernel),
                ("guest_cgroup_observation", self.cgroup)):
            dest = self.folder / self.fixture.index["artifacts"][label]["filename"]
            body = (json.dumps(record, sort_keys=True, separators=(",", ":"))
                    + "\n").encode("utf-8")
            dest.write_bytes(body)
            dest.chmod(0o600)
            self.fixture.index["artifacts"][label]["sha256"] = (
                hashlib.sha256(body).hexdigest())
        self.fixture.write_index()

    def verify(self, *, pin_git=True, **overrides):
        kwargs = {
            "expected_custody_sha256": self.fixture.index_sha256,
            "expected_source_commit": COMMIT,
            "expected_challenge": self.fixture.case.fixture.challenge,
        }
        kwargs.update(overrides)
        if pin_git:
            with mock.patch.object(
                    handoff, "verify_source_checkout_pin",
                    return_value=self.fixture.case.pin) as git:
                result = correlate.verify_observation_custody(
                    self.folder, self.source, **kwargs)
            self.assertEqual(git.call_count, 2)
        else:
            result = correlate.verify_observation_custody(
                self.folder, self.source, **kwargs)
        return result

    def test_s1_53_coherent_full_receipt_custody_and_batch_is_not_vm_proof(self):
        result = self.verify()
        self.assertEqual(result["status"], correlate.STATUS)
        self.assertEqual(result["source_files_rechecked"], 1)
        self.assertTrue(result["operator_batch_timestamp_matches"])
        self.assertTrue(result["cgroup_controller_claims_structurally_consistent"])
        self.assertTrue(result["observation_pins_and_structure_correlated"])
        self.assertFalse(result["operator_logs_authenticated"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["native_kernel_execution_independently_verified"])

    def test_s1_53_rejects_unpinned_modified_observation(self):
        path = self.folder / "guest-kernel-observation.txt"
        path.write_bytes(path.read_bytes() + b"tampered\n")
        with self.assertRaisesRegex(
                correlate.ObservationReviewError, "digest"):
            self.verify()

    def test_s1_53_wrong_external_index_pin_rejected(self):
        with mock.patch.object(
                correlate.custody, "verify_custody_index") as downstream:
            with self.assertRaisesRegex(
                    correlate.ObservationReviewError, "index hash"):
                self.verify(
                    pin_git=False, expected_custody_sha256="f" * 64)
        downstream.assert_not_called()

    def test_s1_53_replayed_other_batch_time_rejected_after_new_index(self):
        self.cgroup["operator_observed_at_utc_not_attested"] = (
            "2026-10-29T04:00:00+00:00")
        self.write_observations()
        with self.assertRaisesRegex(
                correlate.ObservationReviewError, "same local batch"):
            self.verify()

    def test_s1_53_wrong_commit_in_log_rejected_even_when_index_rehashed(self):
        self.kernel["source_commit"] = "b" * 40
        self.write_observations()
        with self.assertRaisesRegex(
                correlate.ObservationReviewError, "conflicting pins"):
            self.verify()

    def test_s1_53_wrong_reviewer_challenge_in_log_rejected(self):
        self.cgroup["reviewer_challenge"] = "f" * 64
        self.write_observations()
        with self.assertRaisesRegex(
                correlate.ObservationReviewError, "conflicting pins"):
            self.verify()

    def test_s1_53_forged_attestation_flag_refused_even_with_new_hash(self):
        self.kernel["independent_vm_attestation"] = True
        self.write_observations()
        with self.assertRaisesRegex(
                correlate.ObservationReviewError, "unsupported security claims"):
            self.verify()

    def test_s1_53_rejects_fake_cgroup_quota_enforcement_claim(self):
        self.cgroup["cgroup_quotas_verified_by_this_command"] = True
        self.write_observations()
        with self.assertRaisesRegex(
                correlate.ObservationReviewError, "enforcement claim"):
            self.verify()

    def test_s1_53_cgroup_enabled_not_available_rejected(self):
        self.cgroup["cgroup_v2_root_subtree_control"] = ["cpu", "memory", "pids", "rdma"]
        self.write_observations()
        with self.assertRaisesRegex(
                correlate.ObservationReviewError, "not among available"):
            self.verify()

    def test_s1_53_unsorted_controllers_rejected(self):
        self.cgroup["cgroup_v2_controllers_available"] = [
            "memory", "cpu", "pids", "io"]
        self.write_observations()
        with self.assertRaisesRegex(
                correlate.ObservationReviewError, "duplicate cgroup"):
            self.verify()

    def test_s1_53_empty_subtree_control_remains_valid(self):
        self.cgroup["cgroup_v2_root_subtree_control"] = []
        self.write_observations()
        self.assertEqual(self.verify()["status"], correlate.STATUS)

    def test_s1_53_rejects_duplicate_json_keys_even_with_rehashed_index(self):
        path = self.folder / "guest-kernel-observation.txt"
        body = b'{"artifact":"first","artifact":"second"}\n'
        path.write_bytes(body)
        self.fixture.index["artifacts"]["guest_kernel_observation"]["sha256"] = (
            hashlib.sha256(body).hexdigest())
        self.fixture.write_index()
        with self.assertRaises(correlate.ObservationReviewError):
            self.verify()

    def test_s1_53_opaque_legacy_guest_logs_rejected_by_strict_layer(self):
        (self.folder / "guest-kernel-observation.txt").write_bytes(
            b"opaque guest uname, still valid for legacy custody\n")
        self.fixture.index["artifacts"]["guest_kernel_observation"]["sha256"] = (
            hashlib.sha256((self.folder /
                "guest-kernel-observation.txt").read_bytes()).hexdigest())
        self.fixture.write_index()
        with self.assertRaisesRegex(
                correlate.ObservationReviewError, "Malformed"):
            self.verify()
        # PE-S1.48 remains backward-compatible with opaque logs.
        with mock.patch.object(
                handoff, "verify_source_checkout_pin",
                return_value=self.fixture.case.pin):
            self.assertEqual(self.fixture.review()["status"],
                             "LOCAL_CUSTODY_PACKAGE_CORRELATED")

    def test_s1_53_changed_log_during_downstream_review_rejected(self):
        original = correlate.custody.verify_custody_index
        def after_full(*args, **kwargs):
            result = original(*args, **kwargs)
            path = self.folder / "guest-kernel-observation.txt"
            path.write_bytes(path.read_bytes() + b"late\n")
            return result
        with mock.patch.object(
                correlate.custody, "verify_custody_index",
                side_effect=after_full):
            with self.assertRaisesRegex(
                    correlate.ObservationReviewError, "changed during"):
                self.verify()

    def test_s1_53_malformed_timestamp_refused(self):
        self.cgroup["operator_observed_at_utc_not_attested"] = "not-a-timestamp"
        self.write_observations()
        with self.assertRaisesRegex(
                correlate.ObservationReviewError, "timestamp malformed"):
            self.verify()

    def test_s1_53_unrecognized_field_rejected_without_guest_execution(self):
        self.kernel["external_tpm_attested"] = True
        self.write_observations()
        with mock.patch.object(
                correlate.custody, "verify_custody_index") as full_review:
            with self.assertRaisesRegex(
                    correlate.ObservationReviewError, "unexpected"):
                self.verify()
        full_review.assert_not_called()

    def test_s1_53_cli_missing_cgroup_observation_refuses(self):
        (self.folder / "guest-cgroup-observation.txt").unlink()
        stderr = StringIO()
        with redirect_stderr(stderr):
            rc = correlate.main([
                "--private-dir", str(self.folder),
                "--source-root", str(self.source),
                "--expected-custody-sha256", self.fixture.index_sha256,
                "--expected-source-commit", COMMIT,
                "--expected-challenge", self.fixture.case.fixture.challenge,
            ])
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(stderr.getvalue())["status"],
                         "REJECTED_GUEST_OBSERVATION_CUSTODY")


if __name__ == "__main__":
    unittest.main()
