"""PE-S1.67: real synthetic receipt + full native stdout binding contracts.

No VM, cgroup, Windows binary or Ghidra executed. The complete receipt and
native report are created using S1.12's well-tested in-memory fixtures.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_67_receipt_binding as binding
import pe_arch_vm_evidence as evidence
import pe_arch_vm_receipt_verify as receipts
from test_pe_arch_vm_evidence import PrivateNativeArchReceiptTests

COMMIT = "a" * 40
CHALLENGE = "b" * 64


class FullNativeReceiptBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PrivateNativeArchReceiptTests(
            "test_s1_27_accepts_matching_inventories_with_partial_decompile")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.challenge = CHALLENGE
        self.local_write = self.fixture.write()
        self.dest = self.fixture.dest
        self.root = self.fixture.root
        self.stdout = {
            **copy.deepcopy(self.fixture.report),
            "local_receipt": {
                "path": str(self.dest),
                "receipt_sha256": self.local_write["receipt_sha256"],
                "record_type": "LOCAL_SELF_REPORT_NOT_SIGNED",
            },
            "local_source_checkout_pin": {
                "status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED",
                "expected_commit": COMMIT,
                "checked_manifest_entries": len(evidence.SOURCE_FILES),
                "worktree_status_clean": True,
                "git_authorship_or_signature_verified": False,
                "native_vm_or_kernel_verified": False,
            },
        }

    def check(self, stdout=None, *, digest=None):
        return binding.verify_launcher_binding(
            self.stdout if stdout is None else stdout,
            self.dest, self.root, expected_challenge=CHALLENGE,
            expected_source_commit=COMMIT,
            expected_receipt_sha256=(
                self.local_write["receipt_sha256"] if digest is None else digest))

    def rewrite_receipt(self, change):
        record = json.loads(self.dest.read_text("utf-8"))
        change(record)
        data = evidence._canonical(record)
        self.dest.write_bytes(data)
        self.dest.chmod(0o600)
        self.stdout["local_receipt"]["receipt_sha256"] = (
            hashlib.sha256(data).hexdigest())
        return self.stdout["local_receipt"]["receipt_sha256"]

    def test_full_synthetic_native_report_and_all_sources_pass_but_hold(self):
        result = self.check()
        self.assertEqual(
            result["status"],
            "LOCAL_PE_S1_67_STRICT_RECEIPT_BINDING_NOT_VM_ATTESTATION")
        self.assertTrue(result["all_report_fields_matched"])
        self.assertTrue(result["source_manifest_revalidated"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["unknown_windows_pe_execution_authorized"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])

    def test_stdout_looks_like_a_valid_but_different_native_report_refused(self):
        altered = copy.deepcopy(self.stdout)
        altered["ghidra"]["ghidra_functions"] = 37
        altered["ghidra"]["arch_real_ghidra_with_both"][
            "ghidra_functions_discovered"] = 37
        altered["ghidra"]["arch_real_ghidra_with_both"][
            "decompiled_functions"] = 1
        # This changed native report is *valid* in isolation.
        report = {k: altered[k] for k in binding.NATIVE_REPORT_FIELDS}
        evidence.validate_native_acceptance_report(report)
        with self.assertRaisesRegex(
                binding.BindingError, "Complete stdout report differs"):
            self.check(altered)

    def test_stdout_extra_external_release_claim_refused(self):
        altered = {**self.stdout, "release_authorized": True}
        with self.assertRaises(binding.BindingError):
            self.check(altered)

    def test_stdout_missing_native_scope_data_refused(self):
        altered = copy.deepcopy(self.stdout)
        del altered["cgroup_lifecycle"]["quota_private_proof"]
        with self.assertRaises(binding.BindingError):
            self.check(altered)

    def test_stdout_seccomp_mode_zero_refused(self):
        altered = copy.deepcopy(self.stdout)
        altered["ghidra"]["arch_real_ghidra_with_both"][
            "ghidra_jvm_seccomp_evidence"]["seccomp_mode"] = 0
        with self.assertRaises(binding.BindingError):
            self.check(altered)

    def test_stdout_source_commit_wrapper_false_identity_refused(self):
        altered = copy.deepcopy(self.stdout)
        altered["local_source_checkout_pin"]["expected_commit"] = "e" * 40
        with self.assertRaises(binding.BindingError):
            self.check(altered)

    def test_stdout_false_external_git_authorship_refused(self):
        altered = copy.deepcopy(self.stdout)
        altered["local_source_checkout_pin"][
            "git_authorship_or_signature_verified"] = True
        with self.assertRaises(binding.BindingError):
            self.check(altered)

    def test_receipt_source_hash_mismatch_is_not_hidden_by_matching_outer_sha(self):
        new_hash = self.rewrite_receipt(
            lambda record: record["source_file_hashes"][
                "tools/synthetic.py"].update({"sha256": "f" * 64}))
        with self.assertRaises(binding.BindingError):
            self.check(digest=new_hash)

    def test_receipt_report_rehashed_to_altered_claim_refused(self):
        def mutate(record):
            report = record["native_acceptance_report"]
            report["environment"]["container"] = True
            record["report_sha256"] = hashlib.sha256(
                evidence._canonical(report)).hexdigest()
        sha = self.rewrite_receipt(mutate)
        with self.assertRaises(binding.BindingError):
            self.check(digest=sha)

    def test_duplicate_key_receipt_refused_even_when_hash_repinned(self):
        raw = self.dest.read_bytes().decode("utf-8")
        self.assertIn('"schema":', raw)
        raw = raw.replace('"schema":', '"schema":"forged","schema":', 1)
        data = raw.encode("utf-8")
        self.dest.write_bytes(data)
        self.stdout["local_receipt"]["receipt_sha256"] = (
            hashlib.sha256(data).hexdigest())
        with self.assertRaises(binding.BindingError):
            self.check(digest=self.stdout["local_receipt"]["receipt_sha256"])

    def test_file_mutated_after_receipt_publication_refused(self):
        self.fixture.source.write_text("changed source\n", encoding="utf-8")
        with self.assertRaises(binding.BindingError):
            self.check()

    def test_source_file_missing_after_receipt_publication_refused(self):
        self.fixture.source.unlink()
        with self.assertRaises(binding.BindingError):
            self.check()

    def test_source_file_symlink_after_receipt_publication_refused(self):
        alias = self.fixture.source.with_name("synthetic-new.py")
        self.fixture.source.rename(alias)
        self.fixture.source.symlink_to(alias)
        with self.assertRaises(binding.BindingError):
            self.check()

    def test_false_external_receipt_pin_is_refused(self):
        with self.assertRaises(binding.BindingError):
            self.check(digest="f" * 64)

    def test_verifier_forged_independent_vm_claim_rejected(self):
        authentic = receipts.verify_local_receipt(
            self.dest, self.root, expected_challenge=CHALLENGE,
            expected_receipt_sha256=self.local_write["receipt_sha256"])
        with mock.patch.object(
                binding.receipts, "verify_local_receipt",
                return_value={**authentic,
                              "independent_vm_attestation": True}):
            with self.assertRaises(binding.BindingError):
                self.check()

    def test_receipt_changed_during_full_source_review_rejected(self):
        original = receipts.verify_local_receipt
        def mutate_after_check(*args, **kwargs):
            result = original(*args, **kwargs)
            self.dest.write_bytes(self.dest.read_bytes() + b"APPENDED")
            return result
        with mock.patch.object(
                binding.receipts, "verify_local_receipt",
                side_effect=mutate_after_check):
            with self.assertRaisesRegex(
                    binding.BindingError, "changed during full cross-check"):
                self.check()


if __name__ == "__main__":
    unittest.main()
