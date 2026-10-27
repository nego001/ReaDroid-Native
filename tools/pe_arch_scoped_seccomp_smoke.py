#!/usr/bin/env python3
"""Native Arch VM acceptance probe for cgroup + seccomp + Bubblewrap together.

Never runs arbitrary Windows code. Refuses hosts outside a disposable Arch VM
when called from CLI, and always requires kernel-proven quota and sandbox
evidence, rather than silently dropping either protective boundary.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from pe_arch_vm_gate import verify_arch_vm, ArchVmUnavailable
from pe_ghidra_sandbox import build_command, SandboxUnavailable
from pe_resource_limits import (new_scope_unit, wrap_in_cgroup_scope,
                                ResourceLimitsUnavailable)
from pe_scope_cleanup_evidence import (stop_and_attest_scope,
                                       ScopeCleanupUnavailable)
from pe_resource_evidence import read_scope_proof, InvalidResourceEvidence
from pe_seccomp_filter import seccomp_filter_count, SeccompUnavailable


class ScopedSeccompSmokeError(RuntimeError):
    pass


TOOLS = Path(__file__).resolve().parent
PROBE = TOOLS.parent / "tests/pe_sandbox_probe.py"
SCRIPT = TOOLS / "ghidra_scripts/NegrescoFunctionInventory.java"
BRIDGE = TOOLS / "pe_scoped_seccomp_launcher.py"


def run_scoped_seccomp_probe(ghidra_home: Path, pe: Path,
                            workspace_root: Path) -> dict:
    """Enforce native Arch VM gate before any systemd/cgroup process launch."""
    if any(not file.is_file() or file.is_symlink()
           for file in (PROBE, SCRIPT, BRIDGE, pe)):
        raise ScopedSeccompSmokeError("Missing trusted synthetic probe fixture")
    if not workspace_root.is_absolute() or workspace_root.is_symlink():
        raise ScopedSeccompSmokeError("Private absolute test root required")
    # Direct library callers must pass the same disposable Arch VM gate as
    # the CLI. Never rely on an undocumented parent-process precondition.
    environment = verify_arch_vm()
    if (environment.get("status") != "ARCH_VM_PREFLIGHT_PASSED"
            or environment.get("vm_confirmed") is not True
            or environment.get("container") is not False):
        raise ScopedSeccompSmokeError("Native Arch VM gate not attested")
    unit = new_scope_unit()
    baseline = seccomp_filter_count()
    with tempfile.TemporaryDirectory(prefix="negresco-scope-seccomp-",
                                     dir=workspace_root) as ephemeral:
        root = Path(ephemeral)
        canary = root / "host-private-canary"
        canary.write_text("synthetic host descriptor", encoding="ascii")
        canary.chmod(0o600)
        work = root / "sandbox-work"
        (work / "scripts").mkdir(parents=True, mode=0o700)
        (work / "project").mkdir(mode=0o700)
        shutil.copyfile(SCRIPT, work / "scripts" / SCRIPT.name)
        shutil.copyfile(PROBE, work / "pe_sandbox_probe.py")
        shutil.copyfile(pe, work / "input.exe")
        proof_root = root / "evidence"
        proof_root.mkdir(mode=0o700)
        proof_path = proof_root / "quota-proof.json"
        bwrap = build_command(ghidra_home, work, 65)
        boundary = bwrap.index("--")
        host_fd = os.open(canary, os.O_RDONLY)
        try:
            os.set_inheritable(host_fd, True)
            canary_id = os.fstat(host_fd)
            bwrap = bwrap[:boundary + 1] + [
                "/usr/bin/python3", "/work/pe_sandbox_probe.py",
                os.readlink("/proc/self/ns/net"), str(canary),
                str(canary_id.st_dev), str(canary_id.st_ino),
                str(baseline)]
            bridge_argv = [
                sys.executable, "-I", str(BRIDGE), "--scope", unit,
                "--timeout", "45", "--", *bwrap]
            argv = wrap_in_cgroup_scope(
                bridge_argv, timeout_seconds=70,
                unit_name=unit, proof_path=proof_path)
            try:
                proc = subprocess.run(
                    argv, stdin=subprocess.DEVNULL, capture_output=True,
                    text=True, check=False, timeout=85, close_fds=True)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ScopedSeccompSmokeError(
                    "Native scoped seccomp probe timed out or could not start") from exc
        finally:
            os.close(host_fd)
            # A transient unit can already be garbage-collected on exit.
            # Accept only systemd-confirmed inactive/dead and unpopulated state.
            scope_cleanup = stop_and_attest_scope(unit)
        if scope_cleanup.get("verified") is not True or scope_cleanup.get("cgroup_unpopulated") is not True:
            raise ScopedSeccompSmokeError("Scope cleanup attestation incomplete")
        if proc.returncode != 0:
            raise ScopedSeccompSmokeError(
                "Scoped seccomp/bwrap child rejected probe (exit nonzero)")
        try:
            records = [json.loads(line) for line in proc.stdout.splitlines()
                       if line.lstrip().startswith("{")]
        except json.JSONDecodeError as exc:
            raise ScopedSeccompSmokeError("Malformed native scoped probe JSON") from exc
        scope_ok = any(
            isinstance(record, dict)
            and record.get("scope_seccomp_guard") == "passed"
            and record.get("scope") == unit
            and record.get("filters_compiled_inside_scope") is True
            for record in records)
        bwrap_fields = (
            "host_home_canary_hidden", "network_namespace_separate",
            "host_etc_hidden", "usr_runtime_read_only",
            "private_work_writable", "inherited_host_fd_hidden",
            "seccomp_enforced")
        sandbox_ok = any(
            isinstance(record, dict)
            and record.get("isolation_probe") == "passed"
            and all(record.get(field) is True for field in bwrap_fields)
            for record in records)
        guard_ok = any(
            isinstance(record, dict)
            and record.get("cgroup_verification") == "passed"
            and record.get("verified") is True
            for record in records)
        if not (scope_ok and sandbox_ok and guard_ok):
            raise ScopedSeccompSmokeError(
                "Cgroup, scope launcher and seccomp isolation were not jointly verified")
        try:
            quota_proof = read_scope_proof(proof_path, unit)
        except InvalidResourceEvidence as exc:
            raise ScopedSeccompSmokeError("Private cgroup proof missing") from exc
        return {
            "status": "PASS_NATIVE_ARCH_VM_SCOPED_SECCOMP",
            "scope": unit,
            "filter_compiled_after_guard": True,
            "cgroup_verification": quota_proof,
            "scope_cleanup_evidence": scope_cleanup,
            "sandbox_checks": list(bwrap_fields),
            "windows_pe_executed": False,
            "ghidra_executed": False,
        }


def main(argv: list[str]) -> int:
    try:
        if len(argv) != 4:
            raise ScopedSeccompSmokeError(
                "Usage: python3 tools/pe_arch_scoped_seccomp_smoke.py GHIDRA_HOME SYNTHETIC_PE PRIVATE_ROOT")
        environment = verify_arch_vm()
        proof = run_scoped_seccomp_probe(
            Path(argv[1]), Path(argv[2]), Path(argv[3]))
        print(json.dumps({"environment": environment, **proof}, sort_keys=True))
        return 0
    except (ScopedSeccompSmokeError, ArchVmUnavailable, SandboxUnavailable,
            SeccompUnavailable, ResourceLimitsUnavailable,
            InvalidResourceEvidence, RuntimeError, OSError, ValueError) as exc:
        print(json.dumps({"status": "REJECTED_NOT_HOMOLOGATED",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
