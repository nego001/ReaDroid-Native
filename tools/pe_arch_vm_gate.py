#!/usr/bin/env python3
"""Fail-closed gate for native Arch Linux VM security validation.

This is deliberately stricter than the ordinary native Arch diagnostic:
CI-like destructive lifecycle tests must run inside a full VM, never on a
personal workstation, container or root shell. No sysctl/security changes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from pe_arch_cgroup_smoke import preflight


class ArchVmUnavailable(RuntimeError):
    pass


def _system_command(name: str, *args: str) -> None:
    executable = shutil.which(name)
    if not executable:
        raise ArchVmUnavailable(name + " not installed")
    try:
        result = subprocess.run(
            [executable, *args], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=8)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ArchVmUnavailable(name + " could not be checked") from exc
    if result.returncode != 0:
        raise ArchVmUnavailable(name + " rejected the required VM/user session")


def verify_arch_vm() -> dict:
    try:
        preflight()
    except (RuntimeError, OSError) as exc:
        raise ArchVmUnavailable(str(exc)) from exc
    if os.geteuid() == 0:
        raise ArchVmUnavailable("root cannot run validation")
    # Check container separately: --vm may also see an underlying hypervisor.
    if not shutil.which("systemd-detect-virt"):
        raise ArchVmUnavailable("systemd-detect-virt unavailable")
    try:
        container = subprocess.run(
            ["systemd-detect-virt", "--container", "--quiet"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ArchVmUnavailable("container check failed") from exc
    if container.returncode == 0:
        raise ArchVmUnavailable("container cannot substitute for a VM")
    if container.returncode != 1:
        raise ArchVmUnavailable("container check was inconclusive")
    _system_command("systemd-detect-virt", "--vm", "--quiet")
    # A service runner without a user systemd bus fails closed.
    _system_command("systemctl", "--user", "--no-ask-password", "show-environment")
    runtime_dir = Path("/run/user") / str(os.getuid())
    if (os.environ.get("XDG_RUNTIME_DIR") != str(runtime_dir)
            or not runtime_dir.is_dir() or runtime_dir.is_symlink()
            or runtime_dir.stat().st_uid != os.geteuid()):
        raise ArchVmUnavailable("private systemd user runtime is unavailable")
    for binary in ("bwrap", "systemd-run", "systemctl", "python3",
                   "x86_64-w64-mingw32-gcc"):
        if not shutil.which(binary):
            raise ArchVmUnavailable(binary + " is missing")
    return {"status": "ARCH_VM_PREFLIGHT_PASSED",
            "vm_confirmed": True, "container": False,
            "root": False, "systemd_user_bus": True,
            "real_cgroup_test_executed": False}


def main() -> int:
    try:
        print(json.dumps(verify_arch_vm(), sort_keys=True))
        return 0
    except (ArchVmUnavailable, OSError) as exc:
        print(json.dumps({"status": "REJECTED_NOT_HOMOLOGATED",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
