#!/usr/bin/env python3
"""PE-S2.19: offline bridge between SIGNED V3 host session and native receipt.

This is NOT a release gate. V3 is an authenticated *text bundle*, local
native receipt is self-reported; correlating hashes and the reviewer challenge
does not independently authenticate a VM, kernel, timestamps or host custody.
No Ghidra, PE, VM, libvirt, network, signing or native child execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_s2_18_signed_host_pair as v3
import pe_arch_vm_checkout_pin as checkout
import pe_arch_vm_evidence as evidence
import pe_arch_vm_receipt_verify as receipt
import pe_arch_vm_s1_65_observer_prepare as dirs

STATUS = "LOCAL_PE_S2_19_SIGNED_HOST_PAIR_AND_NATIVE_RECEIPT_CORRELATED_HOLD"
REJECTED = "REJECTED_PE_S2_19_NATIVE_HOST_SESSION_CUSTODY"
MAX_RECEIPT_BYTES = receipt.MAX_RECEIPT_BYTES


class SessionHandoffError(RuntimeError):
    """Independent host and native-guest evidence could not be correlated."""


def _checked_paths(observer_dir: Path, custody_dir: Path,
                   native_receipt: Path, source_root: Path) -> tuple[Path, Path, Path, Path]:
    try:
        observed, operator = v3._validated_dirs(observer_dir, custody_dir)
        path = Path(native_receipt)
        source = Path(source_root)
        if (not path.is_absolute() or not source.is_absolute()
                or path.parent != operator or path.name in ("", ".", "..")
                or any(part in ("", ".", "..") for part in source.parts[1:])
                or source in (observed, operator)
                or source in observed.parents or source in operator.parents
                or observed in source.parents or operator in source.parents):
            raise SessionHandoffError("Receipt must be in private custody; distinct checkout")
    except (v3.SignedDomstatsExtensionError, ValueError, TypeError) as exc:
        raise SessionHandoffError("Unsafe signed host or guest custody paths") from exc
    return observed, operator, path, source


def _receipt_bytes(path: Path, expected_sha: str) -> bytes:
    try:
        raw = receipt._read_private_receipt(path)
    except (receipt.ReceiptReviewError, OSError) as exc:
        raise SessionHandoffError("No private, immutable native receipt") from exc
    if (len(raw) > MAX_RECEIPT_BYTES
            or hashlib.sha256(raw).hexdigest() != expected_sha):
        raise SessionHandoffError("Native receipt differs from signed host custody pin")
    return raw


def verify_reviewer_session(observer_dir: Path, custody_dir: Path,
                            native_receipt: Path, source_root: Path, *,
                            expected_v3_manifest_sha256: str,
                            expected_v3_signature_sha256: str,
                            expected_native_receipt_sha256: str,
                            **pins: str) -> dict:
    """Offline correlation, never a claim of independent VM attestation."""
    try:
        v3._pins(pins)
        for name, value in (
                ("V3 manifest", expected_v3_manifest_sha256),
                ("V3 signature", expected_v3_signature_sha256),
                ("native receipt", expected_native_receipt_sha256)):
            if (type(value) is not str
                    or receipt.HEX64.fullmatch(value) is None):
                raise SessionHandoffError("Externally held SHA256 missing: " + name)
        if expected_native_receipt_sha256 != pins["expected_receipt_sha256"]:
            raise SessionHandoffError(
                "Native receipt differs from receipt pinned inside signed V1/V2/V3 chain")
        owner, operator, path, source = _checked_paths(
            observer_dir, custody_dir, native_receipt, source_root)
        original = _receipt_bytes(path, expected_native_receipt_sha256)
        signed = v3.verify_signed_domstats_extension(
            owner, operator,
            expected_extension_manifest_sha256=expected_v3_manifest_sha256,
            expected_extension_signature_sha256=expected_v3_signature_sha256,
            **pins)
        if (type(signed) is not dict or signed.get("status") != v3.VERIFIED
                or signed.get("v3_detached_ed25519_signature_verified") is not True
                or signed.get("v2_detached_signature_rechecked") is not True
                or signed.get("v1_detached_signature_rechecked") is not True
                or signed.get("two_phase_hashes_bound_to_signed_v3_only") is not True
                or signed.get("independent_vm_attestation") is not False
                or signed.get("release_authorized") is not False):
            raise SessionHandoffError("V1/V2/V3 signatures failed closed")
        checked = receipt.verify_local_receipt(
            path, source, expected_challenge=pins["expected_challenge"],
            expected_receipt_sha256=expected_native_receipt_sha256,
            require_readonly_source_view=True)
        if (type(checked) is not dict
                or checked.get("status") != "LOCAL_RECEIPT_CONSISTENCY_VALIDATED"
                or checked.get("security_classification") !=
                   "UNSIGNED_NOT_INDEPENDENT_VM_ATTESTATION"
                or checked.get("receipt_sha256") != expected_native_receipt_sha256
                or checked.get("source_files_rechecked") != len(evidence.SOURCE_FILES)
                or checked.get("external_receipt_sha256_pin_matched") is not True
                or checked.get("readonly_source_view_verified") is not True
                or checked.get("reviewer_challenge_correlated") is not True
                or checked.get("native_kernel_execution_independently_verified") is not False
                or checked.get("windows_binary_executed_by_reviewer") is not False
                or checked.get("independent_vm_attestation") is not False):
            raise SessionHandoffError("Local receipt / source manifest contradicted HOLD")
        git = checkout.verify_source_checkout_pin(
            source, pins["expected_source_commit"], evidence.SOURCE_FILES)
        if (type(git) is not dict or
                git.get("status") != "LOCAL_GIT_CHECKOUT_PIN_MATCHED"
                or git.get("expected_commit") != pins["expected_source_commit"]
                or git.get("checked_manifest_entries") != len(evidence.SOURCE_FILES)
                or git.get("worktree_status_clean") is not True
                or git.get("git_authorship_or_signature_verified") is not False
                or git.get("native_vm_or_kernel_verified") is not False):
            raise SessionHandoffError("Local source checkout is not exact pinned commit")
        if _receipt_bytes(path, expected_native_receipt_sha256) != original:
            raise SessionHandoffError("Native receipt changed during host signature review")
        # Repeat the V3 chain after the guest and source checks. There is
        # still no atomic host+guest snapshot or trusted capture timestamp.
        final = v3.verify_signed_domstats_extension(
            owner, operator,
            expected_extension_manifest_sha256=expected_v3_manifest_sha256,
            expected_extension_signature_sha256=expected_v3_signature_sha256,
            **pins)
        if final != signed:
            raise SessionHandoffError("Signed host package changed during joint review")
        if _receipt_bytes(path, expected_native_receipt_sha256) != original:
            raise SessionHandoffError("Guest receipt was replaced during final review")
    except (v3.SignedDomstatsExtensionError,
            receipt.ReceiptReviewError,
            checkout.CheckoutPinError,
            OSError, ValueError, TypeError, KeyError,
            OverflowError, RecursionError) as exc:
        raise SessionHandoffError(
            "Native receipt / signed V3 host evidence joint review rejected") from exc
    return {
        "status": STATUS,
        "v1_v2_v3_detached_signatures_verified": True,
        "v3_before_after_host_sha256_pins_correlated": True,
        "native_receipt_sha256_equals_v1_signed_receipt_pin": True,
        "guest_receipt_challenge_and_sources_rechecked": True,
        "source_commit_checkout_locally_rechecked": True,
        "independent_host_control_attested": False,
        "guest_kernel_execution_independently_attested": False,
        "session_chronology_independently_verified": False,
        "journal_kernel_storage_quota_verified": False,
        "independent_vm_attestation": False,
        "release_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline V3 host + local native receipt correlation. HOLD ONLY")
    parser.add_argument("--observer-dir", type=Path, required=True)
    parser.add_argument("--custody-dir", type=Path, required=True)
    parser.add_argument("--native-receipt", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--expected-native-receipt-sha256", required=True)
    parser.add_argument("--expected-v3-manifest-sha256", required=True)
    parser.add_argument("--expected-v3-signature-sha256", required=True)
    for key in v3.PINS:
        parser.add_argument("--" + key.replace("_", "-"), required=True)
    args = parser.parse_args(argv)
    pins = {key: getattr(args, key) for key in v3.PINS}
    try:
        result = verify_reviewer_session(
            args.observer_dir, args.custody_dir,
            args.native_receipt, args.source_root,
            expected_native_receipt_sha256=args.expected_native_receipt_sha256,
            expected_v3_manifest_sha256=args.expected_v3_manifest_sha256,
            expected_v3_signature_sha256=args.expected_v3_signature_sha256,
            **pins)
        print(json.dumps(result, sort_keys=True))
        return 2  # Authenticated text + local receipt is still HOLD.
    except (SessionHandoffError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "status": REJECTED, "reason": str(exc),
            "independent_vm_attestation": False,
            "release_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
