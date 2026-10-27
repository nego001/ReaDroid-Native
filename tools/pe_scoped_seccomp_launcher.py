#!/usr/bin/env python3
"""PE-S1.9: create and pass seccomp filter *inside* an already verified cgroup.

The optional systemd cgroup guard runs this script by Python -I after
verifying memory/pids/CPU quotas. This launcher rechecks those quotas,
compiles the sealed BPF fd in the scope process, passes it directly to
Bubblewrap, and closes it in the launcher. No fd needs to travel through
systemd-run/D-Bus. This is an experimental bridge, not a production toggle.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

from pe_cgroup_guard import verify_cgroup_limits, CgroupVerificationError
from pe_resource_limits import (MEMORY_MAX_BYTES, TASKS_MAX,
                                CPU_QUOTA_PERCENT, _validate_scope_name,
                                ResourceLimitsUnavailable)
from pe_seccomp_filter import (attach_seccomp_fd, compile_seccomp_bpf_fd,
                               SeccompUnavailable)


class ScopedSeccompUnavailable(RuntimeError):
    pass


def _validated_bwrap_command(argv: list[str]) -> list[str]:
    if (not isinstance(argv, list) or len(argv) < 3
            or argv.count("--") != 1 or argv[-1] == "--"
            or not all(isinstance(item, str) and item for item in argv)):
        raise ScopedSeccompUnavailable("Invalid Bubblewrap argv")
    path = Path(argv[0])
    resolved = shutil.which("bwrap")
    if (not path.is_absolute() or not resolved
            or path.is_symlink() or path.name != "bwrap"
            or not path.is_file() or not os.access(path, os.X_OK)
            or path.resolve(strict=True) != Path(resolved).resolve(strict=True)):
        raise ScopedSeccompUnavailable("Untrusted Bubblewrap launcher")
    if "--seccomp" in argv or "--add-seccomp-fd" in argv:
        raise ScopedSeccompUnavailable("Duplicate seccomp filter rejected")
    return list(argv)


def launch_scoped_bwrap(unit_name: str, command: list[str],
                        *, timeout_seconds: int = 600) -> int:
    if os.geteuid() == 0:
        raise ScopedSeccompUnavailable("Scoped seccomp cannot run as root")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 1800:
        raise ScopedSeccompUnavailable("Invalid scoped seccomp timeout")
    try:
        _validate_scope_name(unit_name)
        argv = _validated_bwrap_command(command)
        proof = verify_cgroup_limits(
            MEMORY_MAX_BYTES, TASKS_MAX, CPU_QUOTA_PERCENT,
            expected_scope=unit_name)
    except (ResourceLimitsUnavailable, CgroupVerificationError, OSError) as exc:
        raise ScopedSeccompUnavailable("Live cgroup membership/quotas not verified") from exc

    # Attesting scope quotas *again* after the guard, before creating the BPF.
    # A proof here only confirms the starting policy, not lifetime invariance.
    if proof.get("verified") is not True:
        raise ScopedSeccompUnavailable("Cgroup verifier did not attest quotas")

    filter_fd = None
    try:
        filter_fd = compile_seccomp_bpf_fd()
        secured = attach_seccomp_fd(argv, filter_fd)
        print(json.dumps({"scope_seccomp_guard": "passed",
                          "scope": unit_name, "filters_compiled_inside_scope": True},
                         sort_keys=True), flush=True)
        try:
            child = subprocess.Popen(
                secured, stdin=subprocess.DEVNULL,
                close_fds=True, pass_fds=(filter_fd,), start_new_session=True)
        except OSError as exc:
            raise ScopedSeccompUnavailable("Scoped bwrap launch refused") from exc
    except (SeccompUnavailable, OSError) as exc:
        raise ScopedSeccompUnavailable("Scoped filter creation refused") from exc
    finally:
        if filter_fd is not None:
            os.close(filter_fd)

    try:
        return child.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)
        raise ScopedSeccompUnavailable("Scoped Bubblewrap exceeded runtime cap") from exc


def main(argv: list[str]) -> int:
    try:
        if (len(argv) < 8 or argv[1] != "--scope"
                or argv[3] != "--timeout" or argv[5] != "--"):
            raise ScopedSeccompUnavailable("Invalid scope bridge arguments")
        return launch_scoped_bwrap(
            argv[2], argv[6:], timeout_seconds=int(argv[4]))
    except (ScopedSeccompUnavailable, OSError, ValueError) as exc:
        print(json.dumps({"status": "REJECTED_NOT_HOMOLOGATED",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
