#!/usr/bin/env python3
"""PE-S1.53: correlate PE-S1.52 *untrusted* observations and PE-S1.48 custody.

No guest execution or VM attestation is performed. Both logs remain authored
by the operator. The SHA-256 is a reviewer-held local integrity reference,
NOT proof that a kernel, virtual machine or cgroup really existed.
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

import pe_arch_vm_custody_review as custody
import pe_arch_vm_observation as obs
import pe_arch_vm_receipt_verify as receipts
from pe_arch_vm_checkout_pin import COMMIT_SHA

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
COMMON = frozenset({
    "artifact", "classification", "source_commit", "reviewer_challenge",
    "operator_observed_at_utc_not_attested", "native_arch_vm_gate_local_pass",
    "independent_vm_attestation", "native_kernel_execution_independently_verified",
    "real_cgroup_limits_or_cleanup_tested_by_this_command",
    "windows_binary_executed",
})
KERNEL = COMMON | frozenset({
    "kernel_release", "kernel_machine", "pid1_comm",
    "systemd_version_first_line", "virtualization_reported_by_local_systemd",
})
CGROUP = COMMON | frozenset({
    "cgroup_v2_controllers_available", "cgroup_v2_root_subtree_control",
    "systemd_user_control_group_locally_observed",
    "cgroup_quotas_verified_by_this_command",
    "cgroup_descendant_cleanup_verified_by_this_command",
})
FALSE_FIELDS = (
    "independent_vm_attestation", "native_kernel_execution_independently_verified",
    "real_cgroup_limits_or_cleanup_tested_by_this_command",
    "windows_binary_executed",
)
STATUS = "LOCAL_GUEST_OBSERVATION_CUSTODY_CORRELATED_NOT_ATTESTED"


class ObservationReviewError(RuntimeError):
    """The guest self-reports are structurally unsafe or disagree with custody."""


def _parse_observation(raw: bytes, *, expected_artifact: str,
                       commit: str, challenge: str) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= obs.MAX_FILE_BYTES:
        raise ObservationReviewError("Guest observation exceeds strict byte limit")
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=receipts._no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ObservationReviewError("Non-finite guest observation")))
    except (UnicodeError, ValueError, TypeError, RecursionError,
            OverflowError) as exc:
        raise ObservationReviewError("Malformed or duplicate guest JSON") from exc
    if not isinstance(parsed, dict) or set(parsed) != (
            KERNEL if expected_artifact == "guest_kernel_observation"
            else CGROUP):
        raise ObservationReviewError("Guest observation fields missing or unexpected")
    if (parsed["artifact"] != expected_artifact
            or parsed["classification"] != obs.STATUS
            or parsed["source_commit"] != commit
            or parsed["reviewer_challenge"] != challenge
            or parsed["native_arch_vm_gate_local_pass"] is not True
            or any(parsed[key] is not False for key in FALSE_FIELDS)):
        raise ObservationReviewError(
            "Guest observation has conflicting pins or unsupported security claims")
    stamp = parsed["operator_observed_at_utc_not_attested"]
    if (not isinstance(stamp, str) or not 20 <= len(stamp) <= 40
            or not stamp.endswith("+00:00")):
        raise ObservationReviewError("Untrusted operator UTC timestamp malformed")
    try:
        if datetime.fromisoformat(stamp).utcoffset().total_seconds() != 0:
            raise ValueError("Not UTC")
    except (ValueError, AttributeError, OverflowError) as exc:
        raise ObservationReviewError("Invalid operator UTC timestamp") from exc
    return parsed


def _safe_text(value: object, limit: int) -> bool:
    return (isinstance(value, str) and 0 < len(value) <= limit
            and all(ch.isascii() and (ch.isprintable() or ch == " ")
                    for ch in value)
            and "\n" not in value and "\r" not in value)


def _validate_observation_pair(kernel: dict, group: dict) -> None:
    # The collector generates one timestamp per pair. Replayed/mixed logs
    # cannot silently become one review, even with a freshly forged index.
    if (kernel["operator_observed_at_utc_not_attested"]
            != group["operator_observed_at_utc_not_attested"]):
        raise ObservationReviewError(
            "Guest observations were not collected in the same local batch")
    for field, max_len in (
            ("kernel_release", 180),
            ("kernel_machine", 80),
            ("systemd_version_first_line", 120),
            ("virtualization_reported_by_local_systemd", 80)):
        if not _safe_text(kernel[field], max_len):
            raise ObservationReviewError("Invalid kernel observation field: " + field)
    if kernel["pid1_comm"] != "systemd":
        raise ObservationReviewError("Kernel observation PID 1 not systemd")
    if not kernel["systemd_version_first_line"].startswith("systemd "):
        raise ObservationReviewError("Invalid systemd version observation")
    if kernel["virtualization_reported_by_local_systemd"] in (
            "none", "docker", "podman", "lxc", "systemd-nspawn"):
        raise ObservationReviewError("Non-VM virtualization string in self-report")

    available = group["cgroup_v2_controllers_available"]
    subtree = group["cgroup_v2_root_subtree_control"]
    for label, fields in (("available", available), ("subtree", subtree)):
        if (not isinstance(fields, list)
                or len(fields) > 32
                or any(not isinstance(s, str) or
                       re.fullmatch(r"[a-z_]{1,24}", s) is None
                       for s in fields)
                or fields != sorted(set(fields))):
            raise ObservationReviewError(
                "Invalid or duplicate cgroup controller list: " + label)
    if not {"cpu", "memory", "pids"}.issubset(set(available)):
        raise ObservationReviewError("Required cgroup controllers not reported")
    if not set(subtree).issubset(set(available)):
        raise ObservationReviewError(
            "Enabled cgroup controllers not among available controllers")
    path = group["systemd_user_control_group_locally_observed"]
    if (not _safe_text(path, 1024) or not path.startswith("/")
            or "//" in path or "/../" in path or "/./" in path
            or path.endswith("/..") or path.endswith("/.")):
        raise ObservationReviewError("Invalid user ControlGroup observation")
    for key in ("cgroup_quotas_verified_by_this_command",
                "cgroup_descendant_cleanup_verified_by_this_command"):
        if group[key] is not False:
            raise ObservationReviewError("Unsupported cgroup enforcement claim")


def verify_observation_custody(
        private_dir: Path, source_root: Path, *,
        expected_custody_sha256: str, expected_source_commit: str,
        expected_challenge: str,
        require_readonly_source_view: bool = False) -> dict:
    """Strictly parse PE-S1.52 records, then require full PE-S1.48 review."""
    if (not isinstance(expected_custody_sha256, str)
            or HEX64.fullmatch(expected_custody_sha256) is None
            or not isinstance(expected_source_commit, str)
            or COMMIT_SHA.fullmatch(expected_source_commit) is None
            or not isinstance(expected_challenge, str)
            or HEX64.fullmatch(expected_challenge) is None
            or expected_challenge == "0" * 64):
        raise ObservationReviewError("Independent reviewer pins required")
    if type(require_readonly_source_view) is not bool:
        raise ObservationReviewError("Readonly source policy must be boolean")
    root = Path(private_dir)
    if (not root.is_absolute() or root.name in ("", ".", "..")
            or any(piece in ("", ".", "..") for piece in root.parts[1:])):
        raise ObservationReviewError("Canonical private directory required")
    try:
        index_raw = receipts._read_private_receipt(
            root / "reviewer-custody-index.json")
        if hashlib.sha256(index_raw).hexdigest() != expected_custody_sha256:
            raise ObservationReviewError("Externally pinned index hash differs")
        index = custody._strict_json(index_raw)
        if (set(index) != custody.INDEX_FIELDS
                or index["schema"] != custody.SCHEMA
                or index["security_classification"] != custody.CLASSIFICATION
                or index["source_commit"] != expected_source_commit
                or index["reviewer_challenge"] != expected_challenge
                or not isinstance(index["artifacts"], dict)
                or set(index["artifacts"]) != set(custody.ARTIFACT_NAMES)):
            raise ObservationReviewError("Custody index and external pins conflict")
        records = {}
        saved = {}
        for label in ("guest_kernel_observation", "guest_cgroup_observation"):
            item = index["artifacts"][label]
            if (not isinstance(item, dict)
                    or set(item) != {"filename", "sha256"}
                    or item["filename"] != custody.ARTIFACT_NAMES[label]
                    or not isinstance(item["sha256"], str)
                    or HEX64.fullmatch(item["sha256"]) is None):
                raise ObservationReviewError(
                    "Invalid reviewer-pinned observation inventory")
            raw = receipts._read_private_receipt(root / item["filename"])
            if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ObservationReviewError(
                    "Guest observation differs from reviewer custody digest")
            saved[label] = raw
            records[label] = _parse_observation(
                raw, expected_artifact=label,
                commit=expected_source_commit,
                challenge=expected_challenge)
        _validate_observation_pair(
            records["guest_kernel_observation"],
            records["guest_cgroup_observation"])

        # This calls the existing full offline receipt/challenge/source
        # manifest verifier. Never substitute just a mocked status in prod.
        verified = custody.verify_custody_index(
            root, source_root,
            expected_custody_sha256=expected_custody_sha256,
            expected_source_commit=expected_source_commit,
            expected_challenge=expected_challenge,
            require_readonly_source_view=require_readonly_source_view)
        if (verified.get("status") != "LOCAL_CUSTODY_PACKAGE_CORRELATED"
                or verified.get("independent_vm_attestation") is not False
                or verified.get("native_kernel_execution_independently_verified")
                   is not False):
            raise ObservationReviewError("Underlying custody review not accepted")
        for label, raw in saved.items():
            if receipts._read_private_receipt(
                    root / custody.ARTIFACT_NAMES[label]) != raw:
                raise ObservationReviewError(
                    "Guest observation changed during custody verification")
        if receipts._read_private_receipt(
                root / "reviewer-custody-index.json") != index_raw:
            raise ObservationReviewError(
                "Reviewer custody index changed during review")
        return {
            "status": STATUS,
            "source_commit": expected_source_commit,
            "custody_index_sha256": expected_custody_sha256,
            "guest_kernel_observation_sha256":
                index["artifacts"]["guest_kernel_observation"]["sha256"],
            "guest_cgroup_observation_sha256":
                index["artifacts"]["guest_cgroup_observation"]["sha256"],
            "source_files_rechecked": verified["source_files_rechecked"],
            "readonly_source_view_verified": verified[
                "readonly_source_view_verified"],
            "observation_pins_and_structure_correlated": True,
            "operator_batch_timestamp_matches": True,
            "cgroup_controller_claims_structurally_consistent": True,
            "operator_logs_authenticated": False,
            "native_kernel_execution_independently_verified": False,
            "independent_vm_attestation": False,
            "host_or_git_authenticity_verified": False,
            "windows_binary_executed_by_reviewer": False,
        }
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            RecursionError, receipts.ReceiptReviewError,
            custody.CustodyReviewError) as exc:
        raise ObservationReviewError(
            "Guest observation custody unavailable, unsafe or inconsistent") from exc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Cross-check self-reported guest metadata with reviewer custody")
    ap.add_argument("--private-dir", type=Path, required=True)
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--expected-custody-sha256", required=True)
    ap.add_argument("--expected-source-commit", required=True)
    ap.add_argument("--expected-challenge", required=True)
    ap.add_argument("--require-readonly-source-view", action="store_true")
    args = ap.parse_args(argv)
    try:
        result = verify_observation_custody(
            args.private_dir, args.source_root,
            expected_custody_sha256=args.expected_custody_sha256,
            expected_source_commit=args.expected_source_commit,
            expected_challenge=args.expected_challenge,
            require_readonly_source_view=args.require_readonly_source_view)
        print(json.dumps(result, sort_keys=True))
        return 0
    except ObservationReviewError as exc:
        print(json.dumps({
            "status": "REJECTED_GUEST_OBSERVATION_CUSTODY",
            "reason": str(exc),
            "native_kernel_execution_independently_verified": False,
            "independent_vm_attestation": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
