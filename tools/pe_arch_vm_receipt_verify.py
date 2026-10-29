#!/usr/bin/env python3
"""PE-S1.20: independently re-check a LOCAL unsigned Arch VM receipt.

This is only an offline consistency and source-integrity check. The hashes
are unkeyed and the report is self-asserted: a passing verification DOES NOT
prove a real VM, kernel enforcement, hypervisor identity or authorship.
Never starts a Windows program, Ghidra, systemd scope or network client.
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
import stat
import sys

import pe_arch_vm_evidence as evidence
from pe_nofollow_paths import open_absolute_directory_nofollow

MAX_RECEIPT_BYTES = 1024 * 1024
RECEIPT_SCHEMA = "negresco_native_arch_vm_local_receipt_v2"
RECEIPT_FIELDS = frozenset({
    "schema", "recorded_at_utc", "security_classification",
    "report_sha256", "source_file_hashes", "native_acceptance_report",
    "windows_executable_launched", "reviewer_challenge",
})
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class ReceiptReviewError(RuntimeError):
    """Review denied without claiming native execution."""


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptReviewError("Duplicate JSON key in local receipt")
        result[key] = value
    return result


def _unchanged_name_entry(descriptor: os.stat_result,
                          entry: os.stat_result) -> bool:
    """Require the directory entry to still name the opened inode."""
    fields = ("st_dev", "st_ino", "st_mode", "st_uid", "st_nlink",
              "st_size", "st_mtime_ns", "st_ctime_ns")
    return all(getattr(descriptor, key) == getattr(entry, key)
               for key in fields)


def _read_private_receipt(path: Path) -> bytes:
    if not path.is_absolute() or path.name in ("", ".", ".."):
        raise ReceiptReviewError("Absolute private receipt path required")
    if evidence.STAGE_PATTERN.fullmatch(path.name) is not None:
        raise ReceiptReviewError(
            "Unpublished temporary stage is not a final receipt")
    # O_NONBLOCK ensures a substituted FIFO cannot hang before fstat
    # checks that the receipt or manifest source is a regular file.
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    with ExitStack() as stack:
        parent_fd = open_absolute_directory_nofollow(path.parent, stack)
        directory = os.fstat(parent_fd)
        if (not stat.S_ISDIR(directory.st_mode)
                or directory.st_uid != os.geteuid()
                or directory.st_mode & 0o077):
            raise ReceiptReviewError("Receipt directory is not owner-only")
        # Cooperate with the writer's exclusive directory flock: a reader
        # must not attest an entry published before directory fsync (or
        # while the writer is still rolling back a failed publication).
        evidence._lock_private_receipt_directory(
            parent_fd, exclusive=False)
        fd = os.open(path.name, flags, dir_fd=parent_fd)
        stack.callback(os.close, fd)
        before = os.fstat(fd)
        opened_entry = os.stat(
            path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (not _unchanged_name_entry(before, opened_entry)
                or not stat.S_ISREG(before.st_mode)
                or before.st_uid != os.geteuid()
                or before.st_mode & 0o077
                # The atomic writer unlinks its staging name before
                # releasing the directory lock; published receipts have one
                # link. Extra hardlinks can expose the inode outside the
                # private directory without changing its mode or digest.
                or before.st_nlink != 1
                or not 1 <= before.st_size <= MAX_RECEIPT_BYTES):
            raise ReceiptReviewError("Receipt owner/mode/length unsafe")
        # Actual descriptor is pinned; compare source and resulting metadata.
        raw = os.read(fd, MAX_RECEIPT_BYTES + 1)
        after = os.fstat(fd)
        current_entry = os.stat(
            path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (len(raw) != before.st_size
                or not _unchanged_name_entry(before, after)
                or not _unchanged_name_entry(before, current_entry)):
            raise ReceiptReviewError(
                "Receipt name or inode changed during read")
        return raw


def _read_source(source_root: Path, relative: str) -> bytes:
    parts = relative.split("/")
    if (not relative or relative.startswith("/")
            or any(part in (".", "..", "") for part in parts)):
        raise ReceiptReviewError("Invalid source manifest path")
    # O_NONBLOCK ensures a substituted FIFO cannot hang before fstat
    # checks that the receipt or manifest source is a regular file.
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    with ExitStack() as stack:
        root_fd = open_absolute_directory_nofollow(source_root, stack)
        directory_fd = root_fd
        # The descriptor alone is not enough: a directory can be renamed
        # after open, leaving us reading a detached source tree. Pin each
        # name to its parent and require a stable entry throughout the read.
        directory_chain = []
        for part in parts[:-1]:
            named_before = os.stat(
                part, dir_fd=directory_fd, follow_symlinks=False)
            fd = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory_fd)
            stack.callback(os.close, fd)
            opened = os.fstat(fd)
            named_after = os.stat(
                part, dir_fd=directory_fd, follow_symlinks=False)
            if (not stat.S_ISDIR(opened.st_mode)
                    or not _unchanged_name_entry(opened, named_before)
                    or not _unchanged_name_entry(opened, named_after)):
                raise ReceiptReviewError(
                    "Source directory name or inode changed during open")
            directory_chain.append((directory_fd, part, fd, opened))
            directory_fd = fd
        fd = os.open(parts[-1], flags, dir_fd=directory_fd)
        stack.callback(os.close, fd)
        before = os.fstat(fd)
        opened_entry = os.stat(
            parts[-1], dir_fd=directory_fd, follow_symlinks=False)
        if (not _unchanged_name_entry(before, opened_entry)
                or not stat.S_ISREG(before.st_mode)
                or not 1 <= before.st_size <= evidence.MAX_SOURCE_BYTES):
            raise ReceiptReviewError("Source file missing/oversized")
        raw = os.read(fd, evidence.MAX_SOURCE_BYTES + 1)
        after = os.fstat(fd)
        current_entry = os.stat(
            parts[-1], dir_fd=directory_fd, follow_symlinks=False)
        if (len(raw) != before.st_size
                or not _unchanged_name_entry(before, after)
                or not _unchanged_name_entry(before, current_entry)):
            raise ReceiptReviewError(
                "Source name or inode changed during verification")
        for parent_fd, component, opened_fd, initial in directory_chain:
            current = os.fstat(opened_fd)
            named = os.stat(
                component, dir_fd=parent_fd, follow_symlinks=False)
            if (not _unchanged_name_entry(initial, current)
                    or not _unchanged_name_entry(initial, named)):
                raise ReceiptReviewError(
                    "Source directory name or inode changed during read")
        return raw


def verify_local_receipt(receipt: Path, source_root: Path, *,
                         expected_challenge: str,
                         expected_receipt_sha256: str | None = None) -> dict:
    """Correlate the unsigned receipt with a prior challenge and optional pin.

    An expected digest must come from an independently retained earlier
    observation. The self-reported digest alone is not authenticated.
    """
    try:
        evidence.require_reviewer_challenge(expected_challenge)
        if (expected_receipt_sha256 is not None
                and (not isinstance(expected_receipt_sha256, str)
                     or HEX64.fullmatch(expected_receipt_sha256) is None)):
            raise ReceiptReviewError(
                "Expected receipt SHA-256 must be 64 lowercase hex digits")
        raw = _read_private_receipt(Path(receipt))
        observed_receipt_sha256 = hashlib.sha256(raw).hexdigest()
        if (expected_receipt_sha256 is not None
                and observed_receipt_sha256 != expected_receipt_sha256):
            raise ReceiptReviewError(
                "Receipt differs from independently retained SHA-256")
        record = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=lambda x: (_ for _ in ()).throw(
                ReceiptReviewError("Non-finite JSON constant")))
        if (not isinstance(record, dict)
                or set(record) != RECEIPT_FIELDS
                or record["schema"] != RECEIPT_SCHEMA
                or record["security_classification"] != "LOCAL_SELF_REPORT_NOT_SIGNED"
                or record["windows_executable_launched"] is not False):
            raise ReceiptReviewError("Unexpected receipt schema or security claims")

        challenge = record["reviewer_challenge"]
        evidence.require_reviewer_challenge(challenge)
        if challenge != expected_challenge:
            raise ReceiptReviewError(
                "Receipt does not match externally supplied reviewer challenge")

        stamp = record["recorded_at_utc"]
        if not isinstance(stamp, str) or len(stamp) > 64:
            raise ReceiptReviewError("Invalid recorded_at_utc")
        date = datetime.fromisoformat(stamp)
        if date.tzinfo is None or date.utcoffset().total_seconds() != 0:
            raise ReceiptReviewError("Receipt timestamp is not UTC")

        report = record["native_acceptance_report"]
        evidence.validate_native_acceptance_report(report)
        report_bytes = evidence._canonical(report)
        digest = record["report_sha256"]
        if (not isinstance(digest, str) or not HEX64.fullmatch(digest)
                or len(report_bytes) > evidence.MAX_REPORT_BYTES
                or hashlib.sha256(report_bytes).hexdigest() != digest):
            raise ReceiptReviewError("Receipt report digest mismatch")

        manifest = record["source_file_hashes"]
        if (not isinstance(manifest, dict)
                or set(manifest) != set(evidence.SOURCE_FILES)):
            raise ReceiptReviewError("Source manifest missing or altered")
        for relative in evidence.SOURCE_FILES:
            entry = manifest[relative]
            if (not isinstance(entry, dict)
                    or set(entry) != {"sha256", "bytes"}
                    or type(entry["bytes"]) is not int
                    or not 1 <= entry["bytes"] <= evidence.MAX_SOURCE_BYTES
                    or not isinstance(entry["sha256"], str)
                    or not HEX64.fullmatch(entry["sha256"])):
                raise ReceiptReviewError("Invalid source manifest entry")
            content = _read_source(Path(source_root), relative)
            if (len(content) != entry["bytes"]
                    or hashlib.sha256(content).hexdigest() != entry["sha256"]):
                raise ReceiptReviewError(
                    "Source does not match original acceptance: " + relative)
        return {
            "status": "LOCAL_RECEIPT_CONSISTENCY_VALIDATED",
            "security_classification": "UNSIGNED_NOT_INDEPENDENT_VM_ATTESTATION",
            "source_files_rechecked": len(evidence.SOURCE_FILES),
            "report_sha256": digest,
            "receipt_sha256": observed_receipt_sha256,
            "external_receipt_sha256_pin_matched": (
                expected_receipt_sha256 is not None),
            "native_kernel_execution_independently_verified": False,
            "windows_binary_executed_by_reviewer": False,
            "reviewer_challenge_correlated": True,
            "independent_vm_attestation": False,
        }
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError,
            OverflowError, evidence.AcceptanceReceiptError) as exc:
        raise ReceiptReviewError("Receipt unavailable, unsafe or inconsistent") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline consistency check; NOT signed native VM attestation")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True,
                        help="Exact source checkout used during VM acceptance")
    parser.add_argument("--expected-challenge", required=True,
                        help="Original random 64-hex token supplied by an outside reviewer")
    parser.add_argument(
        "--expected-receipt-sha256",
        help="Optional exact lowercase SHA-256 retained outside the receipt "
             "BEFORE this review; detects later replacements, not a signature")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(
            verify_local_receipt(
                args.receipt, args.source_root,
                expected_challenge=args.expected_challenge,
                expected_receipt_sha256=args.expected_receipt_sha256),
            sort_keys=True))
        return 0
    except ReceiptReviewError as exc:
        print(json.dumps({
            "status": "REJECTED_LOCAL_RECEIPT",
            "reason": str(exc),
            "native_kernel_execution_independently_verified": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
