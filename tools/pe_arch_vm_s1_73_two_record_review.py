#!/usr/bin/env python3
"""PE-S1.73: offline, fail-closed semantic review of TWO reviewer-held logs.

This reads only S1.70/S1.71 private records, with out-of-band SHA256 pins.
It authenticates neither a host nor a guest kernel. It NEVER creates the
remaining two observations, contacts libvirt, signs, or authorizes release.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

import pe_arch_vm_s1_63_external_observer as external
import pe_arch_vm_s1_65_observer_prepare as prepare
import pe_arch_vm_s1_70_readonly_libvirt_host_capture as host
import pe_arch_vm_s1_71_guestinfo_os_capture as guest

STATUS = "HOLD_PE_S1_73_TWO_PINNED_HOST_RECORDS_NOT_VM_ATTESTED"
REJECTED = "REJECTED_PE_S1_73_TWO_HOST_RECORD_REVIEW"
LOG1 = external.OBS_FILES["host_vm_launch"]
LOG2 = external.OBS_FILES["host_guest_kernel"]
UNVERIFIED = (
    external.OBS_FILES["host_seccomp_cgroups"],
    external.OBS_FILES["host_scope_cleanup"],
)


class TwoRecordReviewError(RuntimeError):
    """The two host-side observations cannot be trusted even as self-reports."""


def _lines(raw: bytes, label: str) -> list[str]:
    if (not isinstance(raw, bytes) or not 0 < len(raw) <= external.MAX_LOG_BYTES
            or not raw.endswith(b"\n") or b"\0" in raw or b"\r" in raw):
        raise TwoRecordReviewError("Missing, oversized or noncanonical " + label)
    try:
        value = raw.decode("utf-8")
    except UnicodeError as exc:
        raise TwoRecordReviewError("Invalid UTF-8 in " + label) from exc
    lines = value[:-1].split("\n")
    if any(not line or any(ord(ch) < 32 or ord(ch) == 127 for ch in line)
           for line in lines):
        raise TwoRecordReviewError("Empty line or control character in " + label)
    return lines


def _clock(line: str) -> None:
    prefix = "observed_utc_untrusted="
    if not line.startswith(prefix) or len(line) > 100:
        raise TwoRecordReviewError("Untrusted local time field missing")
    try:
        value = datetime.fromisoformat(line[len(prefix):])
    except ValueError as exc:
        raise TwoRecordReviewError("Malformed local time") from exc
    if value.tzinfo is None or value.utcoffset().total_seconds() != 0:
        raise TwoRecordReviewError("Local time field must be UTC, not attested")


def _review_host(lines: list[str], *, commit: str, challenge: str,
                 domain: str, uuid: str) -> None:
    prefix = [
        "observation_type=libvirt_readonly_domain_snapshot",
        "classification=HOST_QUERY_OUTPUT_NOT_VM_ATTESTATION",
        "source_commit=" + commit,
        "reviewer_challenge=" + challenge,
    ]
    header = [
        "uri=qemu:///system", "connection=readonly",
        "domain_name=" + domain, "expected_domain_uuid=" + uuid,
        "initial_domuuid:", uuid, "initial_domstate:", "running", "dominfo:",
    ]
    footer = [
        "final_domstate:", "running", "final_domuuid:", uuid,
        "independent_vm_attestation=false", "release_authorized=false",
    ]
    if (len(lines) <= 19 or lines[:4] != prefix
            or lines[5:14] != header or lines[-6:] != footer):
        raise TwoRecordReviewError("S1.70 host record format/pins invalid")
    _clock(lines[4])
    # S1.70 records actual (untrusted) dominfo stdout, not boot evidence.
    info = lines[14:-6]
    if not info or any(
            line.startswith(("source_commit=", "reviewer_challenge=",
                             "final_domstate:", "final_domuuid:",
                             "independent_vm_attestation=", "release_authorized="))
            for line in info):
        raise TwoRecordReviewError("S1.70 dominfo contains reserved markers")
    for key, expected in (
        ("Name:", domain), ("UUID:", uuid), ("State:", "running")
    ):
        observed = [line.split(":", 1)[1].strip()
                    for line in info if line.startswith(key)]
        if observed != [expected]:
            raise TwoRecordReviewError("S1.70 dominfo identity/state conflict")


def _review_guest(lines: list[str], *, commit: str, challenge: str,
                  domain: str, uuid: str, prior_sha: str) -> dict[str, str]:
    prefix = [
        "observation_type=libvirt_readonly_guest_agent_os_kernel",
        "classification=GUEST_AGENT_SELF_REPORT_NOT_KERNEL_ATTESTATION",
        "source_commit=" + commit,
        "reviewer_challenge=" + challenge,
    ]
    header = [
        "uri=qemu:///system", "connection=readonly",
        "domain_name=" + domain, "expected_domain_uuid=" + uuid,
        "prior_host_record_sha256=" + prior_sha,
        "initial_domuuid:", uuid, "initial_domstate:", "running",
        "virsh_guestinfo_os_guest_agent_self_report:",
    ]
    footer = [
        "final_domstate:", "running", "final_domuuid:", uuid,
        "guest_agent_self_report=true",
        "independent_vm_attestation=false", "release_authorized=false",
    ]
    if (len(lines) <= 24 or lines[:4] != prefix
            or lines[5:15] != header or lines[-7:] != footer):
        raise TwoRecordReviewError("S1.71 guest self-report format/pins invalid")
    _clock(lines[4])
    raw_os = lines[15:-10]
    if not raw_os or len("\n".join(raw_os).encode("utf-8")) > host.MAX_COMMAND_BYTES:
        raise TwoRecordReviewError("Missing or oversized guest-agent OS output")
    try:
        fields = guest._parse_guest_os("\n".join(raw_os))
    except guest.GuestKernelObservationError as exc:
        raise TwoRecordReviewError("Invalid guest self-reported OS fields") from exc
    if lines[-10:-7] != [
        "parsed_guest_os_id=" + fields["os.id"],
        "parsed_guest_kernel_release=" + fields["os.kernel-release"],
        "parsed_guest_machine=" + fields["os.machine"],
    ]:
        raise TwoRecordReviewError("Guest raw and parsed fields disagree")
    return fields


def review_two_records(observer_dir: Path, *, domain: str,
                       expected_domain_uuid: str,
                       expected_source_commit: str, reviewer_challenge: str,
                       expected_host_sha256: str,
                       expected_guest_sha256: str) -> dict:
    """Validate externally pinned hashes and matching record semantics.

    Successful review is deliberately a HOLD. It does not access libvirt.
    """
    try:
        owner = host._check(
            domain, expected_domain_uuid, expected_source_commit,
            reviewer_challenge, Path(observer_dir))
    except host.HostCaptureError as exc:
        raise TwoRecordReviewError("Unsafe reviewer pin or observer folder") from exc
    for digest in (expected_host_sha256, expected_guest_sha256):
        if not isinstance(digest, str) or external.SHA256.fullmatch(digest) is None:
            raise TwoRecordReviewError("Two external lowercase SHA-256 pins required")
    try:
        first = prepare._read_file(owner, LOG1)
        second = prepare._read_file(owner, LOG2)
    except prepare.ObserverPreparationError as exc:
        raise TwoRecordReviewError("Private reviewer record missing or unsafe") from exc
    if (hashlib.sha256(first).hexdigest() != expected_host_sha256
            or hashlib.sha256(second).hexdigest() != expected_guest_sha256):
        raise TwoRecordReviewError("Reviewer record differs from independent pin")
    # S1.86: The S1.71 pre-guestinfo gate already checks the complete
    # S1.70 layout, including all reserved identity/authority markers in
    # dominfo. Reuse that exact policy here, otherwise the offline review
    # can claim correlated identity for a re-pinned host record that the
    # earlier capture step would have rejected.
    try:
        guest._check_snapshot(
            first, commit=expected_source_commit,
            challenge=reviewer_challenge, domain=domain,
            uuid=expected_domain_uuid)
    except guest.GuestKernelObservationError as exc:
        raise TwoRecordReviewError(
            "S1.70 snapshot contradicts strict pre-guestinfo policy") from exc
    _review_host(
        _lines(first, "S1.70"), commit=expected_source_commit,
        challenge=reviewer_challenge, domain=domain,
        uuid=expected_domain_uuid)
    parsed = _review_guest(
        _lines(second, "S1.71"), commit=expected_source_commit,
        challenge=reviewer_challenge, domain=domain,
        uuid=expected_domain_uuid, prior_sha=expected_host_sha256)
    # Separate second read catches a persistent file replacement; neither
    # two reads nor SHA-256 prove actual host provenance.
    try:
        if (prepare._read_file(owner, LOG1) != first
                or prepare._read_file(owner, LOG2) != second):
            raise TwoRecordReviewError("Reviewer records changed during review")
    except prepare.ObserverPreparationError as exc:
        raise TwoRecordReviewError("Reviewer records became unsafe") from exc
    return {
        "status": STATUS,
        "host_record_sha256_matched": True,
        "guest_record_sha256_matched": True,
        "guest_record_bound_to_host_sha256": True,
        "domain_uuid_correlated": True,
        "source_commit_correlated": True,
        "reviewer_challenge_correlated": True,
        "guest_os_id_self_reported": parsed["os.id"],
        "guest_kernel_release_self_reported": parsed["os.kernel-release"],
        "semantic_records_checked": 2,
        "other_unverified_records": list(UNVERIFIED),
        "libvirt_queried": False,
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
    ap = argparse.ArgumentParser(
        description="Review first two pinned host logs; always HOLD, no VM queries")
    ap.add_argument("--observer-dir", type=Path, required=True)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--expected-domain-uuid", required=True)
    ap.add_argument("--expected-source-commit", required=True)
    ap.add_argument("--reviewer-challenge", required=True)
    ap.add_argument("--expected-host-sha256", required=True)
    ap.add_argument("--expected-guest-sha256", required=True)
    args = ap.parse_args(argv)
    try:
        result = review_two_records(
            args.observer_dir, domain=args.domain,
            expected_domain_uuid=args.expected_domain_uuid,
            expected_source_commit=args.expected_source_commit,
            reviewer_challenge=args.reviewer_challenge,
            expected_host_sha256=args.expected_host_sha256,
            expected_guest_sha256=args.expected_guest_sha256)
        print(json.dumps(result, sort_keys=True))
    except (TwoRecordReviewError, OSError, ValueError) as exc:
        print(json.dumps({
            "status": REJECTED, "reason": str(exc),
            "independent_vm_attestation": False,
            "release_authorized": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }, sort_keys=True), file=sys.stderr)
    return 2  # Even valid self-reports cannot authorize a release.


if __name__ == "__main__":
    raise SystemExit(main())
