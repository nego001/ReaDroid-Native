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

from pe_arch_vm_checkout_pin import (
    COMMIT_SHA, verify_source_checkout_pin, CheckoutPinError,
)
from pe_arch_vm_evidence import SOURCE_FILES, require_reviewer_challenge
from pe_arch_vm_receipt_verify import _read_private_receipt, _no_duplicate_keys
from pe_nofollow_paths import open_absolute_directory_nofollow
import pe_arch_vm_s1_58_preflight as preflight
from pe_arch_vm_gate import ArchVmUnavailable
from pe_arch_vm_evidence import AcceptanceReceiptError
from pe_arch_vm_receipt_verify import ReceiptReviewError
import pe_arch_vm_s1_67_receipt_binding as binding
import pe_arch_vm_s1_69_bounded_native_child as bounded
import pe_native_workspace_budget as storage

SOURCE_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = SOURCE_ROOT / "tools/pe_arch_vm_validation.py"
PLAN = "PE_S1_66_NATIVE_ACCEPTANCE_NOT_STARTED"
LOCAL_DONE = "LOCAL_PE_S1_66_SYNTHETIC_NATIVE_RECEIPT_NOT_VM_ATTESTATION"
REJECTED = "REJECTED_PE_S1_66_NATIVE_ACCEPTANCE_NOT_HOMOLOGATED"
MAX_STDOUT = 1024 * 1024
MAX_STDERR = 8192


# PE-S1.68: recheck the actual local Git worktree from the reviewer launcher,
# independently of the native child\'s self-reported checkout summary.
def _parent_checkout_pin(expected_source_commit: str) -> dict:
    observed = verify_source_checkout_pin(
        SOURCE_ROOT, expected_source_commit, SOURCE_FILES)
    expected = {
        "status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED",
        "expected_commit": expected_source_commit,
        "checked_manifest_entries": len(SOURCE_FILES),
        "worktree_status_clean": True,
        "git_authorship_or_signature_verified": False,
        "native_vm_or_kernel_verified": False,
    }
    if observed != expected:
        raise ReviewerLaunchError(
            "Parent-side source Git verification contradicted the checkout pin")
    return observed


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
        execute_synthetic_native_acceptance: bool = False,
        native_work_quota_root: Path | None = None) -> dict:
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

    if native_work_quota_root is None:
        raise ReviewerLaunchError(
            "Explicit native quota mount required before synthetic acceptance")
    try:
        quota_root = Path(native_work_quota_root)
        _absolute(quota_root)
        # The writable quota mount must be separate from the checked-out
        # source, the Ghidra release and the private receipt destination.
        # Otherwise a kernel-sized FS may still corrupt trusted evidence.
        if (quota_root == SOURCE_ROOT or quota_root in SOURCE_ROOT.parents
                or SOURCE_ROOT in quota_root.parents
                or quota_root == home or quota_root in home.parents
                or home in quota_root.parents
                or quota_root == receipt.parent
                or quota_root in receipt.parent.parents
                or receipt.parent in quota_root.parents):
            raise ReviewerLaunchError(
                "Native quota root must not overlap trusted source or evidence")
        storage.require_bounded_work_mount(quota_root)
    except (OSError, ValueError, TypeError,
            storage.NativeStorageBudgetError) as exc:
        raise ReviewerLaunchError(
            "Reviewer /work mount is not a private kernel-sized tmpfs") from exc
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

        # Independent of the child process, pin the local checkout before
        # native execution and compare it again after receipt verification.
        checkout_before = _parent_checkout_pin(expected_source_commit)

        argv = [
            sys.executable, "-I", "-B", str(ACCEPTANCE),
            "--ghidra-home", str(home),
            "--ghidra-archive", str(archive),
            "--native-work-quota-root", str(quota_root),
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
        # PE-S1.69: -I ignores Python environment and user site packages.
        # Read both pipes incrementally; never buffer arbitrary-length
        # stdout/stderr before deciding whether to reject the child.
        run = bounded.run_bounded_native(
            argv, env=env, timeout=1800,
            max_stdout=MAX_STDOUT, max_stderr=MAX_STDERR)
        if (run.returncode != 0 or
                not 0 < len(run.stdout) <= MAX_STDOUT or
                len(run.stderr) > MAX_STDERR):
            raise ReviewerLaunchError(
                "Native acceptance refused or output exceeded strict bounds")
        # Duplicate JSON keys and nonfinite literals can make one successful
        # response mean different things to different downstream parsers.
        result = json.loads(
            run.stdout.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ReviewerLaunchError("Nonfinite native acceptance stdout")))
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
        parsed = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ReviewerLaunchError("Nonfinite native receipt")))
        if (not isinstance(parsed, dict)
                or parsed.get("reviewer_challenge") != reviewer_challenge
                or parsed.get("windows_executable_launched") is not False):
            raise ReviewerLaunchError(
                "Native receipt not bound to original reviewer challenge")
        # PE-S1.67: require the ENTIRE native report in stdout to be exactly
        # the one revalidated inside the on-disk receipt, including all
        # source files and the strict S1.20 kernel/scope/seccomp contracts.
        verified = binding.verify_launcher_binding(
            result, receipt, SOURCE_ROOT,
            expected_challenge=reviewer_challenge,
            expected_source_commit=expected_source_commit,
            expected_receipt_sha256=actual)
        if (not isinstance(verified, dict)
                or verified.get("status") !=
                    "LOCAL_PE_S1_67_STRICT_RECEIPT_BINDING_NOT_VM_ATTESTATION"
                or verified.get("receipt_sha256") != actual
                or verified.get("source_commit") != expected_source_commit
                or verified.get("all_report_fields_matched") is not True
                or verified.get("source_manifest_revalidated") is not True
                or verified.get("independent_vm_attestation") is not False
                or verified.get("release_authorized") is not False
                or verified.get("unknown_windows_pe_execution_authorized") is not False
                or verified.get("apk_or_ota_publication_authorized") is not False):
            raise ReviewerLaunchError("Full receipt verifier contradicted HOLD")
        checkout_after = _parent_checkout_pin(expected_source_commit)
        if (checkout_after != checkout_before
                or result["local_source_checkout_pin"] != checkout_after):
            raise ReviewerLaunchError(
                "Child Git report diverged from independently checked parent worktree")
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            OverflowError, RecursionError, subprocess.TimeoutExpired,
            preflight.NativePreflightError, ReceiptReviewError,
            CheckoutPinError,
            binding.BindingError, bounded.BoundedNativeChildError) as exc:
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
    parser.add_argument(
        "--native-work-quota-root", type=Path,
        help="Reviewer-provisioned dedicated 64-512MiB owner-only tmpfs; "
             "mandatory with --execute-synthetic-native-acceptance")
    parser.add_argument("--execute-synthetic-native-acceptance",
                        action="store_true")
    args = parser.parse_args(argv)
    try:
        report = review_native_acceptance(
            args.ghidra_home, args.ghidra_archive, args.evidence_output,
            expected_source_commit=args.expected_source_commit,
            reviewer_challenge=args.reviewer_challenge,
            native_work_quota_root=args.native_work_quota_root,
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
