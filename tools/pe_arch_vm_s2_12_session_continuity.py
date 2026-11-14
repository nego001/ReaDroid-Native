#!/usr/bin/env python3
"""PE-S2.12: read-only before/after continuity of ONE local native acceptance.

This gate prevents an ordinary in-run change of the dedicated /work volume
identity, declared journald limits, or active journald PID/cgroup from being
silently accepted. Not a trusted host/hypervisor measurement, signature,
kernel-level journal quota or independent VM attestation.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import sys

import pe_journald_policy as policy
import pe_journald_runtime as runtime
import pe_native_workspace_budget as storage

WORK_FIELDS = frozenset((
    "work_mount_type", "mounted_size_bytes", "mount_source_kind",
    "kernel_storage_limit_observed_locally", "journald_budget_verified",
    "independent_vm_attested",
))
POLICY_FIELDS = frozenset((
    "status", "storage", "runtime_max_use_bytes", "runtime_max_file_bytes",
    "runtime_keep_free_bytes", "rate_limit_interval_seconds",
    "rate_limit_burst", "journal_daemon_effective_runtime_verified",
    "journal_kernel_quota_verified", "independent_vm_attested",
    "release_authorized",
))
RUNTIME_FIELDS = frozenset((
    "status", "journald_pid_observed",
    "journald_cgroup_v2_observed_locally", "journald_running_observed_locally",
    "effective_journald_configuration_verified",
    "journal_storage_kernel_quota_verified",
    "independent_vm_attested", "release_authorized",
))
SNAPSHOT_FIELDS = frozenset((
    "classification", "work_inode_device", "work_inode_number",
    "work_filesystem_capacity_bytes", "work_mount_policy",
    "journald_declared_policy", "journald_runtime_state",
    "independent_vm_attested", "release_authorized",
))


class NativeContinuityError(RuntimeError):
    """Observed safety prerequisites changed, or could not be measured."""


def capture_local_snapshot(root: Path) -> dict:
    """Capture local readonly measurements before/after scoped work."""
    if (sys.platform != "linux" or os.geteuid() == 0
            or not isinstance(root, Path) or not root.is_absolute()):
        raise NativeContinuityError("Local continuity requires non-root Linux absolute /work")
    try:
        first_work = storage.require_bounded_work_mount(root)
        declared = policy.require_journald_declared_policy()
        service = runtime.observe_live_journald()
        path_meta = root.lstat()
        fs = os.statvfs(root)
        last_work = storage.require_bounded_work_mount(root)
    except (storage.NativeStorageBudgetError, policy.JournaldPolicyError,
            runtime.JournaldRuntimeError, OSError, ValueError, TypeError) as exc:
        raise NativeContinuityError(
            "Native continuity local observations unavailable") from exc
    if (type(first_work) is not dict or set(first_work) != WORK_FIELDS
            or first_work != last_work
            or first_work["work_mount_type"] != "tmpfs"
            or first_work["mount_source_kind"] != "dedicated_reviewer_prepared"
            or first_work["kernel_storage_limit_observed_locally"] is not True
            or first_work["journald_budget_verified"] is not False
            or first_work["independent_vm_attested"] is not False
            or type(first_work["mounted_size_bytes"]) is not int
            or not storage.MIN_LIVE_WORK_BYTES <=
                   first_work["mounted_size_bytes"] <= storage.MAX_LIVE_WORK_BYTES):
        raise NativeContinuityError("Local /work mount contract is contradictory")
    if (type(declared) is not dict or set(declared) != POLICY_FIELDS
            or declared["status"] != "LOCAL_JOURNALD_DECLARED_POLICY_ONLY"
            or declared["storage"] != "volatile"
            or declared["journal_daemon_effective_runtime_verified"] is not False
            or declared["journal_kernel_quota_verified"] is not False
            or declared["independent_vm_attested"] is not False
            or declared["release_authorized"] is not False
            or any(type(declared[name]) is not int or declared[name] < 1
                   for name in ("runtime_max_use_bytes", "runtime_max_file_bytes",
                                "runtime_keep_free_bytes",
                                "rate_limit_interval_seconds", "rate_limit_burst"))):
        raise NativeContinuityError("Local declared journald policy contradictory")
    if (type(service) is not dict or set(service) != RUNTIME_FIELDS
            or service["status"] != "LOCAL_JOURNALD_SERVICE_CGROUP_OBSERVED_ONLY"
            or type(service["journald_pid_observed"]) is not int
            or not 2 <= service["journald_pid_observed"] <= runtime.MAX_PID
            or service["journald_cgroup_v2_observed_locally"] is not True
            or service["journald_running_observed_locally"] is not True
            or service["effective_journald_configuration_verified"] is not False
            or service["journal_storage_kernel_quota_verified"] is not False
            or service["independent_vm_attested"] is not False
            or service["release_authorized"] is not False):
        raise NativeContinuityError("Local journald active service contract contradictory")
    if (not stat.S_ISDIR(path_meta.st_mode)
            or path_meta.st_uid != os.geteuid()
            or stat.S_IMODE(path_meta.st_mode) != 0o700
            or type(path_meta.st_dev) is not int
            or type(path_meta.st_ino) is not int
            or path_meta.st_ino <= 0
            or fs.f_frsize * fs.f_blocks != first_work["mounted_size_bytes"]):
        raise NativeContinuityError("Local /work inode or filesystem capacity changed")
    return {
        "classification": "LOCAL_PRE_POST_NATIVE_STATE_NOT_EXTERNAL_ATTESTATION",
        "work_inode_device": path_meta.st_dev,
        "work_inode_number": path_meta.st_ino,
        "work_filesystem_capacity_bytes": first_work["mounted_size_bytes"],
        "work_mount_policy": first_work,
        "journald_declared_policy": declared,
        "journald_runtime_state": service,
        "independent_vm_attested": False,
        "release_authorized": False,
    }


def require_unchanged_after_work(root: Path, earlier: dict) -> dict:
    """Reject a changed local work mount/journald state after all scoped work."""
    if (type(earlier) is not dict or set(earlier) != SNAPSHOT_FIELDS
            or earlier["classification"] !=
            "LOCAL_PRE_POST_NATIVE_STATE_NOT_EXTERNAL_ATTESTATION"
            or earlier["independent_vm_attested"] is not False
            or earlier["release_authorized"] is not False):
        raise NativeContinuityError("Missing exact pre-work native snapshot")
    current = capture_local_snapshot(root)
    if current != earlier:
        raise NativeContinuityError(
            "Native /work inode, quota or journald process/policy changed during analysis")
    return {
        "status": "LOCAL_NATIVE_WORK_JOURNAL_CONTINUITY_ONLY",
        "work_and_journald_pre_post_equal": True,
        "host_or_hypervisor_independently_verified": False,
        "journald_effective_kernel_storage_quota_verified": False,
        "independent_vm_attested": False,
        "release_authorized": False,
    }
