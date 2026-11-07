#!/usr/bin/env python3
"""PE-S1.63: offline review of separately captured, signed host observations.

A THIRD Ed25519 key, distinct from the custody reviewer and witness keys,
signs four reviewer-side observation file hashes. All public trust roots
and hashes MUST be retained independently of the operator. Signing host
observations verifies a key's authorship, not the physical identity or
independent control of any VM, kernel, hypervisor or sensor. ALWAYS HOLD.
No shell, guest, Ghidra, Windows PE, scope or network execution occurs;
the only child program is OpenSSH ssh-keygen for detached verification.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_receipt_verify as receipts
import pe_arch_vm_witness_review as witness
import pe_arch_vm_witness_trust_review as trust
from pe_arch_vm_checkout_pin import COMMIT_SHA

SCHEMA = "negresco_pe_s1_63_external_observer_pack_v1"
CLASSIFICATION = "THIRD_PARTY_SIGNED_OBSERVATIONS_NOT_VM_ATTESTATION"
NAMESPACE = "negresco-pe-s1-63-external-host-observations"
STATUS = "SIGNED_HOST_OBSERVATION_HASHES_VALID_NOT_VM_ATTESTATION"
REJECTED = "REJECTED_PE_S1_63_UNTRUSTED_EXTERNAL_OBSERVATIONS"
OBS_FILES = {
    "host_vm_launch": "reviewer-host-vm-launch.txt",
    "host_guest_kernel": "reviewer-host-guest-kernel.txt",
    "host_seccomp_cgroups": "reviewer-host-seccomp-cgroups.txt",
    "host_scope_cleanup": "reviewer-host-scope-cleanup.txt",
}
MANIFEST_FILE = "external-observer-manifest.json"
SIGNATURE_FILE = "external-observer-manifest.sig"
SIGNERS_FILE = "external-observer-allowed-signers"
REVIEWER_KEY_FILE = "reviewer-policy-allowed-signers"
WITNESS_KEY_FILE = "witness-allowed-signers"
FIELDS = frozenset({
    "schema", "security_classification", "observer_id", "reviewer_id",
    "witness_id", "source_commit", "reviewer_challenge",
    "request_sha256", "custody_index_sha256", "receipt_sha256",
    "observations", "observer_local_time_utc_not_attested",
    "independent_vm_attestation", "release_authorized",
})
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_LOG_BYTES = 65536
MAX_MANIFEST_BYTES = 8192


class ExternalObserverError(RuntimeError):
    """Not even a consistently signed third-key observation inventory."""


def _pin(value: object, what: str) -> None:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ExternalObserverError("Externally held lowercase SHA256 required: " + what)


def _identity(value: object, what: str) -> None:
    if (not isinstance(value, str)
            or witness.WITNESS_ID.fullmatch(value) is None):
        raise ExternalObserverError("Invalid external identity: " + what)


def _read_pinned(directory: Path, name: str, expected: str) -> bytes:
    data = receipts._read_private_receipt(directory / name)
    if hashlib.sha256(data).hexdigest() != expected:
        raise ExternalObserverError("External pin mismatch: " + name)
    return data


def verify_external_observer(
        observer_dir: Path, custody_dir: Path, *,
        expected_manifest_sha256: str,
        expected_signature_sha256: str,
        expected_observer_signers_sha256: str,
        expected_reviewer_signers_sha256: str,
        expected_witness_signers_sha256: str,
        expected_observer_id: str, expected_reviewer_id: str,
        expected_witness_id: str, expected_source_commit: str,
        expected_challenge: str, expected_request_sha256: str,
        expected_custody_sha256: str,
        expected_receipt_sha256: str) -> dict:
    """Correlate reviewer-held, host-side files with distinct SSH signature.

    This only verifies files and detached signature. A malicious operator
    can fabricate them if the reviewer fails to keep observer keys/capture
    channels outside the operator's control. Do not use for release.
    """
    pins = (
        ("manifest", expected_manifest_sha256),
        ("signature", expected_signature_sha256),
        ("observer key", expected_observer_signers_sha256),
        ("reviewer key", expected_reviewer_signers_sha256),
        ("witness key", expected_witness_signers_sha256),
        ("request", expected_request_sha256),
        ("custody", expected_custody_sha256),
        ("receipt", expected_receipt_sha256),
    )
    for name, pin in pins:
        _pin(pin, name)
    if (not isinstance(expected_source_commit, str)
            or COMMIT_SHA.fullmatch(expected_source_commit) is None
            or expected_source_commit == "0" * 40):
        raise ExternalObserverError("Externally selected full source commit required")
    _pin(expected_challenge, "challenge")
    if expected_challenge == "0" * 64:
        raise ExternalObserverError("Nonzero external reviewer challenge required")
    for name, value in (
            ("observer", expected_observer_id),
            ("reviewer", expected_reviewer_id),
            ("witness", expected_witness_id)):
        _identity(value, name)
    if len({expected_observer_id, expected_reviewer_id,
            expected_witness_id}) != 3:
        raise ExternalObserverError("Three distinct external identities required")

    owner = Path(observer_dir)
    operator = Path(custody_dir)
    if (not owner.is_absolute() or not operator.is_absolute()
            or owner == operator
            or owner in operator.parents or operator in owner.parents
            or any(part in ("", ".", "..") for p in (owner, operator)
                   for part in p.parts[1:])):
        raise ExternalObserverError(
            "Separate canonical absolute observer and operator directories required")
    try:
        raw = _read_pinned(owner, MANIFEST_FILE, expected_manifest_sha256)
        signature = _read_pinned(owner, SIGNATURE_FILE,
                                 expected_signature_sha256)
        observer_key = _read_pinned(owner, SIGNERS_FILE,
                                    expected_observer_signers_sha256)
        reviewer_key = _read_pinned(operator, REVIEWER_KEY_FILE,
                                    expected_reviewer_signers_sha256)
        witness_key = _read_pinned(operator, WITNESS_KEY_FILE,
                                   expected_witness_signers_sha256)
        if not 0 < len(raw) <= MAX_MANIFEST_BYTES:
            raise ExternalObserverError("Observer manifest exceeds bounded size")
        # Enforce three actual distinct Ed25519 public-key blobs, not just
        # separate principal names or differently formatted allowed_signers.
        keys = (
            trust._public_key_blob(observer_key, expected_observer_id),
            trust._public_key_blob(reviewer_key, expected_reviewer_id),
            trust._public_key_blob(witness_key, expected_witness_id),
        )
        if len(set(keys)) != 3:
            raise ExternalObserverError("External observer reused custody signing key")
        record = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=receipts._no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ExternalObserverError("Nonfinite observer manifest")))
        if not isinstance(record, dict) or set(record) != FIELDS:
            raise ExternalObserverError("Unexpected external observer manifest fields")
        if (record["schema"] != SCHEMA
                or record["security_classification"] != CLASSIFICATION
                or record["observer_id"] != expected_observer_id
                or record["reviewer_id"] != expected_reviewer_id
                or record["witness_id"] != expected_witness_id
                or record["source_commit"] != expected_source_commit
                or record["reviewer_challenge"] != expected_challenge
                or record["request_sha256"] != expected_request_sha256
                or record["custody_index_sha256"] != expected_custody_sha256
                or record["receipt_sha256"] != expected_receipt_sha256
                or record["independent_vm_attestation"] is not False
                or record["release_authorized"] is not False):
            raise ExternalObserverError(
                "Observer manifest conflicts with external pins or claims VM proof")
        observed_at = record["observer_local_time_utc_not_attested"]
        if not isinstance(observed_at, str) or not 20 <= len(observed_at) <= 64:
            raise ExternalObserverError("Observer local time malformed")
        stamp = datetime.fromisoformat(observed_at)
        if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
            raise ExternalObserverError("Observer local clock is not UTC")
        entries = record["observations"]
        if not isinstance(entries, dict) or set(entries) != set(OBS_FILES):
            raise ExternalObserverError("Exactly four independent-side logs required")
        contents = {}
        for label, filename in OBS_FILES.items():
            entry = entries[label]
            if (not isinstance(entry, dict)
                    or set(entry) != {"filename", "sha256"}
                    or entry["filename"] != filename):
                raise ExternalObserverError("Unexpected observation entry: " + label)
            _pin(entry["sha256"], label)
            data = receipts._read_private_receipt(owner / filename)
            if not 0 < len(data) <= MAX_LOG_BYTES or b"\0" in data:
                raise ExternalObserverError("Observer host log invalid: " + label)
            # Only structured hashes leave this API, never full host logs.
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ExternalObserverError("Observer log differs: " + label)
            contents[filename] = data

        # Validate a real, namespace-specific detached Ed25519 signature.
        witness._ssh_verify(
            raw, signature, observer_key, expected_observer_id,
            namespace=NAMESPACE)

        # A second read detects lasting replacements during cryptographic
        # verification. This is not a trusted clock or atomic snapshot.
        for name, digest in (
                (MANIFEST_FILE, expected_manifest_sha256),
                (SIGNATURE_FILE, expected_signature_sha256),
                (SIGNERS_FILE, expected_observer_signers_sha256)):
            _read_pinned(owner, name, digest)
        for name, expected in (
                (REVIEWER_KEY_FILE, expected_reviewer_signers_sha256),
                (WITNESS_KEY_FILE, expected_witness_signers_sha256)):
            _read_pinned(operator, name, expected)
        for filename, before in contents.items():
            if receipts._read_private_receipt(owner / filename) != before:
                raise ExternalObserverError(
                    "Observation changed during signature review: " + filename)
    except (OSError, ValueError, UnicodeError, TypeError, KeyError,
            OverflowError, RecursionError, receipts.ReceiptReviewError,
            witness.WitnessReviewError, trust.TrustReviewError) as exc:
        raise ExternalObserverError(
            "External observation package missing, altered or unsafe") from exc

    return {
        "status": STATUS,
        "source_commit": expected_source_commit,
        "reviewer_challenge_correlated": True,
        "request_custody_receipt_pins_correlated": True,
        "external_observer_manifest_sha256": expected_manifest_sha256,
        "external_observer_id": expected_observer_id,
        "distinct_observer_reviewer_witness_ssh_keys_verified": True,
        "external_observer_detached_signature_verified": True,
        "host_observation_file_hashes_matched": True,
        "host_observation_file_count": len(OBS_FILES),
        "observer_clock_independently_verified": False,
        "observer_host_independently_authenticated": False,
        "native_arch_kernel_independently_verified": False,
        "independent_vm_attestation": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate third-party host observation signature; NEVER attest VM")
    parser.add_argument("--observer-dir", type=Path, required=True)
    parser.add_argument("--custody-dir", type=Path, required=True)
    for part in ("manifest-sha256", "signature-sha256",
                 "observer-signers-sha256", "reviewer-signers-sha256",
                 "witness-signers-sha256", "observer-id", "reviewer-id",
                 "witness-id", "source-commit", "challenge", "request-sha256",
                 "custody-sha256", "receipt-sha256"):
        parser.add_argument("--expected-" + part, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_external_observer(
            args.observer_dir, args.custody_dir,
            **{key: getattr(args, key) for key in vars(args)
               if key.startswith("expected_")})
        print(json.dumps(result, sort_keys=True))
    except ExternalObserverError as exc:
        print(json.dumps({
            "status": REJECTED,
            "reason": str(exc),
            "independent_vm_attestation": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
    # A signature over self-reports is never VM attestation or release.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
