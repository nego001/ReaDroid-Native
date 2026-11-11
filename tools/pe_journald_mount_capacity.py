#!/usr/bin/env python3
"""PE-S2.26: read-only local kernel mount capacity for volatile journald.

A dedicated root-owned tmpfs mounted at /run/log/journal may put an upper
bound on filesystem storage. This is NOT proof that journald loaded a given
configuration, that it writes there, or that an independent VM was used.
No mounts, subprocesses, log reads, writes, signatures or releases.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True
from pe_journald_policy import MAX_JOURNAL_USE

TARGET = Path("/run/log/journal")
MOUNTINFO = Path("/proc/self/mountinfo")
MAX_MOUNTINFO = 1024 * 1024
MAX_LINES = 4096
PLAN = "PE_S2_26_JOURNAL_MOUNT_CAP_PLAN_NOT_STARTED"
OBSERVED = "LOCAL_PE_S2_26_DEDICATED_TMPFS_CAP_OBSERVED_HOLD"
REJECTED = "REJECTED_PE_S2_26_JOURNAL_KERNEL_STORAGE_BOUND_NOT_PROVEN"
CLASSIFICATION = "LOCAL_READONLY_MOUNT_CAPACITY_NOT_JOURNALD_OR_VM_ATTESTATION"


class JournalMountError(RuntimeError):
    """A bounded dedicated volatile journal storage mount was not proved."""


def _kernel_mountinfo() -> bytes:
    try:
        fd = os.open(MOUNTINFO, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            raw = os.read(fd, MAX_MOUNTINFO + 1)
        finally:
            os.close(fd)
    except OSError as exc:
        raise JournalMountError("Cannot read kernel mountinfo") from exc
    if not raw or len(raw) > MAX_MOUNTINFO or b"\x00" in raw:
        raise JournalMountError("Kernel mountinfo is missing or oversized")
    return raw


def _unescape_mount_field(raw: str) -> str:
    # Linux mountinfo escapes spaces, tabs, newlines and backslashes as octal.
    if re.fullmatch(r"(?:[^\\]|\\[0-7]{3})*", raw) is None:
        raise JournalMountError("Non-canonical mountinfo pathname escapes")
    decoded = re.sub(r"\\([0-7]{3})",
                     lambda m: chr(int(m.group(1), 8)), raw)
    if any(ord(c) < 32 or ord(c) == 127 for c in decoded):
        raise JournalMountError("Control characters in mountinfo path")
    return decoded


def _journal_mount(raw: bytes, target: Path) -> dict:
    try:
        value = raw.decode("utf-8")
    except UnicodeError as exc:
        raise JournalMountError("Non-UTF8 kernel mountinfo") from exc
    lines = value.splitlines()
    if not lines or len(lines) > MAX_LINES:
        raise JournalMountError("Invalid mountinfo line count")
    destination = str(target)
    exact: list[dict] = []
    nested = False
    for line in lines:
        if not line or len(line) > 8192 or line.count(" - ") != 1:
            raise JournalMountError("Malformed kernel mountinfo record")
        left, right = line.split(" - ", 1)
        fields, fs = left.split(), right.split()
        if len(fields) < 6 or len(fs) < 3:
            raise JournalMountError("Incomplete mountinfo fields")
        location = _unescape_mount_field(fields[4])
        if location.startswith(destination + "/"):
            nested = True
        if location != destination:
            continue
        exact.append({
            "mount_id": fields[0],
            "root": _unescape_mount_field(fields[3]),
            "mountpoint": location,
            "mount_options": fields[5].split(","),
            "filesystem": fs[0],
            "source": fs[1],
        })
    if nested or len(exact) != 1:
        raise JournalMountError(
            "Journal store must be one dedicated mount with no nested mounts")
    item = exact[0]
    if (item["root"] != "/" or item["filesystem"] != "tmpfs"
            or "rw" not in item["mount_options"]
            or "ro" in item["mount_options"]
            or not item["mount_id"].isascii()
            or not item["mount_id"].isdecimal()):
        raise JournalMountError("Journal storage is not a dedicated writable tmpfs")
    return item


def _secure_root_owned_path(target: Path) -> tuple[int, int]:
    if target != TARGET:
        raise JournalMountError("Only the fixed volatile journal path is supported")
    last = None
    for path in (Path("/run"), Path("/run/log"), TARGET):
        try:
            last = path.lstat()
        except OSError as exc:
            raise JournalMountError("Journal mount path is unavailable") from exc
        if (not stat.S_ISDIR(last.st_mode)
                or last.st_uid != 0 or last.st_mode & 0o022):
            raise JournalMountError("Journal mount path has unsafe ownership or mode")
    assert last is not None
    return last.st_dev, last.st_ino


def _filesystem_size(target: Path) -> int:
    try:
        info = os.statvfs(target)
    except OSError as exc:
        raise JournalMountError("Kernel filesystem capacity unavailable") from exc
    for key in ("f_frsize", "f_blocks", "f_bfree", "f_bavail"):
        if type(getattr(info, key, None)) is not int:
            raise JournalMountError("Invalid filesystem capacity field")
    capacity = info.f_blocks * info.f_frsize
    if (not 0 < capacity <= MAX_JOURNAL_USE
            or not 0 <= info.f_bavail <= info.f_bfree <= info.f_blocks):
        raise JournalMountError("Filesystem exceeds journal capacity safety cap")
    return capacity


def observe_local_mount() -> dict:
    """Never equate a local mount view with the daemon's effective policy."""
    if sys.platform != "linux" or os.geteuid() == 0:
        raise JournalMountError("Unprivileged Linux observer required")
    first_identity = _secure_root_owned_path(TARGET)
    first_info = _kernel_mountinfo()
    first_mount = _journal_mount(first_info, TARGET)
    capacity = _filesystem_size(TARGET)
    last_mount = _journal_mount(_kernel_mountinfo(), TARGET)
    last_identity = _secure_root_owned_path(TARGET)
    if first_mount != last_mount or first_identity != last_identity:
        raise JournalMountError("Journal mount identity changed during observation")
    if capacity != _filesystem_size(TARGET):
        raise JournalMountError("Journal filesystem capacity changed during observation")
    return {
        "status": OBSERVED,
        "security_classification": CLASSIFICATION,
        "journal_store_path": str(TARGET),
        "mount_id_locally_observed": first_mount["mount_id"],
        "journal_store_root_owned_locally_observed": True,
        "journal_store_separate_tmpfs_locally_observed": True,
        "kernel_reported_filesystem_capacity_bytes": capacity,
        "kernel_filesystem_capacity_within_32m": True,
        "journald_uses_this_storage_independently_verified": False,
        "journald_effective_runtime_policy_verified": False,
        "journald_storage_quota_independently_verified": False,
        "native_arch_vm_attested": False,
        "independent_vm_attestation": False,
        "release_authorized": False,
        "apk_or_ota_publication_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PE-S2.26 local volatile journal tmpfs capacity; always HOLD")
    parser.add_argument("--inspect-local-journal-mount", action="store_true",
                        help="Opt in to bounded read-only /proc mount and statvfs checks")
    args = parser.parse_args(argv)
    if not args.inspect_local_journal_mount:
        print(json.dumps({
            "status": PLAN, "kernel_mount_files_read": False,
            "independent_vm_attestation": False, "release_authorized": False,
        }, sort_keys=True))
        return 0
    try:
        result = observe_local_mount()
        print(json.dumps(result, sort_keys=True))
    except (JournalMountError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "status": REJECTED, "reason": str(exc),
            "independent_vm_attestation": False, "release_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
    return 2  # Neither a valid local mount nor a rejection attests the VM.


if __name__ == "__main__":
    raise SystemExit(main())
