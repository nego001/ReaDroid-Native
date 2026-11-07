#!/usr/bin/env python3
"""PE-S1.8 synthetic-only Ghidra 12.2 compatibility smoke with real seccomp.

Compiles a repo-owned harmless C fixture into a PE, which Ghidra only parses.
Never launches Windows code. Separately requires a trusted official Ghidra ZIP
and runs Bubblewrap with the sealed libseccomp cBPF filter, no shell or root.
This is a smoke, not approval to turn on seccomp for hostile samples.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from pe_auto_ghidra import _validated_function_evidence, HeadlessError
from pe_ghidra_integrity import verify_pinned_ghidra_tree, GhidraIntegrityError
from pe_ghidra_sandbox import build_command, SandboxUnavailable
from pe_seccomp_filter import (attach_seccomp_fd, compile_seccomp_bpf_fd,
                               SeccompUnavailable)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/pe_headless_smoke.c"
SCRIPT = ROOT / "tools/ghidra_scripts/NegrescoFunctionInventory.java"


class GhidraSeccompSmokeError(RuntimeError):
    pass


def run_ghidra_seccomp_smoke(ghidra_home: Path, archive: Path) -> dict:
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise GhidraSeccompSmokeError("Smoke supported on Linux x86_64 only")
    if os.geteuid() == 0:
        raise GhidraSeccompSmokeError("Real seccomp Ghidra cannot run as root")
    if not FIXTURE.is_file() or FIXTURE.is_symlink():
        raise GhidraSeccompSmokeError("Synthetic fixture is missing")
    if not SCRIPT.is_file() or SCRIPT.is_symlink():
        raise GhidraSeccompSmokeError("Trusted Ghidra export script missing")
    if not shutil.which("x86_64-w64-mingw32-gcc"):
        raise GhidraSeccompSmokeError("Cross compiler unavailable")
    verified_install = verify_pinned_ghidra_tree(ghidra_home, archive)
    with tempfile.TemporaryDirectory(prefix="negresco-pe-seccomp-ghidra-") as temp:
        workspace = Path(temp)
        (workspace / "scripts").mkdir(mode=0o700)
        (workspace / "project").mkdir(mode=0o700)
        shutil.copyfile(SCRIPT, workspace / "scripts" / SCRIPT.name)
        pe = workspace / "input.exe"
        try:
            subprocess.run(
                ["x86_64-w64-mingw32-gcc", "-O0", "-g0",
                 str(FIXTURE), "-o", str(pe)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=90, check=True,
                close_fds=True)
        except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            raise GhidraSeccompSmokeError("Synthetic PE compilation failed") from exc
        command = build_command(ghidra_home, workspace, 420)
        fd = compile_seccomp_bpf_fd()
        try:
            command = attach_seccomp_fd(command, fd)
            try:
                execution = subprocess.run(
                    command, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=420, check=False, close_fds=True, pass_fds=(fd,))
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise GhidraSeccompSmokeError("Sandboxed Ghidra timed out or failed to start") from exc
        finally:
            os.close(fd)
        if execution.returncode != 0:
            raise GhidraSeccompSmokeError("Ghidra failed with seccomp policy active")
        evidence = _validated_function_evidence(workspace / "ghidra-functions.json")
        if evidence["total_discovered"] < 1:
            raise GhidraSeccompSmokeError("Ghidra did not discover any functions")
        return {
            "status": "PASS_REAL_GHIDRA_SECCOMP_SMOKE",
            "ghidra_12_2_pinned_install": verified_install["verified"],
            "matched_ghidra_files": verified_install["matched_files"],
            "seccomp_filter": "narrow_libseccomp_denylist_cBPF",
            "ghidra_functions_discovered": evidence["total_discovered"],
            "bubblewrap": True,
            "windows_binary_executed": False,
            "cgroup_limits_tested": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Real Ghidra 12.2 + experimental seccomp, harmless fixture only")
    parser.add_argument("--ghidra-home", required=True, type=Path)
    parser.add_argument("--ghidra-archive", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(run_ghidra_seccomp_smoke(
            args.ghidra_home, args.ghidra_archive), sort_keys=True))
        return 0
    except (GhidraSeccompSmokeError, HeadlessError, GhidraIntegrityError,
            SandboxUnavailable, SeccompUnavailable, OSError, ValueError) as exc:
        print(json.dumps({"status": "REJECTED_NOT_HOMOLOGATED",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
