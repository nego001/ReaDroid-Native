#!/usr/bin/env python3
"""PE-S1.48: verify a reviewer-pinned custody inventory for Arch VM artifacts.

Reads only bounded, owner-only local files; never executes a Windows PE,
Ghidra, Git hooks, scopes or network commands. The operator's kernel/systemd
logs are self-reported observations, NEVER independent guest attestation.
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

import pe_arch_vm_handoff_review as handoff
import pe_arch_vm_receipt_verify as receipt_review
from pe_arch_vm_checkout_pin import COMMIT_SHA

SCHEMA = "negresco_pe_s1_48_local_custody_index_v1"
ARTIFACT_NAMES = {
    "receipt": "acceptance.json",
    "operator_output": "operator-run-output.json",
    "guest_kernel_observation": "guest-kernel-observation.txt",
    "guest_cgroup_observation": "guest-cgroup-observation.txt",
}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
INDEX_FIELDS = frozenset({
    "schema", "security_classification", "reviewer_challenge",
    "source_commit", "artifacts",
})
CLASSIFICATION = "UNSIGNED_REVIEWER_LOCAL_CUSTODY_NOT_VM_ATTESTATION"


class CustodyReviewError(RuntimeError):
    """Evidence custody index cannot be corroborated safely."""


def _strict_json(data: bytes) -> dict:
    try:
        obj = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=receipt_review._no_duplicate_keys,
            parse_constant=lambda val: (_ for _ in ()).throw(
                CustodyReviewError("Non-finite JSON in custody index")))
    except (UnicodeError, ValueError, TypeError, RecursionError,
            OverflowError) as exc:
        raise CustodyReviewError("Invalid custody index JSON") from exc
    if not isinstance(obj, dict):
        raise CustodyReviewError("Custody index must be a JSON object")
    return obj


def verify_custody_index(
        private_dir: Path, source_root: Path, *,
        expected_custody_sha256: str,
        expected_source_commit: str,
        expected_challenge: str,
        require_readonly_source_view: bool = False) -> dict:
    """Read private evidence and compare to an externally held index SHA256.

    Custody index is created/retained BY THE REVIEWER, not trusted from
    operator stdout. Hashes do not establish who produced a VM observation.
    """
    if (not isinstance(expected_custody_sha256, str)
            or SHA256.fullmatch(expected_custody_sha256) is None):
        raise CustodyReviewError("External custody index SHA-256 required")
    if (not isinstance(expected_source_commit, str)
            or COMMIT_SHA.fullmatch(expected_source_commit) is None):
        raise CustodyReviewError("Reviewer-selected full Git commit required")
    if (not isinstance(expected_challenge, str)
            or SHA256.fullmatch(expected_challenge) is None
            or expected_challenge == "0" * 64):
        raise CustodyReviewError("Reviewer-selected challenge required")
    if type(require_readonly_source_view) is not bool:
        raise CustodyReviewError("Readonly source policy must be boolean")
    root = Path(private_dir)
    if (not root.is_absolute() or root.name in ("", ".", "..")
            or any(part in ("", ".", "..") for part in root.parts[1:])):
        raise CustodyReviewError("Canonical absolute private directory required")

    try:
        index_path = root / "reviewer-custody-index.json"
        raw_index = receipt_review._read_private_receipt(index_path)
        if hashlib.sha256(raw_index).hexdigest() != expected_custody_sha256:
            raise CustodyReviewError(
                "Custody index differs from independently retained SHA-256")
        index = _strict_json(raw_index)
        if (set(index) != INDEX_FIELDS
                or index["schema"] != SCHEMA
                or index["security_classification"] != CLASSIFICATION
                or index["reviewer_challenge"] != expected_challenge
                or index["source_commit"] != expected_source_commit):
            raise CustodyReviewError("Custody index schema or external pins differ")
        artifacts = index["artifacts"]
        if (not isinstance(artifacts, dict)
                or set(artifacts) != set(ARTIFACT_NAMES)):
            raise CustodyReviewError("Custody inventory must list exactly four artifacts")
        opened = {}
        for label, name in ARTIFACT_NAMES.items():
            item = artifacts[label]
            if (not isinstance(item, dict)
                    or set(item) != {"filename", "sha256"}
                    or item["filename"] != name
                    or not isinstance(item["sha256"], str)
                    or SHA256.fullmatch(item["sha256"]) is None):
                raise CustodyReviewError("Invalid custody artifact entry: " + label)
            blob = receipt_review._read_private_receipt(root / name)
            digest = hashlib.sha256(blob).hexdigest()
            if digest != item["sha256"]:
                raise CustodyReviewError(
                    "Custody artifact differs from pinned index: " + label)
            opened[label] = digest

        # Require full source, receipt, operator and challenge correlation.
        result = handoff.verify_operator_handoff(
            root / ARTIFACT_NAMES["operator_output"],
            root / ARTIFACT_NAMES["receipt"], source_root,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            expected_receipt_sha256=opened["receipt"],
            expected_operator_sha256=opened["operator_output"],
            require_readonly_source_view=require_readonly_source_view)
        if (result.get("status") != "LOCAL_OPERATOR_HANDOFF_CORRELATED"
                or result.get("independent_vm_attestation") is not False
                or result.get("native_kernel_execution_independently_verified")
                   is not False):
            raise CustodyReviewError("Underlying handoff did not pass local checks")

        # Re-read the entire private package. This detects lasting mutation
        # during review; it is not a filesystem snapshot or protection from
        # a hostile same-UID actor capable of fast revert/replace.
        for label, name in ARTIFACT_NAMES.items():
            if (hashlib.sha256(receipt_review._read_private_receipt(
                    root / name)).hexdigest() != opened[label]):
                raise CustodyReviewError(
                    "Custody artifact changed during review: " + label)
        if (hashlib.sha256(receipt_review._read_private_receipt(
                index_path)).hexdigest() != expected_custody_sha256):
            raise CustodyReviewError("Custody index changed during review")

        return {
            "schema": SCHEMA,
            "status": "LOCAL_CUSTODY_PACKAGE_CORRELATED",
            "security_classification": CLASSIFICATION,
            "source_commit": expected_source_commit,
            "custody_index_sha256": expected_custody_sha256,
            "artifact_sha256": opened,
            "artifact_count": len(opened),
            "source_files_rechecked": result["source_files_rechecked"],
            "readonly_source_view_verified": result[
                "readonly_source_view_verified"],
            "review_observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "observed_by": "local_reviewer_process_not_external_witness",
            "operator_kernel_log_authenticated": False,
            "operator_cgroup_log_authenticated": False,
            "external_signature_verified": False,
            "native_kernel_execution_independently_verified": False,
            "independent_vm_attestation": False,
            "host_or_git_authenticity_verified": False,
            "windows_binary_executed_by_reviewer": False,
        }
    except (OSError, UnicodeError, ValueError, TypeError, KeyError,
            OverflowError, RecursionError, receipt_review.ReceiptReviewError,
            handoff.HandoffReviewError) as exc:
        raise CustodyReviewError(
            "Custody package unavailable, unsafe or inconsistent") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Review four owner-only local custody files; NOT VM attestation")
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--expected-custody-sha256", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-challenge", required=True)
    parser.add_argument("--require-readonly-source-view", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = verify_custody_index(
            args.private_dir, args.source_root,
            expected_custody_sha256=args.expected_custody_sha256,
            expected_source_commit=args.expected_source_commit,
            expected_challenge=args.expected_challenge,
            require_readonly_source_view=args.require_readonly_source_view)
        print(json.dumps(result, sort_keys=True))
        return 0
    except CustodyReviewError as exc:
        print(json.dumps({
            "status": "REJECTED_LOCAL_CUSTODY_PACKAGE",
            "reason": str(exc),
            "native_kernel_execution_independently_verified": False,
            "independent_vm_attestation": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
