"""PE-S1.13: attest that a transient systemd user scope is quiescent.

systemd can garbage-collect a transient scope immediately after its last
process exits. 'systemctl stop' can then report not found despite successful
cleanup. Accept only a strictly parsed inactive/dead unit (or collected
not-found unit), and reject populated cgroup directories. The caller MUST
also require the independent, privately stored proof that this scope existed
and had effective quotas before it could claim an acceptance PASS.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from pe_resource_limits import _validate_scope_name, stop_scope

MAX_SHOW_BYTES = 4096


class ScopeCleanupUnavailable(RuntimeError):
    pass


def _validated_systemctl(systemctl_path: str | None) -> str:
    command = (systemctl_path if systemctl_path is not None
               else shutil.which("systemctl"))
    if not command:
        raise ScopeCleanupUnavailable("systemctl not available")
    path = Path(command)
    if (not path.is_absolute() or path.is_symlink()
            or not path.is_file() or not os.access(path, os.X_OK)):
        raise ScopeCleanupUnavailable("Untrusted systemctl executable")
    # When discovered from PATH, never treat a user-writable script as a
    # systemd authority. Explicit paths are only an injectable test seam;
    # native acceptance always calls this without a path override.
    if systemctl_path is None:
        metadata = path.stat()
        if metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise ScopeCleanupUnavailable(
                "Discovered systemctl is not a trusted system binary")
    return str(path)


def _parse_show(output: str) -> dict[str, str]:
    if not isinstance(output, str) or not 10 <= len(output) <= MAX_SHOW_BYTES:
        raise ScopeCleanupUnavailable("Missing/bounded systemd status receipt")
    expected = {"LoadState", "ActiveState", "SubState", "ControlGroup"}
    values = {}
    for line in output.splitlines():
        name, equals, value = line.partition("=")
        if not equals or name not in expected or name in values:
            raise ScopeCleanupUnavailable("Malformed/duplicate systemd state")
        values[name] = value
    if set(values) != expected:
        raise ScopeCleanupUnavailable("Incomplete systemd state")
    if (values["LoadState"] not in ("loaded", "not-found")
            or values["ActiveState"] != "inactive"
            or values["SubState"] != "dead"):
        raise ScopeCleanupUnavailable("Scope still active or failed")
    if values["LoadState"] == "not-found" and values["ControlGroup"]:
        raise ScopeCleanupUnavailable("Collected scope has unexpected cgroup")
    return values


def _cgroup_unpopulated(relative: str, unit_name: str,
                        mount_root: Path) -> bool:
    if not relative:
        return True
    parts = relative.split("/")
    if (not relative.startswith("/") or len(parts) < 2
            or parts[-1] != unit_name
            or any(part in (".", "..", "") for part in parts[1:])):
        return False
    root = mount_root.resolve(strict=True)
    scope = (root / relative.lstrip("/")).resolve(strict=False)
    if scope == root or root not in scope.parents:
        return False
    if not scope.exists():
        # cgroup directory has been removed by the kernel.
        return True
    if not scope.is_dir():
        return False
    # cgroup.events is maintained by the kernel for cgroup v2.
    events = (scope / "cgroup.events").read_text(encoding="ascii")
    pairs = [line.split() for line in events.splitlines()]
    found = [v for pair in pairs if len(pair) == 2
             for k, v in [pair] if k == "populated"]
    return len(found) == 1 and found[0] == "0"


def stop_and_attest_scope(unit_name: str, *, systemctl_path: str | None = None,
                          mount_root: Path = Path("/sys/fs/cgroup")) -> dict:
    """Best-effort stop + independent query, without shell or sleeping.

    A failed stop request is not automatically a failed cleanup if systemd
    already collected the transient unit. The final state must still be
    kernel/systemd-verifiable. Any uncertainty refuses native approval.
    """
    try:
        _validate_scope_name(unit_name)
        executable = _validated_systemctl(systemctl_path)
    except (OSError, RuntimeError) as exc:
        raise ScopeCleanupUnavailable("Cannot verify scope cleanup") from exc

    accepted = stop_scope(unit_name, systemctl_path=executable)
    try:
        result = subprocess.run([
            executable, "--user", "--no-ask-password", "--no-pager", "--all",
            "show", unit_name,
            "--property=LoadState,ActiveState,SubState,ControlGroup",
        ], stdin=subprocess.DEVNULL, capture_output=True, text=True,
            check=False, timeout=10)
        if result.returncode != 0:
            raise ScopeCleanupUnavailable("systemd could not confirm scope state")
        state = _parse_show(result.stdout)
        if not _cgroup_unpopulated(state["ControlGroup"], unit_name, mount_root):
            raise ScopeCleanupUnavailable("Scope cgroup still contains processes")
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired) as exc:
        raise ScopeCleanupUnavailable("Scope final state unavailable") from exc
    return {
        "verified": True,
        "scope_quiescent": True,
        "stop_request_accepted": accepted,
        "load_state": state["LoadState"],
        "active_state": state["ActiveState"],
        "sub_state": state["SubState"],
        "scope_collected": state["LoadState"] == "not-found",
        "cgroup_unpopulated": True,
    }
