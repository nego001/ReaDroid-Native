#!/usr/bin/env python3
"""PE-S2.07: real kernel tmpfs ENOSPC probe in Bubblewrap, synthetic-only.

This integration check DOES NOT mount a host filesystem or execute PE/Ghidra.
It uses the production profile, substitutes a tiny Python self-test as the
sandbox command and reduces just the two size values to 1 MiB so ENOSPC can
be tested quickly without consuming hundreds of MiB. It cannot certify a
runtime quota on host-bound /work or journald.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from pe_ghidra_sandbox import (
    build_command, TMPFS_HOME_MAX_BYTES, TMPFS_TMP_MAX_BYTES,
)

PROBE_SIZE_BYTES = 1024 * 1024
PROBE_MAX_FS_BYTES = 2 * PROBE_SIZE_BYTES

CHILD = r'''
import errno
import json
import os

out = {}
for mount in ("/tmp", "/home"):
    stats = os.statvfs(mount)
    total = stats.f_frsize * stats.f_blocks
    if not 0 < total <= 2 * 1024 * 1024:
        raise RuntimeError("Unbounded temp mount: " + mount)
    if os.stat(mount).st_dev == os.stat("/work").st_dev:
        raise RuntimeError("Temporary mount not distinct from /work: " + mount)
    attempted = False
    location = mount + "/negresco-s2-07-enospc"
    try:
        with open(location, "wb", buffering=0) as stream:
            for _ in range(64):
                stream.write(b"Z" * 65536)
    except OSError as exc:
        if exc.errno != errno.ENOSPC:
            raise
        attempted = True
    finally:
        try:
            os.unlink(location)
        except FileNotFoundError:
            pass
    if not attempted:
        raise RuntimeError("Temp write exceeded quota without ENOSPC: " + mount)
    out[mount] = {"size_bytes": total, "enospc_verified": True}
if os.stat("/tmp").st_dev == os.stat("/home").st_dev:
    raise RuntimeError("Temporary mounts share a device unexpectedly")
print(json.dumps(out, sort_keys=True))
'''


def main() -> int:
    if len(sys.argv) != 2 or os.geteuid() == 0:
        raise RuntimeError("Requires an unprivileged CI runner and Ghidra home")
    ghidra = Path(sys.argv[1]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="negresco-tmpfs-quota-ci-") as temp:
        work = Path(temp) / "work"
        scripts = work / "scripts"
        scripts.mkdir(parents=True, mode=0o700)
        (scripts / "NegrescoFunctionInventory.java").write_text(
            "// synthetic CI marker; never executed", encoding="ascii")
        argv = build_command(ghidra, work, 90)
        boundary = argv.index("--")
        profile = argv[:boundary]
        declared = {"/tmp": TMPFS_TMP_MAX_BYTES,
                    "/home": TMPFS_HOME_MAX_BYTES}
        for mount, production_limit in declared.items():
            i = profile.index(mount)
            if profile[i-3:i] != ["--size", str(production_limit), "--tmpfs"]:
                raise RuntimeError("Production profile lacks a pinned size for " + mount)
            # This change affects ONLY the CI test's in-memory argv; the
            # tested code retains its actual production limits.
            profile[i-2] = str(PROBE_SIZE_BYTES)
        command = profile + [
            "--", "/usr/bin/python3", "-I", "-c", CHILD]
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=25, check=False, close_fds=True)
        if (result.returncode != 0 or len(result.stdout) > 4096
                or len(result.stderr) > 4096):
            raise RuntimeError(
                "Real Bubblewrap tmpfs ENOSPC probe rejected the quota")
        report = json.loads(result.stdout.decode("utf-8"))
        if (set(report) != set(declared)
                or any(set(report[m]) != {"size_bytes", "enospc_verified"}
                       or not 0 < report[m]["size_bytes"] <= PROBE_MAX_FS_BYTES
                       or report[m]["enospc_verified"] is not True
                       for m in declared)):
            raise RuntimeError("Inconsistent kernel tmpfs capacity result")
        print(json.dumps({
            "status": "PASS_REAL_BWRAP_TMPFS_SIZE_AND_ENOSPC",
            "test_mount_size_bytes": PROBE_SIZE_BYTES,
            "production_mount_sizes_bytes": declared,
            "kernel_enospc_by_mount": report,
            "host_work_filesystem_quota_verified": False,
            "journald_quota_verified": False,
            "native_arch_vm_homologated": False,
        }, sort_keys=True))
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "REJECTED_NOT_HOMOLOGATED",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
