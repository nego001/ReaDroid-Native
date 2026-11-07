#!/usr/bin/env python3
"""PE-S2.15: optional READ-ONLY libvirt host VM counters, private sidecar.

Runs ONLY on explicit request from a separately controlled reviewer host.
No VM start/stop, no guest commands, no arbitrary shell, no changes to S1.63
signed four-observation schema. The guest and host can still lie; libvirt
runtime counters do NOT attest guest seccomp, cgroups, journald or kernel.
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
import sys

sys.dont_write_bytecode = True
import pe_arch_vm_s1_63_external_observer as external
import pe_arch_vm_s1_65_observer_prepare as prepare
import pe_arch_vm_s1_70_readonly_libvirt_host_capture as host
import pe_arch_vm_s1_73_two_record_review as semantic
import pe_arch_vm_s1_69_bounded_native_child as bounded

PLAN = "PE_S2_15_HOST_RUNTIME_CAPTURE_NOT_STARTED"
CAPTURED = "LOCAL_PE_S2_15_READONLY_LIBVIRT_DOMSTATS_NOT_ATTESTATION"
REVIEWED = "LOCAL_PE_S2_15_PINNED_DOMSTATS_TEXT_HOLD"
REJECTED = "REJECTED_PE_S2_15_HOST_RUNTIME_OBSERVATION"
TARGET = "reviewer-host-libvirt-domstats.txt"
CLASS = "LIBVIRT_HOST_COUNTERS_NOT_GUEST_KERNEL_ATTESTATION"
SHA = external.SHA256
HEADER = "observation_type=libvirt_readonly_domain_runtime_counters"
# A finite schema for the sidecar avoids mixing it into the four-record
# Ed25519 manifest v1 without a separate schema upgrade and key ceremony.
MAX_RECORD = external.MAX_LOG_BYTES
MAX_STATS = 8192
MAX_FIELDS = 96
INT = re.compile(r"(?:0|[1-9][0-9]{0,19})\Z")
KEY = re.compile(r"[a-z][a-z0-9._-]{0,79}\Z")


class HostDomstatsError(RuntimeError):
    """Unable to safely capture/review a host libvirt counter snapshot."""


def _pin(value: object, name: str) -> None:
    if type(value) is not str or SHA.fullmatch(value) is None:
        raise HostDomstatsError("Externally held lowercase SHA-256 required: " + name)


def _inputs(*, source_commit: str, challenge: str, session: str,
            host_sha: str, guest_sha: str) -> None:
    for label, value in (("session", session), ("host record", host_sha),
                         ("guest record", guest_sha)):
        _pin(value, label)
    if session in ("0" * 64, challenge, host_sha, guest_sha):
        raise HostDomstatsError("Reviewer session ID must be unique and out of band")
    if type(source_commit) is not str or not re.fullmatch(
            r"[0-9a-f]{40}", source_commit) or source_commit == "0" * 40:
        raise HostDomstatsError("Full pinned source SHA required")


def _stats(text: str, domain: str) -> dict:
    """Require ONE running domain's raw libvirt CPU/state counters.

    Guest seccomp/cgroup cannot be inferred from these counters.
    """
    if (type(text) is not str or not 0 < len(text.encode("utf-8")) <= MAX_STATS
            or not text.startswith("Domain: ")):
        raise HostDomstatsError("Missing bounded libvirt domstats output")
    lines = text.splitlines()
    if not 3 <= len(lines) <= MAX_FIELDS + 1:
        raise HostDomstatsError("No bounded domain statistics available")
    if lines[0] not in ("Domain: '" + domain + "'", "Domain: " + domain):
        raise HostDomstatsError("libvirt returned different domain or extra domains")
    pairs = {}
    for line in lines[1:]:
        if len(line) > 256 or not line.startswith(" "):
            raise HostDomstatsError("Unexpected domstats line or multiple domains")
        entry = line.strip()
        if entry.count("=") != 1:
            raise HostDomstatsError("Unexpected domstats field")
        key, value = entry.split("=", 1)
        if (KEY.fullmatch(key) is None or key in pairs
                or INT.fullmatch(value) is None or int(value) >= 2**64):
            raise HostDomstatsError("Malformed, duplicate or nonnumeric domstats field")
        pairs[key] = int(value)
    if pairs.get("state.state") != 1 or pairs.get("cpu.time", 0) <= 0:
        raise HostDomstatsError("Domain is not running or real CPU counter unavailable")
    if not any(key.startswith("cpu.") for key in pairs):
        raise HostDomstatsError("CPU counters not collected")
    return pairs


def _read_live(executable: str, domain: str) -> str:
    # Verified virsh syntax: domstats --raw --state --cpu-total DOMAIN.
    # Explicit argv, bounded output/time, read-only URI, no shell or sudo.
    argv = [executable, "--readonly", "--connect", "qemu:///system",
            "--no-pkttyagent", "domstats", "--raw", "--state",
            "--cpu-total", domain]
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C",
           "HOME": os.environ.get("HOME", "/nonexistent")}
    try:
        child = bounded.run_bounded_native(
            argv, env=env, timeout=15, max_stdout=MAX_STATS, max_stderr=2048)
    except bounded.BoundedNativeChildError as exc:
        raise HostDomstatsError("Read-only libvirt domain stats unavailable") from exc
    if child.returncode != 0 or child.stderr.strip():
        raise HostDomstatsError("libvirt domstats command failed")
    try:
        return host._checked_text(child.stdout, "domstats")
    except host.HostCaptureError as exc:
        raise HostDomstatsError("Malformed raw libvirt domstats stdout") from exc


def _offline_pins(directory: Path, *, domain: str, uuid: str, commit: str,
                  challenge: str, host_sha: str, guest_sha: str) -> None:
    try:
        result = semantic.review_two_records(
            directory, domain=domain, expected_domain_uuid=uuid,
            expected_source_commit=commit, reviewer_challenge=challenge,
            expected_host_sha256=host_sha, expected_guest_sha256=guest_sha)
    except semantic.TwoRecordReviewError as exc:
        raise HostDomstatsError("Prior host and guest pinned records invalid") from exc
    if (result["status"] != semantic.STATUS
            or result["semantic_records_checked"] != 2
            or result["independent_vm_attestation"] is not False
            or result["release_authorized"] is not False):
        raise HostDomstatsError("Prior host/guest review contradicted HOLD")


def capture_host_domstats(
        observer_dir: Path, *, domain: str, expected_domain_uuid: str,
        expected_source_commit: str, reviewer_challenge: str,
        expected_session_id: str, expected_host_sha256: str,
        expected_guest_sha256: str,
        capture_from_independent_host: bool = False) -> dict:
    """Collect a fresh one-domain host counter sidecar, only on opt-in."""
    if type(capture_from_independent_host) is not bool:
        raise HostDomstatsError("Explicit opt-in capture flag required")
    try:
        owner = host._check(domain, expected_domain_uuid, expected_source_commit,
                            reviewer_challenge, Path(observer_dir))
    except host.HostCaptureError as exc:
        raise HostDomstatsError("Unsafe pinned host or reviewer directory") from exc
    _inputs(source_commit=expected_source_commit,
            challenge=reviewer_challenge, session=expected_session_id,
            host_sha=expected_host_sha256, guest_sha=expected_guest_sha256)
    if not capture_from_independent_host:
        return {
            "status": PLAN, "libvirt_queried": False, "sidecar_created": False,
            "independent_vm_attestation": False, "release_authorized": False,
        }

    # The extra evidence must precede and never change an already sealed pack.
    for name in (TARGET, external.MANIFEST_FILE, external.SIGNATURE_FILE):
        target = owner / name
        if target.exists() or target.is_symlink():
            raise HostDomstatsError("Existing sidecar/manifest/signature: no overwrite")
    _offline_pins(
        owner, domain=domain, uuid=expected_domain_uuid,
        commit=expected_source_commit, challenge=reviewer_challenge,
        host_sha=expected_host_sha256, guest_sha=expected_guest_sha256)
    executable = shutil.which("virsh", path="/usr/bin:/bin")
    if not executable or not os.path.isabs(executable):
        raise HostDomstatsError("Read-only virsh binary unavailable")
    try:
        initial_uuid = host._virsh_read(executable, "domuuid", domain)
        initial_state = host._virsh_read(executable, "domstate", domain)
        counters = _read_live(executable, domain)
        observed = _stats(counters, domain)
        final_state = host._virsh_read(executable, "domstate", domain)
        final_uuid = host._virsh_read(executable, "domuuid", domain)
    except host.HostCaptureError as exc:
        raise HostDomstatsError("Read-only domain identity query failed") from exc
    if (initial_uuid != expected_domain_uuid or final_uuid != expected_domain_uuid
            or initial_state != "running" or final_state != "running"):
        raise HostDomstatsError("Domain identity changed around host stats read")

    # Catch persistent change of pinned prior records during the libvirt query.
    _offline_pins(
        owner, domain=domain, uuid=expected_domain_uuid,
        commit=expected_source_commit, challenge=reviewer_challenge,
        host_sha=expected_host_sha256, guest_sha=expected_guest_sha256)
    raw = (
        HEADER + "\nclassification=" + CLASS + "\n"
        "source_commit=" + expected_source_commit + "\n"
        "reviewer_challenge=" + reviewer_challenge + "\n"
        "session_id=" + expected_session_id + "\n"
        "domain_name=" + domain + "\n"
        "expected_domain_uuid=" + expected_domain_uuid + "\n"
        "prior_host_record_sha256=" + expected_host_sha256 + "\n"
        "prior_guest_record_sha256=" + expected_guest_sha256 + "\n"
        "observed_utc_untrusted=" + datetime.now(timezone.utc).isoformat() + "\n"
        "uri=qemu:///system\nconnection=readonly\n"
        "initial_domuuid=" + initial_uuid + "\n"
        "initial_domstate=" + initial_state + "\n"
        "raw_virsh_domstats_start\n" + counters + "\n"
        "raw_virsh_domstats_end\n"
        "final_domstate=" + final_state + "\n"
        "final_domuuid=" + final_uuid + "\n"
        "independent_vm_attestation=false\n"
        "release_authorized=false\n"
    ).encode("utf-8")
    if len(raw) > MAX_RECORD or len(observed) > MAX_FIELDS:
        raise HostDomstatsError("Bounded host stats sidecar exceeded policy")
    try:
        prepare._publish_new_file(owner, TARGET, raw)
    except (prepare.ObserverPreparationError, OSError) as exc:
        raise HostDomstatsError("Cannot exclusively publish private host sidecar") from exc
    return {
        "status": CAPTURED, "libvirt_queried": True,
        "sidecar_created": True, "sidecar_sha256": hashlib.sha256(raw).hexdigest(),
        "sidecar_filename": TARGET, "cpu_time_ns_observed": observed["cpu.time"],
        "guest_cgroups_seccomp_verified": False,
        "host_provenance_independently_authenticated": False,
        "included_in_s1_63_signed_manifest": False,
        "independent_vm_attestation": False, "release_authorized": False,
    }


def review_host_domstats(observer_dir: Path, *, expected_record_sha256: str,
        domain: str, expected_domain_uuid: str, expected_source_commit: str,
        reviewer_challenge: str, expected_session_id: str,
        expected_host_sha256: str, expected_guest_sha256: str) -> dict:
    """Offline re-review of a separately pinned sidecar: ALWAYS HOLD."""
    try:
        owner = host._check(domain, expected_domain_uuid, expected_source_commit,
                            reviewer_challenge, Path(observer_dir))
    except host.HostCaptureError as exc:
        raise HostDomstatsError("Invalid reviewer-held sidecar directory") from exc
    _inputs(source_commit=expected_source_commit, challenge=reviewer_challenge,
            session=expected_session_id, host_sha=expected_host_sha256,
            guest_sha=expected_guest_sha256)
    _pin(expected_record_sha256, "host domstats sidecar")
    _offline_pins(owner, domain=domain, uuid=expected_domain_uuid,
                  commit=expected_source_commit, challenge=reviewer_challenge,
                  host_sha=expected_host_sha256, guest_sha=expected_guest_sha256)
    try:
        raw = prepare._read_file(owner, TARGET)
    except prepare.ObserverPreparationError as exc:
        raise HostDomstatsError("Missing private host statistics sidecar") from exc
    if hashlib.sha256(raw).hexdigest() != expected_record_sha256:
        raise HostDomstatsError("Host statistics sidecar disagrees with independent SHA pin")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise HostDomstatsError("Host statistics sidecar not UTF-8") from exc
    expected_prefix = [
        HEADER, "classification=" + CLASS,
        "source_commit=" + expected_source_commit,
        "reviewer_challenge=" + reviewer_challenge,
        "session_id=" + expected_session_id,
        "domain_name=" + domain,
        "expected_domain_uuid=" + expected_domain_uuid,
        "prior_host_record_sha256=" + expected_host_sha256,
        "prior_guest_record_sha256=" + expected_guest_sha256,
    ]
    from datetime import datetime
    if not 23 <= len(lines) <= MAX_FIELDS + 24 or lines[:9] != expected_prefix:
        raise HostDomstatsError("Unexpected host statistics record header")
    clock_line = lines[9]
    if not clock_line.startswith("observed_utc_untrusted="):
        raise HostDomstatsError("Missing explicitly untrusted host timestamp")
    try:
        stamp = datetime.fromisoformat(clock_line.split("=", 1)[1])
    except ValueError as exc:
        raise HostDomstatsError("Malformed untrusted host timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise HostDomstatsError("Host timestamp must be untrusted UTC")
    if lines[10:15] != [
            "uri=qemu:///system", "connection=readonly",
            "initial_domuuid=" + expected_domain_uuid,
            "initial_domstate=running", "raw_virsh_domstats_start"]:
        raise HostDomstatsError("Host record did not use readonly domain query")
    if lines[-5:] != [
            "raw_virsh_domstats_end", "final_domstate=running",
            "final_domuuid=" + expected_domain_uuid,
            "independent_vm_attestation=false", "release_authorized=false"]:
        raise HostDomstatsError("Host record claims changed identity or VM attestation")
    recorded = "\n".join(lines[15:-5])
    parsed = _stats(recorded, domain)
    try:
        if prepare._read_file(owner, TARGET) != raw:
            raise HostDomstatsError("Sidecar changed during offline verification")
    except prepare.ObserverPreparationError as exc:
        raise HostDomstatsError("Sidecar became unsafe during review") from exc
    return {
        "status": REVIEWED,
        "record_sha256_matched": True,
        "prior_signed_host_guest_record_hashes_correlated": True,
        "reviewer_selected_session_id_correlated": True,
        "cpu_time_ns_as_reported_by_host": parsed["cpu.time"],
        "actual_hypervisor_independently_authenticated": False,
        "guest_cgroups_seccomp_independently_verified": False,
        "independent_vm_attestation": False, "release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser("PE-S2.15 readonly host counter sidecar, never release")
    parser.add_argument("--observer-dir", type=Path, required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--expected-domain-uuid", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--reviewer-challenge", required=True)
    parser.add_argument("--expected-session-id", required=True)
    parser.add_argument("--expected-host-sha256", required=True)
    parser.add_argument("--expected-guest-sha256", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--capture-from-independent-host", action="store_true")
    mode.add_argument("--review-existing", action="store_true")
    parser.add_argument("--expected-record-sha256")
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
            if args.expected_record_sha256 is None:
                raise HostDomstatsError("An independently held sidecar SHA pin is required")
            result = review_host_domstats(
                args.observer_dir,
                expected_record_sha256=args.expected_record_sha256, **common)
            print(json.dumps(result, sort_keys=True))
            return 2  # A valid text is still an unauthorized HOLD.
        if args.expected_record_sha256 is not None:
            raise HostDomstatsError("Sidecar SHA pin is only valid for offline review")
        result = capture_host_domstats(
            args.observer_dir,
            capture_from_independent_host=args.capture_from_independent_host,
            **common)
        print(json.dumps(result, sort_keys=True))
        return 0  # File preparation/capture only. Not a release.
    except (HostDomstatsError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": REJECTED, "reason": str(exc),
                          "independent_vm_attestation": False,
                          "release_authorized": False}, sort_keys=True),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
