"""Validate proof measured by the actual Ghidra JVM, not a test subprocess.

One trusted headless postScript reads kernel procfs in Ghidra's own process.
Require an increase relative to the baseline measured by the real scope
launcher BEFORE it handed its sealed cBPF to Bubblewrap.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path
import stat

from pe_nofollow_paths import open_absolute_directory_nofollow

MAX_PROOF_BYTES = 1024
SCHEMA = "negresco_ghidra_seccomp_runtime_v1"


class SeccompRuntimeEvidenceError(RuntimeError):
    pass


def read_ghidra_seccomp_proof(path: Path, baseline: int) -> dict:
    if type(baseline) is not int or not 0 <= baseline <= 4096:
        raise SeccompRuntimeEvidenceError("Invalid pre-bwrap seccomp baseline")
    try:
        # The JVM writes the proof under the private host workspace. Pin
        # every ancestor directory and the final inode to reject path
        # redirection before reading any self-reported seccomp counters.
        proof = Path(path)
        if (not proof.is_absolute()
                or proof.name in ("", ".", "..")):
            raise SeccompRuntimeEvidenceError(
                "Absolute JVM runtime proof path required")
        flags = (os.O_RDONLY | os.O_CLOEXEC |
                 os.O_NOFOLLOW | os.O_NONBLOCK)
        with ExitStack() as stack:
            directory_fd = open_absolute_directory_nofollow(
                proof.parent, stack)
            parent = os.fstat(directory_fd)
            if (not stat.S_ISDIR(parent.st_mode)
                    or parent.st_uid != os.geteuid()
                    or parent.st_mode & 0o022):
                raise SeccompRuntimeEvidenceError(
                    "Runtime proof parent is untrusted")
            fd = os.open(proof.name, flags, dir_fd=directory_fd)
            stack.callback(os.close, fd)
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode)
                    or before.st_uid != os.geteuid()
                    or before.st_mode & 0o022
                    or not 1 <= before.st_size <= MAX_PROOF_BYTES):
                raise SeccompRuntimeEvidenceError(
                    "Unsafe runtime proof file")
            raw = os.read(fd, MAX_PROOF_BYTES + 1)
            after = os.fstat(fd)
            if (len(raw) != before.st_size
                    or (after.st_dev, after.st_ino, after.st_size,
                        after.st_mtime_ns, after.st_ctime_ns) !=
                       (before.st_dev, before.st_ino, before.st_size,
                        before.st_mtime_ns, before.st_ctime_ns)):
                raise SeccompRuntimeEvidenceError(
                    "Runtime proof changed during read")
        # Object pairs hook rejects duplicate security-critical fields.
        def unique_pairs(pairs):
            fields = {}
            for key, value in pairs:
                if key in fields:
                    raise SeccompRuntimeEvidenceError("Duplicate runtime proof key")
                fields[key] = value
            return fields

        record = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs)
    except (OSError, UnicodeError, ValueError) as exc:
        raise SeccompRuntimeEvidenceError("Cannot inspect runtime proof") from exc
    if (not isinstance(record, dict)
            or set(record) != {
                "schema", "seccomp_mode", "seccomp_filters",
                "measurement_source", "measured_process"
            } or record["schema"] != SCHEMA
            or record["measurement_source"] != "/proc/self/status"
            or record["measured_process"] != "ghidra_headless_jvm"
            or type(record["seccomp_mode"]) is not int
            or record["seccomp_mode"] != 2
            or type(record["seccomp_filters"]) is not int
            or not baseline < record["seccomp_filters"] <= 4096):
        raise SeccompRuntimeEvidenceError(
            "No verified additional seccomp filter in Ghidra JVM")
    return {
        "verified": True,
        "measurement_source": "/proc/self/status",
        "measured_process": "ghidra_headless_jvm",
        "seccomp_mode": 2,
        "filters_before_bwrap": baseline,
        "filters_in_ghidra": record["seccomp_filters"],
        "additional_filters_observed": record["seccomp_filters"] - baseline,
    }


def baseline_from_scope_receipts(records: list[dict], unit: str) -> int:
    matches = [item for item in records
               if isinstance(item, dict)
               and item.get("scope_seccomp_guard") == "passed"
               and item.get("scope") == unit
               and item.get("filters_compiled_inside_scope") is True]
    if len(matches) != 1:
        raise SeccompRuntimeEvidenceError("Missing or duplicate scope receipt")
    baseline = matches[0].get("seccomp_filters_before_bwrap")
    if type(baseline) is not int or not 0 <= baseline <= 4096:
        raise SeccompRuntimeEvidenceError("Scope did not report seccomp baseline")
    return baseline
