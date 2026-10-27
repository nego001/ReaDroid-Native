#!/usr/bin/env python3
"""Native Arch Linux smoke: prove *effective* user cgroup quotas on a harmless process.

Run manually as an unprivileged login user under real Arch Linux. Never runs
Windows binaries or changes sysctls, AppArmor, sudo settings, or the host FS.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from pe_resource_limits import (ResourceLimitsUnavailable, new_scope_unit,
                                stop_scope, wrap_in_cgroup_scope)


def preflight() -> None:
    if sys.platform != "linux" or os.geteuid() == 0:
        raise RuntimeError("Requires Linux running as a regular user")
    release = Path("/etc/os-release").read_text(encoding="utf-8")
    if not any(line.strip() == "ID=arch" for line in release.splitlines()):
        raise RuntimeError("Requires native Arch Linux, not an Ubuntu runner")
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        raise RuntimeError("Container is not an Arch host validation")
    if Path("/proc/1/comm").read_text(encoding="utf-8").strip() != "systemd":
        raise RuntimeError("A native host with systemd as PID 1 is required")
    if not Path("/sys/fs/cgroup/cgroup.controllers").is_file():
        raise RuntimeError("cgroup v2 is not visible")


def run_smoke() -> dict:
    preflight()
    unit = new_scope_unit()
    probe = [sys.executable, "-I", "-c",
             "import json; print(json.dumps({'synthetic_child': 'passed'}), flush=True)"]
    argv = wrap_in_cgroup_scope(probe, timeout_seconds=20, unit_name=unit)
    try:
        process = subprocess.run(argv, capture_output=True, text=True,
                                 timeout=28, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Native systemd scope probe timed out") from exc
    finally:
        # If the harmless child has ended, the transient scope may already be
        # garbage collected. A failed stop call is not a cleanup attestation.
        stop_scope(unit)
    if process.returncode != 0:
        raise RuntimeError("Native scope refused verification: " +
                           process.stderr[-1200:])
    lines = process.stdout.splitlines()
    try:
        records = [json.loads(line) for line in lines if line.startswith("{")]
    except json.JSONDecodeError as exc:
        raise RuntimeError("Malformed native scope proof") from exc
    proof = next((item for item in records if
                  item.get("cgroup_verification") == "passed"), None)
    child = next((item for item in records if
                  item.get("synthetic_child") == "passed"), None)
    if not proof or not proof.get("verified") or not child:
        raise RuntimeError("No verified cgroup proof and test child confirmation")
    return {"status": "PASS_NATIVE_ARCH_CGROUP",
            "scope": unit, "memory_max": proof["memory_max"],
            "pids_max": proof["pids_max"],
            "cpu_quota": proof["cpu_quota"],
            "cpu_period": proof["cpu_period"],
            "ghidra_executed": False, "windows_binary_executed": False}


def main() -> int:
    try:
        print(json.dumps(run_smoke(), sort_keys=True))
        return 0
    except (RuntimeError, OSError, ResourceLimitsUnavailable) as exc:
        print(json.dumps({"status": "REJECTED_NOT_HOMOLOGATED",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
