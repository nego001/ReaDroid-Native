#!/usr/bin/env python3
"""PE sandbox CI probe. Runs INSIDE the same bwrap boundary as Ghidra.

This is not a generic command execution API, nor a guarantee against escapes.
Use only a self-authored fixture on disposable CI runners.
"""
from pathlib import Path
import ctypes
import errno
import json
import os
import sys

def require(statement: bool, message: str) -> None:
    if not statement:
        raise RuntimeError("sandbox probe failed: " + message)

def main(argv: list[str]) -> int:
    require(len(argv) in (3, 5, 6), "host namespace, canary, optional FD identity and seccomp baseline required")
    parent_net_ns, host_canary = argv[1:3]
    require(parent_net_ns.startswith("net:[") and parent_net_ns.endswith("]"),
            "invalid host namespace marker")
    sandbox_ns = os.readlink("/proc/self/ns/net")
    require(sandbox_ns != parent_net_ns,
            "process is sharing host network namespace")
    require(not Path(host_canary).exists(),
            "host-private marker unexpectedly visible")
    inherited_host_fd_hidden = None
    if len(argv) >= 5:
        require(all(part.isdecimal() for part in argv[3:5]),
                "invalid host fd inode identity")
        host_dev, host_inode = (int(arg) for arg in argv[3:5])
        require(host_dev > 0 and host_inode > 0, "invalid host fd stat")
        for entry in Path("/proc/self/fd").iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                candidate = os.stat(entry)
            except OSError:
                continue
            require((candidate.st_dev, candidate.st_ino) != (host_dev, host_inode),
                    "inherited descriptor leaked host-private canary")
        inherited_host_fd_hidden = True
    seccomp_enforced = None
    if len(argv) == 6:
        require(argv[5].isdecimal(), "invalid parent seccomp filter count")
        baseline = int(argv[5])
        matches = [line.partition(":")[2].strip()
                   for line in Path("/proc/self/status").read_text().splitlines()
                   if line.startswith("Seccomp_filters:")]
        require(len(matches) == 1 and matches[0].isdecimal(),
                "kernel seccomp count unavailable")
        current = int(matches[0])
        require(current > baseline, "additional seccomp filter not installed")
        libc = ctypes.CDLL(None, use_errno=True)
        libc.ptrace.restype = ctypes.c_long
        libc.ptrace.argtypes = [ctypes.c_long, ctypes.c_long,
                               ctypes.c_void_p, ctypes.c_void_p]
        ctypes.set_errno(0)
        rc = libc.ptrace(0, 0, None, None)  # PTRACE_TRACEME
        require(rc == -1 and ctypes.get_errno() == errno.EPERM,
                "ptrace was not denied with EPERM")
        seccomp_enforced = True
    require(not Path("/etc/passwd").exists(),
            "host account database unexpectedly visible")
    require(not any(Path("/home").iterdir()),
            "host home directory unexpectedly populated")
    require(Path("/work/input.exe").is_file(),
            "sanitized PE snapshot not visible")
    require(Path("/opt/negresco-ghidra/support/analyzeHeadless").is_file(),
            "read-only Ghidra tree unavailable")
    require(Path(os.environ["JAVA_HOME"]).joinpath("bin/java").is_file(),
            "pinned Java executable missing")
    require(os.environ.get("HOME") == "/work",
            "untrusted HOME exposed inside sandbox")
    require(os.environ.get("TMPDIR") == "/tmp",
            "temporary files not redirected")
    require(os.environ.get("GHIDRA_HEADLESS_MAXMEM") == "2G",
            "Ghidra memory budget missing after --clearenv")
    require(os.environ.get("PATH", "").split(":")[0] ==
            os.environ["JAVA_HOME"] + "/bin",
            "pinned JDK not prioritized on PATH")
    mounts = [
        part.split()
        for line in Path("/proc/self/mountinfo").read_text().splitlines()
        for part in [line.split(" - ", 1)[0]]
    ]
    require(any(m[4] == "/usr" and "ro" in m[5].split(",") for m in mounts),
            "/usr runtime not explicitly mounted read-only")
    canary = Path("/work/sandbox-probe-writes-only-here")
    canary.write_text("test-only", encoding="utf-8")
    require(canary.read_text(encoding="utf-8") == "test-only",
            "private workspace is not writable")
    canary.unlink()
    print(json.dumps({
        "isolation_probe": "passed",
        "host_home_canary_hidden": True,
        "network_namespace_separate": True,
        "host_etc_hidden": True,
        "usr_runtime_read_only": True,
        "private_work_writable": True,
        "inherited_host_fd_hidden": inherited_host_fd_hidden,
        "seccomp_enforced": seccomp_enforced,
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
