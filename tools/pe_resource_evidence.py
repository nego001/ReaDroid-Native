"""Fail-closed validation of cgroup quotas attested before Bubblewrap.

The guard writes a 0600 JSON proof outside the sandbox bind mounts.
Read metadata and bytes from ONE no-follow FD, reject duplicate keys and
bound file size. Also correlate the private proof with the guard's stdout
receipt; independent fields may not disagree without refusing acceptance.
These checks are not substitutes for validating the kernel's live cgroup.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

from pe_resource_limits import (MEMORY_MAX_BYTES, TASKS_MAX,
                                CPU_QUOTA_PERCENT, _validate_scope_name,
                                ResourceLimitsUnavailable)

MAX_PROOF_BYTES = 4096
PROOF_SCHEMA = "negresco_cgroup_v2_proof_v1"
PROOF_KEYS = frozenset({
    "schema", "scope", "verified", "memory_max", "pids_max",
    "cpu_quota", "cpu_period"
})
KERNEL_KEYS = ("memory_max", "pids_max", "cpu_quota", "cpu_period")


class InvalidResourceEvidence(RuntimeError):
    pass


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidResourceEvidence("Duplicate cgroup proof key")
        result[key] = value
    return result


def read_scope_proof(path: Path, unit: str) -> dict:
    """Require an owner-only, single-file proof bound to a specific scope."""
    try:
        _validate_scope_name(unit)
        proof = Path(path)
        if not proof.is_absolute() or not hasattr(os, "O_NOFOLLOW"):
            raise InvalidResourceEvidence("Unsafe private proof path")
        # The parent is constructed as 0700 outside Bubblewrap. It must not
        # be redirected to a user-shared directory in native acceptance.
        parent = proof.parent
        # Pin the private directory too, so swapping the parent path after
        # checking metadata cannot redirect the later file open.
        parent_fd = os.open(
            parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        with os.fdopen(parent_fd, "rb") as directory:
            parent_meta = os.fstat(directory.fileno())
            if (not stat.S_ISDIR(parent_meta.st_mode)
                    or parent_meta.st_uid != os.geteuid()
                    or parent_meta.st_mode & 0o077):
                raise InvalidResourceEvidence("Cgroup proof parent is not private")
            flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
            fd = os.open(proof.name, flags, dir_fd=directory.fileno())
            with os.fdopen(fd, "rb") as reader:
                before = os.fstat(reader.fileno())
                if (not stat.S_ISREG(before.st_mode)
                        or before.st_uid != os.geteuid()
                        or before.st_mode & 0o077
                        or not 1 <= before.st_size <= MAX_PROOF_BYTES):
                    raise InvalidResourceEvidence(
                        "Unsafe owner, permissions or cgroup proof length")
                raw = reader.read(MAX_PROOF_BYTES + 1)
                after = os.fstat(reader.fileno())
                if (len(raw) != before.st_size
                        or after.st_size != before.st_size
                        or after.st_ino != before.st_ino
                        or after.st_mtime_ns != before.st_mtime_ns):
                    raise InvalidResourceEvidence("Cgroup proof changed while read")
        record = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                InvalidResourceEvidence("Non-finite proof value")))
    except (ResourceLimitsUnavailable, OSError, UnicodeError, ValueError) as exc:
        raise InvalidResourceEvidence("Private cgroup proof unavailable or invalid") from exc
    if (not isinstance(record, dict)
            or set(record) != PROOF_KEYS
            or record["schema"] != PROOF_SCHEMA
            or record["scope"] != unit
            or record["verified"] is not True
            or any(type(record[k]) is not int for k in KERNEL_KEYS)):
        raise InvalidResourceEvidence("Proof is not an exact verified scope record")
    memory, tasks, quota, period = (record[k] for k in KERNEL_KEYS)
    if (not 0 < memory <= MEMORY_MAX_BYTES
            or not 0 < tasks <= TASKS_MAX
            or not 0 < quota and 0 < period
            or quota * 100 > period * CPU_QUOTA_PERCENT):
        raise InvalidResourceEvidence("Effective cgroup quota exceeds policy")
    return {
        "verification": "guard_verified_before_bwrap",
        "memory_max_bytes": memory,
        "tasks_max": tasks,
        "cpu_quota": quota,
        "cpu_period": period,
    }


def corroborate_guard_receipt(records: list[object],
                              private_limits: dict) -> dict:
    """Cross-check exactly one structured guard record against private proof.

    stdout alone can never authorize PASS: a 0600 validated private proof
    and all four values must match. Fail if contradictory/duplicate claimed
    guard records appear, even when one of them contains valid fields.
    """
    if not isinstance(records, list) or not isinstance(private_limits, dict):
        raise InvalidResourceEvidence("Missing scope guard records")
    matches = [x for x in records if isinstance(x, dict)
               and x.get("cgroup_verification") == "passed"]
    if len(matches) != 1:
        raise InvalidResourceEvidence("Missing or duplicate cgroup guard receipt")
    receipt = matches[0]
    expected = {
        "memory_max": "memory_max_bytes",
        "pids_max": "tasks_max",
        "cpu_quota": "cpu_quota",
        "cpu_period": "cpu_period",
    }
    if (receipt.get("verified") is not True
            or private_limits.get("verification") != "guard_verified_before_bwrap"
            or any(type(receipt.get(k)) is not int
                   or type(private_limits.get(v)) is not int
                   or receipt[k] != private_limits[v]
                   for k, v in expected.items())):
        raise InvalidResourceEvidence(
            "Guard stdout and private kernel cgroup proof disagree")
    return {"corroborated": True, "source": "private_file_and_guard_stdout"}
