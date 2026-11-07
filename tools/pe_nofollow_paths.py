#!/usr/bin/env python3
"""Descriptor-anchored traversal of absolute directories without symlinks.

O_NOFOLLOW on only the final pathname component is NOT enough: a symbolic
link in an ancestor directory can still redirect source or receipt paths.
Callers must use the returned FD with dir_fd and keep stack alive.
"""
from __future__ import annotations

from contextlib import ExitStack
import os
from pathlib import Path


def open_absolute_directory_nofollow(path: Path, stack: ExitStack) -> int:
    """Open each directory component relative to its pinned parent FD.

    Reject relative paths, symlinked ancestors, dot traversal and malformed
    components. Do not resolve() an untrusted path before validating it.
    """
    raw = os.fspath(path)
    if not isinstance(raw, str) or not raw.startswith("/"):
        raise ValueError("Absolute directory path required")
    parts = [] if raw == "/" else raw[1:].split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("Noncanonical directory path")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.open("/", flags)
    stack.callback(os.close, fd)
    for part in parts:
        fd = os.open(part, flags, dir_fd=fd)
        stack.callback(os.close, fd)
    return fd
