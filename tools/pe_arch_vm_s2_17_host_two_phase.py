#!/usr/bin/env python3
"""PE-S2.17: host-only TWO PHASE libvirt domstats collector / offline HOLD.

A reviewer on a separately operated libvirt host can opt in to two bounded
read-only samples, with a reviewer-held hash of the FIRST capture required
before the SECOND. An increasing CPU time is necessary but not sufficient to
prove guest work, host independence, kernel cgroups/seccomp or journal quota.
There is no execution of any guest command, PE or unknown binary.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
import pe_arch_vm_receipt_verify as receipts
import pe_arch_vm_s1_63_external_observer as external
import pe_arch_vm_s1_65_observer_prepare as prepare
import pe_arch_vm_s1_70_readonly_libvirt_host_capture as host
import pe_arch_vm_s2_15_readonly_host_domstats as domstats

SCHEMA = "negresco_pe_s2_17_host_two_phase_domstats_v1"
BEFORE = "reviewer-host-domstats-before.txt"
AFTER = "reviewer-host-domstats-after.txt"
MAX_FILE = 16384
STATUS_PLAN = "PE_S2_17_HOST_TWO_PHASE_NOT_STARTED"
STATUS_COLLECTED = "LOCAL_PE_S2_17_HOST_COUNTERS_CAPTURED_NO_ATTESTATION"
STATUS_REVIEWED = "LOCAL_PE_S2_17_TWO_HOST_COUNTERS_CORRELATED_HOLD"
STATUS_REJECTED = "REJECTED_PE_S2_17_HOST_COUNTERS_SESSION"
PHASES = {"before": BEFORE, "after": AFTER}
FIELDS = frozenset((
    "schema", "classification", "phase",
    "source_commit", "reviewer_challenge", "reviewer_session_id",
    "domain_name", "domain_uuid", "host_record_sha256",
    "guest_record_sha256", "before_record_sha256",
    "host_time_utc_untrusted", "domstats_raw",
    "cpu_time_ns", "initial_domuuid", "final_domuuid",
    "initial_domstate", "final_domstate", "uri",
    "independent_vm_attestation", "release_authorized",
    "windows_binary_executed",
))
CLASSIFICATION = "LIBVIRT_HOST_TWO_SAMPLE_TEXT_NOT_GUEST_KERNEL_ATTESTATION"


class HostTwoPhaseError(RuntimeError):
    """No convincing even locally correlated host counters were observed."""


def _canonical(record: dict) -> bytes:
    return (json.dumps(record, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _inputs(observer_dir: Path, *, domain: str, expected_domain_uuid: str,
            expected_source_commit: str, reviewer_challenge: str,
            expected_session_id: str, expected_host_sha256: str,
            expected_guest_sha256: str) -> Path:
    try:
        owner = host._check(domain, expected_domain_uuid, expected_source_commit,
                            reviewer_challenge, Path(observer_dir))
        domstats._inputs(
            source_commit=expected_source_commit, challenge=reviewer_challenge,
            session=expected_session_id, host_sha=expected_host_sha256,
            guest_sha=expected_guest_sha256)
    except (host.HostCaptureError, domstats.HostDomstatsError,
            OSError, ValueError, TypeError) as exc:
        raise HostTwoPhaseError("Invalid externally selected reviewer pins") from exc
    return owner


def _previous_records(owner: Path, *, domain: str, expected_domain_uuid: str,
                      expected_source_commit: str, reviewer_challenge: str,
                      expected_host_sha256: str,
                      expected_guest_sha256: str) -> None:
    try:
        domstats._offline_pins(
            owner, domain=domain, uuid=expected_domain_uuid,
            commit=expected_source_commit, challenge=reviewer_challenge,
            host_sha=expected_host_sha256, guest_sha=expected_guest_sha256)
    except domstats.HostDomstatsError as exc:
        raise HostTwoPhaseError("Pinned S1.70/S1.71 records changed") from exc


def _decode(raw: bytes, *, phase: str, expected_before_sha256: str | None,
            domain: str, expected_domain_uuid: str,
            expected_source_commit: str, reviewer_challenge: str,
            expected_session_id: str, expected_host_sha256: str,
            expected_guest_sha256: str) -> dict:
    if (type(raw) is not bytes or not 0 < len(raw) <= MAX_FILE
            or not raw.endswith(b"\n") or b"\x00" in raw):
        raise HostTwoPhaseError("Absent or unbounded host snapshot")
    try:
        record = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=receipts._no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                HostTwoPhaseError("Nonfinite host counter")))
    except (ValueError, UnicodeError, TypeError, receipts.ReceiptReviewError,
            RecursionError) as exc:
        raise HostTwoPhaseError("Malformed host sample JSON") from exc
    if (type(record) is not dict or set(record) != FIELDS
            or _canonical(record) != raw):
        raise HostTwoPhaseError("Host sample is not canonical exact schema")
    required = {
        "schema": SCHEMA, "classification": CLASSIFICATION, "phase": phase,
        "source_commit": expected_source_commit,
        "reviewer_challenge": reviewer_challenge,
        "reviewer_session_id": expected_session_id, "domain_name": domain,
        "domain_uuid": expected_domain_uuid,
        "host_record_sha256": expected_host_sha256,
        "guest_record_sha256": expected_guest_sha256,
        "before_record_sha256": expected_before_sha256,
        "initial_domuuid": expected_domain_uuid,
        "final_domuuid": expected_domain_uuid,
        "initial_domstate": "running", "final_domstate": "running",
        "uri": "qemu:///system", "independent_vm_attestation": False,
        "release_authorized": False, "windows_binary_executed": False,
    }
    if any(type(record[key]) is not type(val) or record[key] != val
           for key, val in required.items()):
        raise HostTwoPhaseError("Host sample contradicts external pins/state")
    # S2.17 writes datetime.now(timezone.utc).isoformat(); unlike
    # fromisoformat() alone, the producer's shared rule refuses Z,
    # space/ISO-week aliases and noncanonical fraction precision.
    try:
        host._validate_untrusted_utc_isoformat(
            record["host_time_utc_untrusted"])
    except host.HostCaptureError as exc:
        raise HostTwoPhaseError(
            "Host timestamp is not producer-canonical untrusted UTC") from exc
    if type(record["domstats_raw"]) is not str:
        raise HostTwoPhaseError("Host domstats not text")
    try:
        stats = domstats._stats(record["domstats_raw"], domain)
    except domstats.HostDomstatsError as exc:
        raise HostTwoPhaseError("Host sample raw domstats malformed") from exc
    if (type(record["cpu_time_ns"]) is not int
            or record["cpu_time_ns"] != stats["cpu.time"]):
        raise HostTwoPhaseError("Host CPU time mismatches raw counters")
    return record


def _read_private(owner: Path, phase: str, *, expected_sha256: str,
                  common: dict) -> dict:
    if (type(expected_sha256) is not str
            or external.SHA256.fullmatch(expected_sha256) is None):
        raise HostTwoPhaseError("Independent pinned sample SHA256 required")
    try:
        raw = prepare._read_file(owner, PHASES[phase])
    except (prepare.ObserverPreparationError, OSError) as exc:
        raise HostTwoPhaseError("Missing unsafe phase sample") from exc
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise HostTwoPhaseError("Sample differs from reviewer-held SHA256")
    expected_before = (None if phase == "before"
                       else common["expected_before_sha256"])
    return _decode(
        raw, phase=phase, expected_before_sha256=expected_before,
        **{k: common[k] for k in (
            "domain", "expected_domain_uuid", "expected_source_commit",
            "reviewer_challenge", "expected_session_id",
            "expected_host_sha256", "expected_guest_sha256")})


def _live_sample(domain: str, expected_uuid: str) -> tuple[str, int]:
    # PE-S2.60: the signed BEFORE/AFTER chain may only use the same
    # metadata-verified system executable as the host snapshot producers.
    try:
        executable = host._trusted_virsh_executable()
    except host.HostCaptureError as exc:
        raise HostTwoPhaseError(
            "Trusted system virsh required for two-phase samples") from exc
    try:
        before_uuid = host._virsh_read(executable, "domuuid", domain)
        before_state = host._virsh_read(executable, "domstate", domain)
        text = domstats._read_live(executable, domain)
        parsed = domstats._stats(text, domain)
        after_state = host._virsh_read(executable, "domstate", domain)
        after_uuid = host._virsh_read(executable, "domuuid", domain)
    except (host.HostCaptureError, domstats.HostDomstatsError) as exc:
        raise HostTwoPhaseError("Bounded readonly host queries failed") from exc
    if (before_uuid != expected_uuid or after_uuid != expected_uuid
            or before_state.casefold() != "running"
            or after_state.casefold() != "running"):
        raise HostTwoPhaseError("Domain changed while sampling host counters")
    return text, parsed["cpu.time"]


def capture_phase(observer_dir: Path, *, phase: str, domain: str,
                  expected_domain_uuid: str, expected_source_commit: str,
                  reviewer_challenge: str, expected_session_id: str,
                  expected_host_sha256: str, expected_guest_sha256: str,
                  expected_before_sha256: str | None = None,
                  capture_from_independent_host: bool = False) -> dict:
    """Reviewer explicitly starts/finishes a session; no guest interaction."""
    if phase not in PHASES or type(capture_from_independent_host) is not bool:
        raise HostTwoPhaseError("Expected before/after phase and boolean opt-in")
    common = dict(
        domain=domain, expected_domain_uuid=expected_domain_uuid,
        expected_source_commit=expected_source_commit,
        reviewer_challenge=reviewer_challenge,
        expected_session_id=expected_session_id,
        expected_host_sha256=expected_host_sha256,
        expected_guest_sha256=expected_guest_sha256,
        expected_before_sha256=expected_before_sha256)
    owner = _inputs(observer_dir, **{k:v for k,v in common.items()
                                    if k!="expected_before_sha256"})
    if phase == "before":
        if expected_before_sha256 is not None:
            raise HostTwoPhaseError("Before-phase cannot have prior sample hash")
    elif (type(expected_before_sha256) is not str
          or external.SHA256.fullmatch(expected_before_sha256) is None):
        raise HostTwoPhaseError("After-phase requires out-of-band before SHA")
    if not capture_from_independent_host:
        return {
            "status": STATUS_PLAN, "host_queried": False,
            "sample_created": False, "phase": phase,
            "independent_vm_attestation": False, "release_authorized": False,
        }
    for name in (PHASES[phase], external.MANIFEST_FILE,
                 external.SIGNATURE_FILE):
        target = owner / name
        if target.exists() or target.is_symlink():
            raise HostTwoPhaseError("Sample or signed package already exists")
    if phase == "before" and (
            (owner / AFTER).exists() or (owner / AFTER).is_symlink()):
        raise HostTwoPhaseError("Cannot start after existing completed session")
    _previous_records(owner, **{k:v for k,v in common.items()
                                if k not in ("expected_session_id",
                                             "expected_before_sha256")})
    first = None
    if phase == "after":
        first = _read_private(owner, "before",
                              expected_sha256=expected_before_sha256,
                              common=common)
    text, cpu_time = _live_sample(domain, expected_domain_uuid)
    if first is not None and cpu_time <= first["cpu_time_ns"]:
        raise HostTwoPhaseError("Host CPU counter did not increase over session")
    # Read the original records and before sample again after libvirt I/O.
    _previous_records(owner, **{k:v for k,v in common.items()
                                if k not in ("expected_session_id",
                                             "expected_before_sha256")})
    if phase == "after":
        _read_private(owner, "before",
                      expected_sha256=expected_before_sha256, common=common)
    record = {
        "schema": SCHEMA, "classification": CLASSIFICATION, "phase": phase,
        "source_commit": expected_source_commit,
        "reviewer_challenge": reviewer_challenge,
        "reviewer_session_id": expected_session_id,
        "domain_name": domain, "domain_uuid": expected_domain_uuid,
        "host_record_sha256": expected_host_sha256,
        "guest_record_sha256": expected_guest_sha256,
        "before_record_sha256": expected_before_sha256,
        "host_time_utc_untrusted": datetime.now(timezone.utc).isoformat(),
        "domstats_raw": text, "cpu_time_ns": cpu_time,
        "initial_domuuid": expected_domain_uuid,
        "final_domuuid": expected_domain_uuid,
        "initial_domstate": "running", "final_domstate": "running",
        "uri": "qemu:///system", "independent_vm_attestation": False,
        "release_authorized": False, "windows_binary_executed": False,
    }
    raw = _canonical(record)
    _decode(raw, phase=phase, expected_before_sha256=expected_before_sha256,
            **{k:v for k,v in common.items() if k!="expected_before_sha256"})
    if len(raw) > MAX_FILE:
        raise HostTwoPhaseError("Host phase sample exceeds byte budget")
    try:
        prepare._publish_new_file(owner, PHASES[phase], raw)
    except (prepare.ObserverPreparationError, OSError) as exc:
        raise HostTwoPhaseError("Could not exclusively publish host phase sample") from exc
    return {
        "status": STATUS_COLLECTED, "phase": phase,
        "sample_filename": PHASES[phase],
        "sample_sha256": hashlib.sha256(raw).hexdigest(),
        "cpu_time_ns_as_reported_by_host": cpu_time,
        "guest_isolation_verified": False,
        "sample_is_cryptographically_signed": False,
        "independent_vm_attestation": False, "release_authorized": False,
    }


def review_pair(observer_dir: Path, *, expected_before_sha256: str,
                expected_after_sha256: str, domain: str,
                expected_domain_uuid: str, expected_source_commit: str,
                reviewer_challenge: str, expected_session_id: str,
                expected_host_sha256: str,
                expected_guest_sha256: str) -> dict:
    common = dict(
        domain=domain, expected_domain_uuid=expected_domain_uuid,
        expected_source_commit=expected_source_commit,
        reviewer_challenge=reviewer_challenge,
        expected_session_id=expected_session_id,
        expected_host_sha256=expected_host_sha256,
        expected_guest_sha256=expected_guest_sha256,
        expected_before_sha256=expected_before_sha256)
    owner = _inputs(observer_dir, **{k:v for k,v in common.items()
                                    if k!="expected_before_sha256"})
    _previous_records(owner, **{k:v for k,v in common.items()
                                if k not in ("expected_session_id",
                                             "expected_before_sha256")})
    before = _read_private(owner, "before", expected_sha256=expected_before_sha256,
                           common=common)
    after = _read_private(owner, "after", expected_sha256=expected_after_sha256,
                          common=common)
    if after["cpu_time_ns"] <= before["cpu_time_ns"]:
        raise HostTwoPhaseError("No monotonic host CPU time across session")
    # Guard against lasting replacements during the full two-record review.
    _read_private(owner, "before", expected_sha256=expected_before_sha256,
                  common=common)
    _read_private(owner, "after", expected_sha256=expected_after_sha256,
                  common=common)
    return {
        "status": STATUS_REVIEWED,
        "before_after_sha256_pins_matched": True,
        "external_session_and_domain_correlated": True,
        "host_cpu_time_increased_as_reported_by_libvirt": True,
        "host_provenance_independently_attested": False,
        "guest_process_or_seccomp_cgroup_verified": False,
        "samples_signed_in_s1_63_or_s2_16": False,
        "independent_vm_attestation": False, "release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Two readonly host samples with out-of-band pins. HOLD only")
    parser.add_argument("--observer-dir", type=Path, required=True)
    parser.add_argument("--phase", choices=("before", "after"), default="before")
    parser.add_argument("--capture-from-independent-host", action="store_true")
    parser.add_argument("--review-existing", action="store_true")
    parser.add_argument("--expected-before-sha256")
    parser.add_argument("--expected-after-sha256")
    for key in ("domain", "expected_domain_uuid", "expected_source_commit",
                "reviewer_challenge", "expected_session_id",
                "expected_host_sha256", "expected_guest_sha256"):
        parser.add_argument("--" + key.replace("_", "-"), required=True)
    args = parser.parse_args(argv)
    common = dict(domain=args.domain,
                  expected_domain_uuid=args.expected_domain_uuid,
                  expected_source_commit=args.expected_source_commit,
                  reviewer_challenge=args.reviewer_challenge,
                  expected_session_id=args.expected_session_id,
                  expected_host_sha256=args.expected_host_sha256,
                  expected_guest_sha256=args.expected_guest_sha256)
    try:
        if args.review_existing:
            if args.capture_from_independent_host:
                raise HostTwoPhaseError("Offline review cannot run live queries")
            result = review_pair(
                args.observer_dir,
                expected_before_sha256=args.expected_before_sha256,
                expected_after_sha256=args.expected_after_sha256, **common)
            print(json.dumps(result, sort_keys=True))
            return 2  # Valid host text remains HOLD, never release.
        if args.expected_after_sha256 is not None:
            raise HostTwoPhaseError("After-hash used for offline review only")
        result = capture_phase(
            args.observer_dir, phase=args.phase,
            expected_before_sha256=args.expected_before_sha256,
            capture_from_independent_host=args.capture_from_independent_host,
            **common)
        print(json.dumps(result, sort_keys=True))
        return 0  # Capture only, not release.
    except (HostTwoPhaseError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "status": STATUS_REJECTED, "reason": str(exc),
            "independent_vm_attestation": False, "release_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
