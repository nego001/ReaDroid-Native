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
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import time

from pe_nofollow_paths import open_absolute_directory_nofollow
from pe_ghidra_integrity import GHIDRA_RELEASE_SHA256
from pe_resource_limits import (MEMORY_MAX_BYTES, TASKS_MAX,
                                CPU_QUOTA_PERCENT, CPU_QUOTA_MIN_US,
                                CPU_PERIOD_MIN_US, CPU_PERIOD_MAX_US,
                                SCOPE_PATTERN)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "tools/pe_arch_vm_evidence.py",
    "tools/pe_receipt_stage_cleanup.py",
    "tools/pe_arch_vm_receipt_verify.py",
    "tools/pe_arch_vm_handoff_review.py",
    "tools/pe_arch_vm_custody_review.py",
    "tools/pe_arch_vm_witness_review.py",
    "tools/pe_arch_vm_witness_trust_review.py",
    "tools/pe_arch_vm_dual_control_review.py",
    "tools/pe_nofollow_paths.py",
    "tools/pe_arch_vm_gate.py",
    "tools/pe_arch_vm_observation.py",
    "tools/pe_arch_vm_observation_review.py",
    "tools/pe_arch_vm_end_to_end_review.py",
    "tools/pe_arch_vm_s1_57_release_guard.py",
    "tools/pe_arch_vm_s1_58_preflight.py",
    "tools/pe_arch_cgroup_smoke.py",
    "tools/pe_arch_descendant_smoke.py",
    "tools/pe_auto_ghidra.py",
    "tools/pe_auto_inventory.py",
    "tools/pe_auto_symbols.py",
    "tools/pe_auto_behavior.py",
    "tools/pe_ghidra_integrity.py",
    "tools/pe_arch_vm_validation.py",
    "tools/pe_arch_vm_checkout_pin.py",
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
CHALLENGE_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
STAGE_PATTERN = re.compile(r"\.negresco-receipt-[0-9a-f]{32}\.tmp\Z")
MIN_STAGE_AGE_SECONDS = 24 * 60 * 60
MAX_STAGE_SCAN_ENTRIES = 4096


class AcceptanceReceiptError(RuntimeError):
    pass


def require_reviewer_challenge(value: object) -> str:
    """Require a reviewer-supplied 256-bit, lowercase hex challenge.

    A correct challenge only correlates the receipt with the reviewer's
    prior request. It is not a cryptographic signature, does not establish
    entropy or prevent forgery by the host generating the receipt.
    """
    if (not isinstance(value, str)
            or CHALLENGE_PATTERN.fullmatch(value) is None
            or value == "0" * 64):
        raise AcceptanceReceiptError(
            "Reviewer challenge must be 64 nonzero lowercase hex digits")
    return value


def _canonical(obj: object) -> bytes:
    try:
        return (json.dumps(obj, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, TypeError, OverflowError, RecursionError, RuntimeError) as exc:
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
            and quota >= CPU_QUOTA_MIN_US
            and CPU_PERIOD_MIN_US <= period <= CPU_PERIOD_MAX_US
            and quota * 100 <= period * CPU_QUOTA_PERCENT)


def _valid_scope(unit: object) -> bool:
    return isinstance(unit, str) and SCOPE_PATTERN.fullmatch(unit) is not None


def _verified_scope_cleanup(unit: object, proof: object) -> bool:
    """Validate the full output contract of stop_and_attest_scope().

    systemd can collect a transient scope before the final status query.
    Both a loaded+inactive and a collected+not-found scope are valid.
    They must not be mixed, and the cleanup acknowledgement must match
    its own scope rather than trusting a generic success label.
    """
    if not _valid_scope(unit) or not isinstance(proof, dict):
        return False
    expected = {
        "scope", "verified", "scope_quiescent", "stop_request_accepted",
        "load_state", "active_state", "sub_state", "scope_collected",
        "cgroup_unpopulated",
    }
    return (set(proof) == expected
            and proof.get("scope") == unit
            and proof.get("verified") is True
            and proof.get("scope_quiescent") is True
            and proof.get("cgroup_unpopulated") is True
            and type(proof.get("stop_request_accepted")) is bool
            and type(proof.get("scope_collected")) is bool
            and proof.get("load_state") in ("loaded", "not-found")
            and proof.get("scope_collected")
                is (proof.get("load_state") == "not-found")
            and proof.get("active_state") == "inactive"
            and proof.get("sub_state") == "dead")


# PE-S1.29: accept only fields emitted by the trusted native acceptance
# producers. Unknown fields can carry deceptive approval/attestation claims
# that the verifier never substantiated, even when all real fields look valid.
# Paths are relative to native_acceptance_report, not the outer v2 receipt.
_NATIVE_REPORT_FIELD_CONTRACTS = (
    ((), ("status", "environment", "cgroup", "cgroup_lifecycle",
          "descendants_terminated", "descendant_lifecycle", "ghidra",
          "windows_binary_executed")),
    (("environment",), ("status", "vm_confirmed", "container", "root",
                       "systemd_user_bus", "real_cgroup_test_executed")),
    (("cgroup",), ("memory_max", "pids_max", "cpu_quota", "cpu_period")),
    (("cgroup_lifecycle",), (
        "status", "scope", "memory_max", "pids_max", "cpu_quota",
        "cpu_period", "quota_private_proof", "scope_cleanup_evidence",
        "ghidra_executed", "windows_binary_executed")),
    (("descendant_lifecycle",), (
        "status", "scope", "quota_verified", "systemd_stop_succeeded",
        "quota_private_proof", "descendant_cleanup_evidence",
        "detached_sigterm_ignoring_child_terminated",
        "windows_binary_executed", "ghidra_executed")),
    (("ghidra",), (
        "status", "ghidra_functions", "memory_max_bytes", "tasks_max",
        "cpu_quota", "cpu_period", "pe_executed", "sandbox",
        "ghidra_integrity", "arch_isolation_probe",
        "arch_scoped_seccomp_probe", "arch_real_ghidra_with_both")),
    (("ghidra", "ghidra_integrity"), (
        "verified", "release_sha256", "matched_files",
        "symlinks_allowed", "unexpected_files_allowed")),
    (("ghidra", "arch_isolation_probe"), (
        "status", "host_home_canary_hidden", "network_namespace_separate",
        "host_etc_hidden", "usr_runtime_read_only",
        "private_work_writable", "inherited_host_fd_hidden")),
    (("ghidra", "arch_scoped_seccomp_probe"), (
        "status", "scope", "filter_compiled_after_guard",
        "cgroup_verification", "scope_cleanup_evidence", "sandbox_checks",
        "windows_pe_executed", "ghidra_executed")),
    (("ghidra", "arch_real_ghidra_with_both"), (
        "status", "scope", "scope_stop_accepted",
        "scope_cleanup_verified", "scope_cleanup_evidence",
        "filter_compiled_inside_scope", "quotas_verified_before_bwrap",
        "ghidra_jvm_seccomp_evidence", "ghidra_functions_discovered",
        "decompiled_functions", "bubblewrap", "windows_binary_executed")),
    (("ghidra", "arch_real_ghidra_with_both", "ghidra_jvm_seccomp_evidence"), (
        "verified", "measurement_source", "measured_process",
        "seccomp_mode", "filters_before_bwrap", "filters_in_ghidra",
        "additional_filters_observed")),
    (("cgroup_lifecycle", "quota_private_proof"), (
        "verification", "memory_max_bytes", "tasks_max",
        "cpu_quota", "cpu_period")),
    (("descendant_lifecycle", "quota_private_proof"), (
        "verification", "memory_max_bytes", "tasks_max",
        "cpu_quota", "cpu_period")),
    (("ghidra", "arch_scoped_seccomp_probe", "cgroup_verification"), (
        "verification", "memory_max_bytes", "tasks_max",
        "cpu_quota", "cpu_period")),
    (("ghidra", "arch_real_ghidra_with_both",
      "quotas_verified_before_bwrap"), (
        "verification", "memory_max_bytes", "tasks_max",
        "cpu_quota", "cpu_period")),
)


def _require_native_report_field_contracts(report: object) -> None:
    """Fail closed on extra, missing or malformed self-reported fields.

    These contracts cannot authenticate the VM; they prevent unsupported
    security claims being smuggled into an otherwise valid local receipt.
    """
    for path, expected in _NATIVE_REPORT_FIELD_CONTRACTS:
        node = report
        for component in path:
            if not isinstance(node, dict):
                raise AcceptanceReceiptError("Malformed native report schema")
            node = node.get(component)
        if not isinstance(node, dict) or set(node) != set(expected):
            location = ".".join(path) if path else "report"
            raise AcceptanceReceiptError(
                "Unrecognized or incomplete native report fields: " + location)


def validate_native_acceptance_report(report: dict) -> None:
    """Reject CI-like or incomplete summaries without arch kernel evidence."""
    _require_native_report_field_contracts(report)
    if not isinstance(report, dict) or report.get("status") != "PASS_PE_S1_5_ARCH_VM":
        raise AcceptanceReceiptError("No completed native Arch VM acceptance")
    vm = report.get("environment")
    ghidra = report.get("ghidra")
    if not isinstance(vm, dict) or not isinstance(ghidra, dict):
        raise AcceptanceReceiptError("Missing native VM or Ghidra evidence")
    if (vm.get("status") != "ARCH_VM_PREFLIGHT_PASSED"
            or vm.get("vm_confirmed") is not True
            or vm.get("container") is not False
            or vm.get("real_cgroup_test_executed") is not False
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
    # Each lifecycle's own status must be self-consistent. Separate scopes
    # are allowed to have different stop_request_accepted outcomes.
    for scope, proof in (
        (initial.get("scope"), initial_cleanup),
        (descendants.get("scope"), cleanup),
        (probe.get("scope"), probe.get("scope_cleanup_evidence")),
        (combined.get("scope"), combined.get("scope_cleanup_evidence")),
    ):
        if not _verified_scope_cleanup(scope, proof):
            raise AcceptanceReceiptError(
                "Inconsistent native scope cleanup lifecycle")
    if (type(combined.get("scope_stop_accepted")) is not bool
            or combined["scope_stop_accepted"] is not
               combined["scope_cleanup_evidence"]["stop_request_accepted"]):
        raise AcceptanceReceiptError(
            "Ghidra stop acknowledgement contradicts private cleanup proof")
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

    # PE-S1.22: a valid report needs the actual isolation and release
    # identity observations, not merely successful cgroup/JVM status labels.
    isolation = ghidra.get("arch_isolation_probe")
    isolation_fields = (
        "host_home_canary_hidden", "network_namespace_separate",
        "host_etc_hidden", "usr_runtime_read_only",
        "private_work_writable", "inherited_host_fd_hidden",
    )
    if (ghidra.get("status") != "PASS_REAL_ARCH_VM_GHIDRA"
            or ghidra.get("sandbox") != "bubblewrap"
            or ghidra.get("pe_executed") is not False
            or vm.get("root") is not False
            or vm.get("systemd_user_bus") is not True
            or not isinstance(isolation, dict)
            or isolation.get("status") != "PASS_NATIVE_ARCH_BWRAP_PROBE"
            or any(isolation.get(field) is not True for field in isolation_fields)
            or not isinstance(integrity, dict)
            or integrity.get("verified") is not True
            or integrity.get("release_sha256") != GHIDRA_RELEASE_SHA256
            or type(integrity.get("matched_files")) is not int
            or integrity["matched_files"] < 1
            or integrity.get("symlinks_allowed") is not False
            or integrity.get("unexpected_files_allowed") is not False
            or type(ghidra.get("ghidra_functions")) is not int
            or ghidra["ghidra_functions"] < 1):
        raise AcceptanceReceiptError(
            "Ghidra pinned release or native Bubblewrap isolation unproven")
    # The standalone Ghidra invocation uses its own cgroup scope; validate
    # the four finite effective numbers, without incorrectly requiring
    # equality with other independent scopes.
    ghidra_quota = {key: ghidra.get(key) for key in (
        "memory_max_bytes", "tasks_max", "cpu_quota", "cpu_period")}
    ghidra_quota["verification"] = "guard_verified_before_bwrap"
    if not _finite_budget(ghidra_quota, private=True):
        raise AcceptanceReceiptError("Standalone Ghidra quota summary invalid")
    scoped_sandbox_checks = (*isolation_fields, "seccomp_enforced")
    if (probe.get("filter_compiled_after_guard") is not True
            or probe.get("windows_pe_executed") is not False
            or probe.get("ghidra_executed") is not False
            or probe.get("sandbox_checks") != list(scoped_sandbox_checks)
            or not isinstance(probe.get("scope_cleanup_evidence"), dict)
            or probe["scope_cleanup_evidence"].get("verified") is not True
            or probe["scope_cleanup_evidence"].get("active_state") != "inactive"
            or probe["scope_cleanup_evidence"].get("sub_state") != "dead"
            or descendants.get("windows_binary_executed") is not False
            or descendants.get("ghidra_executed") is not False
            or combined.get("bubblewrap") is not True
            or combined.get("windows_binary_executed") is not False
            or type(combined.get("ghidra_functions_discovered")) is not int
            or combined["ghidra_functions_discovered"] < 1
            # Both inventories inspect the same freshly compiled synthetic
            # PE with the same pinned Ghidra release and inventory script.
            # Two internally valid but contradictory counts cannot PASS.
            or type(ghidra.get("ghidra_functions")) is not int
            or combined["ghidra_functions_discovered"] !=
               ghidra["ghidra_functions"]
            or type(combined.get("decompiled_functions")) is not int
            or not 1 <= combined["decompiled_functions"]
                       <= combined["ghidra_functions_discovered"]):
        raise AcceptanceReceiptError(
            "Conflicting or incomplete scoped security/decompilation evidence")
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


def build_receipt(report: dict, source_root: Path = ROOT, *,
                  reviewer_challenge: str) -> dict:
    require_reviewer_challenge(reviewer_challenge)
    # Canonicalize once, then validate and embed the same detached snapshot.
    # The caller can mutate its original nested dictionaries after returning.
    canonical_report = _canonical(report)
    if len(canonical_report) > MAX_REPORT_BYTES:
        raise AcceptanceReceiptError("Acceptance report exceeds safety bound")
    try:
        report_snapshot = json.loads(canonical_report)
    except (ValueError, TypeError, RecursionError) as exc:
        raise AcceptanceReceiptError("Malformed acceptance report snapshot") from exc
    validate_native_acceptance_report(report_snapshot)
    sources = {}
    # Prevent an attacker-controlled FIFO source from blocking before fstat.
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
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
        "schema": "negresco_native_arch_vm_local_receipt_v2",
        "reviewer_challenge": reviewer_challenge,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "security_classification": "LOCAL_SELF_REPORT_NOT_SIGNED",
        "report_sha256": hashlib.sha256(canonical_report).hexdigest(),
        "source_file_hashes": sources,
        "native_acceptance_report": report_snapshot,
        "windows_executable_launched": False,
    }



def _lock_private_receipt_directory(directory_fd: int, *,
                                    exclusive: bool) -> None:
    """Cooperate with receipt writers/cleanup without waiting on busy locks.

    flock on an already pinned directory descriptor serializes writers and
    cleanup across independent processes, including aliases of the same inode.
    It is advisory: malicious or legacy same-UID processes may ignore it.
    Closing the descriptor releases this lock on every exit path.
    """
    mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    try:
        fcntl.flock(directory_fd, mode | fcntl.LOCK_NB)
    except OSError as exc:
        raise AcceptanceReceiptError(
            "Private receipt directory busy or advisory lock unavailable"
        ) from exc


def cleanup_orphan_receipt_stages(
        directory: Path, *, min_age_seconds: int = MIN_STAGE_AGE_SECONDS,
        apply: bool = False) -> dict:
    """Review old unpublished stage inodes; delete only by explicit opt-in.

    This is never called by the writer or receipt verifier. A crash can
    preserve a .tmp; a currently open writer can also be delayed, so age is
    a conservative hint rather than evidence that an inode is abandoned.
    Never touch final receipts, symlinks, or hard-linked/published stages.
    """
    if (type(min_age_seconds) is not int
            or not MIN_STAGE_AGE_SECONDS <= min_age_seconds <= 365 * 86400
            or type(apply) is not bool):
        raise AcceptanceReceiptError("Invalid stage cleanup controls")
    with ExitStack() as stack:
        try:
            fd = open_absolute_directory_nofollow(Path(directory), stack)
            private = os.fstat(fd)
            if (not stat.S_ISDIR(private.st_mode)
                    or private.st_uid != os.geteuid()
                    or private.st_mode & 0o077):
                raise AcceptanceReceiptError(
                    "Stage cleanup requires owner-only directory")
            # Preview can coexist with other previews, but never with a
            # writer. Apply requires exclusive access through the last unlink.
            _lock_private_receipt_directory(fd, exclusive=apply)
            now_ns = time.time_ns()
            cutoff = now_ns - min_age_seconds * 1_000_000_000
            candidates = []
            scanned = 0
            with os.scandir(fd) as entries:
                for entry in entries:
                    scanned += 1
                    if scanned > MAX_STAGE_SCAN_ENTRIES:
                        raise AcceptanceReceiptError(
                            "Too many entries for bounded stage inspection")
                    name = entry.name
                    if STAGE_PATTERN.fullmatch(name) is None:
                        continue
                    identity = os.stat(
                        name, dir_fd=fd, follow_symlinks=False)
                    # A stage with two links could already be published
                    # under a final receipt name. Do not touch it.
                    if (not stat.S_ISREG(identity.st_mode)
                            or identity.st_uid != os.geteuid()
                            or stat.S_IMODE(identity.st_mode) != 0o600
                            or identity.st_nlink != 1
                            or not 0 <= identity.st_size <=
                            MAX_REPORT_BYTES + MAX_SOURCE_BYTES
                            or identity.st_mtime_ns > cutoff
                            or identity.st_ctime_ns > cutoff):
                        continue
                    candidates.append((name, identity))
            removed = []
            for name, observed in candidates:
                if not apply:
                    continue
                # Reopen by private directory FD with nofollow; compare
                # inode and metadata immediately before unlinking.
                try:
                    stage_fd = os.open(
                        name, os.O_RDONLY | os.O_CLOEXEC |
                        os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                except FileNotFoundError:
                    continue
                try:
                    current = os.fstat(stage_fd)
                    linked = os.stat(
                        name, dir_fd=fd, follow_symlinks=False)
                    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns",
                              "st_ctime_ns", "st_nlink", "st_mode", "st_uid")
                    if (any(getattr(current, key) != getattr(observed, key)
                            or getattr(linked, key) != getattr(observed, key)
                            for key in fields)
                            or current.st_nlink != 1):
                        continue
                    # Python has no inode-conditional unlinkat. The private
                    # directory is required, but same-UID replacement remains
                    # a theoretical race; operator must ensure no writers.
                    os.unlink(name, dir_fd=fd)
                    removed.append(name)
                finally:
                    os.close(stage_fd)
            if removed:
                os.fsync(fd)
            return {
                "status": "STAGE_CLEANUP_APPLIED" if apply
                          else "STAGE_CLEANUP_PREVIEW",
                "minimum_age_seconds": min_age_seconds,
                "eligible_stages": sorted(name for name, _ in candidates),
                "removed_stages": sorted(removed),
                "scanned_entries": scanned,
                "note": "UNSIGNED_LOCAL_MAINTENANCE_NOT_VM_ATTESTATION",
            }
        except (OSError, ValueError) as exc:
            raise AcceptanceReceiptError(
                "Cannot safely inspect private receipt stages") from exc


def write_receipt_no_overwrite(report: dict, destination: Path,
                              source_root: Path = ROOT, *,
                              reviewer_challenge: str) -> dict:
    payload = build_receipt(
        report, source_root, reviewer_challenge=reviewer_challenge)
    encoded = _canonical(payload)
    path = Path(destination)
    if not path.is_absolute() or path.name in ("", ".", ".."):
        raise AcceptanceReceiptError("Absolute new receipt filename required")
    parent = path.parent
    with ExitStack() as directory_stack:
        try:
            directory_fd = open_absolute_directory_nofollow(
                parent, directory_stack)
            meta = os.fstat(directory_fd)
            if (not stat.S_ISDIR(meta.st_mode)
                    or meta.st_uid != os.geteuid()
                    or meta.st_mode & 0o077):
                raise AcceptanceReceiptError(
                    "Receipt parent must be owner-only (0700)")
            # This conflicts with cleanup --apply and other cooperating
            # writers; fail closed rather than waiting on a possibly hung
            # process. The lock lasts through file+directory fsync.
            _lock_private_receipt_directory(directory_fd, exclusive=True)
            # A completed receipt must never be observable under its final
            # name while it is still being written or fsynced. An owner-only
            # staging file receives the full bytes before atomic publication.
            stage_name = ".negresco-receipt-" + secrets.token_hex(16) + ".tmp"
            stage_created = False
            published = False
            identity = None

            def unlink_owned(name: str) -> None:
                # Do not delete another file if the entry was replaced while
                # handling an error. Directory is already validated private.
                try:
                    entry = os.stat(
                        name, dir_fd=directory_fd, follow_symlinks=False)
                    if (identity is not None
                            and (entry.st_dev, entry.st_ino) == identity
                            and stat.S_ISREG(entry.st_mode)):
                        os.unlink(name, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass

            try:
                fd = os.open(
                    stage_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    0o600, dir_fd=directory_fd)
                stage_created = True
                identity_stat = os.fstat(fd)
                identity = (identity_stat.st_dev, identity_stat.st_ino)
                with os.fdopen(fd, "wb") as output:
                    output.write(encoded)
                    output.flush()
                    os.fsync(output.fileno())
                # link() publishes an already-complete inode atomically and
                # refuses to overwrite an existing final name (EEXIST).
                os.link(
                    stage_name, path.name,
                    src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                    follow_symlinks=False)
                published = True
                unlink_owned(stage_name)
                stage_created = False
                os.fsync(directory_fd)
            except BaseException:
                # No success is reported for a failed write, link or durable
                # directory sync. Remove only our own inode, never a receipt
                # installed concurrently by another process.
                if published:
                    try:
                        unlink_owned(path.name)
                    except OSError:
                        pass
                if stage_created:
                    try:
                        unlink_owned(stage_name)
                    except OSError:
                        pass
                try:
                    os.fsync(directory_fd)
                except OSError:
                    pass
                raise
        except (OSError, ValueError) as exc:
            raise AcceptanceReceiptError(
                "Cannot safely publish private receipt") from exc
    return {
        "path": str(path),
        "receipt_sha256": hashlib.sha256(encoded).hexdigest(),
        "record_type": "LOCAL_SELF_REPORT_NOT_SIGNED",
    }
