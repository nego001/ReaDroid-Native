#!/usr/bin/env python3
"""PE-S2.10: real kernel tmpfs ENOSPC test on CI-only isolated /work/limited.

ONLY an unprivileged Ubuntu Bubblewrap fixture, NEVER the reviewer VM's /work,
the host disk, system journal, Windows PE execution or Ghidra execution.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from pe_ghidra_sandbox import build_command

MODULE = Path(__file__).resolve().parents[1] / "tools/pe_native_workspace_budget.py"
BOUNDED_BYTES = 64 * 1024 * 1024
UNDERSIZED_BYTES = 32 * 1024 * 1024
MAX_OUTPUT_BYTES = 4096

CHILD = r'''
import errno
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, "/work")
from pe_native_workspace_budget import (require_bounded_work_mount,
                                       NativeStorageBudgetError)
from pe_native_work_enospc import require_native_work_enospc

mode = sys.argv[1]
root = Path("/work/limited")
workspace = root / "workspace"
workspace.mkdir(mode=0o700)
if (Path("/work/host_secret_marker").exists()
        or os.stat(workspace).st_dev == os.stat("/work").st_dev):
    raise RuntimeError("Host workspace exposed or tmpfs not separate")

if mode != "bounded":
    try:
        require_bounded_work_mount(workspace)
    except NativeStorageBudgetError:
        print(json.dumps({
            "status": "REJECTED_UNSAFE_REAL_WORK_MOUNT",
            "case": mode,
            "kernel_mountinfo_real": True,
            "writes_attempted": False,
            "native_arch_vm_attested": False,
        }, sort_keys=True))
        raise SystemExit(0)
    raise RuntimeError("Unsafe real work mount was incorrectly accepted")

proof = require_bounded_work_mount(workspace)
if (proof["mounted_size_bytes"] != 64 * 1024 * 1024
        or proof["work_mount_type"] != "tmpfs"
        or proof["kernel_storage_limit_observed_locally"] is not True
        or proof["journald_budget_verified"] is not False
        or proof["independent_vm_attested"] is not False):
    raise RuntimeError("Real work filesystem verifier returned unsafe receipt")
limit = os.statvfs(workspace)
capacity = limit.f_frsize * limit.f_blocks
before_free = limit.f_bavail * limit.f_frsize
if capacity != 64 * 1024 * 1024 or before_free < 32 * 1024 * 1024:
    raise RuntimeError("Wrong real tmpfs capacity/free budget")
location = workspace / "enospc-s2-10"
accepted = 0
enospc = False
try:
    with open(location, "xb", buffering=0) as stream:
        for _ in range(80):
            try:
                accepted += stream.write(b"Z" * (1024 * 1024))
            except OSError as exc:
                if exc.errno != errno.ENOSPC:
                    raise
                enospc = True
                break
finally:
    try:
        location.unlink()
    except FileNotFoundError:
        pass
if not enospc or not 0 < accepted <= capacity:
    raise RuntimeError("Real kernel did not enforce ENOSPC")
free_after = os.statvfs(workspace)
if free_after.f_bavail * free_after.f_frsize < 32 * 1024 * 1024:
    raise RuntimeError("Work tmpfs did not recover free space after cleanup")
fallocate_proof = require_native_work_enospc(workspace)
if (fallocate_proof["status"] != "LOCAL_NATIVE_WORK_TMPFS_FALLOCATE_ENOSPC"
        or fallocate_proof["enospc_observed_on_oversize_reservation"] is not True
        or fallocate_proof["recovered_after_cleanup"] is not True
        or fallocate_proof["native_arch_vm_independently_attested"] is not False):
    raise RuntimeError("Native fallocate verifier did not pass on real tmpfs")
print(json.dumps({
    "native_fallocate_enospc": True,
    "native_fallocate_cleanup": True,
    "status": "PASS_REAL_BWRAP_DEDICATED_WORK_TMPFS_ENOSPC",
    "mount_size_bytes": capacity,
    "bytes_written_before_enospc": accepted,
    "enospc_verified": True,
    "real_mountinfo_verifier": True,
    "work_is_separate_from_host": True,
    "cleanup_frees_space": True,
    "host_work_filesystem_quota_verified": False,
    "journald_quota_verified": False,
    "native_arch_vm_attested": False,
}, sort_keys=True))
'''


def build_isolated_work_command(production: list[str], host_work: Path,
                                mode: str) -> list[str]:
    """Replace ONLY the CI subprocess argv: never change production profile."""
    if mode not in ("bounded", "undersized", "nested"):
        raise RuntimeError("Unsupported S2.10 CI probe case")
    if not isinstance(production, list) or production.count("--") != 1:
        raise RuntimeError("Invalid production Bubblewrap command")
    boundary = production.index("--")
    profile = production[:boundary].copy()
    original = ["--dir", "/work", "--bind", str(host_work), "/work"]
    candidates = [i for i in range(len(profile) - len(original) + 1)
                  if profile[i:i + len(original)] == original]
    if len(candidates) != 1:
        raise RuntimeError("Production /work host bind profile changed: abort CI probe")
    pos = candidates[0]
    capacity = UNDERSIZED_BYTES if mode == "undersized" else BOUNDED_BYTES
    # Bubblewrap 0.13.1: --size and --perms apply to the next --tmpfs.
    # The former host bind is REMOVED, not made writable in CI.
    replacement = [
        "--dir", "/work",
        "--size", str(capacity), "--perms", "0700",
        "--tmpfs", "/work/limited",
    ]
    profile[pos:pos + len(original)] = replacement
    if mode == "nested":
        profile.extend([
            "--size", str(1024 * 1024), "--perms", "0700",
            "--tmpfs", "/work/limited/escape",
        ])
    if not MODULE.is_file() or MODULE.is_symlink():
        raise RuntimeError("Pinned storage verifier unavailable")
    native_helper = MODULE.with_name("pe_native_work_enospc.py")
    if not native_helper.is_file() or native_helper.is_symlink():
        raise RuntimeError("Pinned native ENOSPC helper unavailable")
    profile.extend(["--ro-bind", str(MODULE),
                    "/work/pe_native_workspace_budget.py",
                    "--ro-bind", str(native_helper),
                    "/work/pe_native_work_enospc.py"])
    if (any(profile[i:i+3] == ["--bind", str(host_work), "/work"]
            for i in range(len(profile)-2))
            or profile.count("--tmpfs") < 3):
        raise RuntimeError("Unsafe CI mount transformation")
    return profile + ["--", "/usr/bin/python3", "-I", "-B",
                      "-c", CHILD, mode]


def run_case(ghidra: Path, host_work: Path, mode: str) -> dict:
    production = build_command(ghidra, host_work, 90)
    command = build_isolated_work_command(production, host_work, mode)
    result = subprocess.run(
        command, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=40, check=False, close_fds=True,
    )
    if (result.returncode != 0 or not 0 < len(result.stdout) <= MAX_OUTPUT_BYTES
            or len(result.stderr) > MAX_OUTPUT_BYTES):
        raise RuntimeError("Real bounded work mount probe failed closed")
    try:
        record = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError("Real work mount probe report malformed") from exc
    if not isinstance(record, dict):
        raise RuntimeError("Real work mount probe report not an object")
    return record


def main() -> int:
    if len(sys.argv) != 2 or os.geteuid() == 0:
        raise RuntimeError("Unprivileged CI and trusted Ghidra home required")
    ghidra = Path(sys.argv[1]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="negresco-work-tmpfs-ci-") as temp:
        work = Path(temp) / "host-work"
        scripts = work / "scripts"
        scripts.mkdir(parents=True, mode=0o700)
        (scripts / "NegrescoFunctionInventory.java").write_text(
            "// harmless CI profile placeholder", encoding="ascii")
        secret = work / "host_secret_marker"
        secret.write_text("host only", encoding="ascii")
        expected = secret.read_bytes()
        positive = run_case(ghidra, work, "bounded")
        if (set(positive) != {
                "status", "native_fallocate_enospc", "native_fallocate_cleanup",
                "mount_size_bytes", "bytes_written_before_enospc",
                "enospc_verified", "real_mountinfo_verifier",
                "work_is_separate_from_host", "cleanup_frees_space",
                "host_work_filesystem_quota_verified", "journald_quota_verified",
                "native_arch_vm_attested"}
                or positive["status"] !=
                    "PASS_REAL_BWRAP_DEDICATED_WORK_TMPFS_ENOSPC"
                or positive["native_fallocate_enospc"] is not True
                or positive["native_fallocate_cleanup"] is not True
                or type(positive["mount_size_bytes"]) is not int
                or positive["mount_size_bytes"] != BOUNDED_BYTES
                or type(positive["bytes_written_before_enospc"]) is not int
                or not 0 < positive["bytes_written_before_enospc"] <= BOUNDED_BYTES
                or any(positive[k] is not True for k in (
                    "enospc_verified", "real_mountinfo_verifier",
                    "work_is_separate_from_host", "cleanup_frees_space"))
                or any(positive[k] is not False for k in (
                    "host_work_filesystem_quota_verified",
                    "journald_quota_verified", "native_arch_vm_attested"))):
            raise RuntimeError("Real bounded work mount proof contradicted policy")
        rejected = []
        for mode in ("undersized", "nested"):
            outcome = run_case(ghidra, work, mode)
            if outcome != {
                    "status": "REJECTED_UNSAFE_REAL_WORK_MOUNT",
                    "case": mode,
                    "kernel_mountinfo_real": True,
                    "writes_attempted": False,
                    "native_arch_vm_attested": False}:
                raise RuntimeError("Unsafe real work mount accepted: " + mode)
            rejected.append(mode)
        if secret.read_bytes() != expected:
            raise RuntimeError("Host workspace marker was modified")
        print(json.dumps({
            "status": "PASS_PE_S2_10_CI_WORK_TMPFS_QUOTA",
            "real_bubblewrap_work_tmpfs": positive,
            "unsafe_real_work_mounts_rejected": rejected,
            "production_work_host_bind_used_in_probe": False,
            "independent_arch_vm_attested": False,
            "journal_size_kernel_enforced": False,
            "windows_binary_executed": False,
            "release_authorized": False,
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "REJECTED_NOT_HOMOLOGATED",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
