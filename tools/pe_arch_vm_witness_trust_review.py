#!/usr/bin/env python3
"""PE-S1.50: pinned reviewer trust decision for a custody witness SSH key.

This is a *local key lifecycle policy*, not a certificate, OCSP, timestamp,
kernel evidence or VM attestation. Its SHA-256 and signing key fingerprints
must be retained independently by the reviewer, before reviewing a handoff.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_receipt_verify as receipt_review
import pe_arch_vm_witness_review as witness

SCHEMA = "negresco_pe_s1_50_reviewer_witness_trust_v1"
CLASSIFICATION = "EXTERNAL_REVIEWER_PINNED_KEY_LIFECYCLE_NOT_VM_ATTESTATION"
TRUST_FILENAME = "reviewer-witness-trust-policy.json"
FIELDS = frozenset({
    "schema", "security_classification", "witness_id", "signature_namespace",
    "policy_revision", "decision", "active_public_key_sha256",
    "revoked_public_key_sha256",
})
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class TrustReviewError(RuntimeError):
    """The independent reviewer's key lifecycle policy rejected this key."""


def _public_key_blob(signers: bytes, expected_id: str) -> bytes:
    try:
        signer_line = signers.decode("ascii")
    except UnicodeError as exc:
        raise TrustReviewError("Trusted signer entry must be ASCII") from exc
    match = witness.ALLOWED_SIGNER.fullmatch(signer_line)
    if match is None or match.group(1) != expected_id:
        raise TrustReviewError("Expected one exact Ed25519 witness principal")
    try:
        binary = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise TrustReviewError("Invalid Ed25519 public key encoding") from exc
    # SSH wire format: string("ssh-ed25519") followed by string(32-byte key).
    if (len(binary) != 51
            or binary[:15] != b"\x00\x00\x00\x0bssh-ed25519"
            or binary[15:19] != b"\x00\x00\x00\x20"):
        raise TrustReviewError("Expected an Ed25519 SSH wire-format public key")
    return binary


def _read_policy(raw: bytes, *, witness_id: str,
                 expected_policy_revision: int,
                 expected_key_sha256: str) -> dict:
    try:
        policy = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=receipt_review._no_duplicate_keys,
            parse_constant=lambda val: (_ for _ in ()).throw(
                TrustReviewError("Nonfinite value in witness trust policy")))
    except (UnicodeError, ValueError, TypeError, RecursionError,
            OverflowError) as exc:
        raise TrustReviewError("Invalid witness trust policy JSON") from exc
    if (not isinstance(policy, dict) or set(policy) != FIELDS
            or policy["schema"] != SCHEMA
            or policy["security_classification"] != CLASSIFICATION
            or policy["witness_id"] != witness_id
            or policy["signature_namespace"] != witness.NAMESPACE
            or type(policy["policy_revision"]) is not int
            or policy["policy_revision"] != expected_policy_revision
            or policy["active_public_key_sha256"] != expected_key_sha256
            or policy["decision"] not in ("ACTIVE", "SUSPENDED", "REVOKED")):
        raise TrustReviewError(
            "Reviewer trust policy fields, revision or key do not match")
    revoked = policy["revoked_public_key_sha256"]
    if (not isinstance(revoked, list) or len(revoked) > 64
            or any(not isinstance(digest, str)
                   or HEX64.fullmatch(digest) is None for digest in revoked)
            or revoked != sorted(set(revoked))):
        raise TrustReviewError(
            "Revoked key list must be sorted, unique and bounded SHA-256s")
    if (policy["decision"] != "ACTIVE"
            or expected_key_sha256 in revoked):
        raise TrustReviewError(
            "Witness public key is suspended or revoked by reviewer policy")
    return policy


def verify_trusted_witness(
        private_dir: Path, source_root: Path, *,
        expected_policy_sha256: str, expected_policy_revision: int,
        expected_custody_sha256: str, expected_statement_sha256: str,
        expected_signature_sha256: str, expected_signers_sha256: str,
        expected_source_commit: str, expected_challenge: str,
        expected_witness_id: str,
        require_readonly_source_view: bool = False) -> dict:
    """Require externally pinned, ACTIVE non-revoked key before PE-S1.49.

    Revision is independently supplied to expose a stale/rolled-back policy
    IF the reviewer knows a later revision. SHA-256 alone has no authoritative
    version, timestamp, revocation feed or anti-rollback guarantee.
    """
    if (not isinstance(expected_policy_sha256, str)
            or HEX64.fullmatch(expected_policy_sha256) is None):
        raise TrustReviewError("External reviewer trust policy SHA-256 required")
    if (type(expected_policy_revision) is not int
            or not 1 <= expected_policy_revision <= 1000000000):
        raise TrustReviewError("Reviewer-selected positive policy revision required")
    if (not isinstance(expected_witness_id, str)
            or witness.WITNESS_ID.fullmatch(expected_witness_id) is None):
        raise TrustReviewError("Externally selected safe witness identity required")
    if (not isinstance(expected_signers_sha256, str)
            or HEX64.fullmatch(expected_signers_sha256) is None):
        raise TrustReviewError("External signers SHA-256 required")
    if type(require_readonly_source_view) is not bool:
        raise TrustReviewError("Readonly mount policy must be boolean")
    root = Path(private_dir)
    if (not root.is_absolute() or root.name in ("", ".", "..")
            or any(part in ("", ".", "..") for part in root.parts[1:])):
        raise TrustReviewError("Canonical absolute reviewer private dir required")

    try:
        policy_bytes = receipt_review._read_private_receipt(
            root / TRUST_FILENAME)
        if hashlib.sha256(policy_bytes).hexdigest() != expected_policy_sha256:
            raise TrustReviewError(
                "Reviewer trust policy differs from external SHA-256")
        allowed_bytes = receipt_review._read_private_receipt(
            root / witness.FILES["allowed_signers"])
        if hashlib.sha256(allowed_bytes).hexdigest() != expected_signers_sha256:
            raise TrustReviewError(
                "Trusted witness signers file differs from external SHA-256")
        key_blob = _public_key_blob(allowed_bytes, expected_witness_id)
        key_sha256 = hashlib.sha256(key_blob).hexdigest()
        policy = _read_policy(
            policy_bytes, witness_id=expected_witness_id,
            expected_policy_revision=expected_policy_revision,
            expected_key_sha256=key_sha256)

        result = witness.verify_witness_ack(
            root, source_root,
            expected_custody_sha256=expected_custody_sha256,
            expected_statement_sha256=expected_statement_sha256,
            expected_signature_sha256=expected_signature_sha256,
            expected_signers_sha256=expected_signers_sha256,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            expected_witness_id=expected_witness_id,
            require_readonly_source_view=require_readonly_source_view)
        if (result.get("status")
                != "SIGNED_CUSTODY_ACKNOWLEDGEMENT_VERIFIED"
                or result.get("independent_vm_attestation") is not False
                or result.get("witness_time_independently_verified") is not False):
            raise TrustReviewError("Witness signature or custody review rejected")

        # Detect persistent changes to trust material during source review.
        if (receipt_review._read_private_receipt(
                root / TRUST_FILENAME) != policy_bytes
                or receipt_review._read_private_receipt(
                    root / witness.FILES["allowed_signers"]) != allowed_bytes):
            raise TrustReviewError(
                "Reviewer trust policy or signing key changed during review")
        return {
            "status": "REVIEWER_PINNED_WITNESS_KEY_ACTIVE",
            "security_classification": CLASSIFICATION,
            "policy_schema": SCHEMA,
            "policy_revision": policy["policy_revision"],
            "external_policy_sha256_matched": True,
            "externally_selected_policy_revision_matched": True,
            "active_public_key_sha256": key_sha256,
            "revoked_key_count": len(policy["revoked_public_key_sha256"]),
            "witness_signature_verified": True,
            "custody_correlated_locally": True,
            "source_files_rechecked": result["source_files_rechecked"],
            "readonly_source_view_verified": result[
                "readonly_source_view_verified"],
            "revocation_status_independently_fetched": False,
            "policy_time_independently_verified": False,
            "guest_logs_authenticated": False,
            "independent_vm_attestation": False,
            "native_kernel_execution_independently_verified": False,
            "host_or_git_authenticity_verified": False,
            "windows_binary_executed_by_reviewer": False,
        }
    except (OSError, UnicodeError, ValueError, TypeError, KeyError,
            OverflowError, RecursionError, witness.WitnessReviewError,
            receipt_review.ReceiptReviewError) as exc:
        raise TrustReviewError(
            "Witness key trust status unavailable, unsafe or inconsistent") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Require pinned active witness key; does NOT attest a VM")
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--expected-policy-sha256", required=True)
    parser.add_argument("--expected-policy-revision", type=int, required=True)
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
        review = verify_trusted_witness(
            args.private_dir, args.source_root,
            expected_policy_sha256=args.expected_policy_sha256,
            expected_policy_revision=args.expected_policy_revision,
            expected_custody_sha256=args.expected_custody_sha256,
            expected_statement_sha256=args.expected_statement_sha256,
            expected_signature_sha256=args.expected_signature_sha256,
            expected_signers_sha256=args.expected_signers_sha256,
            expected_source_commit=args.expected_source_commit,
            expected_challenge=args.expected_challenge,
            expected_witness_id=args.expected_witness_id,
            require_readonly_source_view=args.require_readonly_source_view)
        print(json.dumps(review, sort_keys=True))
        return 0
    except TrustReviewError as exc:
        print(json.dumps({
            "status": "REJECTED_WITNESS_KEY_TRUST",
            "reason": str(exc),
            "native_kernel_execution_independently_verified": False,
            "independent_vm_attestation": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
