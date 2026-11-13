#!/usr/bin/env python3
"""PE-S2.18: signed v2 supplement for one libvirt host-only domstats sidecar.

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
import pe_arch_vm_s2_16_signed_domstats_extension as v2
import pe_arch_vm_s2_17_host_two_phase as pair
import pe_arch_vm_witness_review as witness
from pe_nofollow_paths import open_absolute_directory_nofollow

SCHEMA = "negresco_pe_s2_18_signed_two_phase_host_supplement_v3"
CLASS = "SIGNED_HOST_TWO_PHASE_SAMPLES_NOT_VM_ATTESTATION"
NAMESPACE = "negresco-pe-s2-18-host-two-phase-supplement-v3"
MANIFEST = "external-host-two-phase-supplement-v3.json"
SIGNATURE = "external-host-two-phase-supplement-v3.sig"
PREPARED = "UNSIGNED_PE_S2_18_EXTENSION_V3_PREPARED_RELEASE_HOLD"
VERIFIED = "SIGNED_PE_S2_18_EXTENSION_V3_VERIFIED_RELEASE_HOLD"
REJECTED = "REJECTED_PE_S2_18_UNSAFE_SIGNED_HOST_PAIR"

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
    "expected_v2_manifest_sha256", "expected_v2_signature_sha256",
    "expected_before_sha256", "expected_after_sha256",
)
MAX_EXTENSION_BYTES = 6144
MAX_SIGNATURE_BYTES = 4096
# The V3 reader must not discard added upstream claims of independent
# verification, nor accept a partially populated V2/pair result as proof.
V2_VERDICT_FIELDS = frozenset((
    "status", "v2_detached_ed25519_signature_verified",
    "v2_namespace_distinct_from_v1",
    "v1_detached_signature_rechecked",
    "sidecar_sha256_bound_to_signed_v2_only",
    "v1_four_observation_manifest_unchanged",
    "host_hypervisor_independently_attested",
    "guest_cgroups_seccomp_verified",
    "independent_vm_attestation", "release_authorized",
    "apk_or_ota_publication_authorized",
))
PAIR_VERDICT_FIELDS = frozenset((
    "status", "before_after_sha256_pins_matched",
    "external_session_and_domain_correlated",
    "host_cpu_time_increased_as_reported_by_libvirt",
    "host_provenance_independently_attested",
    "guest_process_or_seccomp_cgroup_verified",
    "samples_signed_in_s1_63_or_s2_16",
    "independent_vm_attestation", "release_authorized",
))


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
        "v2_extension_manifest_sha256": p["expected_v2_manifest_sha256"],
        "v2_extension_signature_sha256": p["expected_v2_signature_sha256"],
        "before_filename": pair.BEFORE,
        "before_sha256": p["expected_before_sha256"],
        "after_filename": pair.AFTER,
        "after_sha256": p["expected_after_sha256"],
        "pair_is_not_in_v1_or_v2_signed_manifest": True,
        "v3_pair_signature_required": True,
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
            "expected_receipt_sha256", "expected_challenge",
            "expected_v2_manifest_sha256", "expected_v2_signature_sha256",
            "expected_before_sha256", "expected_after_sha256"):
        if external.SHA256.fullmatch(p[key]) is None:
            raise SignedDomstatsExtensionError("Noncanonical external SHA pin: " + key)
    if (p["expected_session_id"] in (
            "0" * 64, p["expected_challenge"],
            p["expected_host_sha256"], p["expected_guest_sha256"],
            p["expected_domstats_sha256"],
            p["expected_before_sha256"], p["expected_after_sha256"])
            or p["expected_before_sha256"] == p["expected_after_sha256"]
            or p["expected_challenge"] == "0"*64):
        raise SignedDomstatsExtensionError(
            "Reviewer session must differ from challenge and record hashes")


def _verified_upstream(owner: Path, operator: Path, p: dict) -> None:
    """Verify V1+V2 actual signatures and pair's two externally held hashes."""
    try:
        signed = v2.verify_signed_domstats_extension(
            owner, operator,
            expected_extension_manifest_sha256=p["expected_v2_manifest_sha256"],
            expected_extension_signature_sha256=p["expected_v2_signature_sha256"],
            **{key: p[key] for key in v2.PINS})
        samples = pair.review_pair(
            owner,
            expected_before_sha256=p["expected_before_sha256"],
            expected_after_sha256=p["expected_after_sha256"],
            domain=p["expected_domain"],
            expected_domain_uuid=p["expected_domain_uuid"],
            expected_source_commit=p["expected_source_commit"],
            reviewer_challenge=p["expected_challenge"],
            expected_session_id=p["expected_session_id"],
            expected_host_sha256=p["expected_host_sha256"],
            expected_guest_sha256=p["expected_guest_sha256"])
    except (v2.SignedDomstatsExtensionError,
            pair.HostTwoPhaseError, OSError, ValueError,
            TypeError, KeyError) as exc:
        raise SignedDomstatsExtensionError(
            "V1/V2 signatures or both host session measurements unverified") from exc
    if (type(signed) is not dict
            or set(signed) != V2_VERDICT_FIELDS
            or signed.get("status") != v2.VERIFIED
            or any(signed.get(field) is not True for field in (
                "v2_detached_ed25519_signature_verified",
                "v2_namespace_distinct_from_v1",
                "v1_detached_signature_rechecked",
                "sidecar_sha256_bound_to_signed_v2_only",
                "v1_four_observation_manifest_unchanged"))
            or any(signed.get(field) is not False for field in (
                "host_hypervisor_independently_attested",
                "guest_cgroups_seccomp_verified",
                "independent_vm_attestation", "release_authorized",
                "apk_or_ota_publication_authorized"))
            or type(samples) is not dict
            or set(samples) != PAIR_VERDICT_FIELDS
            or samples.get("status") != pair.STATUS_REVIEWED
            or any(samples.get(field) is not True for field in (
                "before_after_sha256_pins_matched",
                "external_session_and_domain_correlated",
                "host_cpu_time_increased_as_reported_by_libvirt"))
            or any(samples.get(field) is not False for field in (
                "host_provenance_independently_attested",
                "guest_process_or_seccomp_cgroup_verified",
                "samples_signed_in_s1_63_or_s2_16",
                "independent_vm_attestation", "release_authorized"))):
        raise SignedDomstatsExtensionError("Source signatures/counters contradict HOLD")


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
                    "V3 supplement/signature already exists; no overwrite")
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
            "Atomic private v3 supplement publication failed") from exc


def prepare_signed_domstats_extension(
        observer_dir: Path, custody_dir: Path, **pins: str) -> dict:
    """Create an UNSIGNED canonical v3 manifest, never access signing keys."""
    _pins(pins)
    owner, operator = _validated_dirs(observer_dir, custody_dir)
    _verified_upstream(owner, operator, pins)
    raw = _canonical(_expected(pins))
    if not 0 < len(raw) <= MAX_EXTENSION_BYTES:
        raise SignedDomstatsExtensionError("V3 supplement manifest oversized")
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
    """Verify a separate real Ed25519 v3 signature, always return HOLD."""
    _pins(pins)
    for label, digest in (
            ("v3 manifest", expected_extension_manifest_sha256),
            ("v3 detached signature", expected_extension_signature_sha256)):
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
                "V3 manifest not exact canonical externally pinned schema")
        # A distinct namespace refuses replayed signatures from V1 or V2.
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
                (v2.MANIFEST, pins["expected_v2_manifest_sha256"]),
                (v2.SIGNATURE, pins["expected_v2_signature_sha256"]),
                (pair.BEFORE, pins["expected_before_sha256"]),
                (pair.AFTER, pins["expected_after_sha256"]),
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
        "v3_detached_ed25519_signature_verified": True,
        "v3_namespace_distinct_from_v1_and_v2": True,
        "v2_detached_signature_rechecked": True,
        "v1_detached_signature_rechecked": True,
        "two_phase_hashes_bound_to_signed_v3_only": True,
        "v1_v2_signed_manifests_unchanged": True,
        "host_hypervisor_independently_attested": False,
        "guest_cgroups_seccomp_verified": False,
        "independent_vm_attestation": False,
        "release_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="PE-S2.18 signed v3 host session extension. Never VM attestation")
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
                    "Reviewer-held v3 manifest/signature pins required")
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
                "Expected signed v3 hashes are only for offline verification")
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
