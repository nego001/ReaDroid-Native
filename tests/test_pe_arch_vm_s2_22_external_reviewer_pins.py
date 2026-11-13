"""PE-S2.22 strict reviewer-held external pins. Real disposable V1/V2/V3 SSH keys."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s2_19_reviewer_session_handoff as handoff
import pe_arch_vm_s2_22_external_reviewer_pins as custody_pins
from test_pe_arch_vm_s2_19_reviewer_session_handoff import (
    JointSessionHandoffContracts)


@unittest.skipUnless(shutil.which("ssh-keygen"), "Real OpenSSH required")
class ReviewerHeldPinsContracts(unittest.TestCase):
    def setUp(self):
        fixture = JointSessionHandoffContracts(
            "test_three_real_signatures_and_matching_receipt_still_hold")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f = fixture
        self.folder = fixture.f.old.f.root / "reviewer-pins"
        self.folder.mkdir(mode=0o700)
        self.file = self.folder / custody_pins.PIN_FILE_NAME
        self.pins = {**fixture.pins, **fixture.extras}
        self.put()

    def put(self, **changes):
        record = {
            "schema": custody_pins.SCHEMA,
            "security_classification": custody_pins.CLASSIFICATION,
            "pins": {**self.pins},
            "independent_vm_attestation": False,
            "release_authorized": False,
        }
        record.update(changes)
        self.file.write_bytes(custody_pins._canonical(record))
        self.file.chmod(0o600)
        self.expected = hashlib.sha256(self.file.read_bytes()).hexdigest()

    def examine(self, *, fake_local=False, **changes):
        arguments = dict(
            pin_file=self.file, observer_dir=self.f.observer,
            custody_dir=self.f.custody, native_receipt=self.f.receipt,
            source_root=self.f.checkout,
            expected_pin_bundle_sha256=self.expected,
            **changes)
        if fake_local:
            with mock.patch.object(
                    custody_pins.handoff,
                    "verify_reviewer_session",
                    return_value=self.verified_local_result()) as called:
                result = custody_pins.review_custody(**arguments)
            return result, called
        with (
            mock.patch.object(
                handoff.receipt, "verify_local_receipt",
                return_value=self.f.local_result()) as local,
            mock.patch.object(
                handoff.checkout, "verify_source_checkout_pin",
                return_value=self.f.git_result()) as git,
        ):
            result = custody_pins.review_custody(**arguments)
        return result, (local, git)

    @staticmethod
    def verified_local_result(**change):
        return {
            "status": handoff.STATUS,
            "v1_v2_v3_detached_signatures_verified": True,
            "v3_before_after_host_sha256_pins_correlated": True,
            "native_receipt_sha256_equals_v1_signed_receipt_pin": True,
            "guest_receipt_challenge_and_sources_rechecked": True,
            "source_commit_checkout_locally_rechecked": True,
            "independent_host_control_attested": False,
            "guest_kernel_execution_independently_attested": False,
            "session_chronology_independently_verified": False,
            "journal_kernel_storage_quota_verified": False,
            "independent_vm_attestation": False,
            "release_authorized": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
            **change,
        }

    def test_real_three_signatures_with_external_pin_bundle_still_hold(self):
        report, checked = self.examine()
        self.assertEqual(report["status"], custody_pins.VERIFIED)
        self.assertTrue(report["canonical_out_of_band_pin_bundle_sha256_matched"])
        self.assertTrue(report["v1_v2_v3_detached_signatures_locally_verified"])
        self.assertFalse(report["independent_vm_attestation"])
        self.assertFalse(report["release_authorized"])
        self.assertFalse(report["reviewer_identity_independently_attested"])
        self.assertEqual(len(report["unverified_independent_requirements"]),
                         len(custody_pins.UNPROVEN))
        checked[0].assert_called_once()
        checked[1].assert_called_once()
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)

    def test_invalid_pin_sha_blocked_before_signed_review(self):
        with (mock.patch.object(custody_pins.handoff,
                                "verify_reviewer_session") as actual,
              self.assertRaises(custody_pins.ReviewerPinsError)):
            custody_pins.review_custody(
                self.file, self.f.observer, self.f.custody,
                self.f.receipt, self.f.checkout,
                expected_pin_bundle_sha256="f"*64)
        actual.assert_not_called()

    def test_missing_or_symlinked_pin_file_rejected(self):
        self.file.unlink()
        with self.assertRaises(custody_pins.ReviewerPinsError):
            self.examine(fake_local=True)
        backup = self.folder / "real-file"
        backup.write_bytes(custody_pins._canonical({
            "schema": custody_pins.SCHEMA,
            "security_classification": custody_pins.CLASSIFICATION,
            "pins": self.pins,
            "independent_vm_attestation": False,
            "release_authorized": False,
        }))
        backup.chmod(0o600)
        self.file.symlink_to(backup)
        with self.assertRaises(custody_pins.ReviewerPinsError):
            self.examine(fake_local=True)

    def test_untrusted_extra_or_missing_pin_field_rejected_even_rehashed(self):
        for field, value in (
                ("extra", 1),
                ("release_authorized", True),
                ("independent_vm_attestation", True)):
            with self.subTest(field=field):
                self.put(**{field:value})
                with self.assertRaises(custody_pins.ReviewerPinsError):
                    self.examine(fake_local=True)
        self.put()
        record=json.loads(self.file.read_bytes())
        record["pins"].pop("expected_after_sha256")
        self.file.write_bytes(custody_pins._canonical(record))
        self.expected=hashlib.sha256(self.file.read_bytes()).hexdigest()
        with self.assertRaises(custody_pins.ReviewerPinsError):
            self.examine(fake_local=True)

    def test_duplicate_json_field_rejected_even_with_matching_sha(self):
        raw=self.file.read_bytes().replace(
            b'"schema":', b'"schema":"false","schema":', 1)
        self.file.write_bytes(raw)
        self.expected=hashlib.sha256(raw).hexdigest()
        with self.assertRaises(custody_pins.ReviewerPinsError):
            self.examine(fake_local=True)

    def test_noncanonical_json_rejected_even_with_matching_sha(self):
        raw=json.dumps(json.loads(self.file.read_bytes()), indent=2).encode()
        self.file.write_bytes(raw)
        self.expected=hashlib.sha256(raw).hexdigest()
        with self.assertRaises(custody_pins.ReviewerPinsError):
            self.examine(fake_local=True)

    def test_readonly_custody_bundle_rejects_insecure_permissions(self):
        self.file.chmod(0o644)
        with self.assertRaises(custody_pins.ReviewerPinsError):
            self.examine(fake_local=True)

    def test_pin_folder_cannot_alias_observer_or_custody(self):
        self.file.unlink()
        for wrong in (self.f.observer / custody_pins.PIN_FILE_NAME,
                      self.f.custody / custody_pins.PIN_FILE_NAME):
            with self.subTest(wrong=wrong):
                with self.assertRaises(custody_pins.ReviewerPinsError):
                    custody_pins.review_custody(
                        wrong, self.f.observer, self.f.custody,
                        self.f.receipt, self.f.checkout,
                        expected_pin_bundle_sha256=self.expected)

    def test_pin_folder_inside_source_tree_refused(self):
        self.file.unlink()
        nested = self.f.checkout / "pins"
        nested.mkdir(mode=0o700)
        file=nested / custody_pins.PIN_FILE_NAME
        file.write_bytes(b"no\n")
        file.chmod(0o600)
        with self.assertRaises(custody_pins.ReviewerPinsError):
            custody_pins.review_custody(
                file, self.f.observer, self.f.custody,
                self.f.receipt, self.f.checkout,
                expected_pin_bundle_sha256=self.expected)

    def test_wrong_receipt_sha_even_if_rehashed_refused_before_chain(self):
        self.put()
        data=json.loads(self.file.read_bytes())
        data["pins"]["expected_native_receipt_sha256"] = "e"*64
        raw=custody_pins._canonical(data)
        self.file.write_bytes(raw)
        self.expected=hashlib.sha256(raw).hexdigest()
        with (mock.patch.object(custody_pins.handoff,
                                "verify_reviewer_session") as actual,
              self.assertRaises(custody_pins.ReviewerPinsError)):
            self.examine(fake_local=False)
        actual.assert_not_called()

    def test_spoofed_local_pass_result_refused(self):
        for changed in (
                {"release_authorized": True},
                {"independent_vm_attestation": True},
                {"v1_v2_v3_detached_signatures_verified": False},
                {"apk_or_ota_publication_authorized": True}):
            with self.subTest(changed=changed):
                with (mock.patch.object(
                        custody_pins.handoff, "verify_reviewer_session",
                        return_value=self.verified_local_result(**changed)),
                      self.assertRaises(custody_pins.ReviewerPinsError)):
                    custody_pins.review_custody(
                        self.file, self.f.observer, self.f.custody,
                        self.f.receipt, self.f.checkout,
                        expected_pin_bundle_sha256=self.expected)

    def test_exact_s2_19_schema_preserves_local_only_hold(self):
        expected = self.verified_local_result()
        self.assertEqual(set(expected), custody_pins.S2_19_RESULT_FIELDS)
        result, called = self.examine(fake_local=True)
        called.assert_called_once()
        self.assertEqual(result["status"], custody_pins.VERIFIED)
        self.assertEqual(len(result["unverified_independent_requirements"]), 7)
        self.assertIs(result["independent_vm_attestation"], False)
        self.assertIs(result["release_authorized"], False)

    def test_s2_19_extra_attestation_claim_always_rejected(self):
        for key, value in (
            ("external_vm_attestation_complete", True),
            ("independent_kernel_proof", False),
            ("signed_evidence_source", "operator"),
        ):
            with self.subTest(field=key):
                with (mock.patch.object(
                        custody_pins.handoff, "verify_reviewer_session",
                        return_value=self.verified_local_result(**{key: value})),
                      self.assertRaisesRegex(custody_pins.ReviewerPinsError,
                                             "grant release")):
                    self.examine(fake_local=True)

    def test_s2_19_missing_any_field_is_rejected(self):
        all_fields = self.verified_local_result()
        for absent in sorted(custody_pins.S2_19_RESULT_FIELDS):
            with self.subTest(absent=absent):
                changed = {k: v for k, v in all_fields.items() if k != absent}
                with (mock.patch.object(
                        custody_pins.handoff, "verify_reviewer_session",
                        return_value=changed),
                      self.assertRaises(custody_pins.ReviewerPinsError)):
                    self.examine(fake_local=True)

    def test_s2_19_independence_and_execution_claims_must_be_false(self):
        false_claims = (
            "independent_host_control_attested",
            "guest_kernel_execution_independently_attested",
            "session_chronology_independently_verified",
            "journal_kernel_storage_quota_verified",
            "independent_vm_attestation",
            "release_authorized",
            "unknown_windows_pe_execution_authorized",
            "apk_or_ota_publication_authorized",
        )
        for claim in false_claims:
            with self.subTest(claim=claim):
                with (mock.patch.object(
                        custody_pins.handoff, "verify_reviewer_session",
                        return_value=self.verified_local_result(**{claim: True})),
                      self.assertRaises(custody_pins.ReviewerPinsError)):
                    self.examine(fake_local=True)
        for claim in (
            "v1_v2_v3_detached_signatures_verified",
            "v3_before_after_host_sha256_pins_correlated",
            "native_receipt_sha256_equals_v1_signed_receipt_pin",
            "guest_receipt_challenge_and_sources_rechecked",
            "source_commit_checkout_locally_rechecked",
        ):
            with self.subTest(claim=claim):
                with (mock.patch.object(
                        custody_pins.handoff, "verify_reviewer_session",
                        return_value=self.verified_local_result(**{claim: 1})),
                      self.assertRaises(custody_pins.ReviewerPinsError)):
                    self.examine(fake_local=True)

    def test_replaced_bundle_during_chain_detected(self):
        def mutate(*args, **kwargs):
            record = json.loads(self.file.read_bytes())
            record["pins"]["expected_challenge"] = "e"*64
            self.file.write_bytes(custody_pins._canonical(record))
            return self.verified_local_result()
        with (mock.patch.object(
                custody_pins.handoff, "verify_reviewer_session",
                side_effect=mutate),
              self.assertRaises(custody_pins.ReviewerPinsError)):
            custody_pins.review_custody(
                self.file, self.f.observer, self.f.custody,
                self.f.receipt, self.f.checkout,
                expected_pin_bundle_sha256=self.expected)

    def test_duplicate_pins_or_nonhex_pin_refused(self):
        for change in (
                {"expected_before_sha256": "F"*64},
                {"expected_session_id": "0"*64},
                {"expected_v3_signature_sha256": "not sha"},
                {"expected_domain_uuid": "broken"}):
            with self.subTest(change=change):
                record=json.loads(self.file.read_bytes())
                record["pins"].update(change)
                raw=custody_pins._canonical(record)
                self.file.write_bytes(raw)
                self.expected=hashlib.sha256(raw).hexdigest()
                with self.assertRaises(custody_pins.ReviewerPinsError):
                    self.examine(fake_local=True)
                self.put()

    def test_cli_default_no_file_review_and_active_hold_code_two(self):
        args=[
            "--pin-file",str(self.file),
            "--observer-dir",str(self.f.observer),
            "--custody-dir",str(self.f.custody),
            "--native-receipt",str(self.f.receipt),
            "--source-root",str(self.f.checkout),
            "--expected-pin-bundle-sha256",self.expected,
        ]
        output=StringIO()
        with (redirect_stdout(output),
              mock.patch.object(custody_pins,"review_custody") as review):
            self.assertEqual(custody_pins.main(args),0)
            review.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"],custody_pins.PLAN)
        output=StringIO()
        with (redirect_stdout(output),
              mock.patch.object(custody_pins.handoff,"verify_reviewer_session",
                                return_value=self.verified_local_result())):
            self.assertEqual(custody_pins.main(args+["--review-existing"]),2)
        self.assertEqual(json.loads(output.getvalue())["status"],
                         custody_pins.VERIFIED)

    def test_custody_dir_path_symlink_rejected(self):
        alias = self.f.f.old.f.root / "alias-reviewer"
        alias.symlink_to(self.folder, target_is_directory=True)
        with self.assertRaises(custody_pins.ReviewerPinsError):
            custody_pins.review_custody(
                alias / custody_pins.PIN_FILE_NAME,
                self.f.observer,self.f.custody,self.f.receipt,self.f.checkout,
                expected_pin_bundle_sha256=self.expected)


if __name__ == "__main__":
    unittest.main()
