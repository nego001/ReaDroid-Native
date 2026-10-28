#!/usr/bin/env python3
"""Native Arch cgroup smoke: kernel quota and lifecycle evidence, no PE execution.

A harmless Python child enters one transient systemd scope. Never accept a
stdout PASS without the independent private 0600 cgroup proof, and never
approve while the corresponding unit still contains processes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from pe_resource_limits import (ResourceLimitsUnavailable, new_scope_unit,
                                wrap_in_cgroup_scope)
from pe_resource_evidence import (read_scope_proof, corroborate_guard_receipt,
                                  InvalidResourceEvidence)
from pe_scope_cleanup_evidence import (stop_and_attest_scope,
                                       ScopeCleanupUnavailable)

MAX_STDOUT_BYTES = 32768


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


def _unique_json_pairs(pairs: list[tuple[str, object]]) -> dict:
    record = {}
    for key, value in pairs:
        if key in record:
            raise RuntimeError("Duplicate native cgroup JSON key")
        record[key] = value
    return record


def _parse_probe_records(stdout: str) -> list[dict]:
    if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > MAX_STDOUT_BYTES:
        raise RuntimeError("Native cgroup stdout exceeded bound")
    records = []
    for line in stdout.splitlines():
        if line.lstrip().startswith("{"):
            try:
                record = json.loads(
                    line, object_pairs_hook=_unique_json_pairs,
                    parse_constant=lambda _: (_ for _ in ()).throw(
                        RuntimeError("Non-finite native cgroup receipt")))
            except (ValueError, UnicodeError) as exc:
                raise RuntimeError("Malformed native scope proof") from exc
            if not isinstance(record, dict):
                raise RuntimeError("Invalid native scope record type")
            records.append(record)
    if len(records) > 8:
        raise RuntimeError("Too many native scope records")
    return records


def run_smoke() -> dict:
    preflight()
    unit = new_scope_unit()
    probe = [sys.executable, "-I", "-c",
             "import json; print(json.dumps({'synthetic_child': 'passed'}), flush=True)"]
    with tempfile.TemporaryDirectory(prefix="negresco-arch-cgroup-proof-") as tmp:
        folder = Path(tmp) / "private"
        folder.mkdir(mode=0o700)
        proof_path = folder / "quota.json"
        argv = wrap_in_cgroup_scope(
            probe, timeout_seconds=20, unit_name=unit, proof_path=proof_path)
        try:
            process = subprocess.run(
                argv, stdin=subprocess.DEVNULL, capture_output=True,
                text=True, timeout=28, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("Native systemd scope probe failed or timed out") from exc
        finally:
            try:
                cleanup = stop_and_attest_scope(unit)
            except (ScopeCleanupUnavailable, OSError) as exc:
                raise RuntimeError(
                    "Native cgroup scope final cleanup was not proven") from exc

        if (cleanup.get("scope") != unit or cleanup.get("verified") is not True
                or cleanup.get("scope_quiescent") is not True
                or cleanup.get("cgroup_unpopulated") is not True
                or cleanup.get("active_state") != "inactive"
                or cleanup.get("sub_state") != "dead"):
            raise RuntimeError("Native cgroup scope still active or populated")
        if process.returncode != 0:
            raise RuntimeError("Native scope refused verification: " +
                               process.stderr[-1200:])
        records = _parse_probe_records(process.stdout)
        try:
            private = read_scope_proof(proof_path, unit)
            corroborate_guard_receipt(records, private)
        except InvalidResourceEvidence as exc:
            raise RuntimeError("Private native cgroup quota proof missing or invalid") from exc
        child = [x for x in records if x.get("synthetic_child") == "passed"]
        if len(child) != 1:
            raise RuntimeError("No unique verified synthetic child confirmation")
        return {
            "status": "PASS_NATIVE_ARCH_CGROUP",
            "scope": unit,
            "memory_max": private["memory_max_bytes"],
            "pids_max": private["tasks_max"],
            "cpu_quota": private["cpu_quota"],
            "cpu_period": private["cpu_period"],
            "quota_private_proof": private,
            "scope_cleanup_evidence": cleanup,
            "ghidra_executed": False, "windows_binary_executed": False,
        }


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
