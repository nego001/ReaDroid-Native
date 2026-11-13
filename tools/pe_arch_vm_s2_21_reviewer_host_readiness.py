#!/usr/bin/env python3
"""PE-S2.21: read-only reviewer HOST preflight, NEVER VM attestation.

Explicit opt-in checks known CI/container indicators, /dev/kvm, a FRESH
private host evidence directory and a pinned running libvirt domain using
only bounded readonly commands. No guest commands, starts, writes or PE.
A local success is a candidate host, not independently controlled host proof.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_gate as gate
import pe_arch_vm_s1_70_readonly_libvirt_host_capture as host

PLAN = "PE_S2_21_INDEPENDENT_HOST_PREFLIGHT_NOT_STARTED"
CANDIDATE = "LOCAL_PE_S2_21_READONLY_LIBVIRT_HOST_CANDIDATE_HOLD"
REJECTED = "REJECTED_PE_S2_21_REVIEWER_HOST_NOT_PROVEN"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CI_MARKERS = ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI",
              "TF_BUILD", "BUILD_BUILDID", "RUNNER_OS", "JENKINS_URL")
CONTAINER_MARKERS = ("/.dockerenv", "/run/.containerenv")
# linux/kvm.h: _IO(0xAE, 0x00); stable KVM system API version 12.
KVM_GET_API_VERSION = 0xAE00
KVM_API_VERSION = 12


class ReviewerHostReadinessError(RuntimeError):
    """Local reviewer host prerequisites or provenance are not established."""


def _nonce(value: str, label: str) -> None:
    # Format checks, not entropy or independently witnessed generation.
    if (type(value) is not str or HEX64.fullmatch(value) is None
            or len(set(value)) < 4):
        raise ReviewerHostReadinessError(
            "Reviewer-held non-placeholder 64-hex " + label + " required")


def _has_known_container_marker() -> bool:
    return any(Path(name).exists() for name in CONTAINER_MARKERS)


def _is_expected_kvm_char(node: os.stat_result) -> bool:
    return (stat.S_ISCHR(node.st_mode)
            and os.major(node.st_rdev) == 10
            and os.minor(node.st_rdev) == 232)


def _require_kvm_device() -> None:
    """Check an opened, pinned KVM system FD; never claim host provenance.

    S2.38's lstat 10:232 check alone can accept a fabricated device node,
    or race with another inode before this preflight uses the path. Here
    KVM_GET_API_VERSION is a query-only ioctl, not KVM_CREATE_VM.
    """
    path = "/dev/kvm"
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise ReviewerHostReadinessError(
            "Real KVM character device unavailable") from exc
    if not _is_expected_kvm_char(before):
        raise ReviewerHostReadinessError(
            "KVM must be an unmapped character device 10:232")
    # Pin the inode without following a final symlink, even if /dev/kvm is
    # replaced between lstat and open; never open read/write or create a VM.
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(path, flags)
        try:
            current = os.fstat(fd)
            if (not _is_expected_kvm_char(current)
                    or before.st_dev != current.st_dev
                    or before.st_ino != current.st_ino):
                raise ReviewerHostReadinessError(
                    "KVM descriptor replaced or inconsistent with path")
            api_version = fcntl.ioctl(fd, KVM_GET_API_VERSION)
            if type(api_version) is not int or api_version != KVM_API_VERSION:
                raise ReviewerHostReadinessError(
                    "KVM system API version is not 12")
        finally:
            os.close(fd)
    except OSError as exc:
        raise ReviewerHostReadinessError(
            "Cannot query read-only KVM system API") from exc


def _host_prerequisites(owner: Path) -> str:
    # These markers are UNSPOOFABLE neither positively nor negatively;
    # rejecting known automation is necessary but cannot prove ownership.
    if sys.platform != "linux" or os.geteuid() == 0:
        raise ReviewerHostReadinessError(
            "Linux non-root reviewer-controlled host required")
    if any(os.environ.get(name) for name in CI_MARKERS):
        raise ReviewerHostReadinessError(
            "CI runner cannot substitute for independent reviewer host")
    if _has_known_container_marker():
        raise ReviewerHostReadinessError(
            "Known container marker: not an independent host")
    _require_kvm_device()
    # Require a new empty folder: cannot replay a finished session as fresh.
    try:
        if os.listdir(owner):
            raise ReviewerHostReadinessError(
                "Reviewer evidence directory must start empty")
    except OSError as exc:
        raise ReviewerHostReadinessError(
            "Cannot safely enumerate reviewer evidence directory") from exc
    try:
        detect = gate._trusted_vm_tool("systemd-detect-virt")
        probe = subprocess.run(
            [detect, "--container", "--quiet"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=8, check=False,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C"})
    except (gate.ArchVmUnavailable, OSError, subprocess.TimeoutExpired) as exc:
        raise ReviewerHostReadinessError(
            "Trusted container-detection command unavailable") from exc
    if probe.returncode != 1:
        raise ReviewerHostReadinessError(
            "Container detected or container check inconclusive")
    # Fixed executable path resolution and exact readonly libvirt URI
    # and bounded subprocess are enforced by the existing S1.70 helper.
    try:
        virsh = gate._trusted_vm_tool("virsh")
    except gate.ArchVmUnavailable as exc:
        raise ReviewerHostReadinessError(
            "Trusted local virsh binary unavailable") from exc
    if not (virsh.startswith("/usr/bin/") or virsh.startswith("/bin/")):
        raise ReviewerHostReadinessError(
            "virsh must be a trusted system binary")
    return virsh


def _info_matches(text: str, *, domain: str, uuid: str) -> bool:
    # Never trust a grep/substring match inside unrelated dominfo fields.
    if type(text) is not str:
        return False
    rows = [line.strip() for line in text.splitlines()]
    expected = (("Name:", domain), ("UUID:", uuid), ("State:", "running"))
    for field, value in expected:
        matches = [s[len(field):].strip() for s in rows
                   if s.startswith(field)]
        if matches != [value]:
            return False
    return True


def reviewer_host_readiness(observer_dir: Path, *, domain: str,
                            expected_domain_uuid: str,
                            expected_source_commit: str,
                            reviewer_challenge: str,
                            reviewer_session_id: str,
                            probe_reviewer_host: bool = False) -> dict:
    """No mutation. No runtime probing whatsoever unless explicitly opted in."""
    if type(probe_reviewer_host) is not bool:
        raise ReviewerHostReadinessError("Explicit boolean probe opt-in required")
    try:
        _nonce(reviewer_challenge, "challenge")
        _nonce(reviewer_session_id, "session nonce")
        if reviewer_challenge == reviewer_session_id:
            raise ReviewerHostReadinessError(
                "Reviewer challenge and session must be distinct")
        owner = host._check(
            domain, expected_domain_uuid, expected_source_commit,
            reviewer_challenge, Path(observer_dir))
    except (host.HostCaptureError, OSError, ValueError, TypeError) as exc:
        raise ReviewerHostReadinessError(
            "Reviewer-owned private directory or domain pins invalid") from exc
    if not probe_reviewer_host:
        return {
            "status": PLAN, "libvirt_queried": False,
            "host_prerequisites_probed": False,
            "session_files_created": False,
            "independent_host_control_attested": False,
            "independent_vm_attestation": False,
            "release_authorized": False,
        }
    virsh = _host_prerequisites(owner)
    try:
        actual_uuid = host._virsh_read(virsh, "domuuid", domain)
        state = host._virsh_read(virsh, "domstate", domain)
        info = host._virsh_read(virsh, "dominfo", domain)
        # Check the identity a second time to detect stable replacements.
        after_state = host._virsh_read(virsh, "domstate", domain)
        after_uuid = host._virsh_read(virsh, "domuuid", domain)
    except (host.HostCaptureError, OSError) as exc:
        raise ReviewerHostReadinessError(
            "Bounded readonly libvirt host query failed") from exc
    if (actual_uuid != expected_domain_uuid
            or after_uuid != expected_domain_uuid
            or state.casefold() != "running"
            or after_state.casefold() != "running"
            or not _info_matches(info, domain=domain, uuid=expected_domain_uuid)):
        raise ReviewerHostReadinessError(
            "Domain UUID or running state changed/contradicted libvirt")
    try:
        if os.listdir(owner):
            raise ReviewerHostReadinessError(
                "Observer directory changed during host preflight")
    except OSError as exc:
        raise ReviewerHostReadinessError(
            "Cannot recheck private observer directory") from exc
    return {
        "status": CANDIDATE,
        "libvirt_readonly_uri": "qemu:///system",
        "libvirt_queried": True,
        "domain_uuid_and_state_locally_consistent": True,
        "known_ci_container_markers_rejected": True,
        "kvm_char_device_locally_seen": True,
        "fresh_private_observer_directory": True,
        "session_files_created": False,
        "independent_host_control_attested": False,
        "guest_kernel_independently_attested": False,
        "native_cgroup_seccomp_journald_verified": False,
        "independent_vm_attestation": False,
        "release_authorized": False,
        "unknown_windows_pe_execution_authorized": False,
        "apk_or_ota_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only host readiness preflight. Always HOLD.")
    parser.add_argument("--observer-dir", required=True, type=Path)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--expected-domain-uuid", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--reviewer-challenge", required=True)
    parser.add_argument("--reviewer-session-id", required=True)
    parser.add_argument("--probe-reviewer-host", action="store_true",
                        help="Opt in to known-container, KVM, and readonly virsh queries")
    args = parser.parse_args(argv)
    try:
        result = reviewer_host_readiness(
            args.observer_dir,
            domain=args.domain, expected_domain_uuid=args.expected_domain_uuid,
            expected_source_commit=args.expected_source_commit,
            reviewer_challenge=args.reviewer_challenge,
            reviewer_session_id=args.reviewer_session_id,
            probe_reviewer_host=args.probe_reviewer_host)
        print(json.dumps(result, sort_keys=True))
        # A viable local reviewer host STILL requires real human review.
        return 2 if args.probe_reviewer_host else 0
    except (ReviewerHostReadinessError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "status": REJECTED, "reason": str(exc),
            "independent_host_control_attested": False,
            "independent_vm_attestation": False,
            "release_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
