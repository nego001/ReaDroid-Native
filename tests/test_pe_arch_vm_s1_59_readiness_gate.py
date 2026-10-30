"""PE-S1.59: reviewer-pinned acceptance MUST run strict readiness first.

All tests are unit contracts. CI never runs native Arch cgroups or a VM.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_validation as validation
import pe_arch_vm_s1_58_preflight as preflight
import pe_arch_vm_evidence as evidence

COMMIT = "e" * 40
CHALLENGE = "c" * 64
GHIDRA = Path("/isolated/ghidra_12.2_PUBLIC")
ARCHIVE = Path("/isolated/ghidra_12.2.zip")
DEST = Path("/isolated/private/fresh.json")


class ReviewerPinnedMandatoryReadinessTests(unittest.TestCase):
    def setUp(self):
        self.pin = {
            "status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED",
            "expected_commit": COMMIT,
            "checked_manifest_entries": len(evidence.SOURCE_FILES),
            "worktree_status_clean": True,
            "git_authorship_or_signature_verified": False,
            "native_vm_or_kernel_verified": False,
        }
        self.readiness = {
            "status": preflight.STATUS,
            "source_commit": COMMIT,
            "source_files_rechecked": len(evidence.SOURCE_FILES),
            "reviewer_challenge_format_valid": True,
            "native_guest_preflight_locally_passed": True,
            "source_git_commit_and_clean_tree_locally_verified": True,
            "pinned_ghidra_install_locally_verified": True,
            "ghidra_release_sha256": preflight.GHIDRA_RELEASE_SHA256,
            "receipt_destination_unused_private": True,
            "any_receipt_written": False,
            "any_cgroup_scope_created": False,
            "ghidra_or_windows_binary_executed": False,
            "independent_vm_attestation": False,
            "independent_reviewer_or_hypervisor_verified": False,
            "native_seccomp_and_cgroups_execution_verified": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }

    def argv(self, *, reviewer=True, **overrides):
        argv = ["pe_arch_vm_validation.py",
                "--ghidra-home", str(GHIDRA),
                "--ghidra-archive", str(ARCHIVE),
                "--evidence-output", str(DEST),
                "--reviewer-challenge",
                overrides.get("challenge", CHALLENGE)]
        if reviewer:
            argv.extend(["--reviewer-pinned-checkout",
                         "--expected-source-commit",
                         overrides.get("commit", COMMIT)])
        return argv

    def execute(self, readiness=None, *, argv=None, pin=None):
        result = readiness if readiness is not None else self.readiness
        stdout, stderr = StringIO(), StringIO()
        with (mock.patch.object(validation.sys, "argv",
                                self.argv() if argv is None else argv),
              mock.patch.object(validation, "verify_source_checkout_pin",
                                return_value=self.pin if pin is None else pin) as git,
              mock.patch.object(preflight, "native_readiness",
                                return_value=result) as inspect,
              mock.patch.object(validation, "run_acceptance",
                                return_value={"status": "TEST_ONLY_MOCKED_NATIVE_RESULT",
                                              "windows_binary_executed": False}) as native,
              mock.patch.object(validation, "write_receipt_no_overwrite",
                                return_value={
                                    "path": str(DEST),
                                    "receipt_sha256": "a" * 64,
                                    "record_type": "LOCAL_SELF_REPORT_NOT_SIGNED"}) as receipt,
              redirect_stdout(stdout), redirect_stderr(stderr)):
            rc = validation.main()
        return rc, stdout.getvalue(), stderr.getvalue(), inspect, native, receipt, git

    def test_valid_preflight_is_mandatory_before_mocked_native_acceptance(self):
        rc, out, err, inspect, native, receipt, git = self.execute()
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        inspect.assert_called_once_with(
            GHIDRA, ARCHIVE, validation.Path(validation.__file__).resolve().parents[1],
            DEST, expected_source_commit=COMMIT, reviewer_challenge=CHALLENGE)
        native.assert_called_once_with(GHIDRA, ARCHIVE, timeout_seconds=420)
        receipt.assert_called_once()
        self.assertEqual(git.call_count, 2)
        doc = json.loads(out)
        # Existing handoff stdout contract stays unchanged.
        self.assertEqual(set(doc), {"status", "windows_binary_executed",
                                    "local_source_checkout_pin", "local_receipt"})
        self.assertNotIn("local_native_preflight", doc)

    def test_preflight_exception_blocks_native_run_and_receipt(self):
        out, err = StringIO(), StringIO()
        with (mock.patch.object(validation.sys, "argv", self.argv()),
              mock.patch.object(validation, "verify_source_checkout_pin",
                                return_value=self.pin),
              mock.patch.object(preflight, "native_readiness",
                                side_effect=preflight.NativePreflightError(
                                    "not a native VM")) as inspect,
              mock.patch.object(validation, "run_acceptance") as native,
              mock.patch.object(validation, "write_receipt_no_overwrite") as receipt,
              redirect_stdout(out), redirect_stderr(err)):
            self.assertEqual(validation.main(), 2)
        inspect.assert_called_once()
        native.assert_not_called()
        receipt.assert_not_called()
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(json.loads(err.getvalue())["status"],
                         "REJECTED_NOT_HOMOLOGATED")

    def test_unsigned_or_incomplete_preflight_claims_cannot_continue(self):
        edits = (
            ("native_guest_preflight_locally_passed", False),
            ("pinned_ghidra_install_locally_verified", False),
            ("source_git_commit_and_clean_tree_locally_verified", False),
            ("reviewer_challenge_format_valid", False),
            ("receipt_destination_unused_private", False),
            ("any_cgroup_scope_created", True),
            ("any_receipt_written", True),
            ("ghidra_or_windows_binary_executed", True),
            ("independent_vm_attestation", True),
            ("independent_reviewer_or_hypervisor_verified", True),
            ("native_seccomp_and_cgroups_execution_verified", True),
            ("unknown_windows_pe_execution_authorized", True),
            ("apk_or_ota_publication_authorized", True),
        )
        for field, value in edits:
            with self.subTest(field=field):
                bad = {**self.readiness, field: value}
                rc, out, err, _, native, receipt, _ = self.execute(bad)
                self.assertEqual(rc, 2)
                self.assertEqual(out, "")
                self.assertIn("REJECTED_NOT_HOMOLOGATED", err)
                native.assert_not_called()
                receipt.assert_not_called()

    def test_external_git_pin_mismatch_in_preflight_refused(self):
        bad = {**self.readiness, "source_commit": "f" * 40}
        rc, _, _, _, native, receipt, _ = self.execute(bad)
        self.assertEqual(rc, 2)
        native.assert_not_called()
        receipt.assert_not_called()

    def test_wrong_ghidra_integrity_pin_refused(self):
        bad = {**self.readiness, "ghidra_release_sha256": "f" * 64}
        rc, _, _, _, native, receipt, _ = self.execute(bad)
        self.assertEqual(rc, 2)
        native.assert_not_called()
        receipt.assert_not_called()

    def test_manifest_count_bool_or_wrong_refused(self):
        for value in (True, 0, len(evidence.SOURCE_FILES) - 1):
            with self.subTest(value=value):
                bad = {**self.readiness, "source_files_rechecked": value}
                rc, _, _, _, native, _, _ = self.execute(bad)
                self.assertEqual(rc, 2)
                native.assert_not_called()

    def test_missing_or_extra_preflight_claim_refused(self):
        missing = dict(self.readiness)
        missing.pop("pinned_ghidra_install_locally_verified")
        extra = {**self.readiness, "independent_vm_homologated": True}
        for bad in (missing, extra):
            with self.subTest(fields=set(bad)):
                rc, _, _, _, native, receipt, _ = self.execute(bad)
                self.assertEqual(rc, 2)
                native.assert_not_called()
                receipt.assert_not_called()

    def test_invalid_result_type_refused(self):
        for malformed in (None, False, [], "", "READY"):
            with self.subTest(malformed=malformed):
                rc, _, _, _, native, receipt, _ = self.execute(malformed if malformed is not None else {})
                self.assertEqual(rc, 2)
                native.assert_not_called()
                receipt.assert_not_called()

    def test_invalid_external_challenge_refused_before_preflight_and_native(self):
        rc, out, _, inspect, native, receipt, _ = self.execute(
            argv=self.argv(challenge="0" * 64))
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        inspect.assert_not_called()
        native.assert_not_called()
        receipt.assert_not_called()

    def test_invalid_source_git_pin_refused_before_preflight_and_native(self):
        with (mock.patch.object(validation.sys, "argv", self.argv()),
              mock.patch.object(validation, "verify_source_checkout_pin",
                                side_effect=validation.CheckoutPinError("dirty")) as git,
              mock.patch.object(preflight, "native_readiness") as inspect,
              mock.patch.object(validation, "run_acceptance") as native,
              mock.patch.object(validation, "write_receipt_no_overwrite") as receipt,
              redirect_stdout(StringIO()), redirect_stderr(StringIO())):
            self.assertEqual(validation.main(), 2)
        git.assert_called_once()
        inspect.assert_not_called()
        native.assert_not_called()
        receipt.assert_not_called()

    def test_pinned_workload_refuses_without_new_private_receipt(self):
        argv = ["pe_arch_vm_validation.py",
                "--ghidra-home", str(GHIDRA),
                "--ghidra-archive", str(ARCHIVE),
                "--reviewer-pinned-checkout",
                "--expected-source-commit", COMMIT,
                "--reviewer-challenge", CHALLENGE]
        rc, out, _, inspect, native, receipt, _ = self.execute(argv=argv)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        inspect.assert_not_called()
        native.assert_not_called()
        receipt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
