#!/usr/bin/env python3
"""PE-S2.25: opt-in, read-only snapshot of one guest PID and cgroup v2.

This is a LOCAL process observation, not proof of Ghidra's identity, a
reviewer's independence, native Arch, journald quota, or VM provenance.
Never modifies files, starts processes, signs evidence or authorizes release.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
from pe_nofollow_paths import open_absolute_directory_nofollow
from pe_resource_limits import (
    MEMORY_MAX_BYTES, TASKS_MAX, CPU_QUOTA_PERCENT,
    CPU_QUOTA_MIN_US, CPU_PERIOD_MIN_US, CPU_PERIOD_MAX_US, SCOPE_PATTERN,
)

PLAN = "PE_S2_25_LOCAL_PID_SNAPSHOT_NOT_STARTED"
OBSERVED = "LOCAL_PE_S2_25_SCOPED_PID_CGROUP_SECCOMP_HOLD"
REJECTED = "REJECTED_PE_S2_25_LOCAL_PID_OR_QUOTA_NOT_PROVEN"
MAX_BYTES = 16384
UNTRUSTED = "UNATTESTED_GUEST_LOCAL_KERNEL_VIEW"


class PidSnapshotError(RuntimeError):
    """Kernel process or quota observations could not be correlated safely."""


def _read_bounded(path: Path) -> str:
    """Read complete kernel file with descriptor-pinned, no-symlink ancestors.

    An O_NOFOLLOW flag on the last file alone cannot prevent an intermediate
    /proc, PID or cgroup directory symlink from redirecting local evidence.
    """
    try:
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        with ExitStack() as stack:
            parent_fd = open_absolute_directory_nofollow(path.parent, stack)
            fd = os.open(path.name, flags, dir_fd=parent_fd)
            stack.callback(os.close, fd)
            chunks = bytearray()
            # Require EOF within the byte budget; short reads may hide a
            # contradictory quota or PID/cgroup record after a valid prefix.
            while len(chunks) <= MAX_BYTES:
                part = os.read(fd, MAX_BYTES + 1 - len(chunks))
                if not part:
                    break
                chunks.extend(part)
            raw = bytes(chunks)
        if not raw or len(raw) > MAX_BYTES or b"\x00" in raw:
            raise PidSnapshotError("Empty, oversized or binary kernel evidence")
        return raw.decode("ascii")
    except (OSError, UnicodeError, ValueError) as exc:
        raise PidSnapshotError("Kernel observation unavailable") from exc


def _start_ticks(stat_text: str, pid: int) -> int:
    # /proc/PID/stat's second field is a parenthesized comm containing spaces.
    # Field 22 (starttime) is index 19 after splitting from field 3.
    prefix = str(pid) + " ("
    if not stat_text.startswith(prefix):
        raise PidSnapshotError("PID stat identity mismatch")
    end = stat_text.rfind(") ")
    if end <= len(prefix):
        raise PidSnapshotError("Malformed process stat")
    parts = stat_text[end + 2:].split()
    if len(parts) < 20:
        raise PidSnapshotError("Incomplete process stat")
    try:
        ticks = int(parts[19])
    except ValueError as exc:
        raise PidSnapshotError("Invalid process start ticks") from exc
    if ticks <= 0:
        raise PidSnapshotError("Missing process start ticks")
    return ticks


def _status_fields(data: str) -> tuple[int, int, int]:
    fields = {}
    for name in ("Uid", "Seccomp", "Seccomp_filters"):
        values = re.findall(r"^" + name + r":\s*([^\r\n]+)$",
                            data, flags=re.MULTILINE)
        if len(values) != 1:
            raise PidSnapshotError("Incomplete or duplicated process status")
        fields[name] = values[0]
    try:
        uid_columns = fields["Uid"].split()
        if len(uid_columns) != 4:
            raise ValueError("UID layout")
        uid = int(uid_columns[1])  # Effective UID, not the real UID.
        mode = int(fields["Seccomp"])
        filters = int(fields["Seccomp_filters"])
    except ValueError as exc:
        raise PidSnapshotError("Malformed numeric process status") from exc
    return uid, mode, filters


def _cgroup_path(text: str, expected_scope: str) -> str:
    lines = text.strip().splitlines()
    if len(lines) != 1 or not lines[0].startswith("0::/"):
        raise PidSnapshotError("Exactly one unified cgroup v2 entry required")
    path = lines[0][3:]
    parts = path.split("/")
    if (not path.startswith("/") or any(
            piece in (".", "..", "") for piece in parts[1:])
            or expected_scope not in parts[1:]):
        raise PidSnapshotError("PID outside expected scoped cgroup v2 path")
    return path


def _finite_number(raw: str, maximum: int) -> int:
    if re.fullmatch(r"[0-9]+\n?", raw) is None:
        raise PidSnapshotError("Missing finite kernel quota")
    number = int(raw)
    if not 0 < number <= maximum:
        raise PidSnapshotError("Unbounded or relaxed kernel quota")
    return number


def _cpu_limit(raw: str) -> tuple[int, int]:
    parts = raw.split()
    if len(parts) != 2 or not all(x.isascii() and x.isdecimal() for x in parts):
        raise PidSnapshotError("Unbounded or invalid CPU quota")
    quota, period = map(int, parts)
    if not (CPU_QUOTA_MIN_US <= quota
            and CPU_PERIOD_MIN_US <= period <= CPU_PERIOD_MAX_US
            and quota * 100 <= period * CPU_QUOTA_PERCENT):
        raise PidSnapshotError("Effective CPU quota is too relaxed")
    return quota, period


def _quota_snapshot(folder: Path) -> tuple[int, int, int, int]:
    """Parse an entire local cgroup v2 quota set with strict finite bounds."""
    memory = _finite_number(_read_bounded(folder / "memory.max"),
                            MEMORY_MAX_BYTES)
    tasks = _finite_number(_read_bounded(folder / "pids.max"), TASKS_MAX)
    quota, period = _cpu_limit(_read_bounded(folder / "cpu.max"))
    return memory, tasks, quota, period


def snapshot_pid(pid: int, expected_scope: str, *,
                 proc_root: Path = Path("/proc"),
                 cgroup_root: Path = Path("/sys/fs/cgroup"),
                 expected_uid: int | None = None) -> dict:
    """Read one process twice around actual kernel cgroup quota reads.

    proc_root/cgroup_root are test-only injections; the CLI never exposes them.
    A malicious guest can falsify a local view. An independent host reviewer
    must witness and correlate the live PID/session out of band.
    """
    if type(pid) is not int or not 1 < pid < 1 << 22:
        raise PidSnapshotError("A valid unprivileged target PID is required")
    if not isinstance(expected_scope, str) or not SCOPE_PATTERN.fullmatch(expected_scope):
        raise PidSnapshotError("Exact Negresco transient scope is required")
    if expected_uid is None:
        expected_uid = os.geteuid()
    if type(expected_uid) is not int or expected_uid <= 0:
        raise PidSnapshotError("Non-root effective UID required")
    base = proc_root / str(pid)
    stat_start = _start_ticks(_read_bounded(base / "stat"), pid)
    status_start = _status_fields(_read_bounded(base / "status"))
    group_start = _cgroup_path(_read_bounded(base / "cgroup"), expected_scope)
    uid, mode, filters = status_start
    if uid != expected_uid or mode != 2 or filters < 1:
        raise PidSnapshotError("Process UID or actual seccomp state invalid")
    folder = cgroup_root.joinpath(*group_start.strip("/").split("/"))
    first_quotas = _quota_snapshot(folder)
    stat_end = _start_ticks(_read_bounded(base / "stat"), pid)
    status_end = _status_fields(_read_bounded(base / "status"))
    group_end = _cgroup_path(_read_bounded(base / "cgroup"), expected_scope)
    if stat_start != stat_end or status_start != status_end or group_start != group_end:
        raise PidSnapshotError("Process PID reused, exited or changed while observed")
    # Read the actual kernel quota set again. A quota may be relaxed or
    # tightened while we inspect /proc, so an earlier good value cannot
    # justify a locally consistent result after the cgroup changes.
    second_quotas = _quota_snapshot(folder)
    if first_quotas != second_quotas:
        raise PidSnapshotError("Kernel cgroup quotas changed during observation")
    memory, tasks, quota, period = second_quotas
    return {
        "status": OBSERVED,
        "security_classification": UNTRUSTED,
        "pid": pid, "proc_start_ticks": stat_start,
        "expected_scope": expected_scope,
        "observed_cgroup_v2_path": group_start,
        "local_uid": uid, "seccomp_mode": mode,
        "seccomp_filters": filters,
        "memory_max_bytes": memory, "tasks_max": tasks,
        "cpu_quota_us": quota, "cpu_period_us": period,
        "same_pid_local_kernel_snapshot": True,
        "ghidra_process_identity_independently_verified": False,
        "native_arch_kernel_provenance_verified": False,
        "independent_vm_attestation": False,
        "release_authorized": False,
        "apk_or_ota_publication_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PE-S2.25 scoped PID cgroup/seccomp observation; always HOLD")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--expected-scope", required=True)
    parser.add_argument("--snapshot-local-pid", action="store_true",
                        help="Read the running process and cgroup locally")
    args = parser.parse_args(argv)
    if not args.snapshot_local_pid:
        print(json.dumps({
            "status": PLAN, "kernel_files_read": False,
            "independent_vm_attestation": False,
            "release_authorized": False,
        }, sort_keys=True))
        return 0
    try:
        if sys.platform != "linux" or os.geteuid() == 0:
            raise PidSnapshotError("Linux non-root guest required")
        report = snapshot_pid(args.pid, args.expected_scope)
        print(json.dumps(report, sort_keys=True))
    except (PidSnapshotError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "status": REJECTED, "reason": str(exc),
            "independent_vm_attestation": False,
            "release_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
    return 2  # Both local observation and rejection are NEVER a VM/release PASS.


if __name__ == "__main__":
    raise SystemExit(main())
