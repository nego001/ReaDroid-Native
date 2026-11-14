#!/usr/bin/env python3
"""PE-S1.51: two-key reviewer authorization of a witness trust policy.

Reviewer signs EXACT PE-S1.50 policy bytes in a separate OpenSSH namespace.
A DIFFERENT witness key signs the PE-S1.49 custody acknowledgement.
The reviewer's independently pinned public key, signature, identity, policy
digest and policy revision are mandatory. Neither signature attests a VM.
No guest programs, Windows binaries, network services or key generation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_receipt_verify as receipt_review
import pe_arch_vm_witness_review as witness
import pe_arch_vm_witness_trust_review as trust

NAMESPACE = "negresco-pe-s1-51-reviewer-trust-policy"
REVIEWER_SIGNERS = "reviewer-policy-allowed-signers"
REVIEWER_SIGNATURE = "reviewer-witness-trust-policy.sig"
CLASSIFICATION = "DUAL_SIGNED_REVIEWER_POLICY_AND_WITNESS_CUSTODY_NOT_VM_ATTESTATION"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class DualControlError(RuntimeError):
    """Reviewer/witness dual-control trust prerequisite not satisfied."""


def verify_dual_control(
        private_dir: Path, source_root: Path, *,
        expected_policy_sha256: str, expected_policy_revision: int,
        expected_reviewer_signers_sha256: str,
        expected_reviewer_signature_sha256: str,
        expected_reviewer_id: str,
        expected_custody_sha256: str, expected_statement_sha256: str,
        expected_signature_sha256: str, expected_signers_sha256: str,
        expected_source_commit: str, expected_challenge: str,
        expected_witness_id: str,
        require_readonly_source_view: bool = False) -> dict:
    """Require two distinct external trust anchors, then full PE-S1.50.

    Out-of-band pins must be retained BEFORE receiving evidence. A self-pinned
    reviewer key would only amount to self-authorization. A malicious reviewer
    and witness could collude; even honest signatures are not VM attestation.
    """
    for name, value in (
            ("policy", expected_policy_sha256),
            ("reviewer key", expected_reviewer_signers_sha256),
            ("reviewer signature", expected_reviewer_signature_sha256),
            ("witness key", expected_signers_sha256)):
        if not isinstance(value, str) or HEX64.fullmatch(value) is None:
            raise DualControlError("External lowercase SHA-256 required: " + name)
    if (type(expected_policy_revision) is not int
            or not 1 <= expected_policy_revision <= 1000000000):
        raise DualControlError("Externally pinned positive policy revision required")
    for name, ident in (("reviewer", expected_reviewer_id),
                        ("witness", expected_witness_id)):
        if (not isinstance(ident, str)
                or witness.WITNESS_ID.fullmatch(ident) is None):
            raise DualControlError("Invalid independently selected " + name + " ID")
    if expected_reviewer_id == expected_witness_id:
        raise DualControlError("Reviewer and witness identities must differ")
    if type(require_readonly_source_view) is not bool:
        raise DualControlError("Readonly source policy must be boolean")
    root = Path(private_dir)
    if (not root.is_absolute() or root.name in ("", ".", "..")
            or any(part in ("", ".", "..") for part in root.parts[1:])):
        raise DualControlError("Canonical absolute reviewer directory required")

    try:
        # Owner-only files, no symlinks, no hardlink aliases, bounded by the
        # established private receipt reader. Do not treat untrusted file
        # paths as Python code or shell commands.
        policy_raw = receipt_review._read_private_receipt(
            root / trust.TRUST_FILENAME)
        reviewer_signers = receipt_review._read_private_receipt(
            root / REVIEWER_SIGNERS)
        reviewer_signature = receipt_review._read_private_receipt(
            root / REVIEWER_SIGNATURE)
        witness_signers = receipt_review._read_private_receipt(
            root / witness.FILES["allowed_signers"])
        for label, raw, pin in (
                ("policy", policy_raw, expected_policy_sha256),
                ("reviewer key", reviewer_signers, expected_reviewer_signers_sha256),
                ("reviewer signature", reviewer_signature,
                 expected_reviewer_signature_sha256),
                ("witness key", witness_signers, expected_signers_sha256)):
            if hashlib.sha256(raw).hexdigest() != pin:
                raise DualControlError(
                    "Reviewer-pinned dual-control file differs: " + label)

        # Fully parse key wire formats; not merely comparing their text
        # representations, principal names, or file SHA-256 values.
        reviewer_key_blob = trust._public_key_blob(
            reviewer_signers, expected_reviewer_id)
        witness_key_blob = trust._public_key_blob(
            witness_signers, expected_witness_id)
        if reviewer_key_blob == witness_key_blob:
            raise DualControlError(
                "Reviewer must not approve witness policy with same public key")
        # A valid reviewer policy signature must use a distinct namespace.
        # Reusing the witness custody signature does not authorize a policy.
        witness._ssh_verify(
            policy_raw, reviewer_signature, reviewer_signers,
            expected_reviewer_id, namespace=NAMESPACE)

        result = trust.verify_trusted_witness(
            root, source_root,
            expected_policy_sha256=expected_policy_sha256,
            expected_policy_revision=expected_policy_revision,
            expected_custody_sha256=expected_custody_sha256,
            expected_statement_sha256=expected_statement_sha256,
            expected_signature_sha256=expected_signature_sha256,
            expected_signers_sha256=expected_signers_sha256,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            expected_witness_id=expected_witness_id,
            require_readonly_source_view=require_readonly_source_view)
        if (result.get("status") != "REVIEWER_PINNED_WITNESS_KEY_ACTIVE"
                or result.get("independent_vm_attestation") is not False
                or result.get("native_kernel_execution_independently_verified")
                   is not False or result.get("witness_signature_verified")
                   is not True):
            raise DualControlError("Signed policy or witness custody not validated")

        # Detect persistent replacement of any of the four trust files
        # after expensive source verification. This is not atomic snapshot.
        for label, name, original in (
                ("policy", trust.TRUST_FILENAME, policy_raw),
                ("reviewer key", REVIEWER_SIGNERS, reviewer_signers),
                ("reviewer signature", REVIEWER_SIGNATURE, reviewer_signature),
                ("witness key", witness.FILES["allowed_signers"], witness_signers)):
            if receipt_review._read_private_receipt(root / name) != original:
                raise DualControlError(
                    "Dual-control file changed during review: " + label)
        return {
            "status": "DUAL_CONTROL_CUSTODY_AUTHORIZATION_VERIFIED",
            "security_classification": CLASSIFICATION,
            "reviewer_id": expected_reviewer_id,
            "witness_id": expected_witness_id,
            "reviewer_policy_namespace": NAMESPACE,
            "witness_custody_namespace": witness.NAMESPACE,
            "policy_revision": result["policy_revision"],
            "policy_sha256": expected_policy_sha256,
            "reviewer_signature_sha256": expected_reviewer_signature_sha256,
            "reviewer_signers_sha256": expected_reviewer_signers_sha256,
            "witness_signers_sha256": expected_signers_sha256,
            "reviewer_and_witness_keys_distinct": True,
            "reviewer_policy_signature_verified": True,
            "witness_custody_signature_verified": True,
            "custody_correlated_locally": True,
            "source_files_rechecked": result["source_files_rechecked"],
            "readonly_source_view_verified": result[
                "readonly_source_view_verified"],
            "independent_reviewer_identity_verified": False,
            "independent_vm_attestation": False,
            "native_kernel_execution_independently_verified": False,
            "guest_logs_authenticated": False,
            "reviewer_timestamp_independently_verified": False,
            "revocation_status_independently_fetched": False,
            "host_or_git_authenticity_verified": False,
            "windows_binary_executed_by_reviewer": False,
        }
    except (OSError, UnicodeError, ValueError, TypeError, KeyError,
            RecursionError, OverflowError, witness.WitnessReviewError,
            trust.TrustReviewError, receipt_review.ReceiptReviewError) as exc:
        raise DualControlError(
            "Dual-control review unavailable, unsafe or inconsistent") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Two independent key signatures on policy/custody; NOT VM attestation")
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--expected-policy-sha256", required=True)
    parser.add_argument("--expected-policy-revision", type=int, required=True)
    parser.add_argument("--expected-reviewer-signers-sha256", required=True)
    parser.add_argument("--expected-reviewer-signature-sha256", required=True)
    parser.add_argument("--expected-reviewer-id", required=True)
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
        report = verify_dual_control(
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
        print(json.dumps(report, sort_keys=True))
        return 0
    except DualControlError as exc:
        print(json.dumps({
            "status": "REJECTED_DUAL_CONTROL_CUSTODY_AUTHORIZATION",
            "reason": str(exc),
            "independent_vm_attestation": False,
            "native_kernel_execution_independently_verified": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
