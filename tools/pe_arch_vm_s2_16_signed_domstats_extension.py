#!/usr/bin/env python3
"""PE-S2.16: signed v2 supplement for one libvirt host-only domstats sidecar.

This intentionally DOES NOT edit the legacy S1.63 four-record schema or
its signature. A separate, namespace-specific OpenSSH Ed25519 signature
covers the exact canonical v2 supplement and the sidecar SHA-256.

All results remain HOLD; signing self-reported counters does not prove
physical control of the host, a native Arch VM or guest kernel isolation.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_evidence as evidence
import pe_arch_vm_receipt_verify as receipts
import pe_arch_vm_s1_63_external_observer as external
import pe_arch_vm_s1_65_observer_prepare as prepare
import pe_arch_vm_s2_15_readonly_host_domstats as domstats
import pe_arch_vm_witness_review as witness
from pe_nofollow_paths import open_absolute_directory_nofollow

SCHEMA = "negresco_pe_s2_16_signed_host_domstats_supplement_v2"
CLASS = "SIGNED_LIBVIRT_DOMSTATS_SIDECAR_NOT_VM_ATTESTATION"
NAMESPACE = "negresco-pe-s2-16-host-domstats-supplement-v2"
MANIFEST = "external-host-domstats-supplement-v2.json"
SIGNATURE = "external-host-domstats-supplement-v2.sig"
PREPARED = "UNSIGNED_PE_S2_16_EXTENSION_V2_PREPARED_RELEASE_HOLD"
VERIFIED = "SIGNED_PE_S2_16_EXTENSION_V2_VERIFIED_RELEASE_HOLD"
REJECTED = "REJECTED_PE_S2_16_UNSAFE_HOST_DOMSTATS_SUPPLEMENT"

PINS = (
    "expected_source_commit", "expected_challenge", "expected_session_id",
    "expected_domain", "expected_domain_uuid",
    "expected_host_sha256", "expected_guest_sha256",
    "expected_domstats_sha256", "expected_v1_manifest_sha256",
    "expected_v1_signature_sha256",
    "expected_observer_signers_sha256",
    "expected_reviewer_signers_sha256",
    "expected_witness_signers_sha256",
    "expected_observer_id", "expected_reviewer_id", "expected_witness_id",
    "expected_request_sha256", "expected_custody_sha256",
    "expected_receipt_sha256",
)
MAX_EXTENSION_BYTES = 4096
MAX_SIGNATURE_BYTES = 4096


class SignedDomstatsExtensionError(RuntimeError):
    """At least one signature, identity, hash or source observation is unsafe."""


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False, ensure_ascii=True) + "\n").encode("ascii")


def _expected(p: dict) -> dict:
    return {
        "schema": SCHEMA,
        "security_classification": CLASS,
        "source_commit": p["expected_source_commit"],
        "reviewer_challenge": p["expected_challenge"],
        "reviewer_session_id": p["expected_session_id"],
        "domain_name": p["expected_domain"],
        "domain_uuid": p["expected_domain_uuid"],
        "observer_id": p["expected_observer_id"],
        "v1_observer_manifest_sha256": p["expected_v1_manifest_sha256"],
        "v1_observer_signature_sha256": p["expected_v1_signature_sha256"],
        "v1_observer_allowed_signers_sha256": p[
            "expected_observer_signers_sha256"],
        "host_record_sha256": p["expected_host_sha256"],
        "guest_record_sha256": p["expected_guest_sha256"],
        "host_domstats_sidecar_filename": domstats.TARGET,
        "host_domstats_sidecar_sha256": p["expected_domstats_sha256"],
        "host_domstats_sidecar_is_v1_signed": False,
        "host_domstats_sidecar_v2_signature_required": True,
        "independent_vm_attestation": False,
        "release_authorized": False,
    }


def _validated_dirs(observer_dir: Path, custody_dir: Path) -> tuple[Path, Path]:
    try:
        owner = prepare._directory(Path(observer_dir))
        operator = prepare._directory(Path(custody_dir))
    except (prepare.ObserverPreparationError, OSError, ValueError) as exc:
        raise SignedDomstatsExtensionError(
            "Private separate directories required") from exc
    if (owner == operator or owner in operator.parents
            or operator in owner.parents):
        raise SignedDomstatsExtensionError(
            "External observer and custody directory must be separate")
    return owner, operator


def _pins(p: dict) -> None:
    if type(p) is not dict or set(p) != set(PINS):
        raise SignedDomstatsExtensionError(
            "Exact external supplement review pins required")
    for key in PINS:
        if type(p[key]) is not str or not p[key]:
            raise SignedDomstatsExtensionError("Missing external pin: " + key)
    for key in (
            "expected_session_id", "expected_host_sha256",
            "expected_guest_sha256", "expected_domstats_sha256",
            "expected_v1_manifest_sha256", "expected_v1_signature_sha256",
            "expected_observer_signers_sha256",
            "expected_reviewer_signers_sha256",
            "expected_witness_signers_sha256",
            "expected_request_sha256", "expected_custody_sha256",
            "expected_receipt_sha256", "expected_challenge"):
        if external.SHA256.fullmatch(p[key]) is None:
            raise SignedDomstatsExtensionError("Noncanonical external SHA pin: " + key)
    if (p["expected_session_id"] in (
            "0" * 64, p["expected_challenge"],
            p["expected_host_sha256"], p["expected_guest_sha256"],
            p["expected_domstats_sha256"])
            or p["expected_challenge"] == "0"*64):
        raise SignedDomstatsExtensionError(
            "Reviewer session must differ from challenge and record hashes")


def _verified_upstream(owner: Path, operator: Path, p: dict) -> None:
    """Require genuine detached v1 signature and pinned sidecar before v2."""
    try:
        existing = external.verify_external_observer(
            owner, operator,
            expected_manifest_sha256=p["expected_v1_manifest_sha256"],
            expected_signature_sha256=p["expected_v1_signature_sha256"],
            expected_observer_signers_sha256=p[
                "expected_observer_signers_sha256"],
            expected_reviewer_signers_sha256=p[
                "expected_reviewer_signers_sha256"],
            expected_witness_signers_sha256=p[
                "expected_witness_signers_sha256"],
            expected_observer_id=p["expected_observer_id"],
            expected_reviewer_id=p["expected_reviewer_id"],
            expected_witness_id=p["expected_witness_id"],
            expected_source_commit=p["expected_source_commit"],
            expected_challenge=p["expected_challenge"],
            expected_request_sha256=p["expected_request_sha256"],
            expected_custody_sha256=p["expected_custody_sha256"],
            expected_receipt_sha256=p["expected_receipt_sha256"],
        )
        sidecar = domstats.review_host_domstats(
            owner, expected_record_sha256=p["expected_domstats_sha256"],
            domain=p["expected_domain"],
            expected_domain_uuid=p["expected_domain_uuid"],
            expected_source_commit=p["expected_source_commit"],
            reviewer_challenge=p["expected_challenge"],
            expected_session_id=p["expected_session_id"],
            expected_host_sha256=p["expected_host_sha256"],
            expected_guest_sha256=p["expected_guest_sha256"])
    except (external.ExternalObserverError, domstats.HostDomstatsError,
            OSError, ValueError, TypeError) as exc:
        raise SignedDomstatsExtensionError(
            "Pinned signed v1 package or readonly host sidecar failed review") from exc
    if (existing["status"] != external.STATUS
            or existing["external_observer_detached_signature_verified"] is not True
            or existing["independent_vm_attestation"] is not False
            or sidecar["status"] != domstats.REVIEWED
            or sidecar["record_sha256_matched"] is not True
            or sidecar["independent_vm_attestation"] is not False
            or sidecar["release_authorized"] is not False):
        raise SignedDomstatsExtensionError(
            "Untrusted upstream review attempted to grant attestation")


def _publish(owner: Path, raw: bytes) -> None:
    """Private no-overwrite publish with stage + directory fsync."""
    try:
        with ExitStack() as stack:
            directory_fd = open_absolute_directory_nofollow(owner, stack)
            info = os.fstat(directory_fd)
            if (info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o700):
                raise SignedDomstatsExtensionError("Observer directory unsafe")
            evidence._lock_private_receipt_directory(directory_fd, exclusive=True)
            for name in (MANIFEST, SIGNATURE):
                try:
                    os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                raise SignedDomstatsExtensionError(
                    "V2 supplement/signature already exists; no overwrite")
            stage = ".negresco-receipt-" + secrets.token_hex(16) + ".tmp"
            identity = None
            published = False
            try:
                fd = os.open(
                    stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                    | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600,
                    dir_fd=directory_fd)
                st = os.fstat(fd)
                identity = st.st_dev, st.st_ino
                with os.fdopen(fd, "wb") as fp:
                    fp.write(raw)
                    fp.flush()
                    os.fsync(fp.fileno())
                os.link(stage, MANIFEST, src_dir_fd=directory_fd,
                        dst_dir_fd=directory_fd, follow_symlinks=False)
                published = True
                os.unlink(stage, dir_fd=directory_fd)
                os.fsync(directory_fd)
            except BaseException:
                for name in ((MANIFEST, stage) if published else (stage,)):
                    try:
                        st = os.stat(
                            name, dir_fd=directory_fd, follow_symlinks=False)
                        if (identity is not None and
                                (st.st_dev, st.st_ino) == identity and
                                stat.S_ISREG(st.st_mode)):
                            os.unlink(name, dir_fd=directory_fd)
                    except (FileNotFoundError, OSError):
                        pass
                try:
                    os.fsync(directory_fd)
                except OSError:
                    pass
                raise
    except (OSError, ValueError, evidence.AcceptanceReceiptError) as exc:
        raise SignedDomstatsExtensionError(
            "Atomic private v2 supplement publication failed") from exc


def prepare_signed_domstats_extension(
        observer_dir: Path, custody_dir: Path, **pins: str) -> dict:
    """Create an UNSIGNED canonical v2 manifest, never access signing keys."""
    _pins(pins)
    owner, operator = _validated_dirs(observer_dir, custody_dir)
    _verified_upstream(owner, operator, pins)
    raw = _canonical(_expected(pins))
    if not 0 < len(raw) <= MAX_EXTENSION_BYTES:
        raise SignedDomstatsExtensionError("V2 supplement manifest oversized")
    _publish(owner, raw)
    return {
        "status": PREPARED, "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "manifest_filename": MANIFEST, "detached_signature_created": False,
        "observer_private_key_accessed": False,
        "independent_vm_attestation": False, "release_authorized": False,
    }


def verify_signed_domstats_extension(
        observer_dir: Path, custody_dir: Path, *,
        expected_extension_manifest_sha256: str,
        expected_extension_signature_sha256: str,
        **pins: str) -> dict:
    """Verify a separate real Ed25519 v2 signature, always return HOLD."""
    _pins(pins)
    for label, digest in (
            ("v2 manifest", expected_extension_manifest_sha256),
            ("v2 detached signature", expected_extension_signature_sha256)):
        if type(digest) is not str or external.SHA256.fullmatch(digest) is None:
            raise SignedDomstatsExtensionError(
                "Externally held lowercase SHA-256 required: " + label)
    owner, operator = _validated_dirs(observer_dir, custody_dir)
    _verified_upstream(owner, operator, pins)
    try:
        manifest = external._read_pinned(
            owner, MANIFEST, expected_extension_manifest_sha256)
        signature = external._read_pinned(
            owner, SIGNATURE, expected_extension_signature_sha256)
        trusted_signers = external._read_pinned(
            owner, external.SIGNERS_FILE,
            pins["expected_observer_signers_sha256"])
        if (not 0 < len(manifest) <= MAX_EXTENSION_BYTES
                or not 0 < len(signature) <= MAX_SIGNATURE_BYTES
                or manifest != _canonical(_expected(pins))):
            raise SignedDomstatsExtensionError(
                "V2 manifest not exact canonical externally pinned schema")
        # A different SSH signature namespace than S1.63 prevents a v1
        # signature from being reused as a v2 extension signature.
        witness._ssh_verify(
            manifest, signature, trusted_signers,
            pins["expected_observer_id"], namespace=NAMESPACE)
        # Detect persistent replacement of evidence during verification.
        for name, digest in (
                (MANIFEST, expected_extension_manifest_sha256),
                (SIGNATURE, expected_extension_signature_sha256),
                (external.SIGNERS_FILE,
                 pins["expected_observer_signers_sha256"]),
                (external.MANIFEST_FILE, pins["expected_v1_manifest_sha256"]),
                (external.SIGNATURE_FILE, pins["expected_v1_signature_sha256"]),
                (domstats.TARGET, pins["expected_domstats_sha256"]),
                (external.OBS_FILES["host_vm_launch"],
                 pins["expected_host_sha256"]),
                (external.OBS_FILES["host_guest_kernel"],
                 pins["expected_guest_sha256"])):
            external._read_pinned(owner, name, digest)
        _verified_upstream(owner, operator, pins)
    except (external.ExternalObserverError, witness.WitnessReviewError,
            OSError, ValueError, TypeError, receipts.ReceiptReviewError) as exc:
        raise SignedDomstatsExtensionError(
            "Signed extension or pinned evidence altered/missing") from exc
    return {
        "status": VERIFIED,
        "v2_detached_ed25519_signature_verified": True,
        "v2_namespace_distinct_from_v1": True,
        "v1_detached_signature_rechecked": True,
        "sidecar_sha256_bound_to_signed_v2_only": True,
        "v1_four_observation_manifest_unchanged": True,
        "host_hypervisor_independently_attested": False,
        "guest_cgroups_seccomp_verified": False,
        "independent_vm_attestation": False,
        "release_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="PE-S2.16 signed v2 domstats extension. Never VM attestation")
    ap.add_argument("--observer-dir", type=Path, required=True)
    ap.add_argument("--custody-dir", type=Path, required=True)
    ap.add_argument("--verify-existing", action="store_true")
    for key in PINS:
        ap.add_argument("--" + key.replace("_", "-"), required=True)
    ap.add_argument("--expected-extension-manifest-sha256")
    ap.add_argument("--expected-extension-signature-sha256")
    args = ap.parse_args(argv)
    pins = {key: getattr(args, key) for key in PINS}
    try:
        if args.verify_existing:
            if (args.expected_extension_manifest_sha256 is None
                    or args.expected_extension_signature_sha256 is None):
                raise SignedDomstatsExtensionError(
                    "Reviewer-held v2 manifest/signature pins required")
            report = verify_signed_domstats_extension(
                args.observer_dir, args.custody_dir,
                expected_extension_manifest_sha256=(
                    args.expected_extension_manifest_sha256),
                expected_extension_signature_sha256=(
                    args.expected_extension_signature_sha256), **pins)
            print(json.dumps(report, sort_keys=True))
            return 2  # Verified != authorized. Always HOLD.
        if (args.expected_extension_manifest_sha256 is not None
                or args.expected_extension_signature_sha256 is not None):
            raise SignedDomstatsExtensionError(
                "Expected signed v2 hashes are only for offline verification")
        report = prepare_signed_domstats_extension(
            args.observer_dir, args.custody_dir, **pins)
        print(json.dumps(report, sort_keys=True))
        return 0  # Unsigned preparation only, not release.
    except (SignedDomstatsExtensionError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "status": REJECTED, "reason": str(exc),
            "independent_vm_attestation": False,
            "release_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
