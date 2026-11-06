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
import pe_arch_vm_s1_69_bounded_native_child as bounded
from pe_arch_vm_evidence import _verified_scope_cleanup
import pe_native_workspace_budget as storage
from pe_ghidra_sandbox import build_command, SandboxUnavailable
from pe_resource_limits import (new_scope_unit, wrap_in_cgroup_scope,
                                ResourceLimitsUnavailable)
from pe_scope_cleanup_evidence import (stop_and_attest_scope,
                                       ScopeCleanupUnavailable)
from pe_resource_evidence import (read_scope_proof, corroborate_guard_receipt,
                                  InvalidResourceEvidence)
from pe_seccomp_filter import seccomp_filter_count, SeccompUnavailable


class ScopedSeccompSmokeError(RuntimeError):
    pass


TOOLS = Path(__file__).resolve().parent
PROBE = TOOLS.parent / "tests/pe_sandbox_probe.py"
SCRIPT = TOOLS / "ghidra_scripts/NegrescoFunctionInventory.java"
BRIDGE = TOOLS / "pe_scoped_seccomp_launcher.py"
MAX_SCOPE_STDOUT_BYTES = 64 * 1024
MAX_SCOPE_STDERR_BYTES = 8192


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
        # Capped, exclusive staging BEFORE launching a user-systemd scope.
        # This bounds combined fixture copies, not Ghidra's runtime writes.
        try:
            storage.stage_bounded_fixtures([
                (SCRIPT, work / "scripts" / SCRIPT.name,
                 storage.MAX_STAGE_SCRIPT_BYTES),
                (PROBE, work / "pe_sandbox_probe.py",
                 storage.MAX_STAGE_SCRIPT_BYTES),
                (pe, work / "input.exe",
                 storage.MAX_STAGE_SYNTHETIC_PE_BYTES),
            ])
        except storage.NativeStorageBudgetError as exc:
            raise ScopedSeccompSmokeError(
                "Native seccomp fixtures exceeded bounded staging budget") from exc
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
                # Avoid capture_output=True: it reads the full output into
                # RAM before the host can reject a hostile/noisy descendant.
                proc = bounded.run_bounded_native(
                    argv, env=dict(os.environ), timeout=85,
                    max_stdout=MAX_SCOPE_STDOUT_BYTES,
                    max_stderr=MAX_SCOPE_STDERR_BYTES)
            except bounded.BoundedNativeChildError as exc:
                raise ScopedSeccompSmokeError(
                    "Native scoped seccomp output or execution budget exceeded"
                ) from exc
        finally:
            os.close(host_fd)
            # A transient unit can already be garbage-collected on exit.
            # Accept only systemd-confirmed inactive/dead and unpopulated state.
            try:
                scope_cleanup = stop_and_attest_scope(unit)
            except ScopeCleanupUnavailable as exc:
                raise ScopedSeccompSmokeError(
                    "Cannot prove scoped probe fully stopped") from exc
        # Do not emit an intermediate PASS based on a few affirmative
        # flags when final acceptance demands a complete systemd contract.
        if not _verified_scope_cleanup(unit, scope_cleanup):
            raise ScopedSeccompSmokeError(
                "Scope cleanup attestation failed full contract")
        try:
            storage.audit_postrun_workspace(root)
        except storage.NativeStorageBudgetError as exc:
            raise ScopedSeccompSmokeError(
                "Native seccomp workspace post-run footprint not accepted") from exc
        if proc.returncode != 0:
            raise ScopedSeccompSmokeError(
                "Scoped seccomp/bwrap child rejected probe (exit nonzero)")
        try:
            output = proc.stdout.decode("utf-8")
            records = [json.loads(line) for line in output.splitlines()
                       if line.lstrip().startswith("{")]
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ScopedSeccompSmokeError(
                "Malformed native scoped probe output") from exc
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
            corroborate_guard_receipt(records, quota_proof)
        except InvalidResourceEvidence as exc:
            raise ScopedSeccompSmokeError(
                "Private cgroup quota proof missing or inconsistent") from exc
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
