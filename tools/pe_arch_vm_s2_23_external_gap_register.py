#!/usr/bin/env python3
"""PE-S2.23: finite external-review evidence gap register; always release HOLD.

Compose the existing strict S2.22 review with an explicit, NON-AUTOMATABLE
list of missing independent host/guest proofs. This does NOT certify a host,
guest or reviewer. No external evidence is accepted from a self-asserted
boolean and no automatic path can change any independent proof to 'verified'.
No I/O in PLAN mode. Active mode reads only the S2.22 offline package.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import pe_arch_vm_s2_22_external_reviewer_pins as pins

PLAN = "PE_S2_23_EXTERNAL_HOMOLOGATION_GAP_PLAN_NOT_STARTED"
PENDING = "HOLD_PE_S2_23_SIGNED_CUSTODY_VALID_EXTERNAL_VM_PROOFS_PENDING"
REJECTED = "REJECTED_PE_S2_23_LOCAL_PACKAGE_INVALID_EXTERNAL_VM_HOLD"
MISSING = "PENDING_INDEPENDENT_REVIEWER_EVIDENCE"
FIELDS = frozenset((
    "status", "local_signed_package_correlated", "source_classification",
    "external_evidence_requirement_count", "external_evidence",
    "independent_vm_attestation", "release_authorized",
    "apk_or_ota_publication_authorized", "unknown_windows_pe_execution_authorized",
))
# These are HUMAN reviewer proof requests, not files whose presence or hashes
# would establish authentic provenance.
REVIEW = (
    ("identity_and_independence_of_external_reviewer",
     "Reviewer verifies their identity/authorization and truly independent control"
     " outside the operator account; record reviewer and source of trust"),
    ("physical_or_administrative_control_of_hypervisor",
     "Independent reviewer controls QEMU/libvirt host; verify hypervisor machine,"
     " ownership and original KVM domain UUID outside the guest"),
    ("native_arch_guest_kernel_provenance",
     "Reviewer witnesses disposable native Arch guest boot, systemd, kernel,"
     " exact commit and synthetic-only test input, not a CI container"),
    ("same_session_cgroup_v2_and_seccomp_independently_observed",
     "Independent host/guest records bind running Ghidra PID, seccomp mode 2"
     " and kernel-enforced cgroup v2 limits to same domain/session/nonce"),
    ("journald_effective_kernel_storage_quota",
     "Reviewer establishes effective journal storage mount/limit, not merely"
     " a journald policy configuration or self-reported consumption"),
    ("guest_process_tree_cleanup_independently_observed",
     "Independent observer verifies scope and descendants exited after work,"
     " with no remaining process or scope able to bypass limits"),
    ("chronology_of_guest_work_between_host_samples",
     "Independent reviewer ties before and after host captures to the actual"
     " guest synthetic Ghidra run; increasing cpu.time alone is insufficient"),
)
assert tuple(key for key, _ in REVIEW) == pins.UNPROVEN
SOURCE = "S2.22_OFFLINE_LOCAL_CUSTODY_BYTES_NOT_EXTERNAL_VM_ATTESTATION"


class ExternalGapError(RuntimeError):
    """The supplied locally signed package was unsafe or unverified."""


def _missing_proofs() -> list[dict[str, str]]:
    return [
        {"requirement_id": key, "state": MISSING,
         "owner": "independent_human_reviewer",
         "needed_proof": proof}
        for key, proof in REVIEW
    ]


def _report(status: str, *, local: bool) -> dict:
    return {
        "status": status,
        "local_signed_package_correlated": local,
        "source_classification": SOURCE,
        "external_evidence_requirement_count": len(REVIEW),
        "external_evidence": _missing_proofs(),
        "independent_vm_attestation": False,
        "release_authorized": False,
        "apk_or_ota_publication_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
    }


def audit_external_review(pin_file: Path, observer_dir: Path,
                          custody_dir: Path, native_receipt: Path,
                          source_root: Path, *,
                          expected_pin_bundle_sha256: str) -> dict:
    """Read-only local signed-package correlation plus explicit gap report."""
    try:
        signed = pins.review_custody(
            pin_file, observer_dir, custody_dir, native_receipt, source_root,
            expected_pin_bundle_sha256=expected_pin_bundle_sha256)
    except (pins.ReviewerPinsError, OSError, ValueError, TypeError,
            KeyError, RecursionError) as exc:
        raise ExternalGapError("Local S2.22 signed package is not safe") from exc
    if (type(signed) is not dict
            or signed.get("status") != pins.VERIFIED
            or signed.get("canonical_out_of_band_pin_bundle_sha256_matched")
               is not True
            or signed.get("reviewer_pins_private_directory_disjoint") is not True
            or signed.get("v1_v2_v3_detached_signatures_locally_verified")
               is not True
            or signed.get("readonly_native_receipt_and_git_locally_verified")
               is not True
            or signed.get("unverified_independent_requirements") != list(pins.UNPROVEN)
            or any(signed.get(key) is not False for key in (
                "reviewer_identity_independently_attested",
                "hypervisor_independence_attested",
                "native_vm_kernel_attested",
                "independent_vm_attestation", "release_authorized",
                "apk_or_ota_publication_authorized",
                "unknown_windows_pe_execution_authorized"))):
        raise ExternalGapError(
            "Local review contradicted the independent proof HOLD boundary")
    result = _report(PENDING, local=True)
    if set(result) != FIELDS:
        raise ExternalGapError("Handoff report schema changed")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PE-S2.23 independent native Arch evidence gap report. HOLD only")
    parser.add_argument("--pin-file", required=True, type=Path)
    parser.add_argument("--observer-dir", required=True, type=Path)
    parser.add_argument("--custody-dir", required=True, type=Path)
    parser.add_argument("--native-receipt", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--expected-pin-bundle-sha256", required=True)
    parser.add_argument("--inspect-existing", action="store_true",
                        help="Explicitly opt in to the S2.22 local signed review")
    args = parser.parse_args(argv)
    if not args.inspect_existing:
        print(json.dumps(_report(PLAN, local=False), sort_keys=True))
        return 0  # No I/O, no inspection, no attestation or release.
    try:
        report = audit_external_review(
            args.pin_file, args.observer_dir, args.custody_dir,
            args.native_receipt, args.source_root,
            expected_pin_bundle_sha256=args.expected_pin_bundle_sha256)
        print(json.dumps(report, sort_keys=True))
    except (ExternalGapError, OSError, ValueError, TypeError) as exc:
        report = _report(REJECTED, local=False)
        report["reason"] = str(exc)
        print(json.dumps(report, sort_keys=True), file=sys.stderr)
    return 2  # A valid local signed package cannot approve native VM or release.


if __name__ == "__main__":
    raise SystemExit(main())
