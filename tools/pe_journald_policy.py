#!/usr/bin/env python3
"""PE-S2.09: fail-closed, read-only check of DECLARED journald policy.

This does NOT prove the running daemon loaded this configuration. journald
RuntimeMaxUse is a retention target, not a hard Linux filesystem quota.
No system configuration is changed, and no release is authorized.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import subprocess

SYSTEMD_ANALYZE = Path("/usr/bin/systemd-analyze")
MAX_CONFIG_BYTES = 65536
MAX_CONFIG_LINES = 512
MAX_JOURNAL_USE = 32 * 1024 * 1024
MAX_JOURNAL_FILE = 8 * 1024 * 1024
MIN_KEEP_FREE = 32 * 1024 * 1024
MAX_RATE_BURST = 1000
MAX_RATE_INTERVAL_SECONDS = 60
_SIZE = re.compile(r"([1-9][0-9]{0,9})([KMGT]?)\Z")
_INTERVAL = re.compile(r"([1-9][0-9]{0,5})(s|min|h)\Z")


class JournaldPolicyError(RuntimeError):
    """The journald declared policy cannot be trusted as sufficiently bounded."""


def _size_bytes(value: str) -> int:
    match = _SIZE.fullmatch(value)
    if match is None:
        raise JournaldPolicyError("Journald size must be explicit, fixed and nonzero")
    magnitude = int(match.group(1))
    exponent = {"": 0, "K": 1, "M": 2, "G": 3, "T": 4}[match.group(2)]
    return magnitude * (1024 ** exponent)


def _interval_seconds(value: str) -> int:
    match = _INTERVAL.fullmatch(value)
    if match is None:
        raise JournaldPolicyError("Journald rate-limit interval must be explicit")
    return int(match.group(1)) * {"s": 1, "min": 60, "h": 3600}[match.group(2)]


def parse_declared_journald_config(raw: str) -> dict:
    """Parse the systemd-analyze --tldr rendering, NOT an invented policy file.

    --tldr is systemd's merged configuration presentation. Repeated keys
    are applied in printed order: the last declaration is effective in that
    presentation. Comments, unrelated sections and empty lines are ignored.
    """
    if (not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > MAX_CONFIG_BYTES
            or "\x00" in raw or "\r" in raw):
        raise JournaldPolicyError("Incomplete or oversized journald configuration")
    lines = raw.splitlines()
    if len(lines) > MAX_CONFIG_LINES:
        raise JournaldPolicyError("Too many journald configuration lines")
    fields: dict[str, str] = {}
    section = None
    for line in lines:
        if len(line) > 4096:
            raise JournaldPolicyError("Oversized journald configuration line")
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            if not section or any(c.isspace() for c in section):
                raise JournaldPolicyError("Malformed journald section")
            continue
        if "=" not in line or line.startswith(("[", "!")) or "\\" in line:
            raise JournaldPolicyError("Malformed or continued journald setting")
        key, value = (part.strip() for part in line.split("=", 1))
        if not key or not value:
            raise JournaldPolicyError("Empty journald setting")
        if section == "Journal":
            fields[key] = value
    required = (
        "Storage", "RuntimeMaxUse", "RuntimeMaxFileSize", "RuntimeKeepFree",
        "RateLimitIntervalSec", "RateLimitBurst", "ForwardToSyslog",
        "ForwardToKMsg", "ForwardToConsole", "ForwardToWall",
    )
    if any(key not in fields for key in required):
        raise JournaldPolicyError("Explicit journald policy settings missing")
    if fields["Storage"] != "volatile":
        raise JournaldPolicyError("Journal storage must be volatile in isolated VM")
    if any(fields[key] != "no" for key in
           ("ForwardToSyslog", "ForwardToKMsg",
            "ForwardToConsole", "ForwardToWall")):
        raise JournaldPolicyError("Journal forwarding outside its store is refused")
    maximum = _size_bytes(fields["RuntimeMaxUse"])
    maximum_file = _size_bytes(fields["RuntimeMaxFileSize"])
    keep_free = _size_bytes(fields["RuntimeKeepFree"])
    seconds = _interval_seconds(fields["RateLimitIntervalSec"])
    burst_text = fields["RateLimitBurst"]
    if re.fullmatch(r"[0-9]{1,7}", burst_text) is None:
        raise JournaldPolicyError("Invalid journald rate-limit burst")
    burst = int(burst_text)
    if not (8 * 1024 * 1024 <= maximum <= MAX_JOURNAL_USE
            and 0 < maximum_file <= min(MAX_JOURNAL_FILE, maximum)
            and keep_free >= MIN_KEEP_FREE
            and 0 < seconds <= MAX_RATE_INTERVAL_SECONDS
            and 0 < burst <= MAX_RATE_BURST):
        raise JournaldPolicyError("Journald declared limits are missing or unsafe")
    return {
        "status": "LOCAL_JOURNALD_DECLARED_POLICY_ONLY",
        "storage": "volatile",
        "runtime_max_use_bytes": maximum,
        "runtime_max_file_bytes": maximum_file,
        "runtime_keep_free_bytes": keep_free,
        "rate_limit_interval_seconds": seconds,
        "rate_limit_burst": burst,
        "journal_daemon_effective_runtime_verified": False,
        "journal_kernel_quota_verified": False,
        "independent_vm_attested": False,
        "release_authorized": False,
    }


def require_journald_declared_policy() -> dict:
    """Read merged journald config without sudo, modification or daemon restart."""
    if os.name != "posix" or os.geteuid() == 0:
        raise JournaldPolicyError("Journald probe requires unprivileged Linux")
    try:
        metadata = SYSTEMD_ANALYZE.lstat()
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0
                or metadata.st_mode & 0o022
                or not os.access(SYSTEMD_ANALYZE, os.X_OK)):
            raise JournaldPolicyError("Untrusted systemd-analyze executable")
        result = subprocess.run(
            [str(SYSTEMD_ANALYZE), "cat-config", "--tldr",
             "systemd/journald.conf"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=8, check=False,
            env={"LC_ALL": "C", "LANG": "C", "PATH": "/usr/bin:/bin"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise JournaldPolicyError("Unable to inspect journald declared policy") from exc
    if (result.returncode != 0 or len(result.stdout) > MAX_CONFIG_BYTES
            or len(result.stderr) > 4096):
        raise JournaldPolicyError("Journald policy reader refused or exceeded bounds")
    try:
        return parse_declared_journald_config(result.stdout.decode("utf-8"))
    except UnicodeError as exc:
        raise JournaldPolicyError("Journald policy must be UTF-8") from exc
