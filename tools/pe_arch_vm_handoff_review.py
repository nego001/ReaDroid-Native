#!/usr/bin/env python3
"""PE-S1.47: independently correlate a local unsigned Arch VM evidence handoff.

No VM, Windows executable, Ghidra, systemd scope or network is started.
This is a LOCAL consistency check on separately retained SHA-256 pins and
Git sources, NOT third-party kernel/hypervisor attestation or a signature.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

# The reviewer must not create pycache inside its own pinned Git checkout.
sys.dont_write_bytecode = True

import pe_arch_vm_evidence as evidence
import pe_arch_vm_receipt_verify as receipt_review
from pe_arch_vm_checkout_pin import (
    CheckoutPinError, COMMIT_SHA, verify_source_checkout_pin,
)

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
PIN_FIELDS = frozenset({
    "status", "expected_commit", "checked_manifest_entries",
    "worktree_status_clean", "git_authorship_or_signature_verified",
    "native_vm_or_kernel_verified",
})
RECEIPT_ACK_FIELDS = frozenset({
    "path", "receipt_sha256", "record_type",
})


class HandoffReviewError(RuntimeError):
    """The operator handoff cannot be correlated without unsafe assumptions."""


def _strict_json(raw: bytes) -> object:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=receipt_review._no_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                HandoffReviewError("Non-finite operator JSON value")))
    except (UnicodeError, ValueError, TypeError, RecursionError,
            OverflowError) as exc:
        raise HandoffReviewError("Invalid operator handoff JSON") from exc


def verify_operator_handoff(
        operator_output: Path, receipt: Path, source_root: Path, *,
        expected_source_commit: str, expected_challenge: str,
        expected_receipt_sha256: str, expected_operator_sha256: str,
        require_readonly_source_view: bool = False) -> dict:
    """Compare two reviewer-retained hashes, operator claims, local source.

    Each expected hash MUST have been retained independently of the received
    files. Both local source checks are repeat observations, not an atomic
    snapshot. The stdout and receipt are UNSIGNED operator-controlled data.
    """
    if (not isinstance(expected_source_commit, str)
            or COMMIT_SHA.fullmatch(expected_source_commit) is None):
        raise HandoffReviewError("External full Git commit pin required")
    if (not isinstance(expected_challenge, str)
            or not HEX64.fullmatch(expected_challenge)
            or expected_challenge == "0" * 64):
        raise HandoffReviewError("External reviewer challenge required")
    for name, value in (
            ("receipt", expected_receipt_sha256),
            ("operator", expected_operator_sha256)):
        if not isinstance(value, str) or HEX64.fullmatch(value) is None:
            raise HandoffReviewError(
                "External lowercase SHA-256 required for " + name)
    if type(require_readonly_source_view) is not bool:
        raise HandoffReviewError("Readonly source policy must be boolean")

    try:
        root = Path(source_root)
        receipt_file = Path(receipt)
        stdout_file = Path(operator_output)
        if receipt_file == stdout_file:
            raise HandoffReviewError(
                "Receipt and operator output must be separate private files")
        # Both files are opened with the same owner-only, nofollow, pinned
        # directory and single-link rules as the existing receipt reviewer.
        raw_stdout = receipt_review._read_private_receipt(stdout_file)
        if hashlib.sha256(raw_stdout).hexdigest() != expected_operator_sha256:
            raise HandoffReviewError(
                "Operator output differs from externally retained SHA-256")
        operator = _strict_json(raw_stdout)
        if not isinstance(operator, dict):
            raise HandoffReviewError("Operator output must be a JSON object")

        # Corroborate a reviewer-owned checkout, not the operator's path.
        before_pin = verify_source_checkout_pin(
            root, expected_source_commit, evidence.SOURCE_FILES)
        result = receipt_review.verify_local_receipt(
            receipt_file, root, expected_challenge=expected_challenge,
            expected_receipt_sha256=expected_receipt_sha256,
            require_readonly_source_view=require_readonly_source_view)
        raw_receipt = receipt_review._read_private_receipt(receipt_file)
        if hashlib.sha256(raw_receipt).hexdigest() != expected_receipt_sha256:
            raise HandoffReviewError(
                "Receipt changed between review and handoff comparison")
        record = _strict_json(raw_receipt)
        if not isinstance(record, dict):
            raise HandoffReviewError("Receipt must be a JSON object")
        report = record["native_acceptance_report"]

        # A claim of success in operator stdout is not proof. Require exact
        # equivalence with the already validated canonical receipt report.
        if set(operator) != set(report) | {
                "local_receipt", "local_source_checkout_pin"}:
            raise HandoffReviewError(
                "Operator output has missing or unsupported evidence fields")
        operator_report = {k: operator[k] for k in report}
        if evidence._canonical(operator_report) != evidence._canonical(report):
            raise HandoffReviewError(
                "Operator output does not match the exact receipt report")

        ack = operator["local_receipt"]
        if (not isinstance(ack, dict)
                or set(ack) != RECEIPT_ACK_FIELDS
                or not isinstance(ack["path"], str)
                or len(ack["path"]) > 4096
                or not Path(ack["path"]).is_absolute()
                or Path(ack["path"]).name in ("", ".", "..")
                or ack["receipt_sha256"] != expected_receipt_sha256
                or ack["record_type"] != "LOCAL_SELF_REPORT_NOT_SIGNED"):
            raise HandoffReviewError(
                "Operator receipt publication acknowledgement inconsistent")
        operator_pin = operator["local_source_checkout_pin"]
        if (not isinstance(operator_pin, dict)
                or set(operator_pin) != PIN_FIELDS
                or operator_pin != before_pin):
            raise HandoffReviewError(
                "Operator local Git pin does not match reviewer checkout")

        # A source can change while the report is being compared; re-observe
        # the local Git tree after all receipt/report checks, fail closed.
        after_pin = verify_source_checkout_pin(
            root, expected_source_commit, evidence.SOURCE_FILES)
        if after_pin != before_pin:
            raise HandoffReviewError(
                "Reviewer checkout changed during handoff verification")
        return {
            "status": "LOCAL_OPERATOR_HANDOFF_CORRELATED",
            "security_classification": "UNSIGNED_OPERATOR_SELF_REPORT",
            "external_receipt_sha256_pin_matched": True,
            "external_operator_sha256_pin_matched": True,
            "reviewer_challenge_correlated": True,
            "source_commit_pin_matched_locally": True,
            "source_files_rechecked": result["source_files_rechecked"],
            "readonly_source_view_verified": result[
                "readonly_source_view_verified"],
            "operator_report_matches_receipt": True,
            "native_kernel_execution_independently_verified": False,
            "independent_vm_attestation": False,
            "host_or_git_authenticity_verified": False,
            "windows_binary_executed_by_reviewer": False,
        }
    except (OSError, UnicodeError, ValueError, TypeError, KeyError,
            RecursionError, OverflowError, evidence.AcceptanceReceiptError,
            receipt_review.ReceiptReviewError, CheckoutPinError) as exc:
        raise HandoffReviewError(
            "Operator handoff unavailable, unsafe or inconsistent") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independent local operator handoff check; NOT VM attestation")
    parser.add_argument("--operator-output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-challenge", required=True)
    parser.add_argument("--expected-receipt-sha256", required=True)
    parser.add_argument("--expected-operator-sha256", required=True)
    parser.add_argument(
        "--require-readonly-source-view", action="store_true",
        help="Require Linux ST_RDONLY on all manifest source mount views")
    args = parser.parse_args(argv)
    try:
        report = verify_operator_handoff(
            args.operator_output, args.receipt, args.source_root,
            expected_source_commit=args.expected_source_commit,
            expected_challenge=args.expected_challenge,
            expected_receipt_sha256=args.expected_receipt_sha256,
            expected_operator_sha256=args.expected_operator_sha256,
            require_readonly_source_view=args.require_readonly_source_view)
        print(json.dumps(report, sort_keys=True))
        return 0
    except HandoffReviewError as exc:
        print(json.dumps({
            "status": "REJECTED_LOCAL_OPERATOR_HANDOFF",
            "reason": str(exc),
            "native_kernel_execution_independently_verified": False,
            "independent_vm_attestation": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
