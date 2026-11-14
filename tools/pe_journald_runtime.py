#!/usr/bin/env python3
"""PE-S2.09.1: read-only journald process/cgroup observation in native guest.

This observes local service state twice and matches /proc/PID/cgroup. It does
NOT attest that journald loaded the on-disk configuration, enforce storage
limits, authenticate a VM/hypervisor or authorize any release.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import subprocess
import selectors
import time

SYSTEMCTL = Path("/usr/bin/systemctl")
UNIT = "systemd-journald.service"
EXPECTED_CGROUP = "/system.slice/systemd-journald.service"
PROPERTIES = ("Id", "LoadState", "ActiveState", "SubState",
              "MainPID", "ControlGroup")
MAX_SHOW_BYTES = 8192
MAX_PROC_BYTES = 8192
MAX_PID = 4194304


class JournaldRuntimeError(RuntimeError):
    """The local live journald observation is incomplete or contradictory."""


def parse_systemctl_show(raw: bytes) -> dict:
    if (not isinstance(raw, bytes) or not raw or len(raw) > MAX_SHOW_BYTES
            or b"\x00" in raw or b"\r" in raw):
        raise JournaldRuntimeError("Invalid journald systemctl response")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise JournaldRuntimeError("Non-UTF8 journald systemctl response") from exc
    fields = {}
    for line in lines:
        if len(line) > 1024 or "=" not in line:
            raise JournaldRuntimeError("Malformed journald service property")
        key, value = line.split("=", 1)
        if key not in PROPERTIES or key in fields or not value:
            raise JournaldRuntimeError("Unknown, duplicate or empty service property")
        fields[key] = value
    if set(fields) != set(PROPERTIES):
        raise JournaldRuntimeError("Incomplete journald service properties")
    if (fields["Id"] != UNIT or fields["LoadState"] != "loaded"
            or fields["ActiveState"] != "active"
            or fields["SubState"] != "running"
            or fields["ControlGroup"] != EXPECTED_CGROUP):
        raise JournaldRuntimeError("Journald is not active in expected system cgroup")
    raw_pid = fields["MainPID"]
    if re.fullmatch(r"[1-9][0-9]{0,6}", raw_pid) is None:
        raise JournaldRuntimeError("Invalid journald main PID")
    pid = int(raw_pid)
    if not 2 <= pid <= MAX_PID:
        raise JournaldRuntimeError("Journald main PID outside expected range")
    return {"pid": pid, "control_group": fields["ControlGroup"]}


def _run_systemctl_bounded(command: list[str], *, timeout: float = 8) -> tuple[bytes, bytes, int]:
    """Capture a fixed read-only systemctl command without unbounded PIPE data.

    stdout and stderr must reach EOF within the deadline and hard byte caps.
    A too-chatty, blocked or failed child is terminated and never trusted.
    Tests may supply a benign synthetic command; production fixes argv.
    """
    deadline = time.monotonic() + timeout
    process = None
    try:
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={"LC_ALL": "C", "LANG": "C", "PATH": "/usr/bin:/bin"},
            close_fds=True,
        )
        if process.stdout is None or process.stderr is None:
            raise JournaldRuntimeError("Cannot capture systemctl output streams")
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        limits = {"stdout": MAX_SHOW_BYTES, "stderr": 4096}
        with selectors.DefaultSelector() as poller:
            poller.register(process.stdout, selectors.EVENT_READ, "stdout")
            poller.register(process.stderr, selectors.EVENT_READ, "stderr")
            while poller.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise JournaldRuntimeError("Timed out reading systemctl")
                events = poller.select(remaining)
                if not events:
                    raise JournaldRuntimeError("Timed out reading systemctl")
                for key, _ in events:
                    name = key.data
                    allowed = limits[name] + 1 - len(buffers[name])
                    if allowed <= 0:
                        raise JournaldRuntimeError("Oversized systemctl output")
                    chunk = os.read(key.fileobj.fileno(), min(4096, allowed))
                    if not chunk:
                        poller.unregister(key.fileobj)
                    else:
                        buffers[name].extend(chunk)
                        if len(buffers[name]) > limits[name]:
                            raise JournaldRuntimeError("Oversized systemctl output")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise JournaldRuntimeError("Timed out waiting for systemctl")
        code = process.wait(timeout=remaining)
        return bytes(buffers["stdout"]), bytes(buffers["stderr"]), code
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise JournaldRuntimeError("Bounded systemctl observation unavailable") from exc
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait()
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()


def _systemctl_show() -> dict:
    try:
        info = SYSTEMCTL.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o022 or not os.access(SYSTEMCTL, os.X_OK)):
            raise JournaldRuntimeError("Untrusted systemctl executable")
        stdout, stderr, code = _run_systemctl_bounded(
            [str(SYSTEMCTL), "--system", "show", UNIT,
             *[f"--property={key}" for key in PROPERTIES], "--no-pager"])
    except OSError as exc:
        raise JournaldRuntimeError("Journald service state query unavailable") from exc
    if (code != 0 or not isinstance(stdout, bytes)
            or not isinstance(stderr, bytes)
            or len(stdout) > MAX_SHOW_BYTES or len(stderr) > 4096):
        raise JournaldRuntimeError("Journald service state query failed")
    return parse_systemctl_show(stdout)


def _read_proc_cgroup_bounded(pid: int, *,
                              proc_root: Path = Path("/proc")) -> bytes:
    """Read at most MAX_PROC_BYTES+1 from the exact PID's procfs entry.

    proc_root is test-only injection, never exposed by any CLI. Refuse a
    final-component symlink; no writable file, process, or service is touched.
    """
    if type(pid) is not int or not 2 <= pid <= MAX_PID:
        raise JournaldRuntimeError("Invalid journald PID for /proc")
    try:
        fd = os.open(proc_root / str(pid) / "cgroup",
                     os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            chunks = bytearray()
            # A procfs read may return fewer bytes than requested. Reading
            # only once could accept a valid-looking prefix of a longer,
            # contradictory cgroup entry. Require EOF within the budget.
            while len(chunks) <= MAX_PROC_BYTES:
                part = os.read(fd, MAX_PROC_BYTES + 1 - len(chunks))
                if not part:
                    break
                chunks.extend(part)
            record = bytes(chunks)
        finally:
            os.close(fd)
    except OSError as exc:
        raise JournaldRuntimeError("Cannot read journald kernel cgroup membership") from exc
    if not record or len(record) > MAX_PROC_BYTES or b"\x00" in record:
        raise JournaldRuntimeError("Missing, oversized or binary journald cgroup record")
    return record


def _proc_cgroup(pid: int) -> str:
    record = _read_proc_cgroup_bounded(pid)
    if record not in (
            (f"0::{EXPECTED_CGROUP}\n").encode("ascii"),
            (f"0::{EXPECTED_CGROUP}").encode("ascii")):
        raise JournaldRuntimeError("Journald /proc cgroup contradicts systemctl")
    return EXPECTED_CGROUP


def observe_live_journald() -> dict:
    """Observe current state without controlling/restarting any system service."""
    if os.name != "posix" or os.geteuid() == 0:
        raise JournaldRuntimeError("Native journald runtime probe requires non-root Linux")
    first = _systemctl_show()
    if _proc_cgroup(first["pid"]) != EXPECTED_CGROUP:
        raise JournaldRuntimeError("Journald process cgroup differs from service")
    second = _systemctl_show()
    if second != first or _proc_cgroup(second["pid"]) != EXPECTED_CGROUP:
        raise JournaldRuntimeError("Journald service state changed during observation")
    return {
        "status": "LOCAL_JOURNALD_SERVICE_CGROUP_OBSERVED_ONLY",
        "journald_pid_observed": first["pid"],
        "journald_cgroup_v2_observed_locally": True,
        "journald_running_observed_locally": True,
        "effective_journald_configuration_verified": False,
        "journal_storage_kernel_quota_verified": False,
        "independent_vm_attested": False,
        "release_authorized": False,
    }
