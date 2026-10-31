#!/usr/bin/env python3
"""PE-S1.64: correlate the S1.62 signed local runtime and S1.63 host logs.

This is deliberately an offline, fail-closed HOLD gate. Three valid OpenSSH
signatures and consistent SHA-256 references only prove local documents were
signed by keys selected out of band. They do not authenticate hypervisor
hardware, the observer's physical independence, clocks or native Arch.
No guest execution, PE launch, Ghidra launch or release can occur here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_s1_62_signed_runtime_hold as local
import pe_arch_vm_s1_63_external_observer as external
import pe_arch_vm_receipt_verify as receipts
import pe_arch_vm_s1_57_release_guard as release

STATUS = "HOLD_PE_S1_64_THREE_SIGNED_EVIDENCE_SETS_NOT_VM_ATTESTED"
REJECTED = "REJECTED_PE_S1_64_SIGNED_EVIDENCE_CORRELATION"
LOCAL_FIELDS = frozenset({
    "status", "source_commit", "custody_index_sha256", "receipt_sha256",
    "reviewer_request_sha256", "reviewer_id", "witness_id",
    "dual_ssh_custody_signatures_locally_verified",
    "operator_runtime_report_locally_correlated",
    "operator_reported_scopes_locally_unique",
    "readonly_source_view_verified", "independent_vm_attestation",
    "native_kernel_execution_independently_verified",
    "operator_logs_authenticated", "hypervisor_identity_independently_verified",
    "release_authorized", "unknown_windows_pe_execution_authorized",
    "apk_or_ota_publication_authorized", "required_external_evidence",
})
EXTERNAL_FIELDS = frozenset({
    "status", "source_commit", "reviewer_challenge_correlated",
    "request_custody_receipt_pins_correlated",
    "external_observer_manifest_sha256", "external_observer_id",
    "distinct_observer_reviewer_witness_ssh_keys_verified",
    "external_observer_detached_signature_verified",
    "host_observation_file_hashes_matched",
    "host_observation_file_count", "observer_clock_independently_verified",
    "observer_host_independently_authenticated",
    "native_arch_kernel_independently_verified",
    "independent_vm_attestation", "unknown_windows_pe_execution_authorized",
    "apk_or_ota_publication_authorized",
})
LOCAL_TRUE = (
    "dual_ssh_custody_signatures_locally_verified",
    "operator_runtime_report_locally_correlated",
    "operator_reported_scopes_locally_unique",
)
LOCAL_FALSE = (
    "independent_vm_attestation",
    "native_kernel_execution_independently_verified",
    "operator_logs_authenticated", "hypervisor_identity_independently_verified",
    "release_authorized", "unknown_windows_pe_execution_authorized",
    "apk_or_ota_publication_authorized",
)
EXTERNAL_TRUE = (
    "reviewer_challenge_correlated",
    "request_custody_receipt_pins_correlated",
    "distinct_observer_reviewer_witness_ssh_keys_verified",
    "external_observer_detached_signature_verified",
    "host_observation_file_hashes_matched",
)
EXTERNAL_FALSE = (
    "observer_clock_independently_verified",
    "observer_host_independently_authenticated",
    "native_arch_kernel_independently_verified",
    "independent_vm_attestation", "unknown_windows_pe_execution_authorized",
    "apk_or_ota_publication_authorized",
)
LOCAL_PIN_KEYS = (
    "expected_request_sha256", "expected_custody_sha256",
    "expected_receipt_sha256", "expected_source_commit",
    "expected_challenge", "expected_policy_sha256",
    "expected_policy_revision", "expected_reviewer_signers_sha256",
    "expected_reviewer_signature_sha256", "expected_reviewer_id",
    "expected_statement_sha256", "expected_signature_sha256",
    "expected_signers_sha256", "expected_witness_id",
)
EXTERNAL_PIN_KEYS = (
    "expected_observer_manifest_sha256",
    "expected_observer_signature_sha256",
    "expected_observer_signers_sha256", "expected_observer_id",
)


class ThreeWayReviewError(RuntimeError):
    """Evidence cannot be reconciled, even as an unauthenticated local claim."""


def _strict_local(value: object, *, expected_source_commit: str,
                  expected_custody_sha256: str, expected_receipt_sha256: str,
                  expected_request_sha256: str, expected_reviewer_id: str,
                  expected_witness_id: str, readonly: bool) -> None:
    if (not isinstance(value, dict) or set(value) != LOCAL_FIELDS
            or value["status"] != local.STATUS
            or value["source_commit"] != expected_source_commit
            or value["custody_index_sha256"] != expected_custody_sha256
            or value["receipt_sha256"] != expected_receipt_sha256
            or value["reviewer_request_sha256"] != expected_request_sha256
            or value["reviewer_id"] != expected_reviewer_id
            or value["witness_id"] != expected_witness_id
            or value["readonly_source_view_verified"] is not readonly
            or any(value[key] is not True for key in LOCAL_TRUE)
            or any(value[key] is not False for key in LOCAL_FALSE)
            or value["required_external_evidence"] != release.MISSING):
        raise ThreeWayReviewError("Signed local runtime contract disagrees or overclaims")


def _strict_external(value: object, *, expected_source_commit: str,
                     expected_observer_id: str,
                     expected_observer_manifest_sha256: str) -> None:
    if (not isinstance(value, dict) or set(value) != EXTERNAL_FIELDS
            or value["status"] != external.STATUS
            or value["source_commit"] != expected_source_commit
            or value["external_observer_id"] != expected_observer_id
            or value["external_observer_manifest_sha256"]
               != expected_observer_manifest_sha256
            or type(value["host_observation_file_count"]) is not int
            or value["host_observation_file_count"] != len(external.OBS_FILES)
            or any(value[key] is not True for key in EXTERNAL_TRUE)
            or any(value[key] is not False for key in EXTERNAL_FALSE)):
        raise ThreeWayReviewError(
            "Third-party signature review disagrees or claims VM proof")


def review_three_signed_packages(
        custody_dir: Path, observer_dir: Path, source_root: Path,
        reviewer_request: Path, *, expected_request_sha256: str,
        expected_custody_sha256: str, expected_receipt_sha256: str,
        expected_source_commit: str, expected_challenge: str,
        expected_policy_sha256: str, expected_policy_revision: int,
        expected_reviewer_signers_sha256: str,
        expected_reviewer_signature_sha256: str, expected_reviewer_id: str,
        expected_statement_sha256: str, expected_signature_sha256: str,
        expected_signers_sha256: str, expected_witness_id: str,
        expected_observer_manifest_sha256: str,
        expected_observer_signature_sha256: str,
        expected_observer_signers_sha256: str, expected_observer_id: str,
        require_readonly_source_view: bool = False) -> dict:
    """Require S1.62 and S1.63 with matching out-of-band pin sets.

    Local upstream checks do not attest a native kernel or a human witness.
    Only a separately audited mechanism could ever change this HOLD.
    """
    supplied = locals().copy()
    try:
        # Validate pins in upstream modules; never trust their returned
        # status alone without checking complete flag/schema contracts.
        private = Path(custody_dir)
        observed = Path(observer_dir)
        if (not private.is_absolute() or not observed.is_absolute()
                or private == observed
                or private in observed.parents or observed in private.parents):
            raise ThreeWayReviewError("Observer and operator folders must be separate")

        # Compare exact bytes across both full reviews to catch persistent
        # package replacement between stages; this is not an atomic snapshot.
        before = {
            name: receipts._read_private_receipt(private / name)
            for name in local.PRIVATE_FILES
        }
        request_before = receipts._read_private_receipt(Path(reviewer_request))
        local_kwargs = {key: supplied[key] for key in LOCAL_PIN_KEYS}
        local_result = local.review_signed_runtime(
            private, Path(source_root), Path(reviewer_request),
            require_readonly_source_view=require_readonly_source_view,
            **local_kwargs)
        _strict_local(
            local_result, expected_source_commit=expected_source_commit,
            expected_custody_sha256=expected_custody_sha256,
            expected_receipt_sha256=expected_receipt_sha256,
            expected_request_sha256=expected_request_sha256,
            expected_reviewer_id=expected_reviewer_id,
            expected_witness_id=expected_witness_id,
            readonly=require_readonly_source_view)

        observer_result = external.verify_external_observer(
            observed, private,
            expected_manifest_sha256=expected_observer_manifest_sha256,
            expected_signature_sha256=expected_observer_signature_sha256,
            expected_observer_signers_sha256=expected_observer_signers_sha256,
            expected_reviewer_signers_sha256=expected_reviewer_signers_sha256,
            expected_witness_signers_sha256=expected_signers_sha256,
            expected_observer_id=expected_observer_id,
            expected_reviewer_id=expected_reviewer_id,
            expected_witness_id=expected_witness_id,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            expected_request_sha256=expected_request_sha256,
            expected_custody_sha256=expected_custody_sha256,
            expected_receipt_sha256=expected_receipt_sha256)
        _strict_external(
            observer_result, expected_source_commit=expected_source_commit,
            expected_observer_id=expected_observer_id,
            expected_observer_manifest_sha256=expected_observer_manifest_sha256)

        for name, original in before.items():
            if receipts._read_private_receipt(private / name) != original:
                raise ThreeWayReviewError(
                    "Operator package changed during combined review: " + name)
        if receipts._read_private_receipt(Path(reviewer_request)) != request_before:
            raise ThreeWayReviewError(
                "Reviewer request changed during combined review")
    except (OSError, ValueError, UnicodeError, TypeError, KeyError,
            OverflowError, RecursionError, receipts.ReceiptReviewError,
            local.SignedRuntimeReviewError,
            external.ExternalObserverError) as exc:
        raise ThreeWayReviewError(
            "Three-way signed evidence package unavailable, altered or unsafe") from exc

    return {
        "status": STATUS,
        "source_commit": expected_source_commit,
        "custody_index_sha256": expected_custody_sha256,
        "receipt_sha256": expected_receipt_sha256,
        "reviewer_request_sha256": expected_request_sha256,
        "observer_manifest_sha256": expected_observer_manifest_sha256,
        "three_distinct_signing_keys_locally_verified": True,
        "signed_local_custody_and_runtime_correlated": True,
        "external_host_log_hashes_and_signature_correlated": True,
        "observer_capture_independently_authenticated": False,
        "hypervisor_provenance_independently_verified": False,
        "native_kernel_execution_independently_verified": False,
        "independent_vm_attestation": False,
        "release_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
        "required_external_evidence": release.MISSING,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Three-key offline review of local runtime+host logs, always HOLD")
    ap.add_argument("--custody-dir", type=Path, required=True)
    ap.add_argument("--observer-dir", type=Path, required=True)
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--reviewer-request", type=Path, required=True)
    for key in (*LOCAL_PIN_KEYS, *EXTERNAL_PIN_KEYS):
        opts = {"type": int} if key == "expected_policy_revision" else {}
        ap.add_argument("--" + key.replace("_", "-"), required=True, **opts)
    ap.add_argument("--require-readonly-source-view", action="store_true")
    args = ap.parse_args(argv)
    opts = {key: getattr(args, key)
            for key in (*LOCAL_PIN_KEYS, *EXTERNAL_PIN_KEYS)}
    try:
        result = review_three_signed_packages(
            args.custody_dir, args.observer_dir, args.source_root,
            args.reviewer_request,
            require_readonly_source_view=args.require_readonly_source_view,
            **opts)
        print(json.dumps(result, sort_keys=True))
    except ThreeWayReviewError as exc:
        print(json.dumps({
            "status": REJECTED, "reason": str(exc),
            "independent_vm_attestation": False,
            "release_authorized": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
    # Valid != authorized: both valid and rejected cases exit 2.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
