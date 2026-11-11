#!/usr/bin/env python3
"""PE-S2.27: bounded local journald PID mount-namespace correlation, HOLD.

Observe whether the live systemd-journald service and the local observer see
the same mount namespace/root and dedicated bounded journal tmpfs. This does
NOT prove journal writes, independent provenance or VM attestation. No writes,
mounts, sudo, guest-agent, PE execution or signature operations.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True
import pe_journald_runtime as runtime
import pe_journald_mount_capacity as mount
from pe_arch_vm_s2_25_pid_kernel_snapshot import (
    _start_ticks, _read_bounded, PidSnapshotError,
)

PLAN = "PE_S2_27_JOURNALD_PROCESS_MOUNT_VIEW_NOT_STARTED"
OBSERVED = "LOCAL_PE_S2_27_JOURNALD_SAME_MOUNT_VIEW_HOLD"
REJECTED = "REJECTED_PE_S2_27_JOURNALD_EFFECTIVE_MOUNT_NOT_PROVEN"
CLASSIFICATION = "LOCAL_LIVE_PROCESS_MOUNT_VIEW_NOT_JOURNAL_WRITES_OR_VM_ATTESTATION"


class JournalProcessMountError(RuntimeError):
    """Journald live PID and observer mount views did not correlate."""


def _ns_identity(pid: int) -> tuple[int, int]:
    # /proc/PID/ns/mnt is a kernel namespace handle via a procfs symlink.
    try:
        value = os.stat(Path("/proc") / str(pid) / "ns" / "mnt")
    except OSError as exc:
        raise JournalProcessMountError("Cannot read journal PID mount namespace") from exc
    if not stat.S_ISREG(value.st_mode) or value.st_dev <= 0 or value.st_ino <= 0:
        raise JournalProcessMountError("Invalid kernel mount namespace handle")
    return value.st_dev, value.st_ino


def _root_identity(pid: int) -> tuple[int, int]:
    # Compare process root with observer's / to reject a different chroot.
    try:
        path = Path("/proc") / str(pid) / "root"
        value = os.stat(path)
    except OSError as exc:
        raise JournalProcessMountError("Cannot inspect process root view") from exc
    if not stat.S_ISDIR(value.st_mode):
        raise JournalProcessMountError("Unexpected process root type")
    return value.st_dev, value.st_ino


def _pid_mountinfo(pid: int) -> bytes:
    """The journald mount view must be read through EOF within the cap."""
    path = Path("/proc") / str(pid) / "mountinfo"
    try:
        return mount._read_mountinfo_bounded(path)
    except mount.JournalMountError as exc:
        raise JournalProcessMountError("Cannot read complete journald PID mountinfo") from exc


def _service_pid() -> int:
    try:
        info = runtime.observe_live_journald()
    except (runtime.JournaldRuntimeError, OSError, ValueError) as exc:
        raise JournalProcessMountError("Cannot verify live journald service/cgroup") from exc
    if (type(info) is not dict
            or info.get("status") != "LOCAL_JOURNALD_SERVICE_CGROUP_OBSERVED_ONLY"
            or info.get("journald_cgroup_v2_observed_locally") is not True
            or info.get("journald_running_observed_locally") is not True
            or info.get("effective_journald_configuration_verified") is not False
            or info.get("journal_storage_kernel_quota_verified") is not False
            or info.get("independent_vm_attested") is not False
            or info.get("release_authorized") is not False):
        raise JournalProcessMountError("Unexpected journald service observation")
    pid = info.get("journald_pid_observed")
    if type(pid) is not int or not 2 <= pid <= runtime.MAX_PID:
        raise JournalProcessMountError("Invalid journal service PID")
    return pid


def observe_live_process_mount() -> dict:
    if sys.platform != "linux" or os.geteuid() == 0:
        raise JournalProcessMountError("Non-root Linux observer required")
    pid = _service_pid()
    first_ticks = _start_ticks(_read_bounded(Path("/proc") / str(pid) / "stat"), pid)
    our_ns = _ns_identity(os.getpid())
    pid_ns = _ns_identity(pid)
    our_root = _root_identity(os.getpid())
    pid_root = _root_identity(pid)
    if our_ns != pid_ns or our_root != pid_root:
        raise JournalProcessMountError("Journald has distinct mount namespace/root")
    # The S2.26 observer validates directory modes and kernel capacity,
    # but /proc/self/mountinfo alone could describe a DIFFERENT namespace.
    first_store_identity = mount._secure_root_owned_path(mount.TARGET)
    observer_mount = mount._journal_mount(mount._kernel_mountinfo(), mount.TARGET)
    journal_mount = mount._journal_mount(_pid_mountinfo(pid), mount.TARGET)
    if observer_mount != journal_mount:
        raise JournalProcessMountError("Journald process mount differs from observer")
    capacity = mount._filesystem_size(mount.TARGET)
    if (pid != _service_pid()
            or first_ticks != _start_ticks(
                _read_bounded(Path("/proc") / str(pid) / "stat"), pid)
            or our_ns != _ns_identity(os.getpid())
            or pid_ns != _ns_identity(pid)
            or our_root != _root_identity(os.getpid())
            or pid_root != _root_identity(pid)
            or observer_mount != mount._journal_mount(
                mount._kernel_mountinfo(), mount.TARGET)
            or journal_mount != mount._journal_mount(
                _pid_mountinfo(pid), mount.TARGET)
            or capacity != mount._filesystem_size(mount.TARGET)):
        raise JournalProcessMountError("Process or mount changed during observation")
    if first_store_identity != mount._secure_root_owned_path(mount.TARGET):
        raise JournalProcessMountError("Journal store directory replaced during observation")
    return {
        "status": OBSERVED,
        "security_classification": CLASSIFICATION,
        "journald_pid_locally_observed": pid,
        "journald_pid_start_ticks": first_ticks,
        "journal_mount_id_locally_observed": observer_mount["mount_id"],
        "journal_tmpfs_capacity_bytes": capacity,
        "same_mount_namespace_locally_observed": True,
        "same_process_root_locally_observed": True,
        "same_exact_journal_mount_locally_observed": True,
        "journald_writes_to_this_mount_independently_proven": False,
        "journald_effective_config_independently_verified": False,
        "journald_kernel_storage_cap_independently_attested": False,
        "host_or_guest_provenance_verified": False,
        "independent_vm_attestation": False,
        "release_authorized": False,
        "apk_or_ota_publication_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PE-S2.27 read-only local journald namespace and mount; HOLD only")
    parser.add_argument("--inspect-live-journald-mount", action="store_true",
                        help="Explicit opt-in to local service, namespace and mount reads")
    args = parser.parse_args(argv)
    if not args.inspect_live_journald_mount:
        print(json.dumps({
            "status": PLAN, "service_or_kernel_queried": False,
            "independent_vm_attestation": False,
            "release_authorized": False,
        }, sort_keys=True))
        return 0
    try:
        result = observe_live_process_mount()
        print(json.dumps(result, sort_keys=True))
    except (JournalProcessMountError, mount.JournalMountError,
            runtime.JournaldRuntimeError, PidSnapshotError,
            OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "status": REJECTED, "reason": str(exc),
            "independent_vm_attestation": False,
            "release_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
    return 2  # Local observation and refusal are never release PASS.


if __name__ == "__main__":
    raise SystemExit(main())
