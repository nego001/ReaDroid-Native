#!/usr/bin/env python3
"""PE-S1.5: real, synthetic-only Ghidra + cgroup acceptance inside an Arch VM.

Requires a manually provisioned disposable Arch VM, a normal user session,
JDK 25 and a separately verified Ghidra 12.2 installation. Never downloads
software, runs Windows PE code, changes kernel settings, or publishes artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from pe_arch_vm_gate import verify_arch_vm, ArchVmUnavailable
from pe_arch_vm_checkout_pin import (verify_source_checkout_pin,
                                     CheckoutPinError)
import pe_arch_vm_evidence as evidence
from pe_arch_cgroup_smoke import run_smoke
from pe_arch_descendant_smoke import run_native_descendant_smoke
from pe_auto_ghidra import inspect_functions, HeadlessError
from pe_ghidra_sandbox import build_command, SandboxUnavailable
from pe_ghidra_integrity import verify_pinned_ghidra_tree, GhidraIntegrityError
from pe_arch_scoped_seccomp_smoke import (run_scoped_seccomp_probe,
                                          ScopedSeccompSmokeError)
from pe_arch_scoped_ghidra_smoke import (run_native_scoped_ghidra,
                                         ScopedGhidraError)
from pe_arch_vm_evidence import (write_receipt_no_overwrite,
                                 validate_native_acceptance_report,
                                 require_reviewer_challenge,
                                 AcceptanceReceiptError)

FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/pe_headless_smoke.c"
PROBE = Path(__file__).resolve().parents[1] / "tests/pe_sandbox_probe.py"
GHIDRA_SCRIPT = Path(__file__).resolve().parent / "ghidra_scripts/NegrescoFunctionInventory.java"


class ArchVmValidationError(RuntimeError):
    pass


def java25_preflight() -> None:
    raw = os.environ.get("JAVA_HOME", "")
    if not raw or not Path(raw).is_absolute():
        raise ArchVmValidationError("JAVA_HOME must point to an installed JDK 25")
    java = Path(raw) / "bin/java"
    if java.is_symlink() or not java.is_file() or not os.access(java, os.X_OK):
        raise ArchVmValidationError("JAVA_HOME/bin/java unavailable")
    try:
        result = subprocess.run(
            [str(java), "-version"], capture_output=True, text=True,
            timeout=10, check=False, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ArchVmValidationError("JDK version cannot be checked") from exc
    version_text = result.stdout + result.stderr
    if result.returncode != 0 or not re.search(
            r'(?:openjdk|java) version "25(?:[."]|\+)', version_text, re.I):
        raise ArchVmValidationError("Expected an operational JDK 25")


def validate_ghidra_122_install(ghidra_home: Path) -> None:
    """Check release identity; authenticity still requires a pinned ZIP hash."""
    props = ghidra_home / "Ghidra/application.properties"
    try:
        if props.is_symlink() or not props.is_file() or props.stat().st_size > 8192:
            raise ArchVmValidationError("Ghidra 12.2 version metadata missing")
        values = {}
        for line in props.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "!")):
                continue
            if "=" not in line:
                raise ArchVmValidationError("Malformed Ghidra release metadata")
            key, value = (part.strip() for part in line.split("=", 1))
            if key in values:
                raise ArchVmValidationError("Duplicate Ghidra release property")
            values[key] = value
        if values.get("application.name") != "Ghidra" or values.get("application.version") != "12.2":
            raise ArchVmValidationError("Ghidra release must be exactly 12.2")
    except (OSError, UnicodeError) as exc:
        raise ArchVmValidationError("Ghidra version cannot be verified") from exc


def native_bwrap_probe(ghidra_home: Path, pe: Path, root: Path) -> dict:
    """Run the Ubuntu isolation probe under the actual Arch VM kernel."""
    if not PROBE.is_file() or not GHIDRA_SCRIPT.is_file():
        raise ArchVmValidationError("Bubblewrap probe/source scripts missing")
    canary = root / "host-private-canary"
    canary.write_text("synthetic-marker", encoding="ascii")
    canary.chmod(0o600)
    work = root / "probe-workspace"
    scripts = work / "scripts"
    scripts.mkdir(parents=True, mode=0o700)
    (work / "project").mkdir(mode=0o700)
    shutil.copyfile(GHIDRA_SCRIPT, scripts / GHIDRA_SCRIPT.name)
    shutil.copyfile(PROBE, work / "pe_sandbox_probe.py")
    shutil.copyfile(pe, work / "input.exe")
    try:
        argv = build_command(ghidra_home, work, 120)
        boundary = argv.index("--")
        host_fd = os.open(canary, os.O_RDONLY)
        try:
            os.set_inheritable(host_fd, True)
            identity = os.fstat(host_fd)
            argv = argv[:boundary + 1] + [
                "/usr/bin/python3", "/work/pe_sandbox_probe.py",
                os.readlink("/proc/self/ns/net"), str(canary),
                str(identity.st_dev), str(identity.st_ino)]
            result = subprocess.run(
                argv, stdin=subprocess.DEVNULL, capture_output=True,
                text=True, timeout=35, check=False, close_fds=True)
        finally:
            os.close(host_fd)
    except (OSError, ValueError, SandboxUnavailable,
            subprocess.TimeoutExpired) as exc:
        raise ArchVmValidationError("Real Arch Bubblewrap probe could not execute") from exc
    if result.returncode != 0:
        raise ArchVmValidationError("Real Arch Bubblewrap isolation probe failed")
    try:
        records = [json.loads(line) for line in result.stdout.splitlines()
                   if line.lstrip().startswith("{")]
    except json.JSONDecodeError as exc:
        raise ArchVmValidationError("Real Arch Bubblewrap probe evidence malformed") from exc
    fields = ("host_home_canary_hidden", "network_namespace_separate",
              "host_etc_hidden", "usr_runtime_read_only", "private_work_writable",
              "inherited_host_fd_hidden")
    if not any(isinstance(item, dict) and item.get("isolation_probe") == "passed"
               and all(item.get(field) is True for field in fields)
               for item in records):
        raise ArchVmValidationError("Arch Bubblewrap isolation evidence incomplete")
    return {"status": "PASS_NATIVE_ARCH_BWRAP_PROBE",
            **{field: True for field in fields}}


def validate_real_ghidra(ghidra_home: Path, release_zip: Path, *,
                         timeout_seconds: int = 420) -> dict:
    if (not ghidra_home.is_absolute() or ghidra_home.is_symlink()
            or not (ghidra_home / "support/analyzeHeadless").is_file()):
        raise ArchVmValidationError("Trusted absolute Ghidra directory required")
    integrity = verify_pinned_ghidra_tree(ghidra_home, release_zip)
    validate_ghidra_122_install(ghidra_home)
    if not FIXTURE.is_file() or FIXTURE.is_symlink():
        raise ArchVmValidationError("Synthetic PE fixture source is absent")
    java25_preflight()
    if type(timeout_seconds) is not int or not 90 <= timeout_seconds <= 1800:
        raise ArchVmValidationError("Unsupported timeout for real Ghidra")
    with tempfile.TemporaryDirectory(prefix="negresco-arch-vm-ghidra-") as directory:
        root = Path(directory)
        pe = root / "synthetic-fixture.exe"
        report_path = root / "result.json"
        try:
            subprocess.run(
                ["x86_64-w64-mingw32-gcc", "-O0", "-g0",
                 str(FIXTURE), "-o", str(pe)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, text=True, timeout=90, check=True)
        except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            raise ArchVmValidationError("Synthetic PE compile failed") from exc
        isolation = native_bwrap_probe(ghidra_home, pe, root)
        scoped_seccomp = run_scoped_seccomp_probe(ghidra_home, pe, root)
        if (scoped_seccomp.get("status") != "PASS_NATIVE_ARCH_VM_SCOPED_SECCOMP"
                or scoped_seccomp.get("filter_compiled_after_guard") is not True
                or not isinstance(scoped_seccomp.get("cgroup_verification"), dict)):
            raise ArchVmValidationError(
                "Scoped seccomp/cgroup joint native attestation incomplete")
        actual_combined = run_native_scoped_ghidra(
            ghidra_home, pe, root, timeout_seconds=timeout_seconds)
        if (actual_combined.get("status")
                != "PASS_NATIVE_ARCH_REAL_GHIDRA_WITH_CGROUP_AND_SECCOMP"
                or actual_combined.get("scope_cleanup_verified") is not True
                or not isinstance(actual_combined.get("scope_cleanup_evidence"), dict)
                or actual_combined["scope_cleanup_evidence"].get("scope_quiescent") is not True
                or actual_combined["scope_cleanup_evidence"].get("cgroup_unpopulated") is not True
                or not isinstance(scoped_seccomp.get("scope_cleanup_evidence"), dict)
                or actual_combined["scope_cleanup_evidence"].get("scope")
                   != actual_combined.get("scope")
                or scoped_seccomp["scope_cleanup_evidence"].get("scope")
                   != scoped_seccomp.get("scope")
                or scoped_seccomp["scope_cleanup_evidence"].get("scope_quiescent") is not True
                or actual_combined.get("filter_compiled_inside_scope") is not True
                or not isinstance(
                    actual_combined.get("quotas_verified_before_bwrap"), dict)
                or not isinstance(
                    actual_combined.get("ghidra_jvm_seccomp_evidence"), dict)
                or actual_combined["ghidra_jvm_seccomp_evidence"].get("verified") is not True
                or actual_combined["ghidra_jvm_seccomp_evidence"].get("seccomp_mode") != 2
                or actual_combined.get("decompiled_functions", 0) < 1):
            raise ArchVmValidationError(
                "Real Ghidra under simultaneous cgroup/seccomp not proven")
        report = inspect_functions(
            pe, ghidra_home, report_path, timeout_seconds=timeout_seconds,
            sandbox_mode="bwrap", require_cgroup_limits=True, deep_preview=True)
        limits = report.get("limitations", {})
        proof = limits.get("resource_limits")
        if (limits.get("os_sandbox") != "bubblewrap_profile"
                or limits.get("executable_launched") is not False
                or limits.get("resource_scope") != "systemd_user_cgroup_v2_verified_at_start"
                or not isinstance(proof, dict)
                or proof.get("verification") != "guard_verified_before_bwrap"
                or report["evidence"]["total_discovered"] < 1
                or not any(f.get("decompile_status") == "ok"
                           for f in report["deep_preview"]["functions"])
                or not report_path.is_file()):
            raise ArchVmValidationError("Ghidra or effective cgroup proof incomplete")
        # The two independent analysis runs operate on the same synthetic
        # PE and pinned inventory script. A disagreement is a failed native
        # acceptance rather than two unrelated PASS claims.
        if (type(actual_combined.get("ghidra_functions_discovered")) is not int
                or actual_combined["ghidra_functions_discovered"]
                   != report["evidence"]["total_discovered"]):
            raise ArchVmValidationError(
                "Standalone and combined Ghidra function inventories disagree")
        return {"status": "PASS_REAL_ARCH_VM_GHIDRA",
                "ghidra_functions": report["evidence"]["total_discovered"],
                "memory_max_bytes": proof["memory_max_bytes"],
                "tasks_max": proof["tasks_max"],
                "cpu_quota": proof["cpu_quota"],
                "cpu_period": proof["cpu_period"],
                "pe_executed": False, "sandbox": "bubblewrap",
                "ghidra_integrity": integrity,
                "arch_isolation_probe": isolation,
                "arch_scoped_seccomp_probe": scoped_seccomp,
                "arch_real_ghidra_with_both": actual_combined}


def run_acceptance(ghidra_home: Path, release_zip: Path, *,
                   timeout_seconds: int = 420) -> dict:
    environment = verify_arch_vm()
    quotas = run_smoke()
    # Refuse before starting the SIGTERM-resistant descendant experiment if
    # the harmless initial scope lacked private quotas or final kernel cleanup.
    initial_cleanup = quotas.get("scope_cleanup_evidence")
    if (quotas.get("status") != "PASS_NATIVE_ARCH_CGROUP"
            or not isinstance(quotas.get("quota_private_proof"), dict)
            or quotas["quota_private_proof"].get("verification") != "guard_verified_before_bwrap"
            or not isinstance(initial_cleanup, dict)
            or initial_cleanup.get("scope") != quotas.get("scope")
            or initial_cleanup.get("verified") is not True
            or initial_cleanup.get("scope_quiescent") is not True
            or initial_cleanup.get("cgroup_unpopulated") is not True
            or initial_cleanup.get("active_state") != "inactive"
            or initial_cleanup.get("sub_state") != "dead"):
        raise ArchVmValidationError(
            "Initial native cgroup quotas and lifecycle not approved")
    descendants = run_native_descendant_smoke()
    if (descendants.get("status") != "PASS_NATIVE_ARCH_DESCENDANTS"
            or descendants.get("detached_sigterm_ignoring_child_terminated") is not True
            or descendants.get("systemd_stop_succeeded") is not True
            or descendants.get("quota_verified") is not True
            or not isinstance(descendants.get("quota_private_proof"), dict)
            or descendants["quota_private_proof"].get("verification") != "guard_verified_before_bwrap"
            or not isinstance(descendants.get("descendant_cleanup_evidence"), dict)
            or descendants["descendant_cleanup_evidence"].get("scope") != descendants.get("scope")
            or descendants["descendant_cleanup_evidence"].get("verified") is not True
            or descendants["descendant_cleanup_evidence"].get("scope_quiescent") is not True
            or descendants["descendant_cleanup_evidence"].get("cgroup_unpopulated") is not True):
        raise ArchVmValidationError("Native cgroup and descendant lifecycle not approved")
    ghidra = validate_real_ghidra(ghidra_home, release_zip,
                                 timeout_seconds=timeout_seconds)
    report = {"status": "PASS_PE_S1_5_ARCH_VM", "environment": environment,
              "cgroup": {k: quotas[k] for k in
                         ("memory_max", "pids_max", "cpu_quota", "cpu_period")},
              "cgroup_lifecycle": quotas,
              "descendants_terminated": True, "descendant_lifecycle": descendants,
              "ghidra": ghidra, "windows_binary_executed": False}
    # Enforce the SAME strict report checks whether or not the operator
    # requested an on-disk receipt. Otherwise CLI stdout could announce
    # PASS while a private receipt would correctly reject those claims.
    try:
        validate_native_acceptance_report(report)
    except AcceptanceReceiptError as exc:
        raise ArchVmValidationError(
            "Inconsistent native Arch security evidence; PASS refused") from exc
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Strict PE-S1.5 Arch VM acceptance, synthetic executable only")
    parser.add_argument("--ghidra-home", required=True, type=Path)
    parser.add_argument("--ghidra-archive", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=420)
    parser.add_argument("--evidence-output", type=Path,
                        help="Optional new JSON receipt file inside an owner-only 0700 directory; never overwrites")
    parser.add_argument("--reviewer-challenge",
                        help="External 64-hex challenge chosen BEFORE VM execution; required with --evidence-output")
    parser.add_argument(
        "--reviewer-pinned-checkout", action="store_true",
        help="Opt-in reviewer protocol: require external full commit pin, "
             "challenge and private receipt before running native tests")
    parser.add_argument(
        "--expected-source-commit",
        help="Full lowercase Git commit chosen by reviewer outside the VM")
    args = parser.parse_args()
    try:
        if args.reviewer_pinned_checkout:
            if args.evidence_output is None or args.reviewer_challenge is None:
                raise ArchVmValidationError(
                    "Reviewer-pinned checkout requires private receipt "
                    "and external reviewer challenge")
            if args.expected_source_commit is None:
                raise ArchVmValidationError(
                    "Reviewer-pinned checkout requires external source commit")
        elif args.expected_source_commit is not None:
            raise ArchVmValidationError(
                "Expected source commit requires --reviewer-pinned-checkout")
        if args.evidence_output is not None:
            require_reviewer_challenge(args.reviewer_challenge)
        elif args.reviewer_challenge is not None:
            raise ArchVmValidationError(
                "Reviewer challenge requires --evidence-output")
        # Refuse mismatch/dirty/untracked inputs BEFORE any cgroup,
        # descendant or Ghidra workload is started. This only checks local
        # Git state, never authenticity of the VM or the Git host.
        checkout_pin = None
        if args.reviewer_pinned_checkout:
            checkout_pin = verify_source_checkout_pin(
                Path(__file__).resolve().parents[1],
                args.expected_source_commit, evidence.SOURCE_FILES)
        proof = run_acceptance(args.ghidra_home, args.ghidra_archive,
                               timeout_seconds=args.timeout_seconds)
        if args.evidence_output is not None:
            receipt = write_receipt_no_overwrite(
                proof, args.evidence_output,
                reviewer_challenge=args.reviewer_challenge)
            # Printed acknowledgement is separate from the hashed source
            # report inside the receipt. A digest is NOT a digital signature.
            proof = {**proof, "local_receipt": receipt}
        if checkout_pin is not None:
            # Print the local pin *outside* the strict native report v2
            # schema, after the actual receipt has been published intact.
            proof = {**proof, "local_source_checkout_pin": checkout_pin}
        print(json.dumps(proof, sort_keys=True))
        return 0
    except (CheckoutPinError, ArchVmUnavailable, ArchVmValidationError,
            GhidraIntegrityError,
            ScopedSeccompSmokeError, ScopedGhidraError,
            HeadlessError, AcceptanceReceiptError,
            RuntimeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "REJECTED_NOT_HOMOLOGATED",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
