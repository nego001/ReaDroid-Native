#!/usr/bin/env python3
"""PE-S1.65: prepare a reviewer-held, unsigned host observation manifest.

READ-ONLY with respect to input logs and public keys, single exclusive
publication of an unsigned manifest. The host-side observer must ALREADY
have collected four genuine logs from a trusted machine; this tool cannot
authenticate their origin or invent missing logs. It never accesses private
signing keys, generates keys, runs guest programs or starts a VM.

Success means "manifest prepared for external review", NOT VM attestation.
The next actions are a separately controlled OpenSSH signature (S1.63)
and the existing fail-closed PE-S1.64 correlation.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_s1_63_external_observer as external
import pe_arch_vm_evidence as evidence
import pe_arch_vm_receipt_verify as receipts
import pe_arch_vm_witness_trust_review as trust
import pe_arch_vm_witness_review as witness
from pe_arch_vm_checkout_pin import COMMIT_SHA
from pe_nofollow_paths import open_absolute_directory_nofollow

STATUS = "UNSIGNED_PE_S1_65_HOST_MANIFEST_PREPARED_NOT_VM_ATTESTATION"
REJECTED = "REJECTED_PE_S1_65_UNSAFE_OBSERVER_HANDOFF"
PINS = (
    "expected_source_commit", "expected_challenge", "expected_request_sha256",
    "expected_custody_sha256", "expected_receipt_sha256",
    "expected_observer_signers_sha256",
    "expected_reviewer_signers_sha256",
    "expected_witness_signers_sha256",
    "expected_observer_id", "expected_reviewer_id", "expected_witness_id",
)


class ObserverPreparationError(RuntimeError):
    """Reviewer-side source logs or an exclusive manifest are not safe."""


def _directory(path: Path) -> Path:
    dest = Path(path)
    if (not dest.is_absolute() or dest == Path("/")
            or any(piece in ("", ".", "..") for piece in dest.parts[1:])):
        raise ObserverPreparationError(
            "Canonical absolute private directory required")
    try:
        with ExitStack() as stack:
            fd = open_absolute_directory_nofollow(dest, stack)
            info = os.fstat(fd)
            if (not stat.S_ISDIR(info.st_mode) or
                    info.st_uid != os.geteuid() or
                    stat.S_IMODE(info.st_mode) != 0o700):
                raise ObserverPreparationError(
                    "Reviewer directory must be caller-owned mode 0700")
    except (OSError, ValueError) as exc:
        raise ObserverPreparationError("No safe nofollow private directory") from exc
    return dest


def _read_file(parent: Path, filename: str) -> bytes:
    try:
        return receipts._read_private_receipt(parent / filename)
    except (OSError, receipts.ReceiptReviewError) as exc:
        raise ObserverPreparationError(
            "Missing/unsafe reviewer-owned file: " + filename) from exc


def _require_pin(value: object, label: str) -> None:
    if (not isinstance(value, str)
            or external.SHA256.fullmatch(value) is None):
        raise ObserverPreparationError(
            "Externally selected lowercase SHA-256 required: " + label)


def _canonical(record: dict) -> bytes:
    return (json.dumps(record, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _publish_new_file(parent: Path, filename: str, raw: bytes) -> None:
    """Durable, owner-only, atomic no-overwrite publication under directory FD."""
    try:
        with ExitStack() as stack:
            directory_fd = open_absolute_directory_nofollow(parent, stack)
            info = os.fstat(directory_fd)
            if (info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o700):
                raise ObserverPreparationError("Manifest destination is not private")
            evidence._lock_private_receipt_directory(
                directory_fd, exclusive=True)
            # Prevent creating a fresh manifest alongside an old signature.
            for name in (filename, external.SIGNATURE_FILE):
                try:
                    os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                raise ObserverPreparationError(
                    "Refusing an existing manifest/signature: " + name)
            stage = ".negresco-receipt-" + secrets.token_hex(16) + ".tmp"
            identity = None
            published = False
            try:
                fd = os.open(
                    stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                    os.O_CLOEXEC | os.O_NOFOLLOW, 0o600,
                    dir_fd=directory_fd)
                try:
                    st = os.fstat(fd)
                    identity = (st.st_dev, st.st_ino)
                    with os.fdopen(fd, "wb") as out:
                        out.write(raw)
                        out.flush()
                        os.fsync(out.fileno())
                except BaseException:
                    # If fdopen did not own fd yet, close safely.
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    raise
                os.link(
                    stage, filename, src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd, follow_symlinks=False)
                published = True
                os.unlink(stage, dir_fd=directory_fd)
                os.fsync(directory_fd)
            except BaseException:
                # Never delete a replacement inode belonging to someone
                # else, even if a same-UID process races the writer.
                for name in ((filename, stage) if published else (stage,)):
                    try:
                        st = os.stat(
                            name, dir_fd=directory_fd,
                            follow_symlinks=False)
                        if (identity is not None
                                and (st.st_dev, st.st_ino) == identity
                                and stat.S_ISREG(st.st_mode)):
                            os.unlink(name, dir_fd=directory_fd)
                    except FileNotFoundError:
                        pass
                    except OSError:
                        pass
                try:
                    os.fsync(directory_fd)
                except OSError:
                    pass
                raise
    except (OSError, ValueError, evidence.AcceptanceReceiptError) as exc:
        raise ObserverPreparationError(
            "Could not atomically prepare owner-only observer manifest") from exc


def prepare_observer_manifest(
        observer_dir: Path, custody_dir: Path, *,
        expected_source_commit: str, expected_challenge: str,
        expected_request_sha256: str, expected_custody_sha256: str,
        expected_receipt_sha256: str,
        expected_observer_signers_sha256: str,
        expected_reviewer_signers_sha256: str,
        expected_witness_signers_sha256: str,
        expected_observer_id: str,
        expected_reviewer_id: str,
        expected_witness_id: str) -> dict:
    """Make a bounded unsigned manifest from four existing owner-only logs."""
    for label, pin in (
        ("challenge", expected_challenge),
        ("request", expected_request_sha256),
        ("custody", expected_custody_sha256),
        ("receipt", expected_receipt_sha256),
        ("observer key", expected_observer_signers_sha256),
        ("reviewer key", expected_reviewer_signers_sha256),
        ("witness key", expected_witness_signers_sha256),
    ):
        _require_pin(pin, label)
    if (expected_challenge == "0" * 64
            or not isinstance(expected_source_commit, str)
            or COMMIT_SHA.fullmatch(expected_source_commit) is None
            or expected_source_commit == "0" * 40):
        raise ObserverPreparationError("Reviewer challenge/commit must be pinned")
    for label, identity in (
        ("observer", expected_observer_id),
        ("reviewer", expected_reviewer_id),
        ("witness", expected_witness_id),
    ):
        if (not isinstance(identity, str)
                or witness.WITNESS_ID.fullmatch(identity) is None):
            raise ObserverPreparationError("Invalid signer identity: " + label)
    if len({expected_observer_id, expected_reviewer_id,
            expected_witness_id}) != 3:
        raise ObserverPreparationError("Distinct signer identities required")
    owner = _directory(Path(observer_dir))
    operator = _directory(Path(custody_dir))
    if owner == operator or owner in operator.parents or operator in owner.parents:
        raise ObserverPreparationError(
            "External observer and operator must have separate directories")
    # Never use the operator to establish trust in the observer's key.
    keys = []
    for path, filename, identity, expected in (
        (owner, external.SIGNERS_FILE, expected_observer_id,
         expected_observer_signers_sha256),
        (operator, external.REVIEWER_KEY_FILE, expected_reviewer_id,
         expected_reviewer_signers_sha256),
        (operator, external.WITNESS_KEY_FILE, expected_witness_id,
         expected_witness_signers_sha256),
    ):
        raw = _read_file(path, filename)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ObserverPreparationError("Externally held signer key mismatch")
        try:
            keys.append(trust._public_key_blob(raw, identity))
        except trust.TrustReviewError as exc:
            raise ObserverPreparationError("Invalid Ed25519 signer key") from exc
    if len(set(keys)) != 3:
        raise ObserverPreparationError(
            "Observer's signing key must differ from custody signers")
    readings = {}
    for label, filename in external.OBS_FILES.items():
        data = _read_file(owner, filename)
        if not 0 < len(data) <= external.MAX_LOG_BYTES or b"\0" in data:
            raise ObserverPreparationError(
                "Empty, oversized or binary observation: " + label)
        readings[label] = {
            "filename": filename,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    manifest = {
        "schema": external.SCHEMA,
        "security_classification": external.CLASSIFICATION,
        "observer_id": expected_observer_id,
        "reviewer_id": expected_reviewer_id,
        "witness_id": expected_witness_id,
        "source_commit": expected_source_commit,
        "reviewer_challenge": expected_challenge,
        "request_sha256": expected_request_sha256,
        "custody_index_sha256": expected_custody_sha256,
        "receipt_sha256": expected_receipt_sha256,
        "observer_local_time_utc_not_attested":
            datetime.now(timezone.utc).isoformat(),
        "independent_vm_attestation": False,
        "release_authorized": False,
        "observations": readings,
    }
    output = _canonical(manifest)
    if not 0 < len(output) <= external.MAX_MANIFEST_BYTES:
        raise ObserverPreparationError("Manifest larger than S1.63 limit")
    # Detect persistent input modifications before publication; S1.63
    # separately verifies files again at signature review time.
    for label, entry in readings.items():
        if hashlib.sha256(_read_file(owner, entry["filename"])).hexdigest() != (
                entry["sha256"]):
            raise ObserverPreparationError(
                "Observation changed before manifest publication: " + label)
    _publish_new_file(owner, external.MANIFEST_FILE, output)
    return {
        "status": STATUS,
        "manifest_sha256": hashlib.sha256(output).hexdigest(),
        "host_observation_hashes": {
            label: reading["sha256"] for label, reading in readings.items()
        },
        "observation_count": len(readings),
        "observer_private_key_accessed": False,
        "signature_created": False,
        "external_host_provenance_authenticated": False,
        "native_arch_kernel_independently_verified": False,
        "independent_vm_attestation": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Prepare unsigned external observer manifest, never VM proof")
    ap.add_argument("--observer-dir", type=Path, required=True)
    ap.add_argument("--custody-dir", type=Path, required=True)
    for key in PINS:
        ap.add_argument("--" + key.replace("_", "-"), required=True)
    args = ap.parse_args(argv)
    try:
        report = prepare_observer_manifest(
            args.observer_dir, args.custody_dir,
            **{key: getattr(args, key) for key in PINS})
        print(json.dumps(report, sort_keys=True))
        return 0  # File preparation succeeded; release remains explicitly FALSE.
    except ObserverPreparationError as exc:
        print(json.dumps({
            "status": REJECTED, "reason": str(exc),
            "signature_created": False,
            "independent_vm_attestation": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
