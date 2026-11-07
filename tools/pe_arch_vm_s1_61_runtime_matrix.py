#!/usr/bin/env python3
"""PE-S1.61: correlate guest self-reports with native runtime receipt and reviewer request.

Offline, read-only validation of operator-authored observations. Even when
all four systemd scope claims and JVM seccomp mode 2 are structurally
consistent with the locally reviewed receipt, neither the host kernel nor an
independently controlled Arch VM has been attested. No execution or release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_evidence as evidence
import pe_arch_vm_observation_review as observations
import pe_arch_vm_receipt_verify as receipt
import pe_arch_vm_s1_60_review_request as request

STATUS = "LOCAL_ARCH_RUNTIME_CLAIMS_CORRELATED_NOT_INDEPENDENTLY_ATTESTED"
FAILURE = "REJECTED_PE_S1_61_UNTRUSTED_RUNTIME_CLAIMS"
OBSERVATION_FIELDS = frozenset({
    "status", "source_commit", "custody_index_sha256",
    "guest_kernel_observation_sha256", "guest_cgroup_observation_sha256",
    "source_files_rechecked", "readonly_source_view_verified",
    "observation_pins_and_structure_correlated",
    "operator_batch_timestamp_matches",
    "cgroup_controller_claims_structurally_consistent",
    "operator_logs_authenticated",
    "native_kernel_execution_independently_verified",
    "independent_vm_attestation", "host_or_git_authenticity_verified",
    "windows_binary_executed_by_reviewer",
})
CLEANUP = (
    ("initial_cgroup", ("cgroup_lifecycle",), "scope_cleanup_evidence"),
    ("descendant", ("descendant_lifecycle",), "descendant_cleanup_evidence"),
    ("scoped_seccomp", ("ghidra", "arch_scoped_seccomp_probe"),
     "scope_cleanup_evidence"),
    ("ghidra_with_both", ("ghidra", "arch_real_ghidra_with_both"),
     "scope_cleanup_evidence"),
)


class RuntimeMatrixError(RuntimeError):
    """No reliable basis for even a local claims correlation."""


def _exact_observation_result(result: object, *, source_commit: str,
                              custody_sha256: str, readonly: bool) -> None:
    if (not isinstance(result, dict)
            or set(result) != OBSERVATION_FIELDS
            or result["status"] != observations.STATUS
            or result["source_commit"] != source_commit
            or result["custody_index_sha256"] != custody_sha256
            or type(result["source_files_rechecked"]) is not int
            or result["source_files_rechecked"] != len(evidence.SOURCE_FILES)
            or result["readonly_source_view_verified"] is not readonly
            or any(result[key] is not True for key in (
                "observation_pins_and_structure_correlated",
                "operator_batch_timestamp_matches",
                "cgroup_controller_claims_structurally_consistent"))
            or any(result[key] is not False for key in (
                "operator_logs_authenticated",
                "native_kernel_execution_independently_verified",
                "independent_vm_attestation", "host_or_git_authenticity_verified",
                "windows_binary_executed_by_reviewer"))
            or any(not isinstance(result[key], str)
                   or request.HEX64.fullmatch(result[key]) is None
                   for key in ("guest_kernel_observation_sha256",
                               "guest_cgroup_observation_sha256"))):
        raise RuntimeMatrixError(
            "Operator guest review has contradictory or incomplete claims")


def _scopes(report: dict) -> dict:
    """Extract four separate scope claims from a fully validated local report."""
    scopes = {}
    for label, keys, cleanup_field in CLEANUP:
        item = report
        for key in keys:
            item = item[key]
        scope = item["scope"]
        cleanup = item[cleanup_field]
        if (not evidence._valid_scope(scope)
                or cleanup["scope"] != scope
                or not evidence._verified_scope_cleanup(scope, cleanup)):
            raise RuntimeMatrixError("Unproven local scope cleanup: " + label)
        scopes[label] = scope
    if len(set(scopes.values())) != len(scopes):
        raise RuntimeMatrixError(
            "Distinct runtime stages reused a systemd scope identifier")
    return scopes


def verify_runtime_claims(
        private_dir: Path, source_root: Path, reviewer_request: Path, *,
        expected_request_sha256: str, expected_custody_sha256: str,
        expected_receipt_sha256: str, expected_source_commit: str,
        expected_challenge: str, expected_reviewer_id: str,
        require_readonly_source_view: bool = False) -> dict:
    """Re-check all reviewer-held pins before reporting purely local evidence."""
    if (type(require_readonly_source_view) is not bool
            or not isinstance(expected_receipt_sha256, str)
            or request.HEX64.fullmatch(expected_receipt_sha256) is None
            or not isinstance(expected_custody_sha256, str)
            or request.HEX64.fullmatch(expected_custody_sha256) is None):
        raise RuntimeMatrixError("Reviewer-supplied receipt/custody pin required")

    folder = Path(private_dir)
    receipt_file = folder / "acceptance.json"
    request_path = Path(reviewer_request)
    kwargs = {
        "expected_request_sha256": expected_request_sha256,
        "expected_source_commit": expected_source_commit,
        "expected_challenge": expected_challenge,
        "expected_reviewer_id": expected_reviewer_id,
    }
    try:
        before = request.verify_request(request_path, **kwargs)
        observed = observations.verify_observation_custody(
            folder, Path(source_root),
            expected_custody_sha256=expected_custody_sha256,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            require_readonly_source_view=require_readonly_source_view)
        _exact_observation_result(
            observed, source_commit=expected_source_commit,
            custody_sha256=expected_custody_sha256,
            readonly=require_readonly_source_view)
        verified = receipt.verify_local_receipt(
            receipt_file, Path(source_root),
            expected_challenge=expected_challenge,
            expected_receipt_sha256=expected_receipt_sha256,
            require_readonly_source_view=require_readonly_source_view)
        if (not isinstance(verified, dict)
                or verified.get("status") !=
                   "LOCAL_RECEIPT_CONSISTENCY_VALIDATED"
                or verified.get("receipt_sha256") != expected_receipt_sha256
                or verified.get("external_receipt_sha256_pin_matched") is not True
                or verified.get("source_files_rechecked") !=
                   len(evidence.SOURCE_FILES)
                or verified.get("readonly_source_view_verified") is not
                   require_readonly_source_view
                or verified.get("independent_vm_attestation") is not False
                or verified.get("native_kernel_execution_independently_verified")
                   is not False):
            raise RuntimeMatrixError("Local runtime receipt not independently pinned")

        raw = receipt._read_private_receipt(receipt_file)
        if hashlib.sha256(raw).hexdigest() != expected_receipt_sha256:
            raise RuntimeMatrixError("Runtime receipt changed during review")
        doc = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=receipt._no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                RuntimeMatrixError("Nonfinite runtime report")))
        if (not isinstance(doc, dict)
                or set(doc) != receipt.RECEIPT_FIELDS
                or doc["schema"] != receipt.RECEIPT_SCHEMA
                or doc["reviewer_challenge"] != expected_challenge
                or doc["windows_executable_launched"] is not False):
            raise RuntimeMatrixError("Runtime receipt fields incomplete")
        report = doc["native_acceptance_report"]
        evidence.validate_native_acceptance_report(report)
        if (hashlib.sha256(evidence._canonical(report)).hexdigest()
                != doc["report_sha256"]):
            raise RuntimeMatrixError("Embedded runtime report hash mismatch")
        scopes = _scopes(report)

        combined = report["ghidra"]["arch_real_ghidra_with_both"]
        seccomp = combined["ghidra_jvm_seccomp_evidence"]
        if (seccomp["verified"] is not True
                or type(seccomp["seccomp_mode"]) is not int
                or seccomp["seccomp_mode"] != 2
                or seccomp["measurement_source"] != "/proc/self/status"
                or seccomp["measured_process"] != "ghidra_headless_jvm"
                or type(seccomp["additional_filters_observed"]) is not int
                or seccomp["additional_filters_observed"] < 1
                or combined["bubblewrap"] is not True
                or combined["windows_binary_executed"] is not False):
            raise RuntimeMatrixError("Combined runtime local seccomp claim invalid")
        index_raw = receipt._read_private_receipt(
            folder / "reviewer-custody-index.json")
        if hashlib.sha256(index_raw).hexdigest() != expected_custody_sha256:
            raise RuntimeMatrixError("Local custody changed during runtime review")
        index = json.loads(
            index_raw.decode("utf-8"),
            object_pairs_hook=receipt._no_duplicate_keys)
        if (not isinstance(index, dict)
                or index.get("source_commit") != expected_source_commit
                or index.get("reviewer_challenge") != expected_challenge
                or index["artifacts"]["receipt"]["sha256"]
                   != expected_receipt_sha256
                or any(index["artifacts"][name]["sha256"] != observed[
                    name + "_sha256"] for name in (
                    "guest_kernel_observation",
                    "guest_cgroup_observation"))):
            raise RuntimeMatrixError("Guest observations and runtime receipt differ")

        # Re-check that none of the underlying pinned data was replaced
        # persistently after the downstream local validators returned.
        if receipt._read_private_receipt(receipt_file) != raw:
            raise RuntimeMatrixError("Native runtime receipt changed after check")
        after = request.verify_request(request_path, **kwargs)
        if before != after:
            raise RuntimeMatrixError("Reviewer request changed during runtime review")
    except (OSError, UnicodeError, ValueError, TypeError, KeyError,
            OverflowError, RecursionError, evidence.AcceptanceReceiptError,
            receipt.ReceiptReviewError, request.RequestReviewError,
            observations.ObservationReviewError) as exc:
        raise RuntimeMatrixError(
            "Runtime claims or reviewer pins unavailable or unsafe") from exc

    return {
        "status": STATUS,
        "source_commit": expected_source_commit,
        "custody_index_sha256": expected_custody_sha256,
        "receipt_sha256": expected_receipt_sha256,
        "reviewer_request_sha256": expected_request_sha256,
        "distinct_operator_reported_scopes": len(scopes),
        "operator_reported_scopes_locally_unique": True,
        "operator_reported_scope_cleanup_locally_validated": True,
        "operator_reported_ghidra_seccomp_mode": 2,
        "operator_reported_seccomp_and_cgroups_locally_correlated": True,
        "operator_guest_kernel_and_cgroup_logs_structurally_correlated": True,
        "readonly_source_view_verified": require_readonly_source_view,
        "independent_vm_attestation": False,
        "native_arch_kernel_independently_verified": False,
        "operator_logs_authenticated": False,
        "real_seccomp_and_cgroups_independently_witnessed": False,
        "scope_cleanup_independently_witnessed": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Offline operator runtime claim matrix; never an Arch VM attestation")
    ap.add_argument("--private-dir", required=True, type=Path)
    ap.add_argument("--source-root", required=True, type=Path)
    ap.add_argument("--reviewer-request", required=True, type=Path)
    for part in ("request-sha256", "custody-sha256", "receipt-sha256",
                 "source-commit", "challenge", "reviewer-id"):
        ap.add_argument("--expected-" + part, required=True)
    ap.add_argument("--require-readonly-source-view", action="store_true")
    args = ap.parse_args(argv)
    try:
        print(json.dumps(verify_runtime_claims(
            args.private_dir, args.source_root, args.reviewer_request,
            expected_request_sha256=args.expected_request_sha256,
            expected_custody_sha256=args.expected_custody_sha256,
            expected_receipt_sha256=args.expected_receipt_sha256,
            expected_source_commit=args.expected_source_commit,
            expected_challenge=args.expected_challenge,
            expected_reviewer_id=args.expected_reviewer_id,
            require_readonly_source_view=args.require_readonly_source_view),
            sort_keys=True))
        return 0
    except RuntimeMatrixError as exc:
        print(json.dumps({
            "status": FAILURE,
            "reason": str(exc),
            "independent_vm_attestation": False,
            "native_arch_kernel_independently_verified": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
