#!/usr/bin/env python3
"""PE-S2.13 offline structural review of two observer text records. ALWAYS HOLD.

Checks field shape, pinned host/guest hashes, common session and scope, and
runtime->cleanup SHA256. The observations are UNSIGNED RAW TEXT until external
review signs their hashes; neither that signature nor this shape check is
independent kernel, VM, hypervisor or journal attestation.
"""
from __future__ import annotations

import hashlib
import re
import pe_arch_vm_s1_63_external_observer as external
from pe_resource_limits import (SCOPE_PATTERN, MEMORY_MAX_BYTES, TASKS_MAX,
    CPU_QUOTA_PERCENT, CPU_PERIOD_MIN_US, CPU_PERIOD_MAX_US, CPU_QUOTA_MIN_US)

RUNTIME_SCHEMA = "negresco_pe_s2_13_runtime_observation_v1"
CLEANUP_SCHEMA = "negresco_pe_s2_13_cleanup_observation_v1"
CLASSIFICATION = "OBSERVER_TEXT_NOT_KERNEL_ATTESTATION"
COMMON = {"schema", "classification", "source_commit", "reviewer_challenge",
          "domain_name", "domain_uuid", "prior_host_record_sha256",
          "prior_guest_record_sha256", "session_id", "scope",
          "windows_binary_executed", "independent_vm_attestation",
          "release_authorized"}
RUNTIME_KEYS = frozenset(COMMON | {"memory_max_bytes", "pids_max",
    "cpu_quota_us", "cpu_period_us", "seccomp_mode", "seccomp_filter_count"})
CLEANUP_KEYS = frozenset(COMMON | {"prior_runtime_record_sha256",
    "load_state", "active_state", "sub_state", "cgroup_populated",
    "stop_request_accepted"})
HEX = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
DOMAIN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}\Z")


class RuntimeTextReviewError(RuntimeError):
    """Untrusted observer text fails even minimal same-session coherence."""


def _parse(raw: bytes, keys: frozenset[str]) -> dict[str, str]:
    if (type(raw) is not bytes or not 0 < len(raw) <= external.MAX_LOG_BYTES
            or not raw.endswith(b"\n") or b"\r" in raw or b"\0" in raw):
        raise RuntimeTextReviewError("Malformed or missing runtime observation text")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise RuntimeTextReviewError("Runtime observation is not ASCII") from exc
    if len(lines) != len(keys):
        raise RuntimeTextReviewError("Incomplete or extra runtime observation fields")
    data = {}
    for line in lines:
        if (len(line) > 512 or line.count("=") != 1
                or any(ord(ch) < 33 or ord(ch) > 126 for ch in line)):
            raise RuntimeTextReviewError("Noncanonical runtime observation line")
        key, value = line.split("=", 1)
        if key not in keys or key in data or not value:
            raise RuntimeTextReviewError("Duplicate/unknown/empty runtime field")
        data[key] = value
    if set(data) != keys:
        raise RuntimeTextReviewError("Runtime field set mismatch")
    return data


def _int(value: str, maximum: int) -> int:
    if re.fullmatch(r"[1-9][0-9]{0,11}", value) is None:
        raise RuntimeTextReviewError("Noncanonical or unbounded quota")
    number = int(value)
    if number > maximum:
        raise RuntimeTextReviewError("Quota exceeds safety budget")
    return number


def _pins(data: dict, schema: str, *, commit: str, challenge: str,
          domain: str, uuid: str, host_sha: str, guest_sha: str):
    for value, regex in ((commit, COMMIT), (challenge, HEX),
                         (domain, DOMAIN), (uuid, UUID),
                         (host_sha, HEX), (guest_sha, HEX)):
        if type(value) is not str or regex.fullmatch(value) is None:
            raise RuntimeTextReviewError("Invalid out-of-band pin")
    expected = {"schema": schema, "classification": CLASSIFICATION,
                "source_commit": commit, "reviewer_challenge": challenge,
                "domain_name": domain, "domain_uuid": uuid,
                "prior_host_record_sha256": host_sha,
                "prior_guest_record_sha256": guest_sha}
    if (commit == "0"*40 or challenge == "0"*64
            or any(data[key] != value for key, value in expected.items())
            or HEX.fullmatch(data["session_id"]) is None
            or data["session_id"] == "0"*64
            or SCOPE_PATTERN.fullmatch(data["scope"]) is None
            or any(data[key] != "false" for key in (
                "windows_binary_executed", "independent_vm_attestation",
                "release_authorized"))):
        raise RuntimeTextReviewError("Runtime text contradicts pinned session")


def review_runtime_cleanup_text(runtime_raw: bytes, cleanup_raw: bytes, *,
        expected_source_commit: str, expected_challenge: str,
        expected_domain: str, expected_domain_uuid: str,
        expected_host_sha256: str, expected_guest_sha256: str) -> dict:
    """No I/O: check two already-read texts; never return an attested PASS."""
    r = _parse(runtime_raw, RUNTIME_KEYS)
    c = _parse(cleanup_raw, CLEANUP_KEYS)
    expected = {"commit": expected_source_commit,
                "challenge": expected_challenge, "domain": expected_domain,
                "uuid": expected_domain_uuid, "host_sha": expected_host_sha256,
                "guest_sha": expected_guest_sha256}
    _pins(r, RUNTIME_SCHEMA, **expected)
    _pins(c, CLEANUP_SCHEMA, **expected)
    if (r["session_id"] != c["session_id"] or r["scope"] != c["scope"]
            or c["prior_runtime_record_sha256"] !=
               hashlib.sha256(runtime_raw).hexdigest()):
        raise RuntimeTextReviewError("Runtime/cleanup scope, session or hash chain differs")
    _int(r["memory_max_bytes"], MEMORY_MAX_BYTES)
    _int(r["pids_max"], TASKS_MAX)
    quota = _int(r["cpu_quota_us"], 10_000_000)
    period = _int(r["cpu_period_us"], CPU_PERIOD_MAX_US)
    _int(r["seccomp_filter_count"], 4096)
    if (not CPU_PERIOD_MIN_US <= period <= CPU_PERIOD_MAX_US
            or quota < CPU_QUOTA_MIN_US
            or quota * 100 > period * CPU_QUOTA_PERCENT
            or r["seccomp_mode"] != "2"):
        raise RuntimeTextReviewError("Runtime text cgroup/seccomp contract invalid")
    if (c["load_state"] not in ("loaded", "not-found")
            or c["active_state"] != "inactive"
            or c["sub_state"] != "dead" or c["cgroup_populated"] != "0"
            or c["stop_request_accepted"] != "true"):
        raise RuntimeTextReviewError("Scope cleanup text is contradictory")
    return {"status": "LOCAL_S2_13_TWO_TEXT_RECORDS_STRUCTURALLY_CORRELATED_HOLD",
            "records_structurally_checked": 2,
            "runtime_cleanup_session_and_digest_chain_agree": True,
            "kernel_or_hypervisor_authenticated": False,
            "seccomp_cgroups_independently_verified": False,
            "scope_cleanup_independently_verified": False,
            "independent_vm_attestation": False, "release_authorized": False}
