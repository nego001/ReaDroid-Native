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
import stat
import subprocess
import sys
import tempfile
import time

from pe_arch_cgroup_smoke import preflight
from pe_arch_vm_gate import verify_arch_vm
from pe_scope_cleanup_evidence import stop_and_attest_scope, ScopeCleanupUnavailable
from pe_resource_evidence import (read_scope_proof, corroborate_guard_receipt,
                                  InvalidResourceEvidence)
from pe_resource_limits import (new_scope_unit, stop_scope,
                                wrap_in_cgroup_scope)


class DescendantProbeError(RuntimeError):
    pass


MAX_GUARD_STDOUT_BYTES = 32 * 1024
MAX_GUARD_STDERR_BYTES = 8 * 1024
# PE-S1.90: markers are data supplied by another process, not trusted
# Python objects. Reject oversized files before decoding/JSON allocation.
MAX_CHILD_MARKER_BYTES = 512
MAX_READY_MARKER_BYTES = 64
# Kernel pseudo-file, not an ordinary disk log. Cap reads and reject truncation.
MAX_PROC_LIMITS_BYTES = 8 * 1024
# Linux RLIMIT_FSIZE is per-file, not a whole-disk quota. Set the HARD
# limit too: unprivileged children cannot raise it. Each inherited output
# file is capped at 32 KiB at write-time, including stderr (whose stricter
# *acceptance* limit remains 8 KiB). A native host still needs disk quotas.
MAX_NATIVE_WRITE_FILE_BYTES = MAX_GUARD_STDOUT_BYTES
# Arch's official util-linux installs prlimit here. Never resolve an
# attacker-controlled PATH or a /bin symlink from a minimal container.
PRLIMIT_EXECUTABLE = Path("/usr/bin/prlimit")


def _native_prlimit_prefix() -> list[str]:
    """Pin a trusted util-linux prlimit before spawning any scope.

    A hard per-file RLIMIT_FSIZE is inherited along the ordinary
    systemd-run --scope fork/exec path. No shell; missing or untrusted
    prlimit must refuse native testing instead of silently falling back.
    """
    if sys.platform != "linux":
        raise DescendantProbeError("Native file-size cap requires Linux")
    path = PRLIMIT_EXECUTABLE
    try:
        metadata = path.lstat()
        if (not path.is_absolute() or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != 0 or metadata.st_mode & 0o022
                or not os.access(path, os.X_OK)):
            raise DescendantProbeError("Untrusted prlimit executable")
        # Root ownership of the file alone is insufficient when a
        # non-root user can replace an entry in a writable directory.
        for parent in path.parents:
            meta = parent.lstat()
            if (not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0
                    or meta.st_mode & 0o022):
                raise DescendantProbeError("Untrusted prlimit directory")
    except FileNotFoundError as exc:
        raise DescendantProbeError(
            "Trusted /usr/bin/prlimit is required for native test") from exc
    except OSError as exc:
        raise DescendantProbeError("Cannot verify prlimit executable") from exc
    bound = str(MAX_NATIVE_WRITE_FILE_BYTES)
    return [str(path), "--fsize=" + bound + ":" + bound, "--"]


def _require_inherited_file_limit() -> None:
    """Verify the actual kernel limit in the scoped worker/grandchild.

    A prlimit wrapper is only a request: if systemd launches the worker
    from a process that resets limits, no live scope is accepted.
    """
    try:
        import resource
        actual = resource.getrlimit(resource.RLIMIT_FSIZE)
    except (ImportError, AttributeError, OSError, ValueError) as exc:
        raise DescendantProbeError(
            "Cannot inspect scoped RLIMIT_FSIZE") from exc
    expected = (MAX_NATIVE_WRITE_FILE_BYTES, MAX_NATIVE_WRITE_FILE_BYTES)
    if actual != expected:
        raise DescendantProbeError(
            "Scoped worker did not inherit hard file-size limit")


def _read_bounded_scope_log(path: Path, limit: int) -> bytes:
    """Read only a bounded, regular, owner-controlled smoke output file.

    A regular-file read_bytes() allocates the entire file before the
    caller can reject an oversized guard log. Use O_NOFOLLOW and cap the
    *actual* read; a synthetic worker could also replace a path with a
    symlink or FIFO while the launcher is running.
    """
    if (type(limit) is not int
            or not 0 < limit <= MAX_GUARD_STDOUT_BYTES
            or not hasattr(os, "O_NOFOLLOW")):
        raise DescendantProbeError("Bounded scope log reader unavailable")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(path, flags)
        try:
            metadata = os.fstat(fd)
            if (not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_uid != os.geteuid()
                    or metadata.st_nlink != 1):
                raise DescendantProbeError("Scope log is not a private regular file")
            if metadata.st_size > limit:
                raise DescendantProbeError("Scope log exceeded read budget")
            data = os.read(fd, limit + 1)
            if len(data) > limit or os.fstat(fd).st_size > limit:
                raise DescendantProbeError("Scope log exceeded read budget")
            return data
        finally:
            os.close(fd)
    except OSError as exc:
        raise DescendantProbeError("Scope log unavailable or unsafe") from exc


def _write_new_private_marker(path: Path, payload: bytes, limit: int) -> None:
    """Create a bounded, private one-shot marker without following links.

    The worker and grandchild share an owner-only temporary directory. Never
    truncate an existing target: O_EXCL stops pre-planted regular files and
    symlinks before the first byte is written. A separate pending marker is
    published using rename, which does not follow the destination symlink.
    """
    if (type(payload) is not bytes or type(limit) is not int
            or not 0 < len(payload) <= limit <= MAX_CHILD_MARKER_BYTES
            or not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_CLOEXEC")):
        raise DescendantProbeError("Private marker write budget unavailable")
    try:
        directory = path.parent.lstat()
        if (not stat.S_ISDIR(directory.st_mode)
                or directory.st_uid != os.geteuid()
                or directory.st_mode & 0o077):
            raise DescendantProbeError("Untrusted private marker directory")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        with os.fdopen(fd, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
    except OSError as exc:
        raise DescendantProbeError(
            "Cannot exclusively create private marker") from exc


def _publish_ready_marker(ready: Path) -> None:
    """Publish complete readiness as one directory-entry change.

    A grandchild must never expose the final 'ready' pathname while its
    contents are being written. The worker may observe the final marker at
    any instant; only a complete, fsynced one should be visible. This is
    NOT protection against another hostile process with the same UID.
    """
    pending = ready.with_name(ready.name + ".pending")
    _write_new_private_marker(
        pending, b"sigterm_ignored", MAX_READY_MARKER_BYTES)
    # Refuse pre-planted destinations, including dangling symlinks. The
    # directory belongs to our own temporary VM experiment; do not pretend
    # this precheck makes os.replace race-free against a hostile same-UID
    # process. Replacement is atomic and never follows the destination link.
    try:
        ready.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise DescendantProbeError("Cannot inspect readiness destination") from exc
    else:
        raise DescendantProbeError("Readiness marker already exists")
    try:
        os.replace(pending, ready)
    except OSError as exc:
        raise DescendantProbeError("Cannot atomically publish readiness") from exc


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate JSON keys, including nested keys, before trusting a marker."""
    result = {}
    for name, value in pairs:
        if name in result:
            raise DescendantProbeError("Duplicate child marker JSON key")
        result[name] = value
    return result


def _read_child_marker(path: Path) -> dict:
    """Read and validate the exact worker-to-supervisor marker schema.

    Treat this as untrusted interprocess evidence even though both ends are
    in an owner-only disposable VM temporary directory.
    """
    raw = _read_bounded_scope_log(path, MAX_CHILD_MARKER_BYTES)
    try:
        marker = json.loads(raw.decode("utf-8"),
                            object_pairs_hook=_unique_json_object,
                            parse_constant=lambda _: (_ for _ in ()).throw(
                                ValueError("Non-finite marker number")))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise DescendantProbeError("Invalid child marker JSON") from exc
    if (not isinstance(marker, dict)
            or set(marker) != {"pid", "starttime", "unit"}
            or type(marker["pid"]) is not int or marker["pid"] < 2
            or not isinstance(marker["starttime"], str)
            or not 1 <= len(marker["starttime"]) <= 32
            or not marker["starttime"].isascii()
            or not marker["starttime"].isdecimal()
            or not isinstance(marker["unit"], str)
            or not 1 <= len(marker["unit"]) <= 128
            or not marker["unit"].isascii()):
        raise DescendantProbeError("Invalid child marker schema")
    return marker


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


def _require_pidfd_cleanup() -> None:
    """Do not spawn a detached descendant without race-free Linux cleanup."""
    if (sys.platform != "linux"
            or not callable(getattr(os, "pidfd_open", None))
            or not callable(getattr(signal, "pidfd_send_signal", None))):
        raise DescendantProbeError(
            "Native descendant test requires Linux pidfd cleanup support")


def _pin_descendant_pidfd(pid: int, starttime: str, unit: str) -> int:
    """Pin the specific live scope descendant before attempting scope stop.

    A /proc identity read followed by a numeric os.kill has a PID-reuse
    race. Open a pidfd, then recheck starttime AND cgroup membership
    while the pidfd holds that task's kernel identity. Only the pinned
    descriptor may be used for emergency SIGKILL.
    """
    _require_pidfd_cleanup()
    if not active_identity(pid, starttime) or not belongs_to_scope(pid, unit):
        raise DescendantProbeError("Descendant identity changed before pidfd pin")
    try:
        fd = os.pidfd_open(pid, 0)
    except (OSError, ValueError) as exc:
        raise DescendantProbeError("Cannot pin descendant kernel PID identity") from exc
    try:
        if not active_identity(pid, starttime) or not belongs_to_scope(pid, unit):
            raise DescendantProbeError(
                "Descendant identity or scope changed during pidfd pin")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _require_proc_fsize_record(raw: bytes) -> None:
    """Require one exact kernel /proc/PID/limits Max file size record.

    This checks the actual kernel view, not the worker's self-reported
    marker. The test's 32 KiB per-file policy is not a total disk quota.
    """
    if (type(raw) is not bytes or not 0 < len(raw) <= MAX_PROC_LIMITS_BYTES
            or b"\\x00" in raw):
        raise DescendantProbeError("Invalid bounded kernel process limits")
    try:
        rows = [line.split() for line in raw.decode("ascii").splitlines()]
    except UnicodeError as exc:
        raise DescendantProbeError("Non-ASCII kernel process limits") from exc
    file_rows = [parts for parts in rows
                 if len(parts) >= 3 and parts[:3] == ["Max", "file", "size"]]
    target = str(MAX_NATIVE_WRITE_FILE_BYTES)
    if (len(file_rows) != 1 or file_rows[0] !=
            ["Max", "file", "size", target, target, "bytes"]):
        raise DescendantProbeError(
            "Pinned descendant effective file-size limit not verified")


def _require_pinned_descendant_file_limit(
        pid: int, starttime: str, unit: str) -> None:
    """Externally corroborate a PIDFD-pinned descendant's RLIMIT_FSIZE.

    Call only AFTER _pin_descendant_pidfd succeeds and BEFORE stopping the
    scope. Recheck process identity and membership on both sides of the
    kernel read. A local test with mocked membership is not a native
    systemd scope acceptance.
    """
    if not active_identity(pid, starttime) or not belongs_to_scope(pid, unit):
        raise DescendantProbeError(
            "Pinned descendant identity changed before kernel limit read")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK | os.O_NOFOLLOW
    try:
        fd = os.open(Path("/proc") / str(pid) / "limits", flags)
        try:
            meta = os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid():
                raise DescendantProbeError(
                    "Pinned descendant process limits are not owner-controlled")
            raw = os.read(fd, MAX_PROC_LIMITS_BYTES + 1)
        finally:
            os.close(fd)
    except OSError as exc:
        raise DescendantProbeError(
            "Cannot inspect pinned descendant kernel process limits") from exc
    if not active_identity(pid, starttime) or not belongs_to_scope(pid, unit):
        raise DescendantProbeError(
            "Pinned descendant identity changed during kernel limit read")
    _require_proc_fsize_record(raw)


def wait_until_dead(pid: int, starttime: str, seconds: float) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not active_identity(pid, starttime):
            return True
        time.sleep(0.15)
    return not active_identity(pid, starttime)


def _grandchild(unit: str, ready: Path) -> int:
    if not belongs_to_scope(os.getpid(), unit):
        raise DescendantProbeError("grandchild is outside assigned scope")
    _require_inherited_file_limit()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    _publish_ready_marker(ready)
    while True:
        time.sleep(0.25)


def _worker(marker: Path, unit: str) -> int:
    if not belongs_to_scope(os.getpid(), unit):
        raise DescendantProbeError("worker is outside assigned scope")
    _require_inherited_file_limit()
    ready = marker.with_suffix(".ready")
    child = subprocess.Popen(
        [sys.executable, "-I", str(Path(__file__).resolve()),
         "--grandchild", unit, str(ready)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)
    deadline = time.monotonic() + 5
    while not ready.is_file() and time.monotonic() < deadline:
        if child.poll() is not None:
            raise DescendantProbeError("detached grandchild exited before ready")
        time.sleep(0.05)
    if (not ready.is_file()
            or _read_bounded_scope_log(ready, MAX_READY_MARKER_BYTES)
               != b"sigterm_ignored"):
        raise DescendantProbeError("SIGTERM-resistant child was not ready")
    identity = proc_identity(child.pid)
    if not identity or not belongs_to_scope(child.pid, unit):
        raise DescendantProbeError("grandchild did not enter assigned scope")
    record = {"pid": child.pid, "starttime": identity[1], "unit": unit}
    tmp = marker.with_suffix(".pending")
    _write_new_private_marker(
        tmp, json.dumps(record, separators=(",", ":")).encode("ascii"),
        MAX_CHILD_MARKER_BYTES)
    os.replace(tmp, marker)
    while True:
        time.sleep(0.25)


def run_native_descendant_smoke() -> dict:
    # This test spawns a detached, SIGTERM-resistant grandchild. It must
    # NEVER be directly callable on a personal Arch workstation.
    environment = verify_arch_vm()
    if (environment.get("status") != "ARCH_VM_PREFLIGHT_PASSED"
            or environment.get("vm_confirmed") is not True
            or environment.get("container") is not False):
        raise DescendantProbeError("Disposable native Arch VM not verified")
    # Require a safe kill primitive before ANY detached process is spawned.
    # An unsupported kernel/Python must fail without creating a scope.
    _require_pidfd_cleanup()
    # Preflight before creating a scope or starting a detached process.
    # The returned prefix is applied to the actual systemd-run invocation.
    limiter_prefix = _native_prlimit_prefix()
    unit = new_scope_unit()
    child_pid = None
    child_pidfd = None
    child_starttime = None
    launcher = None
    stopped = False
    proof = False
    quota_private_proof = None
    cleanup_evidence = None

    with tempfile.TemporaryDirectory(prefix="negresco-arch-descendant-") as temp:
        marker = Path(temp) / "child.json"
        out_path = Path(temp) / "scope.stdout"
        err_path = Path(temp) / "scope.stderr"
        proof_dir = Path(temp) / "private-quota-proof"
        proof_dir.mkdir(mode=0o700)
        proof_path = proof_dir / "quota.json"
        command = [
            sys.executable, "-I", str(Path(__file__).resolve()),
            "--worker", str(marker), unit]
        argv = wrap_in_cgroup_scope(command, timeout_seconds=30,
                                    unit_name=unit, proof_path=proof_path)
        # Reuse the trusted executable and exact hard/soft limits checked
        # before starting the scope. Do not resolve a different PATH entry.
        argv = [*limiter_prefix, *argv]
        try:
            with out_path.open("wb") as stdout, err_path.open("wb") as stderr:
                launcher = subprocess.Popen(
                    argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                    close_fds=True, start_new_session=True)
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    if marker.is_file():
                        record = _read_child_marker(marker)
                        child_pid = record["pid"]
                        child_starttime = record["starttime"]
                        if (type(child_pid) is not int or child_pid < 2
                                or not isinstance(child_starttime, str)
                                or record["unit"] != unit
                                or not active_identity(child_pid, child_starttime)
                                or not belongs_to_scope(child_pid, unit)):
                            raise DescendantProbeError(
                                "live detached child not confirmed inside scope")
                        # Pin the exact live task before stopping the
                        # scope. The pidfd prevents a later numeric PID
                        # reuse from redirecting emergency cleanup.
                        child_pidfd = _pin_descendant_pidfd(
                            child_pid, child_starttime, unit)
                        # Independent kernel witness after pidfd pinning:
                        # do not accept readiness alone as proof of RLIMIT_FSIZE.
                        _require_pinned_descendant_file_limit(
                            child_pid, child_starttime, unit)
                        break
                    if launcher.poll() is not None:
                        raise DescendantProbeError("systemd scope terminated early")
                    time.sleep(0.15)
                else:
                    raise DescendantProbeError("child startup marker not produced")
                # Both captured files must be safe before interpreting a
                # PASS receipt. Limit the bytes during read, not after.
                output = _read_bounded_scope_log(
                    out_path, MAX_GUARD_STDOUT_BYTES)
                diagnostic = _read_bounded_scope_log(
                    err_path, MAX_GUARD_STDERR_BYTES)
                if diagnostic:
                    raise DescendantProbeError(
                        "Cgroup guard emitted unexpected stderr")
                try:
                    receipts = [json.loads(line) for line in output.decode(
                        "utf-8").splitlines() if line.lstrip().startswith("{")]
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise DescendantProbeError("Malformed cgroup guard receipt") from exc
                matching = [
                    record for record in receipts
                    if isinstance(record, dict)
                    and record.get("cgroup_verification") == "passed"
                    and record.get("verified") is True]
                if len(matching) != 1:
                    raise DescendantProbeError("Missing or duplicate cgroup guard attestation")
                try:
                    quota_private_proof = read_scope_proof(proof_path, unit)
                except InvalidResourceEvidence as exc:
                    raise DescendantProbeError("Private effective cgroup proof missing") from exc
                try:
                    quota_corroboration = corroborate_guard_receipt(
                        receipts, quota_private_proof)
                except InvalidResourceEvidence as exc:
                    raise DescendantProbeError(
                        "Guard receipt and private quotas do not match") from exc
                if quota_corroboration.get("corroborated") is not True:
                    raise DescendantProbeError("Kernel quota corroboration not proven")
                proof = True
                stopped = stop_scope(unit)
                if not stopped:
                    raise DescendantProbeError("systemctl could not stop scope")
                if not wait_until_dead(child_pid, child_starttime, 9):
                    raise DescendantProbeError("detached child survived scope stop")
                # A vanished PID alone does not prove the whole scope empty.
                # Demand the final systemd state and kernel cgroup.events.
                cleanup_evidence = stop_and_attest_scope(unit)
                if (cleanup_evidence.get("scope") != unit
                        or cleanup_evidence.get("verified") is not True
                        or cleanup_evidence.get("scope_quiescent") is not True
                        or cleanup_evidence.get("cgroup_unpopulated") is not True):
                    raise DescendantProbeError(
                        "Descendant cgroup remained populated or unverified")
        finally:
            # Cleanup fallback is NOT evidence of correct scope termination.
            # Pinning a pidfd before stop prevents SIGKILL from reaching an
            # unrelated task if the old numeric PID was recycled.
            try:
                stop_scope(unit)
            finally:
                try:
                    if child_pidfd is not None:
                        try:
                            signal.pidfd_send_signal(
                                child_pidfd, signal.SIGKILL, None, 0)
                        except ProcessLookupError:
                            # The kernel-pinned original process is gone.
                            pass
                finally:
                    try:
                        if child_pidfd is not None:
                            os.close(child_pidfd)
                    finally:
                        if launcher is not None:
                            try:
                                launcher.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                launcher.kill()
                                launcher.wait(timeout=3)
        return {"status": "PASS_NATIVE_ARCH_DESCENDANTS",
                "scope": unit, "quota_verified": proof,
                "systemd_stop_succeeded": stopped,
                "quota_private_proof": quota_private_proof,
                "descendant_cleanup_evidence": cleanup_evidence,
                "detached_sigterm_ignoring_child_terminated": True,
                "windows_binary_executed": False,
                "ghidra_executed": False}


def main(argv: list[str]) -> int:
    try:
        # Direct CLI calls to the worker/grandchild must pass the same VM gate.
        # They intentionally keep an unbounded loop until systemd terminates
        # the disposable scope, so never enable these on a workstation.
        if len(argv) == 4 and argv[1] in ("--grandchild", "--worker"):
            environment = verify_arch_vm()
            if (environment.get("status") != "ARCH_VM_PREFLIGHT_PASSED"
                    or environment.get("vm_confirmed") is not True
                    or environment.get("container") is not False):
                raise DescendantProbeError("Worker requires disposable native Arch VM")
            if argv[1] == "--grandchild":
                return _grandchild(argv[2], Path(argv[3]))
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
