"""PE-S1.13: attest that a transient systemd user scope is quiescent.

systemd can garbage-collect a transient scope immediately after its last
process exits. 'systemctl stop' can then report not found despite successful
cleanup. Accept only a strictly parsed inactive/dead unit (or collected
not-found unit), and reject populated cgroup directories. The caller MUST
also require the independent, privately stored proof that this scope existed
and had effective quotas before it could claim an acceptance PASS.
"""
from __future__ import annotations

from contextlib import ExitStack
import errno
import os
from pathlib import Path
import shutil
import stat
import subprocess

from pe_resource_limits import _validate_scope_name, stop_scope

MAX_SHOW_BYTES = 4096
MAX_CGROUP_EVENTS_BYTES = 4096


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
    """Read kernel cgroup.events from pinned, no-follow directory FDs.

    A removed transient scope is acceptable only after systemd independently
    attested inactivity. All other uncertainty fails closed. cgroup.events is
    a virtual kernel file with st_size often equal to zero, so bound its READ
    length instead of relying on stat().st_size.
    """
    if not isinstance(relative, str):
        return False
    if relative == "":
        return True
    if not relative.startswith("/"):
        return False
    components = relative[1:].split("/")
    if (components[-1] != unit_name
            or any(part in ("", ".", "..") for part in components)):
        return False
    if not hasattr(os, "O_NOFOLLOW"):
        return False
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    dir_flags = flags | os.O_DIRECTORY
    with ExitStack() as stack:
        root_fd = os.open(mount_root, dir_flags)
        stack.callback(os.close, root_fd)
        parent_fd = root_fd
        for component in components:
            try:
                directory_fd = os.open(component, dir_flags, dir_fd=parent_fd)
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    # A GC'd transient scope may have vanished already.
                    return True
                raise
            stack.callback(os.close, directory_fd)
            parent_fd = directory_fd
        event_fd = os.open("cgroup.events", flags, dir_fd=parent_fd)
        stack.callback(os.close, event_fd)
        if not stat.S_ISREG(os.fstat(event_fd).st_mode):
            return False
        raw = os.read(event_fd, MAX_CGROUP_EVENTS_BYTES + 1)
        if not 1 <= len(raw) <= MAX_CGROUP_EVENTS_BYTES:
            return False
        events = raw.decode("ascii")
        # Reject truncated and malformed kernel status rather than inferring
        # populated=0 from a partial or ambiguous record.
        if not events.endswith("\n"):
            return False
        seen = set()
        for line in events.splitlines():
            parts = line.split()
            if (len(parts) != 2 or parts[0] in seen
                    or not parts[1].isdecimal()):
                return False
            seen.add(parts[0])
            if parts[0] == "populated" and parts[1] != "0":
                return False
        return "populated" in seen


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
        "scope": unit_name,
        "verified": True,
        "scope_quiescent": True,
        "stop_request_accepted": accepted,
        "load_state": state["LoadState"],
        "active_state": state["ActiveState"],
        "sub_state": state["SubState"],
        "scope_collected": state["LoadState"] == "not-found",
        "cgroup_unpopulated": True,
    }
