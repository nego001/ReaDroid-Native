#!/usr/bin/env python3
"""PE-S1.57: prevent signed synthetic/local evidence becoming a VM release.

The signed PE-S1.54 result is an offline, locally correlated review, not an
independent observation of a real kernel. This gate intentionally NEVER grants
VM attestation or permission to execute unknown Windows binaries. A valid
pinned signed review yields a structured HOLD with exit status 2; invalid
results are rejected. The real native Arch test still requires a separately
controlled VM, trusted reviewer and out-of-band verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_end_to_end_review as complete
import pe_arch_vm_evidence as evidence
import pe_arch_vm_receipt_verify as receipts

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
REVIEW_FIELDS = frozenset({
    "status", "source_commit", "custody_index_sha256",
    "policy_revision", "reviewer_id", "witness_id",
    "source_files_rechecked", "readonly_source_view_verified",
    "structured_guest_logs_consistent_with_custody",
    "separate_reviewer_and_witness_signatures_verified",
    "operator_claimed_chronology_consistent",
    "operator_clock_independently_verified",
    "witness_identity_independently_verified",
    "operator_logs_authenticated", "independent_vm_attestation",
    "native_kernel_execution_independently_verified",
    "host_or_git_authenticity_verified",
    "windows_binary_executed_by_reviewer",
})
TRUE_FIELDS = frozenset({
    "readonly_source_view_verified",
    "structured_guest_logs_consistent_with_custody",
    "separate_reviewer_and_witness_signatures_verified",
    "operator_claimed_chronology_consistent",
})
FALSE_FIELDS = frozenset({
    "operator_clock_independently_verified",
    "witness_identity_independently_verified",
    "operator_logs_authenticated", "independent_vm_attestation",
    "native_kernel_execution_independently_verified",
    "host_or_git_authenticity_verified",
    "windows_binary_executed_by_reviewer",
})
MISSING = (
    "independent_reviewer_control_of_native_arch_vm",
    "out_of_band_vm_and_kernel_provenance",
    "independently_witnessed_seccomp_and_cgroup_runtime",
    "independently_witnessed_scope_and_descendant_cleanup",
    "trusted_signer_identity_and_review_timestamps",
)
STATUS = "HOLD_PE_S1_57_INDEPENDENT_ARCH_VM_PROOF_MISSING"


class ReleaseGuardError(RuntimeError):
    """A candidate review is not even a valid pinned local signed package."""


def evaluate_signed_review(review_file: Path, *,
                           expected_review_sha256: str,
                           expected_source_commit: str,
                           expected_custody_sha256: str,
                           expected_policy_revision: int,
                           expected_reviewer_id: str,
                           expected_witness_id: str) -> dict:
    """Validate a pinned LOCAL review, then refuse promotion to VM proof.

    The pin must be held by an external reviewer before this verification;
    it is an integrity reference, not an independently trusted signature.
    """
    for field, value in (
            ("review", expected_review_sha256),
            ("custody", expected_custody_sha256)):
        if not isinstance(value, str) or HEX64.fullmatch(value) is None:
            raise ReleaseGuardError("External lowercase SHA256 pin required: " + field)
    if (not isinstance(expected_source_commit, str)
            or COMMIT.fullmatch(expected_source_commit) is None
            or type(expected_policy_revision) is not int
            or not 1 <= expected_policy_revision <= 1000000000
            or not isinstance(expected_reviewer_id, str)
            or not isinstance(expected_witness_id, str)
            or not expected_reviewer_id or not expected_witness_id
            or expected_reviewer_id == expected_witness_id):
        raise ReleaseGuardError("Invalid external commit, policy or distinct identities")
    try:
        raw = receipts._read_private_receipt(Path(review_file))
        if len(raw) > 16384 or hashlib.sha256(raw).hexdigest() != expected_review_sha256:
            raise ReleaseGuardError("Local review differs from externally retained pin")
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=receipts._no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ReleaseGuardError("Non-finite review value")))
        if not isinstance(document, dict) or set(document) != REVIEW_FIELDS:
            raise ReleaseGuardError("Unsupported or incomplete signed review schema")
        if (document["status"] != complete.STATUS
                or document["source_commit"] != expected_source_commit
                or document["custody_index_sha256"] != expected_custody_sha256
                or type(document["policy_revision"]) is not int
                or document["policy_revision"] != expected_policy_revision
                or document["reviewer_id"] != expected_reviewer_id
                or document["witness_id"] != expected_witness_id
                or type(document["source_files_rechecked"]) is not int
                or document["source_files_rechecked"] != len(evidence.SOURCE_FILES)
                or any(document[key] is not True for key in TRUE_FIELDS)
                or any(document[key] is not False for key in FALSE_FIELDS)):
            raise ReleaseGuardError("Signed local review contradicts external pins or claims")
        # Re-read the owner-only, single-link file. This is not an atomic
        # snapshot, but catches persistent changes across this decision.
        if receipts._read_private_receipt(Path(review_file)) != raw:
            raise ReleaseGuardError("Signed local review changed while being checked")
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError,
            OverflowError, receipts.ReceiptReviewError) as exc:
        raise ReleaseGuardError("Signed local review unreadable or unsafe") from exc

    return {
        "status": STATUS,
        "local_signed_review_pin_matched": True,
        "source_commit": expected_source_commit,
        "custody_index_sha256": expected_custody_sha256,
        "reviewer_id": expected_reviewer_id,
        "witness_id": expected_witness_id,
        "native_arch_vm_independently_verified": False,
        "seccomp_and_cgroups_independently_verified": False,
        "independent_vm_attestation": False,
        "host_or_git_authenticity_verified": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
        "required_external_evidence": MISSING,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Validate signed local review and HOLD native VM release; no attestation")
    ap.add_argument("--review-result", required=True, type=Path)
    ap.add_argument("--expected-review-sha256", required=True)
    ap.add_argument("--expected-source-commit", required=True)
    ap.add_argument("--expected-custody-sha256", required=True)
    ap.add_argument("--expected-policy-revision", required=True, type=int)
    ap.add_argument("--expected-reviewer-id", required=True)
    ap.add_argument("--expected-witness-id", required=True)
    args = ap.parse_args(argv)
    try:
        print(json.dumps(evaluate_signed_review(
            args.review_result,
            expected_review_sha256=args.expected_review_sha256,
            expected_source_commit=args.expected_source_commit,
            expected_custody_sha256=args.expected_custody_sha256,
            expected_policy_revision=args.expected_policy_revision,
            expected_reviewer_id=args.expected_reviewer_id,
            expected_witness_id=args.expected_witness_id,
        ), sort_keys=True))
    except ReleaseGuardError as exc:
        print(json.dumps({
            "status": "REJECTED_PE_S1_57_UNTRUSTED_SIGNED_REVIEW",
            "reason": str(exc),
            "independent_vm_attestation": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
    # There is no success/authorization path until a separately owned native
    # VM evidence flow and external trust roots are implemented and audited.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
