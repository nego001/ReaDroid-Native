#!/usr/bin/env python3
"""PE-S1.52: safely collect bounded, UNSIGNED native Arch VM observations.

Fail closed before touching output if an externally pinned Git checkout or
strict native Arch VM preflight is absent. No PE/Windows executable, Ghidra,
cgroup scope, host security setting, network call or credential collection.
Logs do not authenticate a kernel, VM, hypervisor or reviewer identity.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_evidence as evidence
from pe_arch_vm_checkout_pin import (
    CheckoutPinError, COMMIT_SHA, verify_source_checkout_pin,
)
from pe_arch_vm_gate import ArchVmUnavailable, verify_arch_vm
from pe_nofollow_paths import open_absolute_directory_nofollow

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
FILENAMES = {
    "guest_kernel_observation": "guest-kernel-observation.txt",
    "guest_cgroup_observation": "guest-cgroup-observation.txt",
}
STATUS = "OPERATOR_SELF_REPORTED_NATIVE_ARCH_OBSERVATION_NOT_ATTESTED"
MAX_FILE_BYTES = 16384
MAX_CMD_BYTES = 4096


class ObservationError(RuntimeError):
    """Observation request is unsafe or native evidence incomplete."""


def _command(name: str, *args: str) -> str:
    """Execute only preselected harmless, bounded metadata commands."""
    if (name, args) not in (
        ("systemd-detect-virt", ("--vm",)),
        ("systemd", ("--version",)),
        ("systemctl", ("--user", "--no-ask-password", "show",
                       "--property=ControlGroup", "--value")),
    ):
        raise ObservationError("Unapproved observation command")
    binary = shutil.which(name)
    if not binary or not os.path.isabs(binary):
        raise ObservationError("Required observer command missing: " + name)
    try:
        proc = subprocess.run(
            [binary, *args], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=8, check=False, close_fds=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ObservationError("Observer command unavailable: " + name) from exc
    if proc.returncode != 0 or len(proc.stdout) > MAX_CMD_BYTES:
        raise ObservationError("Observer command rejected: " + name)
    try:
        data = proc.stdout.decode("utf-8").strip()
    except UnicodeError as exc:
        raise ObservationError("Non-UTF8 observer command: " + name) from exc
    if not data or "\x00" in data:
        raise ObservationError("Empty or invalid observer command: " + name)
    return data


def _read_bounded(path: Path, *, limit: int) -> str:
    """Read fixed kernel metadata only; never read arbitrary user files."""
    if path not in (
        Path("/proc/1/comm"), Path("/sys/fs/cgroup/cgroup.controllers"),
        Path("/sys/fs/cgroup/cgroup.subtree_control"),
    ):
        raise ObservationError("Unapproved observation file")
    try:
        with path.open("rb") as f:
            raw = f.read(limit + 1)
    except OSError as exc:
        raise ObservationError("Required kernel metadata unavailable") from exc
    # Empty cgroup.subtree_control is a legitimate observation on a
    # cgroup-v2 root. The controllers *available* file is still required.
    if len(raw) > limit or (not raw and
            path != Path("/sys/fs/cgroup/cgroup.subtree_control")):
        raise ObservationError("Kernel metadata missing or too large")
    try:
        value = raw.decode("ascii").strip()
    except UnicodeError as exc:
        raise ObservationError("Non-ASCII kernel metadata") from exc
    if (not value and path != Path("/sys/fs/cgroup/cgroup.subtree_control")) or "\x00" in value:
        raise ObservationError("Malformed kernel metadata")
    return value


def collect_observations(*, source_commit: str,
                         reviewer_challenge: str,
                         source_root: Path) -> tuple[bytes, bytes]:
    """Read guest metadata after gate; return two self-reported JSON texts."""
    if not isinstance(source_commit, str) or not COMMIT_SHA.fullmatch(source_commit):
        raise ObservationError("Full external Git commit pin required")
    if (not isinstance(reviewer_challenge, str)
            or not SHA256.fullmatch(reviewer_challenge)
            or reviewer_challenge == "0" * 64):
        raise ObservationError("External 256-bit challenge required")

    first = verify_source_checkout_pin(
        source_root, source_commit, evidence.SOURCE_FILES)
    gate = verify_arch_vm()
    if (gate.get("status") != "ARCH_VM_PREFLIGHT_PASSED"
            or gate.get("vm_confirmed") is not True
            or gate.get("container") is not False
            or gate.get("root") is not False):
        raise ObservationError("Native Arch VM preflight refused observation")
    pid1 = _read_bounded(Path("/proc/1/comm"), limit=128)
    if pid1 != "systemd":
        raise ObservationError("PID 1 was not systemd")
    controllers = _read_bounded(
        Path("/sys/fs/cgroup/cgroup.controllers"), limit=1024)
    if not {"cpu", "memory", "pids"}.issubset(set(controllers.split())):
        raise ObservationError("Native cgroup v2 controllers unavailable")
    subtree = _read_bounded(
        Path("/sys/fs/cgroup/cgroup.subtree_control"), limit=1024)
    vm = _command("systemd-detect-virt", "--vm").splitlines()
    systemd = _command("systemd", "--version").splitlines()
    user_group = _command(
        "systemctl", "--user", "--no-ask-password", "show",
        "--property=ControlGroup", "--value")
    if (len(vm) != 1 or len(vm[0]) > 80 or
            len(systemd[0]) > 120 or len(user_group) > 1024
            or not user_group.startswith("/")):
        raise ObservationError("Unexpected guest system metadata format")
    # A second local Git observation catches persistent post-read mutation.
    last = verify_source_checkout_pin(
        source_root, source_commit, evidence.SOURCE_FILES)
    if first != last:
        raise ObservationError("Source changed while observing the guest")
    time_claim = datetime.now(timezone.utc).isoformat()
    common = {
        "classification": STATUS,
        "source_commit": source_commit,
        "reviewer_challenge": reviewer_challenge,
        "operator_observed_at_utc_not_attested": time_claim,
        "native_arch_vm_gate_local_pass": True,
        "independent_vm_attestation": False,
        "native_kernel_execution_independently_verified": False,
        "real_cgroup_limits_or_cleanup_tested_by_this_command": False,
        "windows_binary_executed": False,
    }
    kernel = {
        **common,
        "artifact": "guest_kernel_observation",
        "kernel_release": os.uname().release,
        "kernel_machine": os.uname().machine,
        "pid1_comm": pid1,
        "systemd_version_first_line": systemd[0],
        "virtualization_reported_by_local_systemd": vm[0],
    }
    cgroup = {
        **common,
        "artifact": "guest_cgroup_observation",
        "cgroup_v2_controllers_available": sorted(controllers.split()),
        "cgroup_v2_root_subtree_control": sorted(subtree.split()),
        "systemd_user_control_group_locally_observed": user_group,
        "cgroup_quotas_verified_by_this_command": False,
        "cgroup_descendant_cleanup_verified_by_this_command": False,
    }
    def pack(record: dict) -> bytes:
        payload = (json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ) + "\n").encode("ascii")
        if len(payload) > MAX_FILE_BYTES:
            raise ObservationError("Native guest observation is oversized")
        return payload
    return pack(kernel), pack(cgroup)


def publish_no_overwrite(destination: Path,
                         kernel: bytes, cgroup: bytes) -> dict:
    """Create BOTH owner-only evidence files or roll back our own inodes."""
    for blob in (kernel, cgroup):
        if not isinstance(blob, bytes) or not blob or len(blob) > MAX_FILE_BYTES:
            raise ObservationError("Bounded evidence bytes required")
    root = Path(destination)
    with ExitStack() as stack:
        try:
            directory = open_absolute_directory_nofollow(root, stack)
            meta = os.fstat(directory)
            if (not stat.S_ISDIR(meta.st_mode)
                    or meta.st_uid != os.geteuid()
                    or meta.st_mode & 0o077):
                raise ObservationError("Evidence directory must be owner-only 0700")
            created: list[tuple[str, int, int]] = []
            try:
                for name, payload in zip(FILENAMES.values(), (kernel, cgroup)):
                    fd = os.open(
                        name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                        os.O_CLOEXEC | os.O_NOFOLLOW, 0o600,
                        dir_fd=directory)
                    info = os.fstat(fd)
                    created.append((name, info.st_dev, info.st_ino))
                    with os.fdopen(fd, "wb") as output:
                        output.write(payload)
                        output.flush()
                        os.fsync(output.fileno())
                os.fsync(directory)
            except BaseException:
                # Only remove our own files if still the same inode; never
                # delete a concurrent path replacement or a prior receipt.
                for name, device, inode in reversed(created):
                    try:
                        current = os.stat(
                            name, dir_fd=directory, follow_symlinks=False)
                        if (stat.S_ISREG(current.st_mode)
                                and (current.st_dev, current.st_ino)
                                   == (device, inode)):
                            os.unlink(name, dir_fd=directory)
                    except FileNotFoundError:
                        pass
                try:
                    os.fsync(directory)
                except OSError:
                    pass
                raise
        except (OSError, ValueError) as exc:
            raise ObservationError(
                "Cannot safely publish private native observation") from exc
    return {
        "status": "LOCAL_PRIVATE_OBSERVATIONS_PUBLISHED_NOT_ATTESTED",
        "operator_self_report_only": True,
        "guest_kernel_observation_sha256": hashlib.sha256(kernel).hexdigest(),
        "guest_cgroup_observation_sha256": hashlib.sha256(cgroup).hexdigest(),
        "native_kernel_execution_independently_verified": False,
        "independent_vm_attestation": False,
        "windows_binary_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local Arch VM kernel/cgroup metadata self-report only")
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--reviewer-challenge", required=True)
    args = parser.parse_args(argv)
    try:
        obs = collect_observations(
            source_commit=args.expected_source_commit,
            reviewer_challenge=args.reviewer_challenge,
            source_root=args.source_root)
        result = publish_no_overwrite(args.output_directory, *obs)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ObservationError, CheckoutPinError, ArchVmUnavailable, OSError,
            ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(json.dumps({
            "status": "REJECTED_NATIVE_OBSERVATION_NOT_HOMOLOGATED",
            "reason": str(exc),
            "native_kernel_execution_independently_verified": False,
            "independent_vm_attestation": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
