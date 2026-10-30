#!/usr/bin/env python3
"""PE-S1.49: verify a detached SSH witness acknowledgement of local custody.

The verifier authenticates a detached SSH signature against a reviewer-pinned
allowed_signers key, NOT a hypervisor, kernel, VM, guest telemetry, or time.
All records are unsigned operator data unless an independently trusted human
witness actually signs this narrowly scoped custody acknowledgement.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

import pe_arch_vm_custody_review as custody
import pe_arch_vm_receipt_verify as receipt_review
from pe_arch_vm_checkout_pin import COMMIT_SHA

SCHEMA = "negresco_pe_s1_49_witness_custody_ack_v1"
CLASSIFICATION = "SIGNED_CUSTODY_ACKNOWLEDGEMENT_NOT_VM_ATTESTATION"
NAMESPACE = "negresco-pe-s1-49-custody"
FILES = {
    "statement": "witness-statement.json",
    "signature": "witness-statement.sig",
    "allowed_signers": "witness-allowed-signers",
}
FIELDS = frozenset({
    "schema", "security_classification", "witness_id",
    "source_commit", "reviewer_challenge", "custody_index_sha256",
    "acknowledgement_utc", "vm_attestation_claimed",
})
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
WITNESS_ID = re.compile(r"[A-Za-z0-9._@+-]{1,80}\Z")
ALLOWED_SIGNER = re.compile(
    r"([A-Za-z0-9._@+-]{1,80}) ssh-ed25519 ([A-Za-z0-9+/=]{40,200})\n?\Z")


class WitnessReviewError(RuntimeError):
    """Signed custody acknowledgement is unsafe or not independently pinned."""


def _check_hash(value: str, description: str) -> None:
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise WitnessReviewError(
            "External lowercase SHA-256 required: " + description)


def _read_pinned(root: Path, name: str, expected: str) -> bytes:
    raw = receipt_review._read_private_receipt(root / name)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise WitnessReviewError(
            "Reviewer-pinned witness file differs: " + name)
    return raw


def _ssh_verify(raw_statement: bytes, raw_signature: bytes,
                trusted_signers: bytes, witness_id: str, *,
                namespace: str = NAMESPACE) -> None:
    """Real detached signature verification with the openSSH client.

    Only the pinned bytes are handed to ssh-keygen, never mutable input
    paths or commands supplied by the operator. Uses a private temporary
    directory outside the source checkout; no network or shell.
    """
    executable = shutil.which("ssh-keygen")
    if not executable or not os.path.isabs(executable):
        raise WitnessReviewError("OpenSSH signature verifier unavailable")
    with tempfile.TemporaryDirectory(prefix="negresco-witness-") as scratch:
        directory = Path(scratch)
        def write_private(name: str, raw: bytes) -> Path:
            dest = directory / name
            fd = os.open(
                dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(raw)
            return dest

        sig = write_private("statement.sig", raw_signature)
        allowed = write_private("allowed_signers", trusted_signers)
        env = {"HOME": scratch, "LC_ALL": "C", "LANG": "C"}
        try:
            result = subprocess.run(
                [executable, "-Y", "verify", "-f", str(allowed),
                 "-I", witness_id, "-n", namespace, "-s", str(sig)],
                input=raw_statement, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=15,
                check=False, close_fds=True, env=env)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WitnessReviewError("OpenSSH signature verification failed") from exc
        if result.returncode != 0:
            raise WitnessReviewError(
                "Witness signature rejected by pinned OpenSSH key")


def verify_witness_ack(
        private_dir: Path, source_root: Path, *,
        expected_custody_sha256: str, expected_statement_sha256: str,
        expected_signature_sha256: str, expected_signers_sha256: str,
        expected_source_commit: str, expected_challenge: str,
        expected_witness_id: str,
        require_readonly_source_view: bool = False) -> dict:
    """Only authenticates authorship of a *custody acknowledgement*.

    All expected pins must be supplied through a reviewer-controlled channel.
    Allowed signers must be provisioned independently of the operator's files.
    A signature over operator data cannot attest the operator's VM/kernel.
    """
    for title, value in (
            ("custody index", expected_custody_sha256),
            ("witness statement", expected_statement_sha256),
            ("witness signature", expected_signature_sha256),
            ("trusted signing key", expected_signers_sha256),
            ("reviewer challenge", expected_challenge)):
        _check_hash(value, title)
    if expected_challenge == "0" * 64:
        raise WitnessReviewError("Reviewer challenge cannot be zero")
    if (not isinstance(expected_source_commit, str)
            or COMMIT_SHA.fullmatch(expected_source_commit) is None):
        raise WitnessReviewError("Externally selected full Git SHA required")
    if (not isinstance(expected_witness_id, str)
            or WITNESS_ID.fullmatch(expected_witness_id) is None):
        raise WitnessReviewError("Safe externally selected witness ID required")
    if type(require_readonly_source_view) is not bool:
        raise WitnessReviewError("Readonly source option must be boolean")
    root = Path(private_dir)
    if (not root.is_absolute() or root.name in ("", ".", "..")
            or any(piece in ("", ".", "..") for piece in root.parts[1:])):
        raise WitnessReviewError("Canonical absolute private directory required")

    try:
        statement_raw = _read_pinned(
            root, FILES["statement"], expected_statement_sha256)
        signature_raw = _read_pinned(
            root, FILES["signature"], expected_signature_sha256)
        signer_raw = _read_pinned(
            root, FILES["allowed_signers"], expected_signers_sha256)
        try:
            statement = json.loads(
                statement_raw.decode("utf-8"),
                object_pairs_hook=receipt_review._no_duplicate_keys,
                parse_constant=lambda val: (_ for _ in ()).throw(
                    WitnessReviewError("Nonfinite witness statement value")))
        except (UnicodeError, ValueError, TypeError, RecursionError,
                OverflowError) as exc:
            raise WitnessReviewError("Invalid signed witness statement JSON") from exc
        if (not isinstance(statement, dict)
                or set(statement) != FIELDS
                or statement["schema"] != SCHEMA
                or statement["security_classification"] != CLASSIFICATION
                or statement["witness_id"] != expected_witness_id
                or statement["source_commit"] != expected_source_commit
                or statement["reviewer_challenge"] != expected_challenge
                or statement["custody_index_sha256"] != expected_custody_sha256
                or statement["vm_attestation_claimed"] is not False):
            raise WitnessReviewError(
                "Witness statement schema, claims or pinned values differ")
        when = statement["acknowledgement_utc"]
        if (not isinstance(when, str) or len(when) > 40
                or not when.endswith("Z")):
            raise WitnessReviewError("Witness claimed UTC timestamp malformed")
        try:
            datetime.fromisoformat(when.replace("Z", "+00:00"))
        except ValueError as exc:
            raise WitnessReviewError("Witness claimed UTC timestamp invalid") from exc
        try:
            allowed_text = signer_raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise WitnessReviewError("Trusted signers must be ASCII") from exc
        matcher = ALLOWED_SIGNER.fullmatch(allowed_text)
        if matcher is None or matcher.group(1) != expected_witness_id:
            raise WitnessReviewError(
                "Only one exact, trusted Ed25519 witness signer allowed")

        # This verifies authorship with an independently pinned public key,
        # not the truth of guest logs. Never accept a missing ssh-keygen.
        _ssh_verify(
            statement_raw, signature_raw, signer_raw, expected_witness_id)

        custody_result = custody.verify_custody_index(
            root, source_root,
            expected_custody_sha256=expected_custody_sha256,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            require_readonly_source_view=require_readonly_source_view)
        if (custody_result.get("status") != "LOCAL_CUSTODY_PACKAGE_CORRELATED"
                or custody_result.get("independent_vm_attestation") is not False
                or custody_result.get("external_signature_verified") is not False):
            raise WitnessReviewError("Underlying custody integrity not accepted")
        # Double check pinned material after the full receipt source review.
        for key, pin in (("statement", expected_statement_sha256),
                         ("signature", expected_signature_sha256),
                         ("allowed_signers", expected_signers_sha256)):
            if _read_pinned(root, FILES[key], pin) != {
                    "statement": statement_raw,
                    "signature": signature_raw,
                    "allowed_signers": signer_raw,
            }[key]:
                raise WitnessReviewError("Witness material changed during review")
        return {
            "status": "SIGNED_CUSTODY_ACKNOWLEDGEMENT_VERIFIED",
            "schema": SCHEMA,
            "security_classification": CLASSIFICATION,
            "witness_id": expected_witness_id,
            "source_commit": expected_source_commit,
            "custody_index_sha256": expected_custody_sha256,
            "witness_statement_sha256": expected_statement_sha256,
            "witness_signature_sha256": expected_signature_sha256,
            "trusted_signers_sha256": expected_signers_sha256,
            "signature_namespace": NAMESPACE,
            "detached_witness_signature_verified": True,
            "trusted_witness_key_pin_matched": True,
            "custody_package_correlated_locally": True,
            "source_files_rechecked": custody_result["source_files_rechecked"],
            "readonly_source_view_verified": custody_result[
                "readonly_source_view_verified"],
            "witness_claimed_at_utc": when,
            "witness_time_independently_verified": False,
            "guest_logs_authenticated": False,
            "native_kernel_execution_independently_verified": False,
            "independent_vm_attestation": False,
            "host_or_git_authenticity_verified": False,
            "windows_binary_executed_by_reviewer": False,
        }
    except (OSError, UnicodeError, ValueError, TypeError, KeyError,
            RecursionError, OverflowError, custody.CustodyReviewError,
            receipt_review.ReceiptReviewError) as exc:
        raise WitnessReviewError(
            "Witness acknowledgement unavailable, unsafe or inconsistent") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify detached witness signature on custody, NOT VM")
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--expected-custody-sha256", required=True)
    parser.add_argument("--expected-statement-sha256", required=True)
    parser.add_argument("--expected-signature-sha256", required=True)
    parser.add_argument("--expected-signers-sha256", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-challenge", required=True)
    parser.add_argument("--expected-witness-id", required=True)
    parser.add_argument("--require-readonly-source-view", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = verify_witness_ack(
            args.private_dir, args.source_root,
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
    except WitnessReviewError as exc:
        print(json.dumps({
            "status": "REJECTED_SIGNED_CUSTODY_ACKNOWLEDGEMENT",
            "reason": str(exc),
            "independent_vm_attestation": False,
            "native_kernel_execution_independently_verified": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
