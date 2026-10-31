#!/usr/bin/env python3
"""PE-S1.58: READ-ONLY native Arch VM acceptance preflight.

Run this manually in a disposable, separately provisioned native Arch VM,
before the existing PE-S1.5 acceptance. Never starts Ghidra, a cgroup scope,
a sandbox, a Windows binary, or an unknown guest process. It checks the
already-installed pinned Ghidra tree, reviewer-selected source Git commit,
a valid challenge, and a new private receipt destination. Passing this
local preflight NEVER counts as independent VM/hypervisor attestation.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True

from pe_arch_vm_checkout_pin import COMMIT_SHA, verify_source_checkout_pin, CheckoutPinError
from pe_arch_vm_evidence import (SOURCE_FILES, require_reviewer_challenge,
                                 STAGE_PATTERN, AcceptanceReceiptError)
from pe_arch_vm_gate import verify_arch_vm, ArchVmUnavailable
from pe_arch_vm_validation import (java25_preflight,
                                   validate_ghidra_122_install,
                                   ArchVmValidationError)
from pe_ghidra_integrity import (verify_pinned_ghidra_tree,
                                 GHIDRA_RELEASE_SHA256, GhidraIntegrityError)
from pe_nofollow_paths import open_absolute_directory_nofollow

STATUS = "READY_LOCAL_PE_S1_58_NATIVE_ARCH_VM_PREFLIGHT_NOT_ATTESTED"
REJECTED = "REJECTED_PE_S1_58_VM_PREFLIGHT_NOT_HOMOLOGATED"
WORKSPACE = Path(__file__).resolve().parents[1]


class NativePreflightError(RuntimeError):
    """The local guest or reviewer input is not safe for native acceptance."""


def _inside_or_equal(candidate: Path, ancestor: Path) -> bool:
    return candidate == ancestor or ancestor in candidate.parents


def _private_new_receipt(destination: Path, source: Path,
                         ghidra_home: Path) -> None:
    """Check target name and owner-only ancestor; never create a file."""
    path = Path(destination)
    if (not path.is_absolute() or path.name in ("", ".", "..")
            or any(component in (".", "..", "") for component in path.parts[1:])
            or STAGE_PATTERN.fullmatch(path.name) is not None
            or _inside_or_equal(path, source)
            or _inside_or_equal(path, ghidra_home)):
        raise NativePreflightError(
            "New receipt must be an absolute private path outside source/Ghidra")
    try:
        with ExitStack() as stack:
            fd = open_absolute_directory_nofollow(path.parent, stack)
            metadata = os.fstat(fd)
            if (not stat.S_ISDIR(metadata.st_mode)
                    or metadata.st_uid != os.geteuid()
                    or stat.S_IMODE(metadata.st_mode) != 0o700):
                raise NativePreflightError(
                    "Receipt directory must belong to caller and be mode 0700")
            try:
                os.stat(path.name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                return
            raise NativePreflightError(
                "Receipt destination already exists: never overwrite evidence")
    except (OSError, ValueError) as exc:
        raise NativePreflightError(
            "Cannot inspect nofollow private receipt destination") from exc


def native_readiness(ghidra_home: Path, release_zip: Path,
                     source_root: Path, receipt_destination: Path, *,
                     expected_source_commit: str,
                     reviewer_challenge: str) -> dict:
    """Fail closed without creating any cgroup, receipt, VM, or workload."""
    source = Path(source_root)
    home = Path(ghidra_home)
    archive = Path(release_zip)
    if (not source.is_absolute() or source != WORKSPACE
            or not home.is_absolute() or not archive.is_absolute()
            or any(part in (".", "..", "") for path in (home, archive)
                   for part in path.parts[1:])
            or not isinstance(expected_source_commit, str)
            or COMMIT_SHA.fullmatch(expected_source_commit) is None
            or expected_source_commit == "0" * 40):
        raise NativePreflightError(
            "Exact local tool checkout, absolute Ghidra paths and external commit required")
    try:
        require_reviewer_challenge(reviewer_challenge)
        _private_new_receipt(Path(receipt_destination), source, home)
        # A check performed in the Ubuntu CI is deliberately blocked here.
        # The native gate itself is only a self-observation, not an identity
        # attestation of an external hypervisor/reviewer.
        guest = verify_arch_vm()
        if (not isinstance(guest, dict)
                or guest.get("status") != "ARCH_VM_PREFLIGHT_PASSED"
                or guest.get("vm_confirmed") is not True
                or guest.get("container") is not False
                or guest.get("root") is not False
                or guest.get("systemd_user_bus") is not True
                or guest.get("real_cgroup_test_executed") is not False):
            raise NativePreflightError("Native Arch VM gate incomplete")
        first = verify_source_checkout_pin(
            source, expected_source_commit, SOURCE_FILES)
        if (not isinstance(first, dict)
                or first.get("status") != "LOCAL_GIT_CHECKOUT_PIN_MATCHED"
                or first.get("expected_commit") != expected_source_commit
                or first.get("worktree_status_clean") is not True
                or first.get("checked_manifest_entries") != len(SOURCE_FILES)
                or first.get("git_authorship_or_signature_verified") is not False
                or first.get("native_vm_or_kernel_verified") is not False):
            raise NativePreflightError("Local checkout pin unproven")
        java25_preflight()
        validate_ghidra_122_install(home)
        integrity = verify_pinned_ghidra_tree(home, archive)
        if (not isinstance(integrity, dict)
                or integrity.get("verified") is not True
                or integrity.get("release_sha256") != GHIDRA_RELEASE_SHA256
                or type(integrity.get("matched_files")) is not int
                or integrity["matched_files"] < 1
                or integrity.get("symlinks_allowed") is not False
                or integrity.get("unexpected_files_allowed") is not False):
            raise NativePreflightError("Pinned Ghidra installation unproven")
        last = verify_source_checkout_pin(
            source, expected_source_commit, SOURCE_FILES)
        if last != first:
            raise NativePreflightError("Source checkout changed during preflight")
        # A last check catches a receipt name installed during hashing.
        _private_new_receipt(Path(receipt_destination), source, home)
    except (AcceptanceReceiptError, ArchVmUnavailable,
            ArchVmValidationError, CheckoutPinError, GhidraIntegrityError,
            OSError, ValueError, TypeError, KeyError) as exc:
        raise NativePreflightError("Native read-only readiness checks failed") from exc
    return {
        "status": STATUS,
        "source_commit": expected_source_commit,
        "source_files_rechecked": len(SOURCE_FILES),
        "reviewer_challenge_format_valid": True,
        "native_guest_preflight_locally_passed": True,
        "source_git_commit_and_clean_tree_locally_verified": True,
        "pinned_ghidra_install_locally_verified": True,
        "ghidra_release_sha256": GHIDRA_RELEASE_SHA256,
        "receipt_destination_unused_private": True,
        "any_receipt_written": False,
        "any_cgroup_scope_created": False,
        "ghidra_or_windows_binary_executed": False,
        "independent_vm_attestation": False,
        "independent_reviewer_or_hypervisor_verified": False,
        "native_seccomp_and_cgroups_execution_verified": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Check native Arch VM input readiness WITHOUT running workloads")
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--ghidra-home", type=Path, required=True)
    ap.add_argument("--ghidra-archive", type=Path, required=True)
    ap.add_argument("--evidence-output", type=Path, required=True)
    ap.add_argument("--expected-source-commit", required=True)
    ap.add_argument("--reviewer-challenge", required=True)
    args = ap.parse_args(argv)
    try:
        print(json.dumps(native_readiness(
            args.ghidra_home, args.ghidra_archive,
            args.source_root, args.evidence_output,
            expected_source_commit=args.expected_source_commit,
            reviewer_challenge=args.reviewer_challenge), sort_keys=True))
        return 0
    except NativePreflightError as exc:
        print(json.dumps({
            "status": REJECTED,
            "reason": str(exc),
            "independent_vm_attestation": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
