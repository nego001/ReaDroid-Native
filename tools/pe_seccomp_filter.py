#!/usr/bin/env python3
"""Build a narrow, auditable seccomp cBPF filter for synthetic PE sandbox tests.

This module only compiles rules into a Linux memfd and does not load them on
the caller. Bubblewrap loads the filter via --seccomp FD after setting up its
sandbox. No shell or privilege change. Support intentionally starts at x86_64.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import errno
import os
from pathlib import Path
import platform

SCMP_ACT_ALLOW = 0x7FFF0000
SCMP_ACT_ERRNO_EPERM = 0x00050000 | errno.EPERM

# Restrict kernel introspection, host process access and kernel configuration.
# Do not deny clone/fork, mmap, futex, execve, openat, or local IPC needed
# by the JDK. This is a denylist, not a syscall allowlist.
DENIED_SYSCALLS = (
    "ptrace",
    "process_vm_readv",
    "process_vm_writev",
    "bpf",
    "perf_event_open",
    "userfaultfd",
    "kexec_load",
    "kexec_file_load",
    "init_module",
    "finit_module",
    "delete_module",
    "open_by_handle_at",
    "mount",
    "umount2",
    "pivot_root",
    "setns",
    "unshare",
    "reboot",
    "swapon",
    "swapoff",
)
MAX_BPF_BYTES = 32768


class SeccompUnavailable(RuntimeError):
    pass


def seccomp_filter_count() -> int:
    """Read current filter count for an experimental before/after probe."""
    try:
        records = Path("/proc/self/status").read_text(encoding="ascii").splitlines()
        matches = [part.partition(":")[2].strip()
                   for part in records if part.startswith("Seccomp_filters:")]
        if len(matches) != 1 or not matches[0].isdecimal():
            raise SeccompUnavailable("Kernel cannot report seccomp filter count")
        return int(matches[0])
    except (OSError, UnicodeError) as exc:
        raise SeccompUnavailable("Cannot inspect seccomp state") from exc


def _load_libseccomp():
    library = ctypes.util.find_library("seccomp")
    if not library:
        raise SeccompUnavailable("libseccomp is absent")
    try:
        lib = ctypes.CDLL(library, use_errno=True)
        lib.seccomp_init.restype = ctypes.c_void_p
        lib.seccomp_init.argtypes = [ctypes.c_uint32]
        lib.seccomp_release.argtypes = [ctypes.c_void_p]
        lib.seccomp_release.restype = None
        lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
        lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
        lib.seccomp_rule_add.restype = ctypes.c_int
        lib.seccomp_rule_add.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
        lib.seccomp_export_bpf.restype = ctypes.c_int
        lib.seccomp_export_bpf.argtypes = [ctypes.c_void_p, ctypes.c_int]
        return lib
    except AttributeError as exc:
        raise SeccompUnavailable("libseccomp API incomplete") from exc


def compile_seccomp_bpf_fd() -> int:
    """Return owned CLOEXEC fd; caller MUST close it after subprocess creation.

    The explicitly allowed descriptor must be passed to bwrap via
    subprocess.run(pass_fds=(fd,)). No content from an untrusted PE is used.
    """
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SeccompUnavailable("Seccomp PE prototype requires Linux x86_64")
    if not hasattr(os, "memfd_create"):
        raise SeccompUnavailable("memfd_create unavailable")
    lib = _load_libseccomp()
    ctx = lib.seccomp_init(SCMP_ACT_ALLOW)
    if not ctx:
        raise SeccompUnavailable("libseccomp could not initialize filter")
    fd = None
    try:
        for syscall in DENIED_SYSCALLS:
            number = lib.seccomp_syscall_resolve_name(syscall.encode("ascii"))
            if number < 0:
                raise SeccompUnavailable("Unrecognized syscall: " + syscall)
            if lib.seccomp_rule_add(
                    ctx, SCMP_ACT_ERRNO_EPERM, number, 0) != 0:
                raise SeccompUnavailable("Could not block syscall: " + syscall)
        fd = os.memfd_create("negresco-pe-seccomp", flags=os.MFD_CLOEXEC)
        if lib.seccomp_export_bpf(ctx, fd) != 0:
            raise SeccompUnavailable("libseccomp BPF export failed")
        length = os.lseek(fd, 0, os.SEEK_END)
        if not 8 <= length <= MAX_BPF_BYTES or length % 8 != 0:
            raise SeccompUnavailable("Unexpected seccomp BPF program size")
        os.lseek(fd, 0, os.SEEK_SET)
        result, fd = fd, None
        return result
    finally:
        lib.seccomp_release(ctx)
        if fd is not None:
            os.close(fd)


def attach_seccomp_fd(argv: list[str], fd: int) -> list[str]:
    """Insert --seccomp before the bwrap command after checking its boundary."""
    if (not isinstance(argv, list) or argv.count("--") != 1
            or not argv or not Path(argv[0]).name.startswith("bwrap")
            or type(fd) is not int or fd < 3
            or "--seccomp" in argv or "--add-seccomp-fd" in argv):
        raise SeccompUnavailable("Invalid Bubblewrap command or seccomp FD")
    command = list(argv)
    command[command.index("--"):command.index("--")] = ["--seccomp", str(fd)]
    return command
