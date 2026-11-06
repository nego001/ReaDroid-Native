"""PE-S2.06: bounded fixture staging and post-run workspace accounting.

The staging limit prevents giant source fixtures from being copied onto the
native VM disk before scope launch. Post-run accounting can REFUSE acceptance
of oversized workspace output; it is NOT a kernel-enforced disk/journald quota
and does not bound transient bytes written while an analyzer is running.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat

MAX_STAGE_TOTAL_BYTES = 4 * 1024 * 1024
MAX_STAGE_SCRIPT_BYTES = 512 * 1024
MAX_STAGE_SYNTHETIC_PE_BYTES = 2 * 1024 * 1024
MAX_WORKSPACE_POSTRUN_BYTES = 512 * 1024 * 1024
MAX_WORKSPACE_ENTRIES = 4096
MAX_WORKSPACE_DEPTH = 16
_COPY_CHUNK_BYTES = 64 * 1024


class NativeStorageBudgetError(RuntimeError):
    """Untrusted fixture or workspace exceeds native acceptance budget."""


def _private_parent(path: Path) -> None:
    try:
        info = path.parent.lstat()
    except OSError as exc:
        raise NativeStorageBudgetError("Native fixture destination unavailable") from exc
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o077):
        raise NativeStorageBudgetError(
            "Native fixture destination must be in an owner-only directory")


def _copy_one(source: Path, target: Path, limit: int) -> int:
    """Pin source FD, stream at most limit+1 bytes, never replace a target.

    A size precheck is only an optimization: repeated bounded reads and a
    before/after inode+size+mtime+ctime comparison reject mutable fixtures.
    """
    if (not isinstance(source, Path) or not isinstance(target, Path)
            or type(limit) is not int or not 0 < limit <= MAX_STAGE_TOTAL_BYTES
            or not hasattr(os, "O_NOFOLLOW")):
        raise NativeStorageBudgetError("Invalid native staging budget")
    _private_parent(target)
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    dst_fd = None
    created = False
    try:
        src_fd = os.open(source, flags)
        try:
            before = os.fstat(src_fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or before.st_size < 1 or before.st_size > limit):
                raise NativeStorageBudgetError(
                    "Native fixture is not a bounded exclusive regular file")
            dst_fd = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
                | os.O_NOFOLLOW,
                0o600)
            created = True
            with os.fdopen(dst_fd, "wb") as output:
                dst_fd = None
                total = 0
                while True:
                    data = os.read(
                        src_fd, min(_COPY_CHUNK_BYTES, limit + 1 - total))
                    if not data:
                        break
                    total += len(data)
                    if total > limit:
                        raise NativeStorageBudgetError(
                            "Native fixture grew beyond staging budget")
                    output.write(data)
                output.flush()
                os.fsync(output.fileno())
            after = os.fstat(src_fd)
            identity = lambda m: (
                m.st_dev, m.st_ino, m.st_size, m.st_mtime_ns, m.st_ctime_ns)
            if total != before.st_size or identity(before) != identity(after):
                raise NativeStorageBudgetError(
                    "Native fixture changed during bounded staging")
            return total
        finally:
            os.close(src_fd)
    except OSError as exc:
        raise NativeStorageBudgetError(
            "Native fixture could not be securely staged") from exc
    except BaseException:
        raise
    finally:
        if dst_fd is not None:
            os.close(dst_fd)
        # Success leaves the new exclusive file. Failed partial writes are
        # removed by stage_bounded_fixtures' rollback below, or the private
        # TemporaryDirectory cleanup at the callsite.


def stage_bounded_fixtures(items: list[tuple[Path, Path, int]]) -> int:
    """Stage a finite list, with per-file AND combined byte ceilings.

    The caller owns an already-created 0700 temporary destination tree.
    No subprocess is launched and no path is overwritten.
    """
    if (type(items) is not list or not items or len(items) > 8
            or any(type(item) is not tuple or len(item) != 3
                   for item in items)):
        raise NativeStorageBudgetError("Invalid native fixture staging list")
    total = 0
    created = []
    try:
        for source, target, maximum in items:
            if (not isinstance(source, Path) or not isinstance(target, Path)
                    or type(maximum) is not int or maximum < 1
                    or maximum > MAX_STAGE_TOTAL_BYTES):
                raise NativeStorageBudgetError(
                    "Invalid native fixture staging entry")
            # Refuse a whole stage once the shared budget is exhausted.
            available = MAX_STAGE_TOTAL_BYTES - total
            if available < 1:
                raise NativeStorageBudgetError(
                    "Native fixture aggregate staging budget exhausted")
            # The new destination may exist by the time a copy fails. Track
            # only newly created paths, never delete a preexisting name.
            try:
                size = _copy_one(source, target, min(maximum, available))
            except BaseException:
                # A successful exclusive O_EXCL open can leave an incomplete
                # target even when the copy raises; _copy_one removes it.
                raise
            created.append(target)
            total += size
        return total
    except BaseException:
        for path in reversed(created):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        raise


def audit_postrun_workspace(
        root: Path, *, max_bytes: int = MAX_WORKSPACE_POSTRUN_BYTES) -> int:
    """Reject oversize/unsafe *remaining* files after the scope is stopped.

    This is a conservative post-run observation, not real-time enforcement.
    Both logical sizes and physically allocated bytes are counted, and
    symlinks/special files are never followed. Bound entries/depth too.
    """
    if (not isinstance(root, Path) or type(max_bytes) is not int
            or not 0 < max_bytes <= MAX_WORKSPACE_POSTRUN_BYTES):
        raise NativeStorageBudgetError("Invalid native workspace audit budget")
    try:
        meta = root.lstat()
        if (not stat.S_ISDIR(meta.st_mode)
                or meta.st_uid != os.geteuid()
                or meta.st_mode & 0o077):
            raise NativeStorageBudgetError(
                "Native workspace audit root is not private")
        count = 0
        logical = 0
        allocated = 0
        stack = [(root, 0)]
        while stack:
            parent, depth = stack.pop()
            with os.scandir(parent) as entries:
                for entry in entries:
                    count += 1
                    if count > MAX_WORKSPACE_ENTRIES:
                        raise NativeStorageBudgetError(
                            "Native workspace has too many entries")
                    info = entry.stat(follow_symlinks=False)
                    if info.st_uid != os.geteuid():
                        raise NativeStorageBudgetError(
                            "Native workspace contains foreign-owned entry")
                    if stat.S_ISDIR(info.st_mode):
                        if depth >= MAX_WORKSPACE_DEPTH:
                            raise NativeStorageBudgetError(
                                "Native workspace nesting exceeds budget")
                        stack.append((Path(entry.path), depth + 1))
                    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise NativeStorageBudgetError(
                            "Native workspace contains link or special file")
                    else:
                        logical += info.st_size
                        allocated += info.st_blocks * 512
                        if logical > max_bytes or allocated > max_bytes:
                            raise NativeStorageBudgetError(
                                "Native workspace footprint exceeds post-run budget")
        return max(logical, allocated)
    except OSError as exc:
        raise NativeStorageBudgetError(
            "Native workspace post-run audit could not be completed") from exc
