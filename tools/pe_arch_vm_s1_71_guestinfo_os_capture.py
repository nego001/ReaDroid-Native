#!/usr/bin/env python3
"""PE-S1.71: collect guest-agent OS/kernel self-report from reviewer libvirt HOST.

This is the SECOND of four PE-S1.63 external observer logs. A pinned S1.70
host snapshot must already exist. Only virsh --readonly domuuid/domstate and
guestinfo --os are invoked; guest-exec, qemu-agent-command, VM starts, shell,
unknown Windows PE and all modifications are forbidden.

QEMU guest agent answers come from WITHIN the guest. They are NOT an
independent kernel measurement, nor evidence of host ownership or release.
A readonly connection may reject guestinfo on some libvirt installations:
refuse rather than upgrading permissions.
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

import pe_arch_vm_s1_70_readonly_libvirt_host_capture as host
import pe_arch_vm_s1_63_external_observer as external
import pe_arch_vm_s1_65_observer_prepare as prepare
import pe_arch_vm_s1_69_bounded_native_child as bounded

PLAN = "PE_S1_71_GUEST_KERNEL_HOST_QUERY_NOT_STARTED"
CAPTURED = "LOCAL_PE_S1_71_GUEST_AGENT_KERNEL_SELF_REPORT_NOT_VM_ATTESTATION"
REJECTED = "REJECTED_PE_S1_71_GUEST_AGENT_KERNEL_HOST_OBSERVATION"
TARGET = external.OBS_FILES["host_guest_kernel"]
PRIOR = external.OBS_FILES["host_vm_launch"]
RELEASE = re.compile(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}[A-Za-z0-9._+-]{0,80}\Z")
MACHINE = re.compile(r"(?:x86_64|aarch64)\Z")


class GuestKernelObservationError(RuntimeError):
    """Guest OS/kernel self-report was unavailable or not safely bound."""


def _check_snapshot(raw: bytes, *, commit: str, challenge: str,
                    domain: str, uuid: str) -> None:
    """Cross-reference independently retained S1.70 record fields."""
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise GuestKernelObservationError("Prior host record is not UTF-8") from exc
    required = (
        "observation_type=libvirt_readonly_domain_snapshot",
        "classification=HOST_QUERY_OUTPUT_NOT_VM_ATTESTATION",
        "source_commit=" + commit,
        "reviewer_challenge=" + challenge,
        "domain_name=" + domain,
        "expected_domain_uuid=" + uuid,
        "connection=readonly",
        "independent_vm_attestation=false",
        "release_authorized=false",
    )
    lines = text.splitlines()
    if (len(raw) > external.MAX_LOG_BYTES
            or any(lines.count(field) != 1 for field in required)
            or "initial_domuuid:\n" + uuid + "\n" not in text
            or "final_domuuid:\n" + uuid + "\n" not in text
            or "initial_domstate:\nrunning\n" not in text
            or "final_domstate:\nrunning\n" not in text):
        raise GuestKernelObservationError(
            "Prior reviewer host snapshot does not match current external pins")


def _read_guestinfo(executable: str, domain: str) -> str:
    # Only documented non-mutating guestinfo --os via a readonly connection.
    # Never use qemu-agent-command: it admits arbitrary guest-agent methods
    # and typically requires broader, write-capable libvirt privileges.
    argv = [
        executable, "--readonly", "--connect", "qemu:///system",
        "--no-pkttyagent", "guestinfo", domain, "--os",
    ]
    env = {
        "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
        "HOME": os.environ.get("HOME", "/nonexistent"),
    }
    try:
        result = bounded.run_bounded_native(
            argv, env=env, timeout=15, max_stdout=8192, max_stderr=2048)
    except bounded.BoundedNativeChildError as exc:
        raise GuestKernelObservationError(
            "Bounded guestinfo read-only query unavailable") from exc
    if result.returncode != 0 or result.stderr.strip():
        raise GuestKernelObservationError(
            "Read-only guestinfo command failed or emitted stderr")
    try:
        return host._checked_text(result.stdout, "guestinfo --os")
    except host.HostCaptureError as exc:
        raise GuestKernelObservationError("Unsafe guestinfo output") from exc


def _parse_guest_os(text: str) -> dict[str, str]:
    # Do not trust a benign-looking substring; require one entry per field
    # in the libvirt key:value output, including strictly bounded values.
    fields = {}
    for line in text.splitlines():
        match = re.fullmatch(
            r"\s*(os\.[a-z][a-z-]{0,30})\s*:\s*(.*?)\s*", line)
        if match is None:
            raise GuestKernelObservationError("Unexpected guestinfo OS field")
        key, value = match.groups()
        if (key in fields or not value or len(value) > 200
                or any(ord(c) < 32 or ord(c) > 126 for c in value)):
            raise GuestKernelObservationError("Duplicate, absent or unsafe OS field")
        fields[key] = value
    if (fields.get("os.id") != "arch"
            or not isinstance(fields.get("os.kernel-release"), str)
            or RELEASE.fullmatch(fields["os.kernel-release"]) is None
            or not isinstance(fields.get("os.machine"), str)
            or MACHINE.fullmatch(fields["os.machine"]) is None):
        raise GuestKernelObservationError(
            "Guest agent did not report supported Arch Linux kernel/machine")
    return fields


def capture_guest_kernel_observation(
        observer_dir: Path, *, domain: str, expected_domain_uuid: str,
        expected_source_commit: str, reviewer_challenge: str,
        expected_prior_host_sha256: str,
        capture_from_independent_host: bool = False) -> dict:
    """Capture one host-transported GUEST SELF-REPORT after S1.70 snapshot."""
    if type(capture_from_independent_host) is not bool:
        raise GuestKernelObservationError("Explicit host query option must be boolean")
    try:
        owner = host._check(
            domain, expected_domain_uuid, expected_source_commit,
            reviewer_challenge, Path(observer_dir))
    except host.HostCaptureError as exc:
        raise GuestKernelObservationError("Unsafe host domain or reviewer pin") from exc
    if (not isinstance(expected_prior_host_sha256, str)
            or external.SHA256.fullmatch(expected_prior_host_sha256) is None):
        raise GuestKernelObservationError("Externally pinned S1.70 SHA256 required")
    if not capture_from_independent_host:
        return {
            "status": PLAN, "guestinfo_queried": False,
            "kernel_observation_created": False,
            "guest_kernel_independently_verified": False,
            "independent_vm_attestation": False, "release_authorized": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }
    # No publication once the observer has signed or prepared a manifest.
    for name in (TARGET, external.MANIFEST_FILE, external.SIGNATURE_FILE):
        item = owner / name
        if item.exists() or item.is_symlink():
            raise GuestKernelObservationError(
                "Existing guest observation, manifest or signature: no overwrite")
    try:
        snapshot = prepare._read_file(owner, PRIOR)
    except prepare.ObserverPreparationError as exc:
        raise GuestKernelObservationError("Missing safe S1.70 host record") from exc
    if hashlib.sha256(snapshot).hexdigest() != expected_prior_host_sha256:
        raise GuestKernelObservationError("S1.70 host record differs from external pin")
    _check_snapshot(
        snapshot, commit=expected_source_commit,
        challenge=reviewer_challenge, domain=domain,
        uuid=expected_domain_uuid)
    executable = shutil.which("virsh", path="/usr/bin:/bin")
    if not executable or not os.path.isabs(executable):
        raise GuestKernelObservationError("Host virsh unavailable")
    try:
        before_uuid = host._virsh_read(executable, "domuuid", domain)
        before_state = host._virsh_read(executable, "domstate", domain)
        guestinfo = _read_guestinfo(executable, domain)
        after_state = host._virsh_read(executable, "domstate", domain)
        after_uuid = host._virsh_read(executable, "domuuid", domain)
    except host.HostCaptureError as exc:
        raise GuestKernelObservationError("Host domain query failed") from exc
    if (before_uuid != expected_domain_uuid or after_uuid != expected_domain_uuid
            or before_state.casefold() != "running"
            or after_state.casefold() != "running"):
        raise GuestKernelObservationError(
            "Domain UUID or running state changed around guest agent query")
    parsed = _parse_guest_os(guestinfo)
    # A persistent replacement between host reads must never be accepted.
    try:
        if prepare._read_file(owner, PRIOR) != snapshot:
            raise GuestKernelObservationError("S1.70 record changed during host query")
    except prepare.ObserverPreparationError as exc:
        raise GuestKernelObservationError("S1.70 record became unsafe") from exc
    raw = (
        "observation_type=libvirt_readonly_guest_agent_os_kernel\n"
        "classification=GUEST_AGENT_SELF_REPORT_NOT_KERNEL_ATTESTATION\n"
        "source_commit=" + expected_source_commit + "\n"
        "reviewer_challenge=" + reviewer_challenge + "\n"
        "observed_utc_untrusted=" + datetime.now(timezone.utc).isoformat() + "\n"
        "uri=qemu:///system\nconnection=readonly\n"
        "domain_name=" + domain + "\n"
        "expected_domain_uuid=" + expected_domain_uuid + "\n"
        "prior_host_record_sha256=" + expected_prior_host_sha256 + "\n"
        "initial_domuuid:\n" + before_uuid + "\n"
        "initial_domstate:\n" + before_state + "\n"
        "virsh_guestinfo_os_guest_agent_self_report:\n" + guestinfo + "\n"
        "parsed_guest_os_id=" + parsed["os.id"] + "\n"
        "parsed_guest_kernel_release=" + parsed["os.kernel-release"] + "\n"
        "parsed_guest_machine=" + parsed["os.machine"] + "\n"
        "final_domstate:\n" + after_state + "\n"
        "final_domuuid:\n" + after_uuid + "\n"
        "guest_agent_self_report=true\n"
        "independent_vm_attestation=false\nrelease_authorized=false\n"
    ).encode("utf-8")
    if len(raw) > external.MAX_LOG_BYTES:
        raise GuestKernelObservationError("Observation exceeds signed log bounds")
    try:
        prepare._publish_new_file(owner, TARGET, raw)
    except (prepare.ObserverPreparationError, OSError) as exc:
        raise GuestKernelObservationError("Cannot exclusively publish host observation") from exc
    return {
        "status": CAPTURED,
        "guestinfo_queried": True,
        "kernel_observation_created": True,
        "kernel_observation_sha256": hashlib.sha256(raw).hexdigest(),
        "kernel_record_filename": TARGET,
        "prior_host_record_sha256_matched": True,
        "guest_os_id_self_reported": parsed["os.id"],
        "guest_kernel_release_self_reported": parsed["os.kernel-release"],
        "guest_kernel_independently_verified": False,
        "independent_vm_attestation": False,
        "release_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Query only guestinfo --os via readonly libvirt; NEVER attest kernel")
    parser.add_argument("--observer-dir", type=Path, required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--expected-domain-uuid", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--reviewer-challenge", required=True)
    parser.add_argument("--expected-prior-host-sha256", required=True)
    parser.add_argument("--capture-from-independent-host", action="store_true")
    args = parser.parse_args(argv)
    try:
        out = capture_guest_kernel_observation(
            args.observer_dir, domain=args.domain,
            expected_domain_uuid=args.expected_domain_uuid,
            expected_source_commit=args.expected_source_commit,
            reviewer_challenge=args.reviewer_challenge,
            expected_prior_host_sha256=args.expected_prior_host_sha256,
            capture_from_independent_host=args.capture_from_independent_host)
        print(json.dumps(out, sort_keys=True))
        return 0
    except (GuestKernelObservationError, OSError, ValueError) as exc:
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
