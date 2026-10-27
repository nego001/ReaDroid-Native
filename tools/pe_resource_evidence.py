"""Validate a cgroup proof written by the pre-Bubblewrap guard.

The proof directory is private to the Python parent and NOT mounted in /work.
This prevents the Ghidra parser from replacing the guard's evidence.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

from pe_resource_limits import MEMORY_MAX_BYTES, TASKS_MAX, CPU_QUOTA_PERCENT


class InvalidResourceEvidence(RuntimeError):
    pass


def read_scope_proof(path: Path, unit: str) -> dict:
    try:
        if path.is_symlink():
            raise InvalidResourceEvidence("Prova de cgroup não pode ser symlink")
        meta = path.stat()
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_mode & 0o077 or not 1 <= meta.st_size <= 4096):
            raise InvalidResourceEvidence("Prova de cgroup sem permissões ou tamanho seguro")
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise InvalidResourceEvidence("Prova de cgroup não é objeto")
        if (record.get("schema") != "negresco_cgroup_v2_proof_v1"
                or record.get("scope") != unit
                or record.get("verified") is not True):
            raise InvalidResourceEvidence("Prova de cgroup não corresponde ao escopo")
        keys = ("memory_max", "pids_max", "cpu_quota", "cpu_period")
        if any(type(record.get(key)) is not int for key in keys):
            raise InvalidResourceEvidence("Valores não inteiros na prova de cgroup")
        memory, tasks, cpu, period = (record[key] for key in keys)
        if (not 0 < memory <= MEMORY_MAX_BYTES
                or not 0 < tasks <= TASKS_MAX
                or not 0 < cpu and 0 < period
                or cpu * 100 > period * CPU_QUOTA_PERCENT):
            raise InvalidResourceEvidence("Limites efetivos de cgroup fora da política")
        return {
            "verification": "guard_verified_before_bwrap",
            "memory_max_bytes": memory,
            "tasks_max": tasks,
            "cpu_quota": cpu,
            "cpu_period": period,
        }
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidResourceEvidence("Prova de cgroup indisponível ou inválida") from exc
