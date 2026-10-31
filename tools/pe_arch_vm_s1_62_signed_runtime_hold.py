#!/usr/bin/env python3
"""PE-S1.62: dual-signed local custody + runtime matrix, ALWAYS release HOLD.

This reviewer-side, read-only composition verifies the exact externally
pinned local PE-S1.54 dual-signature package and PE-S1.61 runtime claims on
the same request, Git commit, challenge and custody index. The signed keys
authorize custody policy, NOT attest a guest, kernel, hypervisor or execution.
Even a valid review returns HOLD (exit code 2), not release.
No Windows PE, Ghidra, cgroup, network or native VM is started.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_end_to_end_review as signed
import pe_arch_vm_s1_61_runtime_matrix as runtime
import pe_arch_vm_s1_57_release_guard as hold
import pe_arch_vm_evidence as evidence
import pe_arch_vm_receipt_verify as receipts
import pe_arch_vm_s1_60_review_request as request
import pe_arch_vm_dual_control_review as dual
import pe_arch_vm_witness_review as witness
import pe_arch_vm_witness_trust_review as trust

STATUS = "HOLD_PE_S1_62_SIGNED_LOCAL_RUNTIME_NOT_EXTERNAL_VM_ATTESTATION"
REJECTED = "REJECTED_PE_S1_62_UNTRUSTED_SIGNED_RUNTIME"
# All private bytes are rechecked after BOTH underlying full reviews.
PRIVATE_FILES = (
    "reviewer-custody-index.json", "acceptance.json",
    "operator-run-output.json",
    "guest-kernel-observation.txt", "guest-cgroup-observation.txt",
    trust.TRUST_FILENAME, dual.REVIEWER_SIGNERS, dual.REVIEWER_SIGNATURE,
    witness.FILES["statement"], witness.FILES["signature"],
    witness.FILES["allowed_signers"],
)
RUNTIME_FIELDS = frozenset({
    "status", "source_commit", "custody_index_sha256", "receipt_sha256",
    "reviewer_request_sha256", "distinct_operator_reported_scopes",
    "operator_reported_scopes_locally_unique",
    "operator_reported_scope_cleanup_locally_validated",
    "operator_reported_ghidra_seccomp_mode",
    "operator_reported_seccomp_and_cgroups_locally_correlated",
    "operator_guest_kernel_and_cgroup_logs_structurally_correlated",
    "readonly_source_view_verified", "independent_vm_attestation",
    "native_arch_kernel_independently_verified",
    "operator_logs_authenticated",
    "real_seccomp_and_cgroups_independently_witnessed",
    "scope_cleanup_independently_witnessed",
    "unknown_windows_pe_execution_authorized",
    "apk_or_ota_publication_authorized",
})
RUNTIME_TRUE = (
    "operator_reported_scopes_locally_unique",
    "operator_reported_scope_cleanup_locally_validated",
    "operator_reported_seccomp_and_cgroups_locally_correlated",
    "operator_guest_kernel_and_cgroup_logs_structurally_correlated",
)
RUNTIME_FALSE = (
    "independent_vm_attestation", "native_arch_kernel_independently_verified",
    "operator_logs_authenticated",
    "real_seccomp_and_cgroups_independently_witnessed",
    "scope_cleanup_independently_witnessed",
    "unknown_windows_pe_execution_authorized",
    "apk_or_ota_publication_authorized",
)
SIGNED_TRUE = (
    "structured_guest_logs_consistent_with_custody",
    "separate_reviewer_and_witness_signatures_verified",
    "operator_claimed_chronology_consistent",
)
SIGNED_FALSE = (
    "operator_clock_independently_verified",
    "witness_identity_independently_verified",
    "operator_logs_authenticated", "independent_vm_attestation",
    "native_kernel_execution_independently_verified",
    "host_or_git_authenticity_verified",
    "windows_binary_executed_by_reviewer",
)
PINS = (
    "expected_request_sha256", "expected_custody_sha256",
    "expected_receipt_sha256", "expected_source_commit",
    "expected_challenge", "expected_policy_sha256",
    "expected_reviewer_signers_sha256",
    "expected_reviewer_signature_sha256",
    "expected_statement_sha256", "expected_signature_sha256",
    "expected_signers_sha256",
)


class SignedRuntimeReviewError(RuntimeError):
    """Not even a complete pinned local reviewer package."""


def _check_signed(result: object, *, commit: str, custody_hash: str,
                  policy_revision: int, reviewer_id: str, witness_id: str,
                  readonly: bool) -> None:
    if (not isinstance(result, dict)
            or set(result) != hold.REVIEW_FIELDS
            or result["status"] != signed.STATUS
            or result["source_commit"] != commit
            or result["custody_index_sha256"] != custody_hash
            or type(result["policy_revision"]) is not int
            or result["policy_revision"] != policy_revision
            or result["reviewer_id"] != reviewer_id
            or result["witness_id"] != witness_id
            or type(result["source_files_rechecked"]) is not int
            or result["source_files_rechecked"] != len(evidence.SOURCE_FILES)
            or result["readonly_source_view_verified"] is not readonly
            or any(result[k] is not True for k in SIGNED_TRUE)
            or any(result[k] is not False for k in SIGNED_FALSE)):
        raise SignedRuntimeReviewError(
            "Signed custody report incomplete or falsely claims VM attestation")


def _check_runtime(result: object, *, commit: str, custody_hash: str,
                   receipt_hash: str, request_hash: str, readonly: bool) -> None:
    if (not isinstance(result, dict)
            or set(result) != RUNTIME_FIELDS
            or result["status"] != runtime.STATUS
            or result["source_commit"] != commit
            or result["custody_index_sha256"] != custody_hash
            or result["receipt_sha256"] != receipt_hash
            or result["reviewer_request_sha256"] != request_hash
            or type(result["distinct_operator_reported_scopes"]) is not int
            or result["distinct_operator_reported_scopes"] != 4
            or type(result["operator_reported_ghidra_seccomp_mode"]) is not int
            or result["operator_reported_ghidra_seccomp_mode"] != 2
            or result["readonly_source_view_verified"] is not readonly
            or any(result[k] is not True for k in RUNTIME_TRUE)
            or any(result[k] is not False for k in RUNTIME_FALSE)):
        raise SignedRuntimeReviewError(
            "Runtime report incomplete or contains unsupported security claims")


def review_signed_runtime(
        private_dir: Path, source_root: Path, reviewer_request: Path, *,
        expected_request_sha256: str, expected_custody_sha256: str,
        expected_receipt_sha256: str, expected_source_commit: str,
        expected_challenge: str, expected_policy_sha256: str,
        expected_policy_revision: int, expected_reviewer_signers_sha256: str,
        expected_reviewer_signature_sha256: str, expected_reviewer_id: str,
        expected_statement_sha256: str, expected_signature_sha256: str,
        expected_signers_sha256: str, expected_witness_id: str,
        require_readonly_source_view: bool = False) -> dict:
    """Compose independent PINNED local checks, never grant a VM release."""
    for key, val in ((key, locals()[key]) for key in PINS):
        if not isinstance(val, str) or (
            (len(val) != 40 if key == "expected_source_commit" else len(val) != 64)
        ) or any(c not in "0123456789abcdef" for c in val):
            raise SignedRuntimeReviewError("External lowercase pin missing: " + key)
    if (expected_challenge == "0" * 64
            or type(expected_policy_revision) is not int
            or not 1 <= expected_policy_revision <= 1000000000
            or type(require_readonly_source_view) is not bool
            or not isinstance(expected_reviewer_id, str)
            or not isinstance(expected_witness_id, str)
            or witness.WITNESS_ID.fullmatch(expected_reviewer_id) is None
            or witness.WITNESS_ID.fullmatch(expected_witness_id) is None
            or expected_reviewer_id == expected_witness_id):
        raise SignedRuntimeReviewError("Invalid external challenge/reviewer policy")

    root = Path(private_dir)
    if (not root.is_absolute() or root.name in ("", ".", "..")
            or any(piece in ("", ".", "..") for piece in root.parts[1:])):
        raise SignedRuntimeReviewError("Canonical private source directory required")
    # Paths are accessed only through existing nofollow, private-only readers.
    try:
        start = {
            name: receipts._read_private_receipt(root / name)
            for name in PRIVATE_FILES
        }
        request_before = request.verify_request(
            reviewer_request,
            expected_request_sha256=expected_request_sha256,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            expected_reviewer_id=expected_reviewer_id)
        signed_result = signed.verify_complete_review(
            root, source_root,
            expected_policy_sha256=expected_policy_sha256,
            expected_policy_revision=expected_policy_revision,
            expected_reviewer_signers_sha256=expected_reviewer_signers_sha256,
            expected_reviewer_signature_sha256=expected_reviewer_signature_sha256,
            expected_reviewer_id=expected_reviewer_id,
            expected_custody_sha256=expected_custody_sha256,
            expected_statement_sha256=expected_statement_sha256,
            expected_signature_sha256=expected_signature_sha256,
            expected_signers_sha256=expected_signers_sha256,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            expected_witness_id=expected_witness_id,
            require_readonly_source_view=require_readonly_source_view)
        _check_signed(
            signed_result, commit=expected_source_commit,
            custody_hash=expected_custody_sha256,
            policy_revision=expected_policy_revision,
            reviewer_id=expected_reviewer_id,
            witness_id=expected_witness_id,
            readonly=require_readonly_source_view)

        matrix = runtime.verify_runtime_claims(
            root, source_root, reviewer_request,
            expected_request_sha256=expected_request_sha256,
            expected_custody_sha256=expected_custody_sha256,
            expected_receipt_sha256=expected_receipt_sha256,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            expected_reviewer_id=expected_reviewer_id,
            require_readonly_source_view=require_readonly_source_view)
        _check_runtime(
            matrix, commit=expected_source_commit,
            custody_hash=expected_custody_sha256,
            receipt_hash=expected_receipt_sha256,
            request_hash=expected_request_sha256,
            readonly=require_readonly_source_view)
        if (signed_result["source_files_rechecked"] !=
                matrix["distinct_operator_reported_scopes"] - 4
                + len(evidence.SOURCE_FILES)):
            raise SignedRuntimeReviewError("Cross-review source count mismatch")

        # Entire pinned local evidence must remain the exact same bytes,
        # not merely the same SHA claimed by two separately-run verifiers.
        for name, before in start.items():
            if receipts._read_private_receipt(root / name) != before:
                raise SignedRuntimeReviewError(
                    "Local signed/runtime evidence changed: " + name)
        request_after = request.verify_request(
            reviewer_request,
            expected_request_sha256=expected_request_sha256,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            expected_reviewer_id=expected_reviewer_id)
        if request_before != request_after:
            raise SignedRuntimeReviewError(
                "Reviewer request changed during dual-review")
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            RecursionError, receipts.ReceiptReviewError,
            request.RequestReviewError, signed.EndToEndReviewError,
            runtime.RuntimeMatrixError) as exc:
        raise SignedRuntimeReviewError(
            "Pinned signed runtime review unavailable, altered or unsafe") from exc

    return {
        "status": STATUS,
        "source_commit": expected_source_commit,
        "custody_index_sha256": expected_custody_sha256,
        "receipt_sha256": expected_receipt_sha256,
        "reviewer_request_sha256": expected_request_sha256,
        "reviewer_id": expected_reviewer_id,
        "witness_id": expected_witness_id,
        "dual_ssh_custody_signatures_locally_verified": True,
        "operator_runtime_report_locally_correlated": True,
        "operator_reported_scopes_locally_unique": True,
        "readonly_source_view_verified": require_readonly_source_view,
        "independent_vm_attestation": False,
        "native_kernel_execution_independently_verified": False,
        "operator_logs_authenticated": False,
        "hypervisor_identity_independently_verified": False,
        "release_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
        "required_external_evidence": hold.MISSING,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Review locally signed runtime claims and HOLD release")
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--reviewer-request", type=Path, required=True)
    for pin in PINS:
        parser.add_argument("--" + pin.replace("_", "-"), required=True)
    parser.add_argument("--expected-policy-revision", type=int, required=True)
    parser.add_argument("--expected-reviewer-id", required=True)
    parser.add_argument("--expected-witness-id", required=True)
    parser.add_argument("--require-readonly-source-view", action="store_true")
    args = parser.parse_args(argv)
    kwargs = {name: getattr(args, name) for name in PINS}
    try:
        output = review_signed_runtime(
            args.private_dir, args.source_root, args.reviewer_request,
            expected_policy_revision=args.expected_policy_revision,
            expected_reviewer_id=args.expected_reviewer_id,
            expected_witness_id=args.expected_witness_id,
            require_readonly_source_view=args.require_readonly_source_view,
            **kwargs)
        print(json.dumps(output, sort_keys=True))
    except SignedRuntimeReviewError as exc:
        print(json.dumps({
            "status": REJECTED,
            "reason": str(exc),
            "independent_vm_attestation": False,
            "release_authorized": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
    # Exit 2 even on a valid signed package. No native VM attestation exists.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
