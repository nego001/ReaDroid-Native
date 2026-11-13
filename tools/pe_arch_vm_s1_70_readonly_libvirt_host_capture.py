#!/usr/bin/env python3
"""PE-S1.70: acquire ONE genuine host-side libvirt observation, read-only.

Reviewers run this on THEIR OWN independently controlled Linux QEMU/libvirt
HOST, not in the operator's guest. This tool never starts/stops a domain,
queries a guest agent, runs a Windows executable, collects guest kernel logs,
or manufactures other three PE-S1.63 observation logs. A successful virsh
read does NOT prove host provenance, hypervisor, kernel or independence.

Default mode only inspects policy inputs; actual host queries require
--capture-from-independent-host. Output is a single exclusive private
reviewer-host-vm-launch.txt compatible with S1.63/S1.65.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_evidence as evidence
import pe_arch_vm_s1_63_external_observer as external
import pe_arch_vm_s1_65_observer_prepare as prepare
import pe_arch_vm_s1_69_bounded_native_child as bounded
from pe_arch_vm_checkout_pin import COMMIT_SHA

PLAN = "PE_S1_70_HOST_CAPTURE_NOT_STARTED"
CAPTURED = "LOCAL_PE_S1_70_READONLY_LIBVIRT_HOST_OBSERVATION_NOT_VM_ATTESTATION"
REJECTED = "REJECTED_PE_S1_70_HOST_OBSERVATION_NOT_VM_ATTESTED"
DOMAIN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
TARGET = external.OBS_FILES["host_vm_launch"]
VIRSH_COMMANDS = ("domuuid", "domstate", "dominfo")
MAX_COMMAND_BYTES = 8192
# PE-S2.47: virsh dominfo uses printable "Label: value" records. A free-form
# line can disguise a second domain identity or a forged authority claim.
# This stays an ordinary text-format check, NEVER hypervisor authentication.
DOMINFO_LABEL = re.compile(r"[A-Za-z][A-Za-z0-9 ()/_.+-]{0,63}\Z")
# PE-S2.46: observation-envelope markers cannot be injected by dominfo.
# S1.71 reuses these exact prefixes for its prior-snapshot verification.
DOMINFO_RESERVED_PREFIXES = (
    "source_commit=", "reviewer_challenge=", "domain_name=",
    "expected_domain_uuid=", "initial_domuuid:", "initial_domstate:",
    "final_domstate:", "final_domuuid:", "independent_vm_attestation=",
    "release_authorized=", "observation_type=", "classification=",
    "uri=", "connection=", "dominfo:",
)


class HostCaptureError(RuntimeError):
    """External libvirt snapshot could not be safely recorded."""



def _validate_dominfo_shape(info: str) -> None:
    """Reject hidden assignments and ambiguous/duplicate virsh labels.

    Reused by S1.71 for independently re-pinned S1.70 file bytes.
    This validates the *format* of text, not the truth of host reports.
    """
    if type(info) is not str or not 0 < len(info) <= MAX_COMMAND_BYTES:
        raise HostCaptureError("Missing or oversized host dominfo")
    labels = set()
    for line in info.split("\n"):
        if (not line or line[0].isspace() or "=" in line
                or ":" not in line
                or any(ord(char) < 32 or ord(char) == 127
                       for char in line)):
            raise HostCaptureError("Noncanonical host dominfo line")
        label, value = line.split(":", 1)
        folded = label.casefold()
        if (DOMINFO_LABEL.fullmatch(label) is None
                or label != label.strip() or not value.strip()
                or folded in labels
                or line.startswith(DOMINFO_RESERVED_PREFIXES)):
            raise HostCaptureError("Invalid, repeated or reserved dominfo field")
        labels.add(folded)


def _check(domain: str, expected_uuid: str, commit: str,
           challenge: str, directory: Path) -> Path:
    if not isinstance(domain, str) or DOMAIN.fullmatch(domain) is None:
        raise HostCaptureError("Simple non-option libvirt domain name required")
    if (not isinstance(expected_uuid, str) or
            UUID.fullmatch(expected_uuid) is None or
            expected_uuid == "00000000-0000-0000-0000-000000000000"):
        raise HostCaptureError("Externally pinned full lowercase domain UUID required")
    if (not isinstance(commit, str)
            or COMMIT_SHA.fullmatch(commit) is None
            or commit == "0" * 40):
        raise HostCaptureError("Externally pinned 40-digit Git SHA required")
    try:
        evidence.require_reviewer_challenge(challenge)
        path = prepare._directory(directory)
    except (evidence.AcceptanceReceiptError,
            prepare.ObserverPreparationError) as exc:
        raise HostCaptureError("Reviewer challenge or private host folder invalid") from exc
    if path == Path(__file__).resolve().parents[1] or (
            Path(__file__).resolve().parents[1] in path.parents):
        raise HostCaptureError("Observer evidence cannot be inside checkout")
    return path


def _checked_text(data: bytes, label: str) -> str:
    if (not isinstance(data, bytes) or not 0 < len(data) <= MAX_COMMAND_BYTES
            or b"\0" in data):
        raise HostCaptureError("Absent, oversized or binary virsh output: " + label)
    try:
        result = data.decode("utf-8")
    except UnicodeError as exc:
        raise HostCaptureError("Invalid UTF-8 from libvirt: " + label) from exc
    # Keep capture output compatible with the S1.71/S1.73 LF-only parser.
    if any((ord(c) < 32 and c != "\n") or ord(c) == 127 for c in result):
        raise HostCaptureError("Control character in libvirt result: " + label)
    stripped = result.strip()
    if not stripped:
        raise HostCaptureError("Empty libvirt query response: " + label)
    return stripped


def _virsh_read(executable: str, verb: str, domain: str) -> str:
    if verb not in VIRSH_COMMANDS:
        raise HostCaptureError("Host capture only permits three read-only commands")
    # Explicit qemu:///system and read-only connection; never accept URI,
    # shell commands or subcommands from the operator.
    argv = [
        executable, "--readonly", "--connect", "qemu:///system",
        "--no-pkttyagent", verb, domain,
    ]
    env = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "LANG": "C",
        "HOME": os.environ.get("HOME", "/nonexistent"),
    }
    try:
        run = bounded.run_bounded_native(
            argv, env=env, timeout=15,
            max_stdout=MAX_COMMAND_BYTES, max_stderr=2048)
    except bounded.BoundedNativeChildError as exc:
        raise HostCaptureError("No bounded read-only libvirt observation") from exc
    if run.returncode != 0 or run.stderr.strip():
        raise HostCaptureError("Read-only libvirt command failed or emitted stderr")
    return _checked_text(run.stdout, verb)


def capture_host_domain(
        observer_dir: Path, *, domain: str,
        expected_domain_uuid: str,
        expected_source_commit: str,
        reviewer_challenge: str,
        capture_from_independent_host: bool = False) -> dict:
    """Publish one observed host record; never claim a VM was authenticated."""
    if type(capture_from_independent_host) is not bool:
        raise HostCaptureError("Explicit host capture option must be boolean")
    owner = _check(
        domain, expected_domain_uuid, expected_source_commit,
        reviewer_challenge, Path(observer_dir))
    if not capture_from_independent_host:
        return {
            "status": PLAN,
            "host_queries_executed": False,
            "host_log_created": False,
            "independent_vm_attestation": False,
            "release_authorized": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }

    # Validate no final evidence or signature prior to ANY host commands.
    if ((owner / TARGET).exists()
            or (owner / TARGET).is_symlink()
            or (owner / external.MANIFEST_FILE).exists()
            or (owner / external.MANIFEST_FILE).is_symlink()
            or (owner / external.SIGNATURE_FILE).exists()
            or (owner / external.SIGNATURE_FILE).is_symlink()):
        raise HostCaptureError("Existing host record or signed package: refuse overwrite")
    executable = shutil.which("virsh", path="/usr/bin:/bin")
    if not executable or not os.path.isabs(executable):
        raise HostCaptureError("Local virsh executable missing; no host data captured")
    # Re-observe UUID and state both before and after the information read.
    # A persistent name rebind or stopped VM invalidates the snapshot.
    initial_uuid = _virsh_read(executable, "domuuid", domain)
    first_state = _virsh_read(executable, "domstate", domain)
    info = _virsh_read(executable, "dominfo", domain)
    final_state = _virsh_read(executable, "domstate", domain)
    final_uuid = _virsh_read(executable, "domuuid", domain)
    # Deny a second, forged source identity or release claim inside
    # a valid-looking dominfo query, before any private log is written.
    _validate_dominfo_shape(info)
    # Cross-check dominfo fields against separate libvirt queries. This
    # prevents a mid-capture name rebind being quietly accepted.
    info_uuid = re.findall(r"^UUID:\s*(\S+)\s*$", info, flags=re.MULTILINE)
    info_name = re.findall(r"^Name:\s*(\S+)\s*$", info, flags=re.MULTILINE)
    info_state = re.findall(r"^State:\s*(\S+)\s*$", info, flags=re.MULTILINE)
    if (initial_uuid != expected_domain_uuid
            or final_uuid != expected_domain_uuid
            or first_state.casefold() != "running"
            or final_state.casefold() != "running"
            or info_uuid != [expected_domain_uuid]
            or info_name != [domain]
            or [state.casefold() for state in info_state] != ["running"]):
        raise HostCaptureError(
            "Host domain identity/state changed or dominfo is inconsistent")
    # This file records the actual virsh stdout, never a PASS boolean or
    # a fictional proof of guest kernel, cgroups or scope cleanup.
    raw = (
        "observation_type=libvirt_readonly_domain_snapshot\n"
        "classification=HOST_QUERY_OUTPUT_NOT_VM_ATTESTATION\n"
        "source_commit=" + expected_source_commit + "\n"
        "reviewer_challenge=" + reviewer_challenge + "\n"
        "observed_utc_untrusted=" + datetime.now(timezone.utc).isoformat() + "\n"
        "uri=qemu:///system\n"
        "connection=readonly\n"
        "domain_name=" + domain + "\n"
        "expected_domain_uuid=" + expected_domain_uuid + "\n"
        "initial_domuuid:\n" + initial_uuid + "\n"
        "initial_domstate:\n" + first_state + "\n"
        "dominfo:\n" + info + "\n"
        "final_domstate:\n" + final_state + "\n"
        "final_domuuid:\n" + final_uuid + "\n"
        "independent_vm_attestation=false\n"
        "release_authorized=false\n"
    ).encode("utf-8")
    if len(raw) > external.MAX_LOG_BYTES:
        raise HostCaptureError("Libvirt observation exceeds S1.63 log limit")
    try:
        # Reuse no-overwrite stage/fsync publication. It never creates fake
        # kernel/seccomp/cleanup logs or an observer manifest.
        prepare._publish_new_file(owner, TARGET, raw)
    except (prepare.ObserverPreparationError, OSError) as exc:
        raise HostCaptureError("Cannot safely publish observed host record") from exc
    return {
        "status": CAPTURED,
        "host_queries_executed": True,
        "host_log_created": True,
        "host_log_sha256": hashlib.sha256(raw).hexdigest(),
        "host_record_filename": TARGET,
        "required_other_host_records_not_created": [
            external.OBS_FILES[name] for name in external.OBS_FILES
            if name != "host_vm_launch"
        ],
        "independent_host_control_verified": False,
        "guest_kernel_independently_verified": False,
        "seccomp_cgroups_independently_verified": False,
        "scope_cleanup_independently_verified": False,
        "independent_vm_attestation": False,
        "release_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture libvirt read-only host snapshot only; never certify VM")
    parser.add_argument("--observer-dir", type=Path, required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--expected-domain-uuid", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--reviewer-challenge", required=True)
    parser.add_argument("--capture-from-independent-host", action="store_true")
    args = parser.parse_args(argv)
    try:
        outcome = capture_host_domain(
            args.observer_dir, domain=args.domain,
            expected_domain_uuid=args.expected_domain_uuid,
            expected_source_commit=args.expected_source_commit,
            reviewer_challenge=args.reviewer_challenge,
            capture_from_independent_host=args.capture_from_independent_host)
        print(json.dumps(outcome, sort_keys=True))
        return 0  # Capture only: NOT VM attestation.
    except (HostCaptureError, OSError, ValueError) as exc:
        print(json.dumps({
            "status": REJECTED, "reason": str(exc),
            "independent_vm_attestation": False,
            "release_authorized": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
