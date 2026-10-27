#!/usr/bin/env python3
"""Real Bubblewrap/seccomp bridge smoke, with ONLY cgroup verification mocked.

Intended for a disposable Ubuntu CI worker without a native systemd user
scope. It really builds a sealed BPF policy and invokes the exact in-scope
launcher code, testing its FD handoff, syscall denial and namespaces.
It is NOT evidence of actual cgroup enforcement. No Windows code is run.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import pe_scoped_seccomp_launcher as bridge
from pe_ghidra_sandbox import build_command
from pe_seccomp_filter import seccomp_filter_count

PROBE = ROOT / "tests/pe_sandbox_probe.py"
EXPORT = ROOT / "tools/ghidra_scripts/NegrescoFunctionInventory.java"
UNIT = "negresco-pe-0123456789abcdef01234567.scope"


def real_bridge_smoke(ghidra_home: Path, synthetic_pe: Path) -> dict:
    if os.geteuid() == 0:
        raise RuntimeError("Smoke requires non-root sandbox test user")
    if not PROBE.is_file() or not EXPORT.is_file() or not synthetic_pe.is_file():
        raise RuntimeError("Required trusted fixtures are missing")
    with tempfile.TemporaryDirectory(prefix="negresco-bridge-real-ci-") as temp:
        root = Path(temp)
        canary = root / "host-private-canary"
        canary.write_text("synthetic host only", encoding="ascii")
        canary.chmod(0o600)
        work = root / "workspace"
        (work / "scripts").mkdir(parents=True, mode=0o700)
        (work / "project").mkdir(mode=0o700)
        shutil.copyfile(EXPORT, work / "scripts" / EXPORT.name)
        shutil.copyfile(PROBE, work / "pe_sandbox_probe.py")
        shutil.copyfile(synthetic_pe, work / "input.exe")
        command = build_command(ghidra_home, work, 90)
        start = command.index("--")
        fd = os.open(canary, os.O_RDONLY)
        try:
            os.set_inheritable(fd, True)
            stat_result = os.fstat(fd)
            command = command[:start + 1] + [
                "/usr/bin/python3", "/work/pe_sandbox_probe.py",
                os.readlink("/proc/self/ns/net"), str(canary),
                str(stat_result.st_dev), str(stat_result.st_ino),
                str(seccomp_filter_count()),
            ]
            # This mock is deliberate and local to CI. Actual Ghidra + scope
            # acceptance must execute verify_cgroup_limits in the Arch VM.
            with mock.patch.object(
                    bridge, "verify_cgroup_limits",
                    return_value={"verified": True}) as mocked_scope:
                exit_code = bridge.launch_scoped_bwrap(
                    UNIT, command, timeout_seconds=50)
            mocked_scope.assert_called_once()
        finally:
            os.close(fd)
        if exit_code != 0:
            raise RuntimeError("Real Bubblewrap/seccomp bridge exited nonzero")
        return {"status": "PASS_REAL_BRIDGE_WITH_MOCKED_CGROUP",
                "seccomp_and_bubblewrap_real": True,
                "cgroup_enforcement_real": False,
                "windows_binary_executed": False}


def main(argv: list[str]) -> int:
    try:
        if len(argv) != 3:
            raise RuntimeError("Usage: smoke.py GHIDRA_HOME SYNTHETIC_PE")
        result = real_bridge_smoke(Path(argv[1]), Path(argv[2]))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "REJECTED_NOT_HOMOLOGATED",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
