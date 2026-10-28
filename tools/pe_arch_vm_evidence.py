#!/usr/bin/env python3
"""PE-S1.12 local receipt for an already completed native Arch VM acceptance.

Not a signature, third-party attestation, or proof of a physical hypervisor:
the receipt records checked local results and hashes, so another reviewer can
correlate evidence with the source. Only writes to an owned 0700 directory,
never overwrites an earlier result, and never runs a Windows executable.
"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat

from pe_nofollow_paths import open_absolute_directory_nofollow
from pe_resource_limits import (MEMORY_MAX_BYTES, TASKS_MAX,
                                CPU_QUOTA_PERCENT, SCOPE_PATTERN)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "tools/pe_arch_vm_evidence.py",
    "tools/pe_arch_vm_receipt_verify.py",
    "tools/pe_nofollow_paths.py",
    "tools/pe_arch_vm_gate.py",
    "tools/pe_arch_cgroup_smoke.py",
    "tools/pe_arch_descendant_smoke.py",
    "tools/pe_auto_ghidra.py",
    "tools/pe_auto_inventory.py",
    "tools/pe_auto_symbols.py",
    "tools/pe_auto_behavior.py",
    "tools/pe_ghidra_integrity.py",
    "tools/pe_arch_vm_validation.py",
    "tools/pe_arch_scoped_ghidra_smoke.py",
    "tools/pe_arch_scoped_seccomp_smoke.py",
    "tools/pe_scoped_seccomp_launcher.py",
    "tools/pe_seccomp_filter.py",
    "tools/pe_seccomp_runtime_evidence.py",
    "tools/pe_cgroup_guard.py",
    "tools/pe_resource_limits.py",
    "tools/pe_scope_cleanup_evidence.py",
    "tools/pe_resource_evidence.py",
    "tools/pe_ghidra_sandbox.py",
    "tools/ghidra_scripts/NegrescoFunctionInventory.java",
    "tools/ghidra_scripts/NegrescoDeepPreview.java",
    "tools/ghidra_scripts/NegrescoSeccompRuntimeProof.java",
    "tests/fixtures/pe_headless_smoke.c",
    "tests/pe_sandbox_probe.py",
)
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_REPORT_BYTES = 512 * 1024


class AcceptanceReceiptError(RuntimeError):
    pass


def _canonical(obj: object) -> bytes:
    try:
        return (json.dumps(obj, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, TypeError, OverflowError) as exc:
        raise AcceptanceReceiptError("Non-serializable acceptance report") from exc


def _finite_budget(values: object, *, private: bool) -> bool:
    """Check actual finite kernel numbers, not merely a PASS status label.

    Each stage runs in a different transient scope, so the values may be
    stricter than the requested budgets and need not be identical across
    stages. A string, bool, empty object, unbounded max, or larger number is
    not an effective quota.
    """
    if not isinstance(values, dict):
        return False
    if private and values.get("verification") != "guard_verified_before_bwrap":
        return False
    names = (("memory_max_bytes", "tasks_max", "cpu_quota", "cpu_period")
             if private else
             ("memory_max", "pids_max", "cpu_quota", "cpu_period"))
    if any(type(values.get(k)) is not int for k in names):
        return False
    memory, tasks, quota, period = (values[k] for k in names)
    return (0 < memory <= MEMORY_MAX_BYTES
            and 0 < tasks <= TASKS_MAX
            and 0 < quota and 0 < period
            and quota * 100 <= period * CPU_QUOTA_PERCENT)


def _valid_scope(unit: object) -> bool:
    return isinstance(unit, str) and SCOPE_PATTERN.fullmatch(unit) is not None


def validate_native_acceptance_report(report: dict) -> None:
    """Reject CI-like or incomplete summaries without arch kernel evidence."""
    if not isinstance(report, dict) or report.get("status") != "PASS_PE_S1_5_ARCH_VM":
        raise AcceptanceReceiptError("No completed native Arch VM acceptance")
    vm = report.get("environment")
    ghidra = report.get("ghidra")
    if not isinstance(vm, dict) or not isinstance(ghidra, dict):
        raise AcceptanceReceiptError("Missing native VM or Ghidra evidence")
    if (vm.get("status") != "ARCH_VM_PREFLIGHT_PASSED"
            or vm.get("vm_confirmed") is not True
            or vm.get("container") is not False
            or report.get("descendants_terminated") is not True
            or report.get("windows_binary_executed") is not False):
        raise AcceptanceReceiptError("Kernel, descendant or VM checks incomplete")
    integrity = ghidra.get("ghidra_integrity")
    combined = ghidra.get("arch_real_ghidra_with_both")
    probe = ghidra.get("arch_scoped_seccomp_probe")
    descendants = report.get("descendant_lifecycle")
    initial = report.get("cgroup_lifecycle")
    # Inspect types BEFORE accessing nested attributes. Malformed/CI-like
    # reports must raise a deliberate refusal, never an incidental TypeError.
    if (not isinstance(probe, dict)
            or not isinstance(combined, dict)
            or not isinstance(descendants, dict)
            or not isinstance(initial, dict)):
        raise AcceptanceReceiptError("Missing native lifecycle reports")
    cleanup = descendants.get("descendant_cleanup_evidence")
    initial_cleanup = initial.get("scope_cleanup_evidence")
    initial_budget = initial.get("quota_private_proof")
    if (initial.get("status") != "PASS_NATIVE_ARCH_CGROUP"
            or initial.get("windows_binary_executed") is not False
            or initial.get("ghidra_executed") is not False
            or not _finite_budget(initial_budget, private=True)
            or not isinstance(initial_cleanup, dict)
            or initial_cleanup.get("scope") != initial.get("scope")
            or initial_cleanup.get("verified") is not True
            or initial_cleanup.get("scope_quiescent") is not True
            or initial_cleanup.get("cgroup_unpopulated") is not True
            or initial_cleanup.get("active_state") != "inactive"
            or initial_cleanup.get("sub_state") != "dead"):
        raise AcceptanceReceiptError("Initial native cgroup lifecycle unproven")
    # The original smoke measured one scope, independently of the later
    # descendant, seccomp and Ghidra scopes. Report the measured values once
    # and refuse if the summary or private file differs.
    reported = report.get("cgroup")
    original = {
        "memory_max": "memory_max_bytes",
        "pids_max": "tasks_max",
        "cpu_quota": "cpu_quota",
        "cpu_period": "cpu_period",
    }
    if (not isinstance(reported, dict)
            or any(type(initial.get(key)) is not int
                   or initial[key] != reported.get(key)
                   or type(initial_budget.get(private_key)) is not int
                   or initial_budget[private_key] != initial[key]
                   for key, private_key in original.items())):
        raise AcceptanceReceiptError("Initial cgroup report and private quota mismatch")
    scopes = [initial.get("scope"), descendants.get("scope"),
              probe.get("scope"), combined.get("scope")]
    if (not all(_valid_scope(unit) for unit in scopes)
            or len(set(scopes)) != 4
            or not _finite_budget(report.get("cgroup"), private=False)
            or not _finite_budget(descendants.get("quota_private_proof"),
                                  private=True)
            or not _finite_budget(probe.get("cgroup_verification"),
                                  private=True)
            or not _finite_budget(combined.get("quotas_verified_before_bwrap"),
                                  private=True)):
        raise AcceptanceReceiptError(
            "Invalid/replayed scope identity or unbounded kernel quotas")
    if (descendants.get("status") != "PASS_NATIVE_ARCH_DESCENDANTS"
            or descendants.get("detached_sigterm_ignoring_child_terminated") is not True
            or descendants.get("systemd_stop_succeeded") is not True
            or descendants.get("quota_verified") is not True
            or not isinstance(descendants.get("quota_private_proof"), dict)
            or descendants["quota_private_proof"].get("verification") != "guard_verified_before_bwrap"
            or not isinstance(descendants.get("scope"), str)
            or not isinstance(cleanup, dict)
            or cleanup.get("scope") != descendants.get("scope")
            or cleanup.get("verified") is not True
            or cleanup.get("scope_quiescent") is not True
            or cleanup.get("cgroup_unpopulated") is not True
            or cleanup.get("active_state") != "inactive"
            or cleanup.get("sub_state") != "dead"):
        raise AcceptanceReceiptError("Detached descendant cleanup was not proven")
    if (not isinstance(integrity, dict) or integrity.get("verified") is not True
            or not isinstance(combined, dict)
            or combined.get("status")
            != "PASS_NATIVE_ARCH_REAL_GHIDRA_WITH_CGROUP_AND_SECCOMP"
            or combined.get("scope_cleanup_verified") is not True
            or not isinstance(combined.get("scope_cleanup_evidence"), dict)
            or combined["scope_cleanup_evidence"].get("scope")
               != combined.get("scope")
            or combined["scope_cleanup_evidence"].get("scope_quiescent") is not True
            or combined["scope_cleanup_evidence"].get("cgroup_unpopulated") is not True
            or combined["scope_cleanup_evidence"].get("active_state") != "inactive"
            or combined["scope_cleanup_evidence"].get("sub_state") != "dead"
            or not isinstance(probe.get("scope_cleanup_evidence"), dict)
            or probe["scope_cleanup_evidence"].get("scope")
               != probe.get("scope")
            or probe["scope_cleanup_evidence"].get("scope_quiescent") is not True
            or probe["scope_cleanup_evidence"].get("cgroup_unpopulated") is not True
            or combined.get("filter_compiled_inside_scope") is not True
            or type(combined.get("decompiled_functions")) is not int
            or combined["decompiled_functions"] < 1
            or probe.get("status") != "PASS_NATIVE_ARCH_VM_SCOPED_SECCOMP"
            or not isinstance(combined.get("quotas_verified_before_bwrap"), dict)
            or combined["quotas_verified_before_bwrap"].get("verification")
            != "guard_verified_before_bwrap"):
        raise AcceptanceReceiptError("Real combined security controls unproven")
    jvm = combined.get("ghidra_jvm_seccomp_evidence")
    if (not isinstance(jvm, dict) or jvm.get("verified") is not True
            or jvm.get("measured_process") != "ghidra_headless_jvm"
            or jvm.get("measurement_source") != "/proc/self/status"
            or type(jvm.get("seccomp_mode")) is not int
            or jvm.get("seccomp_mode") != 2
            or type(jvm.get("filters_before_bwrap")) is not int
            or type(jvm.get("filters_in_ghidra")) is not int
            or not 0 <= jvm["filters_before_bwrap"] <= 4096
            or not jvm["filters_before_bwrap"] < jvm["filters_in_ghidra"] <= 4096
            or type(jvm.get("additional_filters_observed")) is not int
            or jvm["additional_filters_observed"] != (
                jvm["filters_in_ghidra"] - jvm["filters_before_bwrap"])):
        raise AcceptanceReceiptError("Ghidra JVM seccomp proof incomplete")


def build_receipt(report: dict, source_root: Path = ROOT) -> dict:
    validate_native_acceptance_report(report)
    canonical_report = _canonical(report)
    if len(canonical_report) > MAX_REPORT_BYTES:
        raise AcceptanceReceiptError("Acceptance report exceeds safety bound")
    sources = {}
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        # Pin the source checkout via every ancestor, not just its leaf.
        with ExitStack() as checkout_stack:
            checkout_fd = open_absolute_directory_nofollow(
                Path(source_root), checkout_stack)
            for relative in SOURCE_FILES:
                parts = relative.split("/")
                if not relative or any(p in ("", ".", "..") for p in parts):
                    raise AcceptanceReceiptError("Invalid source manifest path")
                with ExitStack() as file_stack:
                    directory_fd = checkout_fd
                    for part in parts[:-1]:
                        directory_fd = os.open(
                            part, flags | os.O_DIRECTORY, dir_fd=directory_fd)
                        file_stack.callback(os.close, directory_fd)
                    fd = os.open(parts[-1], flags, dir_fd=directory_fd)
                    file_stack.callback(os.close, fd)
                    before = os.fstat(fd)
                    if (not stat.S_ISREG(before.st_mode)
                            or not 1 <= before.st_size <= MAX_SOURCE_BYTES):
                        raise AcceptanceReceiptError(
                            "Unsafe or oversized source: " + relative)
                    with os.fdopen(fd, "rb", closefd=False) as src:
                        data = src.read(MAX_SOURCE_BYTES + 1)
                    after = os.fstat(fd)
                    if (len(data) != before.st_size
                            or (after.st_dev, after.st_ino, after.st_size,
                                after.st_mtime_ns, after.st_ctime_ns) !=
                               (before.st_dev, before.st_ino, before.st_size,
                                before.st_mtime_ns, before.st_ctime_ns)):
                        raise AcceptanceReceiptError(
                            "Changed source: " + relative)
                sources[relative] = {
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
    except (OSError, ValueError) as exc:
        raise AcceptanceReceiptError("Cannot hash trusted source checkout") from exc
    return {
        "schema": "negresco_native_arch_vm_local_receipt_v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "security_classification": "LOCAL_SELF_REPORT_NOT_SIGNED",
        "report_sha256": hashlib.sha256(canonical_report).hexdigest(),
        "source_file_hashes": sources,
        "native_acceptance_report": report,
        "windows_executable_launched": False,
    }

def write_receipt_no_overwrite(report: dict, destination: Path,
                              source_root: Path = ROOT) -> dict:
    payload = build_receipt(report, source_root)
    encoded = _canonical(payload)
    path = Path(destination)
    if not path.is_absolute() or path.name in ("", ".", ".."):
        raise AcceptanceReceiptError("Absolute new receipt filename required")
    parent = path.parent
    directory_stack = ExitStack()
    try:
        directory_fd = open_absolute_directory_nofollow(parent, directory_stack)
        meta = os.fstat(directory_fd)
        if (not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_mode & 0o077):
            raise AcceptanceReceiptError("Receipt parent must be owner-only (0700)")
        fd = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600, dir_fd=directory_fd)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            os.fsync(directory_fd)
        except BaseException:
            # Never leave an apparently completed but truncated proof.
            try:
                os.unlink(path.name, dir_fd=directory_fd)
            except OSError:
                pass
            raise
    except (OSError, ValueError) as exc:
        raise AcceptanceReceiptError("Cannot safely write private receipt") from exc
    finally:
        directory_stack.close()
    return {
        "path": str(path),
        "receipt_sha256": hashlib.sha256(encoded).hexdigest(),
        "record_type": "LOCAL_SELF_REPORT_NOT_SIGNED",
    }
