"""PE-S1.48 custody-package tests; synthetic self-reports only."""
from __future__ import annotations

from contextlib import redirect_stderr
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_custody_review as custody
import pe_arch_vm_handoff_review as handoff
from test_pe_arch_vm_handoff_review import ReviewerHandoffTests, COMMIT


class CustodyPackageTests(unittest.TestCase):
    def setUp(self):
        self.case = ReviewerHandoffTests(
            "test_s1_47_complete_correlated_handoff_never_attests_vm")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.folder = self.case.fixture.private
        self.operator = self.folder / custody.ARTIFACT_NAMES["operator_output"]
        self.case.operator_path.replace(self.operator)
        self.receipt = self.case.fixture.dest
        self.kernel = self.folder / custody.ARTIFACT_NAMES[
            "guest_kernel_observation"]
        self.cgroup = self.folder / custody.ARTIFACT_NAMES[
            "guest_cgroup_observation"]
        self.kernel.write_bytes(b"synthetic guest uname, NOT attested\n")
        self.cgroup.write_bytes(b"synthetic guest systemd/cgroup, NOT attested\n")
        self.kernel.chmod(0o600)
        self.cgroup.chmod(0o600)
        self.index_file = self.folder / "reviewer-custody-index.json"
        self.index = {
            "schema": custody.SCHEMA,
            "security_classification": custody.CLASSIFICATION,
            "reviewer_challenge": self.case.fixture.challenge,
            "source_commit": COMMIT,
            "artifacts": {
                label: {
                    "filename": name,
                    "sha256": hashlib.sha256(
                        (self.folder / name).read_bytes()).hexdigest(),
                }
                for label, name in custody.ARTIFACT_NAMES.items()
            },
        }
        self.write_index()

    def write_index(self, raw=None):
        if raw is None:
            raw = (json.dumps(self.index, sort_keys=True,
                              separators=(",", ":")) + "\n").encode("utf-8")
        self.index_file.write_bytes(raw)
        self.index_file.chmod(0o600)
        self.index_sha256 = hashlib.sha256(raw).hexdigest()

    def review(self, **options):
        kwargs = {
            "expected_custody_sha256": self.index_sha256,
            "expected_source_commit": COMMIT,
            "expected_challenge": self.case.fixture.challenge,
        }
        kwargs.update(options)
        with mock.patch.object(
                handoff, "verify_source_checkout_pin",
                return_value=self.case.pin) as pin:
            result = custody.verify_custody_index(
                self.folder, self.case.fixture.root, **kwargs)
        self.assertEqual(pin.call_count, 2)
        return result

    def test_s1_48_complete_custody_package_correlates_without_vm_attestation(self):
        result = self.review()
        self.assertEqual(result["status"], "LOCAL_CUSTODY_PACKAGE_CORRELATED")
        self.assertEqual(result["artifact_count"], 4)
        self.assertEqual(result["source_files_rechecked"], 1)
        self.assertFalse(result["operator_kernel_log_authenticated"])
        self.assertFalse(result["operator_cgroup_log_authenticated"])
        self.assertFalse(result["external_signature_verified"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["native_kernel_execution_independently_verified"])
        self.assertFalse(result["host_or_git_authenticity_verified"])
        self.assertEqual(result["artifact_sha256"]["receipt"],
                         self.case.receipt_sha256)

    def test_s1_48_wrong_external_index_pin_rejected_before_git(self):
        with mock.patch.object(handoff, "verify_source_checkout_pin") as git:
            with self.assertRaisesRegex(
                    custody.CustodyReviewError, "independently retained"):
                custody.verify_custody_index(
                    self.folder, self.case.fixture.root,
                    expected_custody_sha256="f" * 64,
                    expected_source_commit=COMMIT,
                    expected_challenge=self.case.fixture.challenge)
        git.assert_not_called()

    def test_s1_48_modified_kernel_log_rejected_even_though_just_a_log(self):
        self.kernel.write_bytes(b"hostile replacement of guest observation\n")
        with self.assertRaisesRegex(custody.CustodyReviewError,
                                    "pinned index"):
            self.review()

    def test_s1_48_modified_cgroup_log_rejected(self):
        self.cgroup.write_bytes(b"unexpected cgroup claims\n")
        with self.assertRaisesRegex(custody.CustodyReviewError,
                                    "pinned index"):
            self.review()

    def test_s1_48_rejects_reviewer_index_extra_attestation_claim(self):
        self.index["independent_vm_attestation"] = True
        self.write_index()
        with self.assertRaisesRegex(custody.CustodyReviewError,
                                    "schema or external pins"):
            self.review()

    def test_s1_48_rejects_missing_or_unknown_inventory_artifact(self):
        for choice in ("missing", "extra"):
            with self.subTest(choice=choice):
                original = dict(self.index["artifacts"])
                if choice == "missing":
                    del self.index["artifacts"]["guest_cgroup_observation"]
                else:
                    self.index["artifacts"]["unknown_operator_script"] = {
                        "filename": "unknown.txt", "sha256": "a" * 64}
                self.write_index()
                with self.assertRaisesRegex(custody.CustodyReviewError,
                                            "exactly four"):
                    self.review()
                self.index["artifacts"] = original

    def test_s1_48_duplicate_index_json_keys_rejected_after_repinned(self):
        self.write_index(b'{"schema":"A","schema":"B"}\n')
        with self.assertRaises(custody.CustodyReviewError):
            self.review()

    def test_s1_48_symlink_log_rejected_even_with_matching_digest(self):
        data = self.kernel.read_bytes()
        target = self.folder / "replaced-kernel.txt"
        target.write_bytes(data)
        target.chmod(0o600)
        self.kernel.unlink()
        self.kernel.symlink_to(target)
        with self.assertRaises(custody.CustodyReviewError):
            self.review()

    def test_s1_48_hardlink_and_world_readable_log_rejected(self):
        source = self.cgroup
        hardlink = self.folder / "extra-cgroup-link.txt"
        os.link(source, hardlink)
        with self.assertRaises(custody.CustodyReviewError):
            self.review()
        hardlink.unlink()
        source.chmod(0o644)
        with self.assertRaises(custody.CustodyReviewError):
            self.review()

    def test_s1_48_changed_log_during_handoff_rejected(self):
        original = handoff.verify_operator_handoff

        def modify_during_call(*args, **kwargs):
            result = original(*args, **kwargs)
            self.kernel.write_bytes(b"changed after first hash\n")
            return result

        with (mock.patch.object(handoff, "verify_source_checkout_pin",
                                return_value=self.case.pin),
              mock.patch.object(handoff, "verify_operator_handoff",
                                side_effect=modify_during_call)):
            with self.assertRaisesRegex(custody.CustodyReviewError,
                                        "changed during review"):
                custody.verify_custody_index(
                    self.folder, self.case.fixture.root,
                    expected_custody_sha256=self.index_sha256,
                    expected_source_commit=COMMIT,
                    expected_challenge=self.case.fixture.challenge)

    def test_s1_48_unsafe_external_pin_rejected_before_any_read(self):
        for field, bad in (("expected_custody_sha256", ""),
                           ("expected_source_commit", "A" * 40),
                           ("expected_challenge", "0" * 64)):
            with self.subTest(field=field):
                kwargs = {
                    "expected_custody_sha256": self.index_sha256,
                    "expected_source_commit": COMMIT,
                    "expected_challenge": self.case.fixture.challenge,
                }
                kwargs[field] = bad
                with mock.patch.object(
                        custody.receipt_review, "_read_private_receipt"
                        ) as read:
                    with self.assertRaises(custody.CustodyReviewError):
                        custody.verify_custody_index(
                            self.folder, self.case.fixture.root, **kwargs)
                read.assert_not_called()

    def test_s1_48_cli_must_reject_without_index(self):
        self.index_file.unlink()
        stderr = StringIO()
        with redirect_stderr(stderr):
            code = custody.main([
                "--private-dir", str(self.folder),
                "--source-root", str(self.case.fixture.root),
                "--expected-custody-sha256", self.index_sha256,
                "--expected-source-commit", COMMIT,
                "--expected-challenge", self.case.fixture.challenge,
            ])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["status"],
                         "REJECTED_LOCAL_CUSTODY_PACKAGE")


if __name__ == "__main__":
    unittest.main()
