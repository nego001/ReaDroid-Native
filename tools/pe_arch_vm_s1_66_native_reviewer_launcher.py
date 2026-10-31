#!/usr/bin/env python3
"""PE-S1.66: deliberately gated reviewer-side *native* synthetic acceptance.

Default is a NO-EXECUTION plan. Only --execute-synthetic-native-acceptance
in a disposable, independently administered Arch VM may start the existing
S1.5 native acceptance. The existing S1.58 preflight and S1.59 in-process
gate are mandatory; neither this tool nor its CI can attest a hypervisor,
person, trusted external host, native kernel provenance or signing time.

This tool never launches arbitrary/unknown Windows binaries and never
merges or publishes APK/OTA. Synthetic input is baked into the existing
native acceptance module. Success is LOCAL evidence, not release.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

sys.dont_write_bytecode = True

from pe_arch_vm_checkout_pin import COMMIT_SHA
from pe_arch_vm_evidence import SOURCE_FILES, require_reviewer_challenge
from pe_arch_vm_receipt_verify import _read_private_receipt
from pe_nofollow_paths import open_absolute_directory_nofollow
import pe_arch_vm_s1_58_preflight as preflight
from pe_arch_vm_gate import ArchVmUnavailable
from pe_arch_vm_evidence import AcceptanceReceiptError
from pe_arch_vm_receipt_verify import ReceiptReviewError

SOURCE_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = SOURCE_ROOT / "tools/pe_arch_vm_validation.py"
PLAN = "PE_S1_66_NATIVE_ACCEPTANCE_NOT_STARTED"
LOCAL_DONE = "LOCAL_PE_S1_66_SYNTHETIC_NATIVE_RECEIPT_NOT_VM_ATTESTATION"
REJECTED = "REJECTED_PE_S1_66_NATIVE_ACCEPTANCE_NOT_HOMOLOGATED"
MAX_STDOUT = 1024 * 1024
MAX_STDERR = 8192


class ReviewerLaunchError(RuntimeError):
    """No safe grounds to start or accept a reviewer VM's local run."""


def _absolute(path: Path) -> None:
    raw = os.fspath(path)
    if (not isinstance(raw, str) or not raw.startswith("/")
            or raw == "/" or any(c in ("", ".", "..")
                                  for c in raw[1:].split("/"))):
        raise ReviewerLaunchError("Canonical non-root absolute path required")


def _private_destination(path: Path) -> None:
    _absolute(path)
    with ExitStack() as stack:
        folder_fd = open_absolute_directory_nofollow(path.parent, stack)
        meta = os.fstat(folder_fd)
        if (meta.st_uid != os.geteuid()
                or not stat.S_ISDIR(meta.st_mode)
                or stat.S_IMODE(meta.st_mode) != 0o700):
            raise ReviewerLaunchError("Reviewer receipt folder must be owned 0700")
        try:
            os.stat(path.name, dir_fd=folder_fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise ReviewerLaunchError("Never overwrite an existing receipt")


def review_native_acceptance(
        ghidra_home: Path, ghidra_archive: Path, evidence_output: Path, *,
        expected_source_commit: str, reviewer_challenge: str,
        execute_synthetic_native_acceptance: bool = False) -> dict:
    """Return no-exec plan by default; explicit run only in vetted native VM.

    IMPORTANT: the local VM gate is a necessary safety precondition, but
    never a trusted independent attestation of the VM's origin.
    """
    if type(execute_synthetic_native_acceptance) is not bool:
        raise ReviewerLaunchError("Execution authorization must be boolean")
    if (not isinstance(expected_source_commit, str)
            or COMMIT_SHA.fullmatch(expected_source_commit) is None
            or expected_source_commit == "0" * 40):
        raise ReviewerLaunchError("Full, externally pinned source commit required")
    try:
        require_reviewer_challenge(reviewer_challenge)
        home = Path(ghidra_home)
        archive = Path(ghidra_archive)
        receipt = Path(evidence_output)
        for path in (home, archive, receipt):
            _absolute(path)
        # Early collision/path test, BEFORE any VM probes or subprocess.
        if (receipt == home or receipt in home.parents
                or home in receipt.parents
                or receipt == SOURCE_ROOT or SOURCE_ROOT in receipt.parents
                or not ACCEPTANCE.is_file() or ACCEPTANCE.is_symlink()):
            raise ReviewerLaunchError(
                "Receipt must be outside tool checkout and Ghidra tree")
        _private_destination(receipt)
    except (OSError, ValueError, AcceptanceReceiptError) as exc:
        raise ReviewerLaunchError("Invalid reviewer-controlled paths") from exc

    if not execute_synthetic_native_acceptance:
        return {
            "status": PLAN,
            "source_commit": expected_source_commit,
            "reviewer_challenge_correlated": True,
            "private_receipt_destination_unused": True,
            "native_guest_preflight_executed": False,
            "synthetic_acceptance_executed": False,
            "any_receipt_written": False,
            "independent_vm_attestation": False,
            "release_authorized": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }

    try:
        # S1.58: real VM/container/user-bus + pinned source/Ghidra preflight.
        # It is repeated *inside* S1.5's --reviewer-pinned-checkout flow.
        readiness = preflight.native_readiness(
            home, archive, SOURCE_ROOT, receipt,
            expected_source_commit=expected_source_commit,
            reviewer_challenge=reviewer_challenge)
        if (not isinstance(readiness, dict)
                or readiness.get("status") != preflight.STATUS
                or readiness.get("source_commit") != expected_source_commit
                or type(readiness.get("source_files_rechecked")) is not int
                or readiness["source_files_rechecked"] != len(SOURCE_FILES)
                or readiness.get("native_guest_preflight_locally_passed") is not True
                or readiness.get("pinned_ghidra_install_locally_verified") is not True
                or readiness.get("receipt_destination_unused_private") is not True
                or readiness.get("any_receipt_written") is not False
                or readiness.get("independent_vm_attestation") is not False
                or readiness.get("apk_or_ota_publication_authorized") is not False):
            raise ReviewerLaunchError("Native preflight output contradicted security contract")

        argv = [
            sys.executable, "-B", str(ACCEPTANCE),
            "--ghidra-home", str(home),
            "--ghidra-archive", str(archive),
            "--evidence-output", str(receipt),
            "--expected-source-commit", expected_source_commit,
            "--reviewer-challenge", reviewer_challenge,
            "--reviewer-pinned-checkout",
        ]
        # Untrusted environment variables must not alter Python module
        # resolution, Git worktree or Java runtime arguments.
        env = {name: val for name, val in os.environ.items()
               if not name.startswith("GIT_") and name not in {
                   "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP",
                   "PYTHONINSPECT", "PYTHONBREAKPOINT",
                   "JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS",
               }}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        run = subprocess.run(
            argv, stdin=subprocess.DEVNULL,
            capture_output=True, timeout=1800, check=False,
            close_fds=True, env=env)
        if (run.returncode != 0 or
                not 0 < len(run.stdout) <= MAX_STDOUT or
                len(run.stderr) > MAX_STDERR):
            raise ReviewerLaunchError(
                "Native acceptance refused or output exceeded strict bounds")
        result = json.loads(run.stdout.decode("utf-8"))
        if (not isinstance(result, dict)
                or result.get("status") != "PASS_PE_S1_5_ARCH_VM"
                or result.get("windows_binary_executed") is not False
                or not isinstance(result.get("local_receipt"), dict)
                or set(result["local_receipt"]) != {
                    "path", "receipt_sha256", "record_type",
                }
                or result["local_receipt"]["path"] != str(receipt)
                or result["local_receipt"]["record_type"] !=
                    "LOCAL_SELF_REPORT_NOT_SIGNED"
                or not isinstance(result["local_receipt"]["receipt_sha256"], str)
                or re.fullmatch(
                    r"[0-9a-f]{64}",
                    result["local_receipt"]["receipt_sha256"]) is None
                or not isinstance(result.get("local_source_checkout_pin"), dict)
                or result["local_source_checkout_pin"].get(
                    "expected_commit") != expected_source_commit
                or result["local_source_checkout_pin"].get(
                    "worktree_status_clean") is not True
                or result["local_source_checkout_pin"].get(
                    "native_vm_or_kernel_verified") is not False):
            raise ReviewerLaunchError(
                "Native acceptance stdout has incompatible or false claims")
        raw = _read_private_receipt(receipt)
        actual = hashlib.sha256(raw).hexdigest()
        if actual != result["local_receipt"]["receipt_sha256"]:
            raise ReviewerLaunchError("Local receipt hash differs from runner record")
        # Check exact hash binding/challenge, not only supplied stdout.
        parsed = json.loads(raw.decode("utf-8"))
        if (not isinstance(parsed, dict)
                or parsed.get("reviewer_challenge") != reviewer_challenge
                or parsed.get("windows_executable_launched") is not False):
            raise ReviewerLaunchError(
                "Native receipt not bound to original reviewer challenge")
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            OverflowError, RecursionError, subprocess.TimeoutExpired,
            preflight.NativePreflightError, ReceiptReviewError) as exc:
        raise ReviewerLaunchError(
            "Native synthetic acceptance refused; never interpret as VM attestation"
        ) from exc

    return {
        "status": LOCAL_DONE,
        "source_commit": expected_source_commit,
        "local_receipt_sha256": actual,
        "reviewer_challenge_correlated": True,
        "native_guest_preflight_locally_passed": True,
        "synthetic_acceptance_executed": True,
        "unknown_windows_pe_executed": False,
        "independent_vm_attestation": False,
        "host_or_hypervisor_independently_authenticated": False,
        "release_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Readiness plan by default; native synthetic test requires explicit opt-in")
    parser.add_argument("--ghidra-home", required=True, type=Path)
    parser.add_argument("--ghidra-archive", required=True, type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--reviewer-challenge", required=True)
    parser.add_argument("--execute-synthetic-native-acceptance",
                        action="store_true")
    args = parser.parse_args(argv)
    try:
        report = review_native_acceptance(
            args.ghidra_home, args.ghidra_archive, args.evidence_output,
            expected_source_commit=args.expected_source_commit,
            reviewer_challenge=args.reviewer_challenge,
            execute_synthetic_native_acceptance=
                args.execute_synthetic_native_acceptance)
        print(json.dumps(report, sort_keys=True))
        return 0  # Only local preflight planning or synthetic receipt completed.
    except ReviewerLaunchError as exc:
        print(json.dumps({
            "status": REJECTED, "reason": str(exc),
            "independent_vm_attestation": False,
            "release_authorized": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
