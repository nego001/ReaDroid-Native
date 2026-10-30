#!/usr/bin/env python3
"""PE-S1.60: reviewer-controlled local challenge request and custody correlation.

Issue an unpredictable 256-bit challenge OUTSIDE the operator's Arch guest,
pin the request digest in a separate reviewer-controlled channel, and verify
it against a later local custody index. A digest or correct nonce is NOT a
signature or attestation of a guest, kernel, hypervisor, time, or reviewer.
Never runs Ghidra, PE, cgroups, a VM, shell, networking or subprocesses.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_custody_review as custody
import pe_arch_vm_evidence as evidence
import pe_arch_vm_receipt_verify as receipts
from pe_arch_vm_checkout_pin import COMMIT_SHA
from pe_arch_vm_witness_review import WITNESS_ID
from pe_ghidra_integrity import GHIDRA_RELEASE_SHA256
from pe_nofollow_paths import open_absolute_directory_nofollow

SCHEMA = "negresco_pe_s1_60_reviewer_request_v1"
CLASSIFICATION = "LOCAL_REVIEWER_REQUEST_NOT_VM_ATTESTATION"
ISSUED = "LOCAL_REVIEW_REQUEST_ISSUED_NOT_VM_ATTESTED"
VERIFIED = "LOCAL_REVIEW_REQUEST_PIN_MATCHED_NOT_VM_ATTESTED"
CORRELATED = "LOCAL_REQUEST_AND_CUSTODY_CORRELATED_NOT_VM_ATTESTED"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
NAME = re.compile(r"review-request-[a-zA-Z0-9_-]{1,64}\.json\Z")
FIELDS = frozenset({
    "schema", "security_classification", "source_commit",
    "reviewer_challenge", "reviewer_id", "ghidra_release_sha256",
    "reviewer_local_issued_at_utc_not_attested",
    "independent_vm_attestation", "operator_evidence_accepted",
    "native_seccomp_and_cgroups_verified", "release_authorized",
})
FALSE_FIELDS = (
    "independent_vm_attestation", "operator_evidence_accepted",
    "native_seccomp_and_cgroups_verified", "release_authorized",
)
MAX_BYTES = 8192


class RequestReviewError(RuntimeError):
    """Unsafe, forged or improperly pinned reviewer request."""


def _validate_inputs(commit: str, challenge: str | None,
                     reviewer_id: str, request_hash: str | None = None) -> None:
    if not isinstance(commit, str) or COMMIT_SHA.fullmatch(commit) is None:
        raise RequestReviewError("External full lowercase Git commit required")
    if (not isinstance(reviewer_id, str)
            or WITNESS_ID.fullmatch(reviewer_id) is None):
        raise RequestReviewError("Reviewer identity must be explicit and bounded")
    if challenge is not None:
        try:
            evidence.require_reviewer_challenge(challenge)
        except evidence.AcceptanceReceiptError as exc:
            raise RequestReviewError("Externally retained challenge malformed") from exc
    if request_hash is not None and (
            not isinstance(request_hash, str)
            or HEX64.fullmatch(request_hash) is None):
        raise RequestReviewError("External SHA-256 request pin is required")


def _check_name(path: Path) -> None:
    raw = os.fspath(path)
    if (not path.is_absolute()
            or any(component in ("", ".", "..") for component in raw[1:].split("/"))
            or NAME.fullmatch(path.name) is None):
        raise RequestReviewError("Canonical absolute named reviewer request required")


def _canonical(document: dict) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def issue_request(path: Path, *, expected_source_commit: str,
                  reviewer_id: str) -> dict:
    """Write one reviewer request without overwriting, with fsync durability."""
    _validate_inputs(expected_source_commit, None, reviewer_id)
    destination = Path(path)
    _check_name(destination)
    challenge = secrets.token_hex(32)
    evidence.require_reviewer_challenge(challenge)
    record = {
        "schema": SCHEMA,
        "security_classification": CLASSIFICATION,
        "source_commit": expected_source_commit,
        "reviewer_challenge": challenge,
        "reviewer_id": reviewer_id,
        "ghidra_release_sha256": GHIDRA_RELEASE_SHA256,
        "reviewer_local_issued_at_utc_not_attested":
            datetime.now(timezone.utc).isoformat(),
        "independent_vm_attestation": False,
        "operator_evidence_accepted": False,
        "native_seccomp_and_cgroups_verified": False,
        "release_authorized": False,
    }
    encoded = _canonical(record)
    if len(encoded) > MAX_BYTES:
        raise RequestReviewError("Request exceeded bounded format")
    try:
        with ExitStack() as handles:
            parent_fd = open_absolute_directory_nofollow(
                destination.parent, handles)
            parent = os.fstat(parent_fd)
            if (not stat.S_ISDIR(parent.st_mode)
                    or parent.st_uid != os.geteuid()
                    or stat.S_IMODE(parent.st_mode) != 0o700):
                raise RequestReviewError(
                    "Request parent must be owned 0700 private directory")
            # Cooperating readers see only completed files; non-cooperating
            # readers must still not treat unsigned request bytes as trust.
            evidence._lock_private_receipt_directory(parent_fd, exclusive=True)
            fd = os.open(
                destination.name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
            identity = os.fstat(fd)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.fsync(parent_fd)
            except BaseException:
                # Never remove someone else's replacement under a raced name.
                current = os.stat(
                    destination.name, dir_fd=parent_fd,
                    follow_symlinks=False)
                if ((current.st_dev, current.st_ino) ==
                        (identity.st_dev, identity.st_ino)):
                    os.unlink(destination.name, dir_fd=parent_fd)
                    os.fsync(parent_fd)
                raise
    except (OSError, ValueError, evidence.AcceptanceReceiptError) as exc:
        raise RequestReviewError("Cannot safely publish reviewer request") from exc
    return {
        "status": ISSUED,
        "reviewer_challenge": challenge,
        "source_commit": expected_source_commit,
        "reviewer_id": reviewer_id,
        "request_sha256": hashlib.sha256(encoded).hexdigest(),
        "independent_vm_attestation": False,
        "operator_evidence_accepted": False,
        "release_authorized": False,
    }


def verify_request(path: Path, *, expected_request_sha256: str,
                   expected_source_commit: str,
                   expected_challenge: str, expected_reviewer_id: str) -> dict:
    """Read reviewer-held request twice and require all *external* pins."""
    _validate_inputs(expected_source_commit, expected_challenge,
                     expected_reviewer_id, expected_request_sha256)
    request = Path(path)
    _check_name(request)
    try:
        raw = receipts._read_private_receipt(request)
        if not 0 < len(raw) <= MAX_BYTES:
            raise RequestReviewError("Reviewer request too large or empty")
        if hashlib.sha256(raw).hexdigest() != expected_request_sha256:
            raise RequestReviewError("Request differs from external SHA-256")
        obj = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=receipts._no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                RequestReviewError("Non-finite request JSON")))
        if not isinstance(obj, dict) or set(obj) != FIELDS:
            raise RequestReviewError("Missing or unexpected request fields")
        if (obj["schema"] != SCHEMA
                or obj["security_classification"] != CLASSIFICATION
                or obj["source_commit"] != expected_source_commit
                or obj["reviewer_challenge"] != expected_challenge
                or obj["reviewer_id"] != expected_reviewer_id
                or obj["ghidra_release_sha256"] != GHIDRA_RELEASE_SHA256
                or any(obj[field] is not False for field in FALSE_FIELDS)):
            raise RequestReviewError(
                "Request contradicts external pins or contains VM claims")
        stamp = obj["reviewer_local_issued_at_utc_not_attested"]
        if not isinstance(stamp, str) or not 20 <= len(stamp) <= 64:
            raise RequestReviewError("Malformed untrusted reviewer timestamp")
        time = datetime.fromisoformat(stamp)
        if time.tzinfo is None or time.utcoffset().total_seconds() != 0:
            raise RequestReviewError("Reviewer timestamp must be UTC")
        if receipts._read_private_receipt(request) != raw:
            raise RequestReviewError("Reviewer request changed during checking")
    except (OSError, UnicodeError, TypeError, ValueError, OverflowError,
            RecursionError, receipts.ReceiptReviewError) as exc:
        raise RequestReviewError("Reviewer request missing or unsafe") from exc
    return {
        "status": VERIFIED,
        "source_commit": expected_source_commit,
        "reviewer_challenge": expected_challenge,
        "reviewer_id": expected_reviewer_id,
        "request_sha256": expected_request_sha256,
        "external_request_pin_matched": True,
        "independent_vm_attestation": False,
        "operator_evidence_accepted": False,
        "release_authorized": False,
    }


def correlate_request_custody(
        request: Path, evidence_dir: Path, source_root: Path, *,
        expected_request_sha256: str,
        expected_source_commit: str, expected_challenge: str,
        expected_reviewer_id: str, expected_custody_sha256: str,
        require_readonly_source_view: bool = False) -> dict:
    """Join reviewer-issued challenge and independently pinned LOCAL custody.

    This exercises PE-S1.48's full receipt/operator/source checks; logs
    remain self-reported and this API never grants native VM attestation.
    """
    if (not isinstance(expected_custody_sha256, str)
            or HEX64.fullmatch(expected_custody_sha256) is None
            or type(require_readonly_source_view) is not bool):
        raise RequestReviewError("External custody pin and readonly policy required")
    before = verify_request(
        request, expected_request_sha256=expected_request_sha256,
        expected_source_commit=expected_source_commit,
        expected_challenge=expected_challenge,
        expected_reviewer_id=expected_reviewer_id)
    try:
        evidence_result = custody.verify_custody_index(
            Path(evidence_dir), Path(source_root),
            expected_custody_sha256=expected_custody_sha256,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            require_readonly_source_view=require_readonly_source_view)
        if (not isinstance(evidence_result, dict)
                or evidence_result.get("status") != custody.STATUS
                or evidence_result.get("independent_vm_attestation") is not False
                or evidence_result.get("native_kernel_execution_independently_verified")
                   is not False
                or evidence_result.get("source_files_rechecked") !=
                    len(evidence.SOURCE_FILES)):
            raise RequestReviewError("Local custody validation not proven")
    except custody.CustodyReviewError as exc:
        raise RequestReviewError("Local custody package unsafe") from exc
    after = verify_request(
        request, expected_request_sha256=expected_request_sha256,
        expected_source_commit=expected_source_commit,
        expected_challenge=expected_challenge,
        expected_reviewer_id=expected_reviewer_id)
    if before != after:
        raise RequestReviewError("Reviewer request changed during custody check")
    return {
        "status": CORRELATED,
        "source_commit": expected_source_commit,
        "reviewer_id": expected_reviewer_id,
        "reviewer_challenge_correlated": True,
        "external_request_sha256_pin_matched": True,
        "external_custody_sha256_pin_matched": True,
        "source_files_rechecked": len(evidence.SOURCE_FILES),
        "readonly_source_view_verified": require_readonly_source_view,
        "independent_vm_attestation": False,
        "native_kernel_execution_independently_verified": False,
        "operator_logs_authenticated": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    issue = modes.add_parser("issue")
    issue.add_argument("--output", required=True, type=Path)
    issue.add_argument("--expected-source-commit", required=True)
    issue.add_argument("--reviewer-id", required=True)
    common = [
        ("--request", dict(required=True, type=Path)),
        ("--expected-request-sha256", dict(required=True)),
        ("--expected-source-commit", dict(required=True)),
        ("--expected-challenge", dict(required=True)),
        ("--expected-reviewer-id", dict(required=True)),
    ]
    for name in ("verify", "correlate"):
        cmd = modes.add_parser(name)
        for flag, options in common:
            cmd.add_argument(flag, **options)
        if name == "correlate":
            cmd.add_argument("--private-dir", required=True, type=Path)
            cmd.add_argument("--source-root", required=True, type=Path)
            cmd.add_argument("--expected-custody-sha256", required=True)
            cmd.add_argument("--require-readonly-source-view",
                             action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.mode == "issue":
            result = issue_request(
                args.output, expected_source_commit=args.expected_source_commit,
                reviewer_id=args.reviewer_id)
        else:
            kwargs = {
                "expected_request_sha256": args.expected_request_sha256,
                "expected_source_commit": args.expected_source_commit,
                "expected_challenge": args.expected_challenge,
                "expected_reviewer_id": args.expected_reviewer_id,
            }
            if args.mode == "verify":
                result = verify_request(args.request, **kwargs)
            else:
                result = correlate_request_custody(
                    args.request, args.private_dir, args.source_root,
                    expected_custody_sha256=args.expected_custody_sha256,
                    require_readonly_source_view=args.require_readonly_source_view,
                    **kwargs)
        print(json.dumps(result, sort_keys=True))
        return 0
    except RequestReviewError as exc:
        print(json.dumps({
            "status": "REJECTED_PE_S1_60_LOCAL_REQUEST_OR_CUSTODY",
            "reason": str(exc),
            "independent_vm_attestation": False,
            "operator_evidence_accepted": False,
            "release_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
