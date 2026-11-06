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
from pe_resource_limits import _trusted_discovered_systemd_binary


class ArchVmUnavailable(RuntimeError):
    pass


def _trusted_vm_tool(name: str) -> str:
    """Never execute a PATH-injected user binary as a VM safety witness.

    Require an absolute normalized, root-owned, non-writable executable and
    root-owned, non-writable, non-symlinked ancestors before any native probe.
    Metadata checks are necessary local preconditions, NOT independent proof
    of a hypervisor, VM origin, or a trusted operator.
    """
    executable = shutil.which(name)
    if not _trusted_discovered_systemd_binary(executable):
        raise ArchVmUnavailable(name + " is not a trusted system binary")
    return executable


def _system_command(name: str, *args: str) -> None:
    executable = _trusted_vm_tool(name)
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
    virt_tool = _trusted_vm_tool("systemd-detect-virt")
    try:
        container = subprocess.run(
            [virt_tool, "--container", "--quiet"],
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
        _trusted_vm_tool(binary)
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
