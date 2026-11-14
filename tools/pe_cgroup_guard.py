#!/usr/bin/env python3
"""Fail closed unless the current systemd scope has effective cgroup v2 limits.

Executes before Bubblewrap, while /sys/fs/cgroup is still visible. No shell,
network, privilege escalation, or fallback command is used.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from pe_resource_limits import (CPU_PERIOD_MIN_US, CPU_PERIOD_MAX_US,
                                CPU_QUOTA_MIN_US)


class CgroupVerificationError(RuntimeError):
    pass


def verify_cgroup_limits(memory_budget: int, tasks_budget: int,
                         cpu_percent: int, *, expected_scope: str | None = None,
                         proc_cgroup: Path = Path("/proc/self/cgroup"),
                         mount_root: Path = Path("/sys/fs/cgroup")) -> dict:
    if any(type(x) is not int or x <= 0 for x in
           (memory_budget, tasks_budget, cpu_percent)):
        raise CgroupVerificationError("invalid resource policy")
    try:
        lines = proc_cgroup.read_text(encoding="utf-8").splitlines()
        entries = [line[3:] for line in lines if line.startswith("0::")]
        if len(entries) != 1 or not entries[0].startswith("/"):
            raise CgroupVerificationError("missing unified v2 membership")
        parts = Path(entries[0]).parts
        if not any(part.endswith(".scope") for part in parts):
            raise CgroupVerificationError("not running in systemd scope")
        if expected_scope is not None and (not expected_scope.endswith(".scope")
                or "/" in expected_scope or parts[-1] != expected_scope):
            raise CgroupVerificationError("running outside assigned scope")
        mount = mount_root.resolve(strict=True)
        group = (mount / entries[0].lstrip("/")).resolve(strict=True)
        if group == mount or mount not in group.parents:
            raise CgroupVerificationError("scope outside cgroup mount")

        def finite_int(name: str) -> int:
            value = (group / name).read_text(encoding="ascii").strip()
            if not value.isdecimal():
                raise CgroupVerificationError(name + " is not finite")
            return int(value)

        memory = finite_int("memory.max")
        tasks = finite_int("pids.max")
        cpu = (group / "cpu.max").read_text(encoding="ascii").split()
        if len(cpu) != 2 or any(not x.isdecimal() for x in cpu):
            raise CgroupVerificationError("cpu.max is not finite")
        quota, period = map(int, cpu)
        if (not CPU_PERIOD_MIN_US <= period <= CPU_PERIOD_MAX_US
                or quota < CPU_QUOTA_MIN_US):
            raise CgroupVerificationError(
                "cpu.max period/quota outside Linux CFS bounds")
        if not (0 < memory <= memory_budget
                and 0 < tasks <= tasks_budget
                and quota * 100 <= period * cpu_percent):
            raise CgroupVerificationError("effective resource budgets exceed policy")
    except (OSError, UnicodeError, ValueError) as exc:
        raise CgroupVerificationError("cgroup controls cannot be verified") from exc
    return {"verified": True, "memory_max": memory,
            "pids_max": tasks, "cpu_quota": quota, "cpu_period": period}


def main(argv: list[str]) -> int:
    if len(argv) < 8 or argv[6] != "--" or not argv[7]:
        print("cgroup verifier: invalid arguments", file=sys.stderr)
        return 2
    try:
        proof = verify_cgroup_limits(int(argv[1]), int(argv[2]), int(argv[3]),
                                     expected_scope=argv[4])
        if argv[5] != "-":
            # The parent creates an exclusively owned private directory. This
            # file lies outside Bubblewrap's mounts, preventing the analyzer
            # from altering the quota attestation.
            path = Path(argv[5])
            if not path.is_absolute():
                raise CgroupVerificationError("invalid proof path")
            record = {"schema": "negresco_cgroup_v2_proof_v1",
                      "scope": argv[4], **proof}
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            with os.fdopen(os.open(path, flags, 0o600), "w",
                           encoding="utf-8") as result:
                json.dump(record, result, sort_keys=True)
                result.flush()
                os.fsync(result.fileno())
    except (CgroupVerificationError, ValueError, OSError) as exc:
        print("cgroup verifier: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"cgroup_verification": "passed", **proof},
                     sort_keys=True), flush=True)
    try:
        os.execvpe(argv[7], argv[7:], os.environ)
    except OSError as exc:
        print("cgroup verifier: command unavailable: " + str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
