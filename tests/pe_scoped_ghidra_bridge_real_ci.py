#!/usr/bin/env python3
"""PE-S1.10.1: run REAL Ghidra via REAL scoped-seccomp bridge in Ubuntu CI.

Only the live systemd-cgroup membership check is mocked in this disposable
Ubuntu CI experiment. The bridge compiles and seals the actual libseccomp
cBPF, transfers its FD to actual Bubblewrap, and runs actual Ghidra 12.2
headless with both function inventory and decompilation against a synthetic PE.
This MUST NOT claim native cgroup verification or Arch VM approval.
"""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import pe_scoped_seccomp_launcher as bridge
from pe_auto_ghidra import (_validated_deep_evidence,
                            _validated_function_evidence, inspect_pe)
from pe_ghidra_integrity import verify_pinned_ghidra_tree
from pe_ghidra_sandbox import build_command

INVENTORY = ROOT / "tools/ghidra_scripts/NegrescoFunctionInventory.java"
DEEP = ROOT / "tools/ghidra_scripts/NegrescoDeepPreview.java"
SCOPE_UNIT = "negresco-pe-0123456789abcdef01234567.scope"


class RealBridgeGhidraError(RuntimeError):
    pass


def run_real_bridge_ghidra(ghidra_home: Path, ghidra_archive: Path,
                           synthetic_pe: Path) -> dict:
    if os.geteuid() == 0:
        raise RealBridgeGhidraError("Real sandbox experiment requires non-root")
    if not synthetic_pe.is_file() or synthetic_pe.is_symlink():
        raise RealBridgeGhidraError("Trusted synthetic input is missing")
    if any(not path.is_file() or path.is_symlink()
           for path in (INVENTORY, DEEP)):
        raise RealBridgeGhidraError("Trusted Ghidra exporter scripts missing")
    inspection = inspect_pe(synthetic_pe)
    if inspection.get("architecture") != "x86_64":
        raise RealBridgeGhidraError("Expected synthetic PE64 x86_64")
    release_proof = verify_pinned_ghidra_tree(ghidra_home, ghidra_archive)
    if release_proof.get("verified") is not True:
        raise RealBridgeGhidraError("Pinned official Ghidra release not verified")

    with tempfile.TemporaryDirectory(prefix="negresco-real-bridge-ghidra-") as tmp:
        work = Path(tmp)
        (work / "scripts").mkdir(mode=0o700)
        (work / "project").mkdir(mode=0o700)
        shutil.copyfile(INVENTORY, work / "scripts" / INVENTORY.name)
        shutil.copyfile(DEEP, work / "scripts" / DEEP.name)
        target = work / "input.exe"
        shutil.copyfile(synthetic_pe, target)
        if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(
                synthetic_pe.read_bytes()).digest():
            raise RealBridgeGhidraError("Fixture snapshot differs from original")

        command = build_command(
            ghidra_home, work, 420, deep_preview=True)
        receipts = io.StringIO()
        # Explicitly mock ONLY cgroup verification. libseccomp, FD transfer,
        # Bubblewrap and Ghidra execution all remain real subprocesses.
        with mock.patch.object(
                bridge, "verify_cgroup_limits",
                return_value={"verified": True}) as quota_mock:
            with redirect_stdout(receipts):
                exit_code = bridge.launch_scoped_bwrap(
                    SCOPE_UNIT, command, timeout_seconds=420)
        quota_mock.assert_called_once_with(
            bridge.MEMORY_MAX_BYTES, bridge.TASKS_MAX,
            bridge.CPU_QUOTA_PERCENT, expected_scope=SCOPE_UNIT)
        try:
            records = [json.loads(line) for line in receipts.getvalue().splitlines()
                       if line.lstrip().startswith("{")]
        except json.JSONDecodeError as exc:
            raise RealBridgeGhidraError("Malformed real bridge receipt") from exc
        if (exit_code != 0
                or not any(
                    isinstance(item, dict)
                    and item.get("scope_seccomp_guard") == "passed"
                    and item.get("scope") == SCOPE_UNIT
                    and item.get("filters_compiled_inside_scope") is True
                    for item in records)):
            raise RealBridgeGhidraError(
                "Real Ghidra rejected by scoped seccomp bridge")
        # These read ACTUAL files written by Ghidra inside Bubblewrap.
        inventory = _validated_function_evidence(work / "ghidra-functions.json")
        preview = _validated_deep_evidence(work / "ghidra-deep.json")
        successes = sum(
            item.get("decompile_status") == "ok"
            for item in preview["functions"])
        if inventory["total_discovered"] < 1 or successes < 1:
            raise RealBridgeGhidraError(
                "Real seccomp bridge did not produce valid Ghidra decompilation")
        return {
            "status": "PASS_REAL_GHIDRA_BRIDGE_MOCKED_CGROUP_ONLY",
            "real_libseccomp_bpf": True,
            "real_bubblewrap": True,
            "real_ghidra_12_2": True,
            "ghidra_pinned_release_verified": True,
            "filter_created_by_actual_scoped_launcher": True,
            "inventory_total_discovered": inventory["total_discovered"],
            "decompiled_functions": successes,
            "cgroup_verification": "MOCK_ONLY_NOT_HOMOLOGATED",
            "native_arch_vm_executed": False,
            "windows_binary_executed": False,
        }


def main(argv: list[str]) -> int:
    try:
        if len(argv) != 4:
            raise RealBridgeGhidraError(
                "Usage: ci.py GHIDRA_HOME GHIDRA_RELEASE_ZIP SYNTHETIC_PE")
        report = run_real_bridge_ghidra(*map(Path, argv[1:]))
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"status": "REJECTED_NOT_HOMOLOGATED",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
