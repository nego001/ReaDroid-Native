#!/usr/bin/env python3
"""PE-S2.22: independent-held, NOFOLLOW pin bundle for PE-S2.19 review.

An external reviewer supplies a canonical pin bundle from a separate private
directory, and separately retains its SHA256. This only correlates bytes.
It does NOT independently authenticate the reviewer, host or guest, and
does not turn an unsigned native receipt into kernel/VM attestation.
No shell, libvirt, network, Ghidra, PE, signature creation or file writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_receipt_verify as receipt
import pe_arch_vm_s1_65_observer_prepare as directory
import pe_arch_vm_s1_70_readonly_libvirt_host_capture as libvirt
from pe_arch_vm_checkout_pin import COMMIT_SHA
import pe_arch_vm_s2_18_signed_host_pair as v3
import pe_arch_vm_s2_19_reviewer_session_handoff as handoff

SCHEMA = "negresco_pe_s2_22_external_reviewer_pins_v1"
CLASSIFICATION = "REVIEWER_HELD_HASH_REFERENCES_NOT_VM_ATTESTATION"
PIN_FILE_NAME = "reviewer-held-pins.json"
EXTRA = frozenset((
    "expected_v3_manifest_sha256",
    "expected_v3_signature_sha256",
    "expected_native_receipt_sha256",
))
FIELDS = frozenset((
    "schema", "security_classification", "pins",
    "independent_vm_attestation", "release_authorized",
))
MAX_BYTES = 8192
PLAN = "PE_S2_22_REVIEWER_PIN_CUSTODY_NOT_STARTED"
VERIFIED = "LOCAL_PE_S2_22_SEPARATE_PIN_BUNDLE_AND_SIGNED_CHAIN_REVIEWED_HOLD"
REJECTED = "REJECTED_PE_S2_22_REVIEWER_HELD_PINS_OR_CHAIN"
# Closed contract for the entire PE-S2.19 result. A future change to the
# signed-session reviewer cannot add a claim of external attestation silently.
S2_19_RESULT_FIELDS = frozenset((
    "status",
    "v1_v2_v3_detached_signatures_verified",
    "v3_before_after_host_sha256_pins_correlated",
    "native_receipt_sha256_equals_v1_signed_receipt_pin",
    "guest_receipt_challenge_and_sources_rechecked",
    "source_commit_checkout_locally_rechecked",
    "independent_host_control_attested",
    "guest_kernel_execution_independently_attested",
    "session_chronology_independently_verified",
    "journal_kernel_storage_quota_verified",
    "independent_vm_attestation",
    "release_authorized",
    "unknown_windows_pe_execution_authorized",
    "apk_or_ota_publication_authorized",
))
UNPROVEN = (
    "identity_and_independence_of_external_reviewer",
    "physical_or_administrative_control_of_hypervisor",
    "native_arch_guest_kernel_provenance",
    "same_session_cgroup_v2_and_seccomp_independently_observed",
    "journald_effective_kernel_storage_quota",
    "guest_process_tree_cleanup_independently_observed",
    "chronology_of_guest_work_between_host_samples",
)


class ReviewerPinsError(RuntimeError):
    """No safe independently-held input bundle or matching review."""


def _canonical(obj: dict) -> bytes:
    return (json.dumps(obj, sort_keys=True, ensure_ascii=True,
                       allow_nan=False, separators=(",", ":")) + "\n").encode("ascii")


def _is_canonical_abs(path: Path) -> bool:
    return (path.is_absolute() and path != Path("/")
            and all(piece not in ("", ".", "..") for piece in path.parts[1:]))


def _disjoint(a: Path, b: Path) -> bool:
    return a != b and a not in b.parents and b not in a.parents


def _private_pin_file(pin_file: Path, owner: Path, custody: Path,
                      source: Path) -> Path:
    try:
        target = Path(pin_file)
        if (target.name != PIN_FILE_NAME or not _is_canonical_abs(target)
                or not _is_canonical_abs(owner)
                or not _is_canonical_abs(custody)
                or not _is_canonical_abs(source)):
            raise ReviewerPinsError("Absolute canonical reviewer pin paths required")
        pins = directory._directory(target.parent)
        observer, operator = v3._validated_dirs(owner, custody)
        if (not _disjoint(pins, observer) or not _disjoint(pins, operator)
                or not _disjoint(pins, source)
                or not _disjoint(observer, source)
                or not _disjoint(operator, source)):
            raise ReviewerPinsError(
                "Pins, observer, custody and readonly checkout must be separate")
        return target
    except (directory.ObserverPreparationError,
            v3.SignedDomstatsExtensionError,
            OSError, TypeError, ValueError) as exc:
        raise ReviewerPinsError(
            "Reviewer-only pins directory could not be safely verified") from exc


def _read_pins(path: Path, expected_hash: str) -> tuple[dict, bytes]:
    if (type(expected_hash) is not str
            or receipt.HEX64.fullmatch(expected_hash) is None):
        raise ReviewerPinsError("Externally retained canonical pin SHA256 required")
    try:
        raw = receipt._read_private_receipt(path)
    except (receipt.ReceiptReviewError, OSError, ValueError) as exc:
        raise ReviewerPinsError("Unsafe missing reviewer-held pins file") from exc
    if (len(raw) > MAX_BYTES
            or hashlib.sha256(raw).hexdigest() != expected_hash):
        raise ReviewerPinsError(
            "Reviewer-held pins differ from independent SHA256 reference")
    try:
        obj = json.loads(raw.decode("ascii"),
                         object_pairs_hook=receipt._no_duplicate_keys)
    except (receipt.ReceiptReviewError, UnicodeError,
            ValueError, TypeError, RecursionError) as exc:
        raise ReviewerPinsError("Reviewer pins JSON not valid canonical ASCII") from exc
    if (type(obj) is not dict or set(obj) != FIELDS
            or obj["schema"] != SCHEMA
            or obj["security_classification"] != CLASSIFICATION
            or obj["independent_vm_attestation"] is not False
            or obj["release_authorized"] is not False
            or type(obj["pins"]) is not dict
            or set(obj["pins"]) != set(v3.PINS) | EXTRA
            or _canonical(obj) != raw):
        raise ReviewerPinsError("Exact canonical external pins schema required")
    pins = obj["pins"]
    try:
        v3._pins({key: pins[key] for key in v3.PINS})
    except (v3.SignedDomstatsExtensionError, KeyError, ValueError,
            TypeError) as exc:
        raise ReviewerPinsError("Invalid V3 external pin values") from exc
    for key in EXTRA:
        value = pins[key]
        if type(value) is not str or receipt.HEX64.fullmatch(value) is None:
            raise ReviewerPinsError("Invalid reviewer-held SHA256: " + key)
    # A signature verifier would eventually refuse this, but external
    # reviewer-provided identity must be checked BEFORE any signed review.
    if (COMMIT_SHA.fullmatch(pins["expected_source_commit"]) is None
            or pins["expected_source_commit"] == "0" * 40
            or libvirt.DOMAIN.fullmatch(pins["expected_domain"]) is None
            or libvirt.UUID.fullmatch(pins["expected_domain_uuid"]) is None
            or pins["expected_domain_uuid"] ==
               "00000000-0000-0000-0000-000000000000"):
        raise ReviewerPinsError("Malformed reviewer-pinned commit/domain/UUID")
    if pins["expected_native_receipt_sha256"] != pins["expected_receipt_sha256"]:
        raise ReviewerPinsError("Unsigned native receipt differs from signed V1 pin")
    return pins, raw


def review_custody(pin_file: Path, observer_dir: Path,
                   custody_dir: Path, native_receipt: Path,
                   source_root: Path, *,
                   expected_pin_bundle_sha256: str) -> dict:
    """One read-only offline review, fail-closed if any pin or evidence drifts."""
    pin_path = _private_pin_file(
        pin_file, observer_dir, custody_dir, source_root)
    pins, raw = _read_pins(pin_path, expected_pin_bundle_sha256)
    try:
        observed = handoff.verify_reviewer_session(
            observer_dir, custody_dir, native_receipt, source_root,
            **pins)
    except (handoff.SessionHandoffError,
            OSError, ValueError, TypeError, KeyError) as exc:
        raise ReviewerPinsError(
            "Signed V1/V2/V3 host and native receipt failed local review") from exc
    if (type(observed) is not dict
            or set(observed) != S2_19_RESULT_FIELDS
            or observed.get("status") != handoff.STATUS
            or any(observed.get(key) is not True for key in (
                "v1_v2_v3_detached_signatures_verified",
                "v3_before_after_host_sha256_pins_correlated",
                "native_receipt_sha256_equals_v1_signed_receipt_pin",
                "guest_receipt_challenge_and_sources_rechecked",
                "source_commit_checkout_locally_rechecked"))
            or any(observed.get(key) is not False for key in (
                "independent_host_control_attested",
                "guest_kernel_execution_independently_attested",
                "session_chronology_independently_verified",
                "journal_kernel_storage_quota_verified",
                "independent_vm_attestation",
                "release_authorized",
                "unknown_windows_pe_execution_authorized",
                "apk_or_ota_publication_authorized"))):
        raise ReviewerPinsError("Local joint review attempted to grant release")
    repeated, second_raw = _read_pins(pin_path, expected_pin_bundle_sha256)
    if repeated != pins or second_raw != raw:
        raise ReviewerPinsError("Reviewer-held pins changed during joint review")
    return {
        "status": VERIFIED,
        "canonical_out_of_band_pin_bundle_sha256_matched": True,
        "reviewer_pins_private_directory_disjoint": True,
        "v1_v2_v3_detached_signatures_locally_verified": True,
        "readonly_native_receipt_and_git_locally_verified": True,
        "unverified_independent_requirements": list(UNPROVEN),
        "reviewer_identity_independently_attested": False,
        "hypervisor_independence_attested": False,
        "native_vm_kernel_attested": False,
        "independent_vm_attestation": False,
        "release_authorized": False,
        "apk_or_ota_publication_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PE-S2.22 external reviewer pin custody + offline HOLD")
    parser.add_argument("--pin-file", required=True, type=Path)
    parser.add_argument("--observer-dir", required=True, type=Path)
    parser.add_argument("--custody-dir", required=True, type=Path)
    parser.add_argument("--native-receipt", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--expected-pin-bundle-sha256", required=True)
    parser.add_argument("--review-existing", action="store_true",
                        help="Opt in to the actual offline file/signature review")
    args = parser.parse_args(argv)
    try:
        if not args.review_existing:
            print(json.dumps({
                "status": PLAN,
                "pins_or_evidence_files_read": False,
                "independent_vm_attestation": False,
                "release_authorized": False,
            }, sort_keys=True))
            return 0
        report = review_custody(
            args.pin_file, args.observer_dir, args.custody_dir,
            args.native_receipt, args.source_root,
            expected_pin_bundle_sha256=args.expected_pin_bundle_sha256)
        print(json.dumps(report, sort_keys=True))
        return 2  # Even a cryptographically valid package is NOT VM attestation.
    except (ReviewerPinsError, ValueError, TypeError, OSError) as exc:
        print(json.dumps({
            "status": REJECTED, "reason": str(exc),
            "independent_vm_attestation": False,
            "release_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
