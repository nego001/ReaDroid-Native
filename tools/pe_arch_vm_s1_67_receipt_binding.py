#!/usr/bin/env python3
"""PE-S1.67: bind complete S1.5 stdout to the rigorously verified local receipt.

Hashes and self-reported data are not VM attestation. This module has no
network access or guest execution; it rejects any forged PASS when stdout,
receipt, source hashes, or reviewer challenge disagree. Release ALWAYS HOLD.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pe_arch_vm_evidence as evidence
import pe_arch_vm_receipt_verify as receipts
from pe_arch_vm_checkout_pin import COMMIT_SHA

LOCAL_RECEIPT_FIELDS = frozenset({"path", "receipt_sha256", "record_type"})
SOURCE_PIN_FIELDS = frozenset({
    "status", "expected_commit", "checked_manifest_entries",
    "worktree_status_clean", "git_authorship_or_signature_verified",
    "native_vm_or_kernel_verified",
})
REVIEW_FIELDS = frozenset({
    "status", "security_classification", "source_files_rechecked",
    "report_sha256", "receipt_sha256",
    "external_receipt_sha256_pin_matched",
    "readonly_source_view_verified",
    "native_kernel_execution_independently_verified",
    "windows_binary_executed_by_reviewer",
    "reviewer_challenge_correlated",
    "independent_vm_attestation",
})


class BindingError(RuntimeError):
    """One or more local documents are contradictory or forged."""


def verify_launcher_binding(
        stdout: dict, receipt_file: Path, source_root: Path, *,
        expected_challenge: str, expected_source_commit: str,
        expected_receipt_sha256: str) -> dict:
    """Return only report hashes and always-false release claims.

    Full source review and exact report comparison reuse the S1.20
    validator. All returned flags remain local/unauthenticated.
    """
    try:
        evidence.require_reviewer_challenge(expected_challenge)
        if (not isinstance(expected_source_commit, str)
                or COMMIT_SHA.fullmatch(expected_source_commit) is None
                or expected_source_commit == "0" * 40):
            raise BindingError("Reviewer source commit pin invalid")
        if (not isinstance(expected_receipt_sha256, str)
                or receipts.HEX64.fullmatch(expected_receipt_sha256) is None):
            raise BindingError("Reviewer receipt hash invalid")
        # Accept only the known native report keys and the two supported
        # stdout metadata wrappers. No extra approval fields can piggyback.
        if (not isinstance(stdout, dict) or set(stdout) != (
                set(evidence.NATIVE_REPORT_FIELDS)
                | {"local_receipt", "local_source_checkout_pin"})):
            raise BindingError("Unexpected native stdout fields")
        receipt_info = stdout["local_receipt"]
        source_info = stdout["local_source_checkout_pin"]
        if (not isinstance(receipt_info, dict)
                or set(receipt_info) != LOCAL_RECEIPT_FIELDS
                or receipt_info["path"] != str(receipt_file)
                or receipt_info["receipt_sha256"] != expected_receipt_sha256
                or receipt_info["record_type"] != "LOCAL_SELF_REPORT_NOT_SIGNED"
                or not isinstance(source_info, dict)
                or set(source_info) != SOURCE_PIN_FIELDS
                or source_info["status"] != "LOCAL_GIT_CHECKOUT_PIN_MATCHED"
                or source_info["expected_commit"] != expected_source_commit
                or type(source_info["checked_manifest_entries"]) is not int
                or source_info["checked_manifest_entries"] !=
                    len(evidence.SOURCE_FILES)
                or source_info["worktree_status_clean"] is not True
                or source_info["git_authorship_or_signature_verified"] is not False
                or source_info["native_vm_or_kernel_verified"] is not False):
            raise BindingError("Runner receipt or source pin wrapper contradicted")
        report = {key: stdout[key] for key in evidence.NATIVE_REPORT_FIELDS}
        evidence.validate_native_acceptance_report(report)
        raw = receipts._read_private_receipt(receipt_file)
        if hashlib.sha256(raw).hexdigest() != expected_receipt_sha256:
            raise BindingError("Receipt SHA-256 changed or diverged")
        record = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=receipts._no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                BindingError("Nonfinite receipt content")))
        if not isinstance(record, dict) or set(record) != receipts.RECEIPT_FIELDS:
            raise BindingError("Receipt contains unrecognized fields")
        if (record["reviewer_challenge"] != expected_challenge
                or record["windows_executable_launched"] is not False):
            raise BindingError("Receipt challenge/Windows execution contradicted")
        # JSON canonical bytes prevent Python's True == 1 treating a
        # different typed security statement as the same object.
        if evidence._canonical(record["native_acceptance_report"]) != (
                evidence._canonical(report)):
            raise BindingError("Complete stdout report differs from signed-in receipt")
        reviewed = receipts.verify_local_receipt(
            receipt_file, source_root,
            expected_challenge=expected_challenge,
            expected_receipt_sha256=expected_receipt_sha256)
        if (not isinstance(reviewed, dict)
                or set(reviewed) != REVIEW_FIELDS
                or reviewed["status"] != "LOCAL_RECEIPT_CONSISTENCY_VALIDATED"
                or reviewed["security_classification"] !=
                    "UNSIGNED_NOT_INDEPENDENT_VM_ATTESTATION"
                or reviewed["receipt_sha256"] != expected_receipt_sha256
                or reviewed["report_sha256"] != record["report_sha256"]
                or type(reviewed["source_files_rechecked"]) is not int
                or reviewed["source_files_rechecked"] != len(evidence.SOURCE_FILES)
                or reviewed["external_receipt_sha256_pin_matched"] is not True
                or reviewed["readonly_source_view_verified"] is not False
                or reviewed["reviewer_challenge_correlated"] is not True
                or reviewed["native_kernel_execution_independently_verified"] is not False
                or reviewed["windows_binary_executed_by_reviewer"] is not False
                or reviewed["independent_vm_attestation"] is not False):
            raise BindingError("Rigorously verified receipt made unsupported claims")
        # A second read catches persistent file replacement after full
        # source verification. Not a filesystem snapshot or host attestation.
        if receipts._read_private_receipt(receipt_file) != raw:
            raise BindingError("Receipt changed during full cross-check")
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            RecursionError, OverflowError, evidence.AcceptanceReceiptError,
            receipts.ReceiptReviewError) as exc:
        raise BindingError(
            "Full native receipt and stdout correlation rejected") from exc
    return {
        "status": "LOCAL_PE_S1_67_STRICT_RECEIPT_BINDING_NOT_VM_ATTESTATION",
        "receipt_sha256": expected_receipt_sha256,
        "source_commit": expected_source_commit,
        "all_report_fields_matched": True,
        "source_manifest_revalidated": True,
        "reviewer_challenge_correlated": True,
        "independent_vm_attestation": False,
        "release_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }
