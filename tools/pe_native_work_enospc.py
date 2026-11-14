#!/usr/bin/env python3
"""PE-S2.11: bounded *local* native /work kernel ENOSPC preflight.

Only invoked from explicit synthetic-only native VM acceptance. The caller must
already have verified a reviewer-provisioned dedicated tmpfs (64-512 MiB).
Never mounts, restarts systemd or reads/writes journals. posix_fallocate can
reserve tmpfs pages; this test should only run inside a disposable VM with
adequate memory. A local kernel observation is NOT external VM attestation.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path
import secrets
import stat
import sys

import pe_native_workspace_budget as storage

INITIAL_RESERVATION = 1024 * 1024
EXCESS_BYTES = 1024 * 1024
FREE_RECOVERY_TOLERANCE = 1024 * 1024


class NativeWorkEnospcError(RuntimeError):
    """Cannot establish real kernel work storage ceiling without risk."""


def _capacity_and_free(fd: int) -> tuple[int, int]:
    fs = os.fstatvfs(fd)
    capacity = fs.f_frsize * fs.f_blocks
    available = fs.f_frsize * fs.f_bavail
    return capacity, available


def require_native_work_enospc(root: Path) -> dict:
    """Safely reserve 1 MiB then request capacity+1 MiB via posix_fallocate.

    The allocation MUST return ENOSPC, and all reserved tmpfs pages MUST be
    released. No arbitrary disk-filling loops. Root is a separate private tmpfs
    mounted by a VM reviewer, never an ordinary directory or host /tmp.
    """
    if (sys.platform != "linux" or os.geteuid() == 0
            or not isinstance(root, Path) or not root.is_absolute()
            or not hasattr(os, "posix_fallocate")):
        raise NativeWorkEnospcError("Native ENOSPC probe requires nonroot Linux tmpfs")
    try:
        pre = storage.require_bounded_work_mount(root)
    except (storage.NativeStorageBudgetError, OSError, ValueError) as exc:
        raise NativeWorkEnospcError("Native ENOSPC probe lacks trusted private tmpfs") from exc
    if (type(pre) is not dict
            or pre.get("work_mount_type") != "tmpfs"
            or pre.get("kernel_storage_limit_observed_locally") is not True
            or pre.get("independent_vm_attested") is not False
            or type(pre.get("mounted_size_bytes")) is not int):
        raise NativeWorkEnospcError("Native work mount prerequisite incomplete")
    root_fd = None
    sample_fd = None
    created = False
    marker = ".negresco-pe-s2-11-" + secrets.token_hex(16)
    try:
        root_fd = os.open(root, os.O_RDONLY | os.O_CLOEXEC
                          | os.O_DIRECTORY | os.O_NOFOLLOW)
        meta = os.fstat(root_fd)
        if (not stat.S_ISDIR(meta.st_mode)
                or meta.st_uid != os.geteuid()
                or stat.S_IMODE(meta.st_mode) != 0o700):
            raise NativeWorkEnospcError("Native work root ownership/mode changed")
        capacity, free_before = _capacity_and_free(root_fd)
        if (capacity != pre["mounted_size_bytes"]
                or not storage.MIN_LIVE_WORK_BYTES <= capacity <= storage.MAX_LIVE_WORK_BYTES
                or free_before < 32 * 1024 * 1024):
            raise NativeWorkEnospcError("Native tmpfs capacity/free space changed")
        sample_fd = os.open(
            marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL
            | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=root_fd)
        created = True
        sample_meta = os.fstat(sample_fd)
        if (not stat.S_ISREG(sample_meta.st_mode)
                or sample_meta.st_nlink != 1
                or sample_meta.st_dev != meta.st_dev
                or sample_meta.st_uid != os.geteuid()
                or stat.S_IMODE(sample_meta.st_mode) != 0o600):
            raise NativeWorkEnospcError("Native work proof inode is not private")
        os.posix_fallocate(sample_fd, 0, INITIAL_RESERVATION)
        _, free_during = _capacity_and_free(root_fd)
        if not (free_during <= free_before - INITIAL_RESERVATION // 2):
            raise NativeWorkEnospcError("Initial tmpfs reservation did not consume space")
        try:
            os.posix_fallocate(sample_fd, 0, capacity + EXCESS_BYTES)
        except OSError as exc:
            if exc.errno != errno.ENOSPC:
                raise NativeWorkEnospcError(
                    "Native work kernel refused with unexpected errno") from exc
        else:
            raise NativeWorkEnospcError(
                "Native work did not enforce ENOSPC beyond mount size")
    except (OSError, ValueError, TypeError) as exc:
        raise NativeWorkEnospcError("Native work ENOSPC check failed closed") from exc
    finally:
        if sample_fd is not None:
            os.close(sample_fd)
        if created and root_fd is not None:
            os.unlink(marker, dir_fd=root_fd)
        if root_fd is not None:
            os.close(root_fd)
    # Recheck after release: don't publish success if the mount went away or
    # physical tmpfs space was not recovered. This check remains local only.
    try:
        post = storage.require_bounded_work_mount(root)
        if (post != pre
                or type(post.get("mounted_size_bytes")) is not int
                or post["mounted_size_bytes"] != capacity):
            raise NativeWorkEnospcError("Work quota changed after ENOSPC")
        recovered_fs = os.statvfs(root)
        recovered = recovered_fs.f_frsize * recovered_fs.f_bavail
        if recovered + FREE_RECOVERY_TOLERANCE < free_before:
            raise NativeWorkEnospcError("Native work quota probe did not free space")
    except (storage.NativeStorageBudgetError, OSError, ValueError) as exc:
        raise NativeWorkEnospcError("Native work recovery could not be verified") from exc
    return {
        "status": "LOCAL_NATIVE_WORK_TMPFS_FALLOCATE_ENOSPC",
        "tmpfs_capacity_bytes": capacity,
        "initial_reservation_bytes": INITIAL_RESERVATION,
        "enospc_observed_on_oversize_reservation": True,
        "recovered_after_cleanup": True,
        "journal_kernel_quota_verified": False,
        "native_arch_vm_independently_attested": False,
        "release_authorized": False,
    }
