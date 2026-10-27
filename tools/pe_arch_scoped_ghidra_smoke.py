#!/usr/bin/env python3
"""PE-S1.10: real Ghidra + seccomp + cgroup in the SAME native Arch VM scope.

This is only called after the Arch VM-only preflight and independent
namespace/cgroup/descendant checks. The Windows PE is an inert, project-owned
fixture: Ghidra parses it, but no Windows executable is launched.
No production --require-seccomp+--require-cgroup-limits switch is enabled.
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
from pe_auto_ghidra import (_validated_function_evidence,
                            _validated_deep_evidence, HeadlessError)
from pe_ghidra_sandbox import build_command, SandboxUnavailable
from pe_resource_limits import (new_scope_unit, wrap_in_cgroup_scope,
                                ResourceLimitsUnavailable)
from pe_scope_cleanup_evidence import (stop_and_attest_scope,
                                       ScopeCleanupUnavailable)
from pe_resource_evidence import read_scope_proof, InvalidResourceEvidence
from pe_seccomp_runtime_evidence import (baseline_from_scope_receipts,
                                         read_ghidra_seccomp_proof,
                                         SeccompRuntimeEvidenceError)

SCRIPT_HOME = Path(__file__).resolve().parent / "ghidra_scripts"
BRIDGE = Path(__file__).resolve().parent / "pe_scoped_seccomp_launcher.py"


class ScopedGhidraError(RuntimeError):
    pass


def run_native_scoped_ghidra(ghidra_home: Path, synthetic_pe: Path,
                             private_root: Path, *,
                             timeout_seconds: int = 420) -> dict:
    """Run the actual Ghidra 12.2 in the same user scope as its seccomp filter."""
    if sys.platform != "linux" or os.geteuid() == 0:
        raise ScopedGhidraError("Scoped Ghidra requires an unprivileged Linux user")
    if (type(timeout_seconds) is not int
            or not 90 <= timeout_seconds <= 1500):
        raise ScopedGhidraError("Unsupported Ghidra scoped runtime")
    if (not private_root.is_absolute() or private_root.is_symlink()
            or not private_root.is_dir()
            or not synthetic_pe.is_file() or synthetic_pe.is_symlink()
            or not ghidra_home.is_absolute() or ghidra_home.is_symlink()
            or any(path.is_symlink() or not path.is_file()
                   for path in (BRIDGE,
                                SCRIPT_HOME / "NegrescoFunctionInventory.java",
                                SCRIPT_HOME / "NegrescoDeepPreview.java",
                                SCRIPT_HOME / "NegrescoSeccompRuntimeProof.java"))):
        raise ScopedGhidraError("Missing private workspace or trusted synthetic fixture")

    # Enforce the VM boundary HERE too, not only in the parent CLI.
    # A caller importing this function directly must not be able to start
    # this lifecycle experiment on a workstation or container.
    environment = verify_arch_vm()
    if (environment.get("status") != "ARCH_VM_PREFLIGHT_PASSED"
            or environment.get("vm_confirmed") is not True
            or environment.get("container") is not False):
        raise ScopedGhidraError("Native Arch VM safety gate was not attested")

    unit = new_scope_unit()
    with tempfile.TemporaryDirectory(prefix="negresco-native-arch-ghidra-both-",
                                     dir=private_root) as temp:
        root = Path(temp)
        workspace = root / "workspace"
        scripts = workspace / "scripts"
        scripts.mkdir(parents=True, mode=0o700)
        (workspace / "project").mkdir(mode=0o700)
        for name in ("NegrescoFunctionInventory.java", "NegrescoDeepPreview.java",
                     "NegrescoSeccompRuntimeProof.java"):
            shutil.copyfile(SCRIPT_HOME / name, scripts / name)
        shutil.copyfile(synthetic_pe, workspace / "input.exe")
        proof_folder = root / "private-cgroup-proof"
        proof_folder.mkdir(mode=0o700)
        proof_path = proof_folder / "quota.json"

        # Critical ordering: systemd enters real cgroup -> guard attests ->
        # bridge independently rechecks quotas and constructs sealed BPF ->
        # Bubblewrap receives the only explicitly passed FD -> real Ghidra.
        command = build_command(
            ghidra_home, workspace, timeout_seconds, deep_preview=True)
        if command.count("-analysisTimeoutPerFile") != 1:
            raise ScopedGhidraError("Missing trusted seccomp postScript insertion point")
        before = command.index("-analysisTimeoutPerFile")
        command[before:before] = [
            "-postScript", "NegrescoSeccompRuntimeProof.java",
            "/work/ghidra-seccomp-runtime.json"]
        bridge = [sys.executable, "-I", str(BRIDGE), "--scope", unit,
                  "--timeout", str(timeout_seconds), "--", *command]
        wrapped = wrap_in_cgroup_scope(
            bridge, timeout_seconds=timeout_seconds,
            unit_name=unit, proof_path=proof_path)
        try:
            try:
                result = subprocess.run(
                    wrapped, stdin=subprocess.DEVNULL, capture_output=True,
                    text=True, timeout=timeout_seconds + 30,
                    check=False, close_fds=True)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ScopedGhidraError(
                    "Native scoped Ghidra failed to start or timed out") from exc
        finally:
            scope_cleanup = stop_and_attest_scope(unit)
        if scope_cleanup.get("verified") is not True or scope_cleanup.get("cgroup_unpopulated") is not True:
            raise ScopedGhidraError("Ghidra scope cleanup attestation incomplete")
        if result.returncode != 0:
            raise ScopedGhidraError("Real Ghidra with cgroup/seccomp exited nonzero")
        if len(result.stdout) > 128 * 1024:
            raise ScopedGhidraError("Ghidra scope attestation stdout exceeded bound")
        try:
            lines = [json.loads(line) for line in result.stdout.splitlines()
                     if line.lstrip().startswith("{")]
        except json.JSONDecodeError as exc:
            raise ScopedGhidraError("Malformed native scoped Ghidra receipt") from exc
        scope_confirmed = any(
            isinstance(item, dict) and item.get("scope_seccomp_guard") == "passed"
            and item.get("scope") == unit
            and item.get("filters_compiled_inside_scope") is True
            for item in lines)
        cgroup_confirmed = any(
            isinstance(item, dict) and item.get("cgroup_verification") == "passed"
            and item.get("verified") is True for item in lines)
        if not scope_confirmed or not cgroup_confirmed:
            raise ScopedGhidraError(
                "Ghidra cgroup membership and seccomp bridge receipts missing")
        try:
            baseline = baseline_from_scope_receipts(lines, unit)
            runtime = read_ghidra_seccomp_proof(
                workspace / "ghidra-seccomp-runtime.json", baseline)
            limits = read_scope_proof(proof_path, unit)
            inventory = _validated_function_evidence(
                workspace / "ghidra-functions.json")
            preview = _validated_deep_evidence(workspace / "ghidra-deep.json")
        except (InvalidResourceEvidence, SeccompRuntimeEvidenceError,
                HeadlessError, OSError) as exc:
            raise ScopedGhidraError(
                "Private cgroup proof or real Ghidra evidence missing") from exc
        if (limits.get("verification") != "guard_verified_before_bwrap"
                or inventory["total_discovered"] < 1
                or not any(item.get("decompile_status") == "ok"
                           for item in preview["functions"])):
            raise ScopedGhidraError(
                "Ghidra did not decompile with proven effective cgroup quotas")
        return {
            "status": "PASS_NATIVE_ARCH_REAL_GHIDRA_WITH_CGROUP_AND_SECCOMP",
            "scope": unit,
            "scope_stop_accepted": scope_cleanup["stop_request_accepted"],
            "scope_cleanup_verified": True,
            "scope_cleanup_evidence": scope_cleanup,
            "filter_compiled_inside_scope": True,
            "quotas_verified_before_bwrap": limits,
            "ghidra_jvm_seccomp_evidence": runtime,
            "ghidra_functions_discovered": inventory["total_discovered"],
            "decompiled_functions": sum(
                item.get("decompile_status") == "ok"
                for item in preview["functions"]),
            "bubblewrap": True,
            "windows_binary_executed": False,
        }
