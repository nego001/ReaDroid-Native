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


def _systemctl_show() -> dict:
    try:
        info = SYSTEMCTL.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o022 or not os.access(SYSTEMCTL, os.X_OK)):
            raise JournaldRuntimeError("Untrusted systemctl executable")
        result = subprocess.run(
            [str(SYSTEMCTL), "--system", "show", UNIT,
             *[f"--property={key}" for key in PROPERTIES], "--no-pager"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=8, check=False,
            env={"LC_ALL": "C", "LANG": "C", "PATH": "/usr/bin:/bin"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise JournaldRuntimeError("Journald service state query unavailable") from exc
    if (result.returncode != 0
            or not isinstance(result.stdout, bytes)
            or len(result.stdout) > MAX_SHOW_BYTES
            or not isinstance(result.stderr, bytes)
            or len(result.stderr) > 4096):
        raise JournaldRuntimeError("Journald service state query failed")
    return parse_systemctl_show(result.stdout)


def _proc_cgroup(pid: int) -> str:
    if type(pid) is not int or not 2 <= pid <= MAX_PID:
        raise JournaldRuntimeError("Invalid journald PID for /proc")
    try:
        record = (Path("/proc") / str(pid) / "cgroup").read_bytes()
    except OSError as exc:
        raise JournaldRuntimeError("Cannot read journald kernel cgroup membership") from exc
    if (len(record) > MAX_PROC_BYTES or
            record not in (
                (f"0::{EXPECTED_CGROUP}\n").encode("ascii"),
                (f"0::{EXPECTED_CGROUP}").encode("ascii"))):
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
