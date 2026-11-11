"""PE-S2.23 explicit external reviewer handoff HOLD; no fake approval path.

S2.22 fixture uses REAL disposable Ed25519 V1/V2/V3 signatures.
libvirt remains MOCKED and local receipt/Git are mocked in these unit tests.
"""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import hashlib
from io import StringIO
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s2_23_external_gap_register as gap
import pe_arch_vm_s2_22_external_reviewer_pins as pins
import pe_arch_vm_s2_19_reviewer_session_handoff as handoff
from test_pe_arch_vm_s2_22_external_reviewer_pins import ReviewerHeldPinsContracts


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH needed")
class ExternalGapRegisterContracts(unittest.TestCase):
    def setUp(self):
        older = ReviewerHeldPinsContracts(
            "test_real_three_signatures_with_external_pin_bundle_still_hold")
        older.setUp()
        self.addCleanup(older.doCleanups)
        self.o = older

    def args(self):
        return dict(
            pin_file=self.o.file, observer_dir=self.o.f.observer,
            custody_dir=self.o.f.custody, native_receipt=self.o.f.receipt,
            source_root=self.o.f.checkout,
            expected_pin_bundle_sha256=self.o.expected,
        )

    def real_signatures(self):
        # Only the guest-local native receipt and checkout validators are
        # mocked because the fixed unit fixture uses synthetic local bytes.
        with (
            mock.patch.object(
                handoff.receipt, "verify_local_receipt",
                return_value=self.o.f.local_result()),
            mock.patch.object(
                handoff.checkout, "verify_source_checkout_pin",
                return_value=self.o.f.git_result()),
        ):
            return gap.audit_external_review(**self.args())

    def test_valid_real_three_signatures_still_all_external_proofs_missing(self):
        response = self.real_signatures()
        self.assertEqual(response["status"], gap.PENDING)
        self.assertEqual(set(response), gap.FIELDS)
        self.assertTrue(response["local_signed_package_correlated"])
        self.assertEqual(response["external_evidence_requirement_count"], 7)
        self.assertEqual(
            [x["requirement_id"] for x in response["external_evidence"]],
            list(pins.UNPROVEN))
        self.assertTrue(all(
            x["state"] == gap.MISSING
            and x["owner"] == "independent_human_reviewer"
            and bool(x["needed_proof"])
            for x in response["external_evidence"]))
        self.assertFalse(response["independent_vm_attestation"])
        self.assertFalse(response["release_authorized"])
        self.assertFalse(response["apk_or_ota_publication_authorized"])

    def test_default_plan_has_no_file_or_signature_access(self):
        argv = ["--pin-file", str(self.o.file),
                "--observer-dir", str(self.o.f.observer),
                "--custody-dir", str(self.o.f.custody),
                "--native-receipt", str(self.o.f.receipt),
                "--source-root", str(self.o.f.checkout),
                "--expected-pin-bundle-sha256", self.o.expected]
        out=StringIO()
        with (mock.patch.object(gap.pins, "review_custody") as signed,
              redirect_stdout(out)):
            rc=gap.main(argv)
        self.assertEqual(rc,0)
        signed.assert_not_called()
        response=json.loads(out.getvalue())
        self.assertEqual(response["status"],gap.PLAN)
        self.assertFalse(response["local_signed_package_correlated"])
        self.assertEqual(response["external_evidence_requirement_count"],7)

    def test_broken_external_sha_refused(self):
        args=self.args()
        args["expected_pin_bundle_sha256"]="f"*64
        with self.assertRaises(gap.ExternalGapError):
            gap.audit_external_review(**args)

    def test_tampered_v3_detached_signature_refused(self):
        self.o.f.f.sig.write_bytes(b"malformed-test-signature\n")
        self.o.f.f.sig.chmod(0o600)
        with (mock.patch.object(handoff.receipt, "verify_local_receipt",
                                return_value=self.o.f.local_result()),
              mock.patch.object(handoff.checkout, "verify_source_checkout_pin",
                                return_value=self.o.f.git_result()),
              self.assertRaises(gap.ExternalGapError)):
            gap.audit_external_review(**self.args())

    def test_missing_reviewer_bundle_refused(self):
        self.o.file.unlink()
        with self.assertRaises(gap.ExternalGapError):
            gap.audit_external_review(**self.args())

    def test_spoofed_success_is_rejected(self):
        wrong = (
            {"release_authorized": True},
            {"independent_vm_attestation": True},
            {"reviewer_identity_independently_attested": True},
            {"hypervisor_independence_attested": True},
            {"native_vm_kernel_attested": True},
            {"apk_or_ota_publication_authorized": True},
            {"unknown_windows_pe_execution_authorized": True},
            {"status": "RELEASE_APPROVED"},
            {"unverified_independent_requirements": []},
            {"readonly_native_receipt_and_git_locally_verified": False},
            {"canonical_out_of_band_pin_bundle_sha256_matched": False},
            {"v1_v2_v3_detached_signatures_locally_verified": False},
        )
        good={
            "status": pins.VERIFIED,
            "canonical_out_of_band_pin_bundle_sha256_matched": True,
            "reviewer_pins_private_directory_disjoint": True,
            "v1_v2_v3_detached_signatures_locally_verified": True,
            "readonly_native_receipt_and_git_locally_verified": True,
            "unverified_independent_requirements": list(pins.UNPROVEN),
            "reviewer_identity_independently_attested": False,
            "hypervisor_independence_attested": False,
            "native_vm_kernel_attested": False,
            "independent_vm_attestation": False,
            "release_authorized": False,
            "apk_or_ota_publication_authorized": False,
            "unknown_windows_pe_execution_authorized": False,
        }
        for bad in wrong:
            with self.subTest(changed=bad):
                with (mock.patch.object(
                        gap.pins, "review_custody",
                        return_value={**good, **bad}),
                      self.assertRaises(gap.ExternalGapError)):
                    gap.audit_external_review(**self.args())

    def test_success_cli_always_returns_hold_code_two(self):
        out=StringIO()
        argv = ["--pin-file", str(self.o.file),
                "--observer-dir", str(self.o.f.observer),
                "--custody-dir", str(self.o.f.custody),
                "--native-receipt", str(self.o.f.receipt),
                "--source-root", str(self.o.f.checkout),
                "--expected-pin-bundle-sha256", self.o.expected,
                "--inspect-existing"]
        with (mock.patch.object(handoff.receipt,"verify_local_receipt",
                                return_value=self.o.f.local_result()),
              mock.patch.object(handoff.checkout,"verify_source_checkout_pin",
                                return_value=self.o.f.git_result()),
              redirect_stdout(out)):
            rc=gap.main(argv)
        self.assertEqual(rc,2)
        self.assertEqual(json.loads(out.getvalue())["status"],gap.PENDING)

    def test_invalid_cli_package_reports_rejected_without_release(self):
        argv=["--pin-file",str(self.o.file),
              "--observer-dir",str(self.o.f.observer),
              "--custody-dir",str(self.o.f.custody),
              "--native-receipt",str(self.o.f.receipt),
              "--source-root",str(self.o.f.checkout),
              "--expected-pin-bundle-sha256","b"*64,
              "--inspect-existing"]
        out,err=StringIO(),StringIO()
        with redirect_stdout(out),redirect_stderr(err):
            rc=gap.main(argv)
        self.assertEqual(rc,2)
        self.assertFalse(out.getvalue())
        obj=json.loads(err.getvalue())
        self.assertEqual(obj["status"],gap.REJECTED)
        self.assertFalse(obj["release_authorized"])
        self.assertFalse(obj["independent_vm_attestation"])
        self.assertEqual(len(obj["external_evidence"]),7)

    def test_no_automatic_external_proof_approval_flag_exists(self):
        self.assertNotIn("approve",gap.FIELDS)
        self.assertEqual(tuple(x[0] for x in gap.REVIEW),pins.UNPROVEN)
        for x in gap._missing_proofs():
            self.assertEqual(set(x),{
                "requirement_id", "state", "owner", "needed_proof"})
        for status in (gap.PLAN,gap.PENDING,gap.REJECTED):
            obj=gap._report(status,local=(status==gap.PENDING))
            self.assertEqual(set(obj),gap.FIELDS)
            self.assertFalse(obj["release_authorized"])
            self.assertFalse(obj["independent_vm_attestation"])
            self.assertFalse(obj["unknown_windows_pe_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
