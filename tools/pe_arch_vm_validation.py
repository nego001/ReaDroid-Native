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
import subprocess
import sys
import tempfile

from pe_arch_vm_gate import verify_arch_vm, ArchVmUnavailable
from pe_arch_cgroup_smoke import run_smoke
from pe_arch_descendant_smoke import run_native_descendant_smoke
from pe_auto_ghidra import inspect_functions, HeadlessError

FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/pe_headless_smoke.c"


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


def validate_real_ghidra(ghidra_home: Path, *, timeout_seconds: int = 420) -> dict:
    if (not ghidra_home.is_absolute() or ghidra_home.is_symlink()
            or not (ghidra_home / "support/analyzeHeadless").is_file()):
        raise ArchVmValidationError("Trusted absolute Ghidra directory required")
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
        return {"status": "PASS_REAL_ARCH_VM_GHIDRA",
                "ghidra_functions": report["evidence"]["total_discovered"],
                "memory_max_bytes": proof["memory_max_bytes"],
                "tasks_max": proof["tasks_max"],
                "cpu_quota": proof["cpu_quota"],
                "cpu_period": proof["cpu_period"],
                "pe_executed": False, "sandbox": "bubblewrap"}


def run_acceptance(ghidra_home: Path, *, timeout_seconds: int = 420) -> dict:
    environment = verify_arch_vm()
    quotas = run_smoke()
    descendants = run_native_descendant_smoke()
    if (quotas.get("status") != "PASS_NATIVE_ARCH_CGROUP"
            or descendants.get("status") != "PASS_NATIVE_ARCH_DESCENDANTS"
            or descendants.get("detached_sigterm_ignoring_child_terminated") is not True):
        raise ArchVmValidationError("Native cgroup and descendant checks not approved")
    ghidra = validate_real_ghidra(ghidra_home, timeout_seconds=timeout_seconds)
    return {"status": "PASS_PE_S1_5_ARCH_VM", "environment": environment,
            "cgroup": {k: quotas[k] for k in
                       ("memory_max", "pids_max", "cpu_quota", "cpu_period")},
            "descendants_terminated": True, "ghidra": ghidra,
            "windows_binary_executed": False}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Strict PE-S1.5 Arch VM acceptance, synthetic executable only")
    parser.add_argument("--ghidra-home", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=420)
    args = parser.parse_args()
    try:
        proof = run_acceptance(args.ghidra_home,
                               timeout_seconds=args.timeout_seconds)
        print(json.dumps(proof, sort_keys=True))
        return 0
    except (ArchVmUnavailable, ArchVmValidationError, HeadlessError,
            RuntimeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "REJECTED_NOT_HOMOLOGATED",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
