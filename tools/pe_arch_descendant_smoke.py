#!/usr/bin/env python3
"""Native Arch-only scope descendant test using a synthetic Python process.

The worker deliberately ignores SIGTERM and detaches its session, but remains
in the scope's cgroup. A passing test proves systemd stopped that descendant
under the tested host conditions. Never runs any Windows binary or Ghidra.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from pe_arch_cgroup_smoke import preflight
from pe_resource_limits import (new_scope_unit, stop_scope,
                                wrap_in_cgroup_scope)


class DescendantProbeError(RuntimeError):
    pass


def proc_identity(pid: int) -> tuple[str, str] | None:
    """Return state + procfs starttime, guarding against recycled PIDs."""
    if type(pid) is not int or pid < 2:
        return None
    try:
        stat = Path("/proc") / str(pid) / "stat"
        fields = stat.read_text(encoding="ascii").rsplit(") ", 1)[1].split()
        if len(fields) < 20 or not fields[19].isdecimal():
            return None
        return fields[0], fields[19]
    except (OSError, UnicodeError, IndexError):
        return None


def active_identity(pid: int, starttime: str) -> bool:
    current = proc_identity(pid)
    return (current is not None and current[1] == starttime
            and current[0] not in ("Z", "X", "x"))


def belongs_to_scope(pid: int, unit: str) -> bool:
    try:
        lines = (Path("/proc") / str(pid) / "cgroup").read_text().splitlines()
        groups = [line[3:] for line in lines if line.startswith("0::")]
        return len(groups) == 1 and groups[0].endswith("/" + unit)
    except (OSError, UnicodeError):
        return False


def wait_until_dead(pid: int, starttime: str, seconds: float) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not active_identity(pid, starttime):
            return True
        time.sleep(0.15)
    return not active_identity(pid, starttime)


def _grandchild(unit: str) -> int:
    if not belongs_to_scope(os.getpid(), unit):
        raise DescendantProbeError("grandchild is outside assigned scope")
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        time.sleep(0.25)


def _worker(marker: Path, unit: str) -> int:
    if not belongs_to_scope(os.getpid(), unit):
        raise DescendantProbeError("worker is outside assigned scope")
    child = subprocess.Popen(
        [sys.executable, "-I", str(Path(__file__).resolve()),
         "--grandchild", unit],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)
    identity = proc_identity(child.pid)
    if not identity or not belongs_to_scope(child.pid, unit):
        raise DescendantProbeError("grandchild did not enter assigned scope")
    record = {"pid": child.pid, "starttime": identity[1], "unit": unit}
    tmp = marker.with_suffix(".pending")
    tmp.write_text(json.dumps(record), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, marker)
    while True:
        time.sleep(0.25)


def run_native_descendant_smoke() -> dict:
    preflight()
    unit = new_scope_unit()
    child_pid = None
    child_starttime = None
    launcher = None
    stopped = False
    proof = False

    with tempfile.TemporaryDirectory(prefix="negresco-arch-descendant-") as temp:
        marker = Path(temp) / "child.json"
        out_path = Path(temp) / "scope.stdout"
        err_path = Path(temp) / "scope.stderr"
        command = [
            sys.executable, "-I", str(Path(__file__).resolve()),
            "--worker", str(marker), unit]
        argv = wrap_in_cgroup_scope(command, timeout_seconds=30, unit_name=unit)
        try:
            with out_path.open("wb") as stdout, err_path.open("wb") as stderr:
                launcher = subprocess.Popen(
                    argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                    close_fds=True, start_new_session=True)
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    if marker.is_file():
                        record = json.loads(marker.read_text(encoding="utf-8"))
                        child_pid = record["pid"]
                        child_starttime = record["starttime"]
                        if (type(child_pid) is not int or child_pid < 2
                                or not isinstance(child_starttime, str)
                                or record["unit"] != unit
                                or not active_identity(child_pid, child_starttime)
                                or not belongs_to_scope(child_pid, unit)):
                            raise DescendantProbeError(
                                "live detached child not confirmed inside scope")
                        break
                    if launcher.poll() is not None:
                        raise DescendantProbeError("systemd scope terminated early")
                    time.sleep(0.15)
                else:
                    raise DescendantProbeError("child startup marker not produced")
                output = out_path.read_text(encoding="utf-8", errors="replace")
                proof = '"cgroup_verification": "passed"' in output
                if not proof:
                    raise DescendantProbeError("quota verifier did not pass")
                stopped = stop_scope(unit)
                if not stopped:
                    raise DescendantProbeError("systemctl could not stop scope")
                if not wait_until_dead(child_pid, child_starttime, 9):
                    raise DescendantProbeError("detached child survived scope stop")
        finally:
            stop_scope(unit)
            if launcher is not None:
                try:
                    launcher.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    launcher.kill()
                    launcher.wait(timeout=3)
            # Cleanup fallback is NOT evidence of correct scope termination.
            if (child_pid is not None and child_starttime is not None
                    and active_identity(child_pid, child_starttime)):
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        return {"status": "PASS_NATIVE_ARCH_DESCENDANTS",
                "scope": unit, "quota_verified": proof,
                "systemd_stop_succeeded": stopped,
                "detached_sigterm_ignoring_child_terminated": True,
                "windows_binary_executed": False,
                "ghidra_executed": False}


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 3 and argv[1] == "--grandchild":
            return _grandchild(argv[2])
        if len(argv) == 4 and argv[1] == "--worker":
            return _worker(Path(argv[2]), argv[3])
        if len(argv) == 1:
            print(json.dumps(run_native_descendant_smoke(), sort_keys=True))
            return 0
        raise DescendantProbeError("unsupported command")
    except (DescendantProbeError, RuntimeError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "REJECTED_NOT_HOMOLOGATED",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
