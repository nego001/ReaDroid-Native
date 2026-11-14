#!/usr/bin/env python3
"""PE-S1.54: require BOTH dual signed custody authorization and strict guest logs.

This composes PE-S1.51 and PE-S1.53 over one exact externally pinned
PE-S1.48 index. It only validates the *claimed* chronology of the operator's
receipt and guest observations; neither is an independently trusted clock.
No Windows PE, Ghidra, hypervisor probe, network call or key generation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_dual_control_review as dual
import pe_arch_vm_observation_review as observation
import pe_arch_vm_receipt_verify as receipts
from pe_arch_vm_checkout_pin import COMMIT_SHA

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
STATUS = "LOCAL_SIGNED_CUSTODY_AND_GUEST_LOGS_CORRELATED_NOT_VM_ATTESTED"


class EndToEndReviewError(RuntimeError):
    """Full reviewer package is incomplete, inconsistent, or unsafe."""


def _time(raw: object) -> datetime:
    if not isinstance(raw, str) or not 20 <= len(raw) <= 64:
        raise EndToEndReviewError("Claimed operator timestamp is malformed")
    try:
        value = datetime.fromisoformat(raw)
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise EndToEndReviewError("Claimed operator timestamp must be UTC")
        return value
    except (TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise EndToEndReviewError("Claimed operator timestamp is invalid") from exc


def verify_complete_review(
        private_dir: Path, source_root: Path, *,
        expected_policy_sha256: str, expected_policy_revision: int,
        expected_reviewer_signers_sha256: str,
        expected_reviewer_signature_sha256: str, expected_reviewer_id: str,
        expected_custody_sha256: str, expected_statement_sha256: str,
        expected_signature_sha256: str, expected_signers_sha256: str,
        expected_source_commit: str, expected_challenge: str,
        expected_witness_id: str,
        require_readonly_source_view: bool = False) -> dict:
    """Fail closed unless both independent workflows pass with identical pins."""
    for field, value in (
            ("policy", expected_policy_sha256),
            ("reviewer key", expected_reviewer_signers_sha256),
            ("reviewer signature", expected_reviewer_signature_sha256),
            ("custody index", expected_custody_sha256),
            ("witness statement", expected_statement_sha256),
            ("witness signature", expected_signature_sha256),
            ("witness key", expected_signers_sha256),
            ("challenge", expected_challenge)):
        if not isinstance(value, str) or HEX64.fullmatch(value) is None:
            raise EndToEndReviewError("External reviewer SHA-256 required: " + field)
    if expected_challenge == "0" * 64:
        raise EndToEndReviewError("Reviewer challenge cannot be zero")
    if (not isinstance(expected_source_commit, str)
            or COMMIT_SHA.fullmatch(expected_source_commit) is None
            or type(expected_policy_revision) is not int
            or not 1 <= expected_policy_revision <= 1000000000):
        raise EndToEndReviewError("Externally pinned commit/revision required")
    for identity in (expected_reviewer_id, expected_witness_id):
        if (not isinstance(identity, str)
                or dual.witness.WITNESS_ID.fullmatch(identity) is None):
            raise EndToEndReviewError("Externally selected identity required")
    if expected_reviewer_id == expected_witness_id:
        raise EndToEndReviewError("Reviewer and witness must be different")
    if type(require_readonly_source_view) is not bool:
        raise EndToEndReviewError("Readonly source policy must be boolean")
    root = Path(private_dir)
    if (not root.is_absolute() or root.name in ("", ".", "..")
            or any(part in ("", ".", "..") for part in root.parts[1:])):
        raise EndToEndReviewError("Canonical absolute private folder required")

    try:
        # Hold exact initial bytes while the other two validators re-read
        # their own sources, hashes and all reviewer-trusted public material.
        files = ("reviewer-custody-index.json",
                 "acceptance.json", "guest-kernel-observation.txt",
                 "guest-cgroup-observation.txt",
                 "reviewer-witness-trust-policy.json",
                 "witness-statement.json",
                 "witness-statement.sig", "witness-allowed-signers",
                 dual.REVIEWER_SIGNERS, dual.REVIEWER_SIGNATURE)
        initial = {
            name: receipts._read_private_receipt(root / name)
            for name in files
        }
        if (hashlib.sha256(initial["reviewer-custody-index.json"]).hexdigest()
                != expected_custody_sha256):
            raise EndToEndReviewError("Reviewer custody index pin differs")
        # Enforce structured observations first, so forged log claims do
        # not get promoted via an otherwise valid witness signature.
        logs = observation.verify_observation_custody(
            root, source_root,
            expected_custody_sha256=expected_custody_sha256,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            require_readonly_source_view=require_readonly_source_view)
        if (logs.get("status") != observation.STATUS
                or logs.get("operator_logs_authenticated") is not False
                or logs.get("independent_vm_attestation") is not False):
            raise EndToEndReviewError("Strict guest log/custody validation missing")

        signatures = dual.verify_dual_control(
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
        if (signatures.get("status") !=
                "DUAL_CONTROL_CUSTODY_AUTHORIZATION_VERIFIED"
                or signatures.get("reviewer_policy_signature_verified") is not True
                or signatures.get("witness_custody_signature_verified") is not True
                or signatures.get("independent_vm_attestation") is not False):
            raise EndToEndReviewError("Dual-control signed trust missing")
        if (logs["source_files_rechecked"] !=
                signatures["source_files_rechecked"]
                or logs["readonly_source_view_verified"] is not
                   signatures["readonly_source_view_verified"]):
            raise EndToEndReviewError("Reviewer source verification inconsistent")

        # Both dates come exclusively from operator-controlled files.
        # This is only a string/claimed-clock consistency check; NEVER a
        # signed, wall-clock, TPM, hypervisor or VM timing attestation.
        receipt = json.loads(
            initial["acceptance.json"].decode("utf-8"),
            object_pairs_hook=receipts._no_duplicate_keys)
        kernel = json.loads(
            initial["guest-kernel-observation.txt"].decode("utf-8"),
            object_pairs_hook=receipts._no_duplicate_keys)
        group = json.loads(
            initial["guest-cgroup-observation.txt"].decode("utf-8"),
            object_pairs_hook=receipts._no_duplicate_keys)
        accepted_at = _time(receipt["recorded_at_utc"])
        collected_at = _time(kernel["operator_observed_at_utc_not_attested"])
        if (kernel["operator_observed_at_utc_not_attested"] !=
                group["operator_observed_at_utc_not_attested"]
                or collected_at < accepted_at):
            raise EndToEndReviewError(
                "Operator-claimed guest collection predates acceptance or differs")
        for name, original in initial.items():
            if receipts._read_private_receipt(root / name) != original:
                raise EndToEndReviewError(
                    "Reviewer private package changed during full review: " + name)
        return {
            "status": STATUS,
            "source_commit": expected_source_commit,
            "custody_index_sha256": expected_custody_sha256,
            "policy_revision": expected_policy_revision,
            "reviewer_id": expected_reviewer_id,
            "witness_id": expected_witness_id,
            "source_files_rechecked": logs["source_files_rechecked"],
            "readonly_source_view_verified": logs[
                "readonly_source_view_verified"],
            "structured_guest_logs_consistent_with_custody": True,
            "separate_reviewer_and_witness_signatures_verified": True,
            "operator_claimed_chronology_consistent": True,
            "operator_clock_independently_verified": False,
            "witness_identity_independently_verified": False,
            "operator_logs_authenticated": False,
            "independent_vm_attestation": False,
            "native_kernel_execution_independently_verified": False,
            "host_or_git_authenticity_verified": False,
            "windows_binary_executed_by_reviewer": False,
        }
    except (OSError, UnicodeError, ValueError, TypeError, KeyError,
            OverflowError, RecursionError, receipts.ReceiptReviewError,
            observation.ObservationReviewError, dual.DualControlError) as exc:
        raise EndToEndReviewError(
            "Full reviewer package is unsafe, incomplete or inconsistent") from exc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Require signed dual control AND structured guest custody; no VM attestation")
    ap.add_argument("--private-dir", type=Path, required=True)
    ap.add_argument("--source-root", type=Path, required=True)
    for flag in ("policy-sha256", "reviewer-signers-sha256",
                 "reviewer-signature-sha256", "reviewer-id",
                 "custody-sha256", "statement-sha256",
                 "signature-sha256", "signers-sha256",
                 "source-commit", "challenge", "witness-id"):
        ap.add_argument("--expected-" + flag, required=True)
    ap.add_argument("--expected-policy-revision", type=int, required=True)
    ap.add_argument("--require-readonly-source-view", action="store_true")
    args = ap.parse_args(argv)
    try:
        result = verify_complete_review(
            args.private_dir, args.source_root,
            expected_policy_sha256=args.expected_policy_sha256,
            expected_policy_revision=args.expected_policy_revision,
            expected_reviewer_signers_sha256=args.expected_reviewer_signers_sha256,
            expected_reviewer_signature_sha256=args.expected_reviewer_signature_sha256,
            expected_reviewer_id=args.expected_reviewer_id,
            expected_custody_sha256=args.expected_custody_sha256,
            expected_statement_sha256=args.expected_statement_sha256,
            expected_signature_sha256=args.expected_signature_sha256,
            expected_signers_sha256=args.expected_signers_sha256,
            expected_source_commit=args.expected_source_commit,
            expected_challenge=args.expected_challenge,
            expected_witness_id=args.expected_witness_id,
            require_readonly_source_view=args.require_readonly_source_view)
        print(json.dumps(result, sort_keys=True))
        return 0
    except EndToEndReviewError as exc:
        print(json.dumps({
            "status": "REJECTED_SIGNED_GUEST_CUSTODY_REVIEW",
            "reason": str(exc),
            "independent_vm_attestation": False,
            "native_kernel_execution_independently_verified": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
