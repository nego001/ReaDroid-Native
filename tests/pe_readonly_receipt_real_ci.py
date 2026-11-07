#!/usr/bin/env python3
"""PE-S1.44: exercise the full offline receipt CLI in real Bubblewrap mounts.

Synthetic, self-asserted report fixture only. The host creates the private
receipt and retains its SHA-256; the sandbox independently checks the full
manifest via actual readonly/writable mounts. Not an Arch VM attestation.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CHALLENGE = "a12bcdef" * 8
CASE_EXPECTED = {
    "readonly": "PASS_REAL_READONLY_FULL_RECEIPT",
    "writable": "REJECT_REAL_WRITABLE_FULL_RECEIPT",
    "nested-writable": "REJECT_REAL_NESTED_WRITABLE_FULL_RECEIPT",
    "tampered": "REJECT_REAL_READONLY_TAMPERED_SOURCE",
    "wrong-pin": "REJECT_REAL_READONLY_WRONG_PIN",
    "wrong-challenge": "REJECT_REAL_READONLY_WRONG_CHALLENGE",
}
HANDOFF_EXPECTED = {
    "valid": "PASS_REAL_READONLY_OPERATOR_HANDOFF",
    "wrong-operator-pin": "REJECT_REAL_WRONG_OPERATOR_HASH",
    "different-report": "REJECT_REAL_PINNED_OPERATOR_REPORT_MISMATCH",
}
CUSTODY_EXPECTED = {
    "valid": "PASS_REAL_READONLY_FOUR_ARTIFACT_CUSTODY",
    "wrong-index-pin": "REJECT_REAL_WRONG_CUSTODY_INDEX_PIN",
    "modified-kernel": "REJECT_REAL_MODIFIED_GUEST_KERNEL_LOG",
}
OBSERVATION_EXPECTED = {
    "valid": "PASS_REAL_READONLY_STRUCTURED_GUEST_CUSTODY",
    "wrong-index-pin": "REJECT_REAL_WRONG_OBSERVATION_INDEX_PIN",
    "different-batch": "REJECT_REAL_DIFFERENT_GUEST_OBSERVATION_BATCH",
}


def _fixture_report(repository: Path) -> dict:
    """Reuse only the existing unittest's synthetic report schema fixture."""
    sys.path.insert(0, str(repository / "tools"))
    sys.path.insert(0, str(repository / "tests"))
    from test_pe_arch_vm_evidence import PrivateNativeArchReceiptTests

    case = PrivateNativeArchReceiptTests(
        "test_s1_42_default_mode_preserves_legacy_success")
    case.setUp()
    try:
        return copy.deepcopy(case.report)
    finally:
        case.doCleanups()  # Restore SOURCE_FILES patch before issuing receipt.


def _child(mode: str, pin: str) -> int:
    # No statvfs/fstatvfs patches: the genuine Linux mount is checked by
    # verify_local_receipt / _read_source in BOTH manifest passes.
    import pe_arch_vm_evidence as evidence
    import pe_arch_vm_receipt_verify as verifier

    source_root = Path("/audit/source")
    sample = source_root / evidence.SOURCE_FILES[0]
    flags = {
        "source_root_readonly": bool(
            os.statvfs(source_root).f_flag & os.ST_RDONLY),
        "first_source_readonly": bool(
            os.statvfs(sample).f_flag & os.ST_RDONLY),
    }
    first_dir = source_root / evidence.SOURCE_FILES[0].split("/")[0]
    flags["source_subdir_readonly"] = bool(
        os.statvfs(first_dir).f_flag & os.ST_RDONLY)
    expected_flags = {
        "readonly": (True, True, True),
        "writable": (False, False, False),
        "nested-writable": (True, False, False),
        "tampered": (True, True, True),
        "wrong-pin": (True, True, True),
        "wrong-challenge": (True, True, True),
    }
    observed = tuple(flags.values())
    if observed != expected_flags[mode]:
        raise AssertionError(
            f"Kernel mount flags differ for {mode}: {flags}")
    challenge = CHALLENGE if mode != "wrong-challenge" else "f" * 64
    external_pin = pin if mode != "wrong-pin" else "f" * 64
    if external_pin == pin and mode == "wrong-pin":
        raise AssertionError("Bad pin accidentally matched the original")
    args = [
        "--receipt", "/audit/private/acceptance.json",
        "--source-root", "/audit/source",
        "--expected-challenge", challenge,
        "--expected-receipt-sha256", external_pin,
        "--require-readonly-source-view",
    ]
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = verifier.main(args)
    if mode == "readonly":
        if exit_code != 0 or stderr.getvalue():
            raise AssertionError("Valid readonly receipt CLI did not pass")
        review = json.loads(stdout.getvalue())
        if (review.get("status") != "LOCAL_RECEIPT_CONSISTENCY_VALIDATED"
                or review.get("readonly_source_view_verified") is not True
                or review.get("external_receipt_sha256_pin_matched") is not True
                or review.get("source_files_rechecked") != len(evidence.SOURCE_FILES)
                or review.get("independent_vm_attestation") is not False
                or review.get("native_kernel_execution_independently_verified") is not False):
            raise AssertionError("Readonly receipt review produced invalid claims")
    else:
        if exit_code != 2 or stdout.getvalue():
            raise AssertionError("Unsafe source/receipt unexpectedly accepted")
        failure = json.loads(stderr.getvalue())
        if failure.get("status") != "REJECTED_LOCAL_RECEIPT":
            raise AssertionError("Unsafe review did not fail closed")
        reason = failure.get("reason", "")
        required = {
            "writable": "readonly mount required",
            "nested-writable": "readonly mount required",
            "tampered": "Source does not match original acceptance",
            "wrong-pin": "independently retained SHA-256",
            "wrong-challenge": "reviewer challenge",
        }[mode]
        if required not in reason:
            raise AssertionError(f"Unexpected rejection for {mode}: {reason}")
    print(json.dumps({
        "status": CASE_EXPECTED[mode],
        "real_mount_flags": flags,
        "source_manifest_files": len(evidence.SOURCE_FILES),
        "cli_exit_code": exit_code,
        "external_pin_provided_separately": True,
        "fstatvfs_mocked": False,
        "synthetic_self_asserted_report": True,
        "windows_binary_executed": False,
        "independent_arch_vm_attestation": False,
    }, sort_keys=True))
    return 0



def _child_handoff(
        mode: str, receipt_pin: str, operator_pin: str,
        commit: str, changed_pin: str) -> int:
    import pe_arch_vm_evidence as evidence
    import pe_arch_vm_handoff_review as handoff

    if not all(
            os.statvfs(Path("/audit/source") / rel).f_flag & os.ST_RDONLY
            for rel in evidence.SOURCE_FILES):
        raise AssertionError("Full source manifest must be truly readonly")
    if not (os.statvfs("/audit/source").f_flag & os.ST_RDONLY):
        raise AssertionError("Checkout mount must be genuinely readonly")
    output_file = ("/audit/private/operator-modified.json"
                   if mode == "different-report" else
                   "/audit/private/operator.json")
    expected_pin = (
        "f" * 64 if mode == "wrong-operator-pin"
        else changed_pin if mode == "different-report" else operator_pin)
    if expected_pin == operator_pin and mode != "valid":
        raise AssertionError("Negative test cannot reuse unmodified pin")
    args = [
        "--operator-output", output_file,
        "--receipt", "/audit/private/acceptance.json",
        "--source-root", "/audit/source",
        "--expected-source-commit", commit,
        "--expected-challenge", CHALLENGE,
        "--expected-receipt-sha256", receipt_pin,
        "--expected-operator-sha256", expected_pin,
        "--require-readonly-source-view",
    ]
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = handoff.main(args)
    if mode == "valid":
        if result != 0 or stderr.getvalue():
            raise AssertionError("Genuine readonly handoff was rejected")
        review = json.loads(stdout.getvalue())
        if (review.get("status") != "LOCAL_OPERATOR_HANDOFF_CORRELATED"
                or review.get("source_files_rechecked") != len(evidence.SOURCE_FILES)
                or review.get("readonly_source_view_verified") is not True
                or review.get("independent_vm_attestation") is not False
                or review.get("native_kernel_execution_independently_verified")
                   is not False):
            raise AssertionError("Handoff produced ungrounded security claims")
    else:
        if result != 2 or stdout.getvalue():
            raise AssertionError("Unsafe operator handoff was accepted")
        review = json.loads(stderr.getvalue())
        expected_reason = (
            "externally retained SHA-256"
            if mode == "wrong-operator-pin" else
            "does not match the exact receipt report")
        if (review.get("status") != "REJECTED_LOCAL_OPERATOR_HANDOFF"
                or expected_reason not in review.get("reason", "")):
            raise AssertionError("Unexpected handoff rejection result")
    print(json.dumps({
        "status": HANDOFF_EXPECTED[mode],
        "source_manifest_files": len(evidence.SOURCE_FILES),
        "exit_code": result,
        "actual_readonly_mount": True,
        "git_real_checkout": True,
        "operator_hash_external": True,
        "receipt_hash_external": True,
        "fstatvfs_mocked": False,
        "self_reported_synthetic_fixture": True,
        "native_arch_vm_attestation": False,
        "windows_binary_executed": False,
    }, sort_keys=True))
    return 0



def _child_custody(mode: str, index_hash: str, commit: str) -> int:
    import pe_arch_vm_custody_review as custody
    import pe_arch_vm_evidence as evidence

    if not all(
            os.statvfs(Path("/audit/source") / rel).f_flag & os.ST_RDONLY
            for rel in evidence.SOURCE_FILES):
        raise AssertionError("Custody source mount is not genuinely readonly")
    selected = ("f" * 64 if mode == "wrong-index-pin" else index_hash)
    if mode == "wrong-index-pin" and selected == index_hash:
        raise AssertionError("Bad custody pin unexpectedly equals original")
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        rc = custody.main([
            "--private-dir", "/audit/private",
            "--source-root", "/audit/source",
            "--expected-custody-sha256", selected,
            "--expected-source-commit", commit,
            "--expected-challenge", CHALLENGE,
            "--require-readonly-source-view",
        ])
    if mode == "valid":
        if rc != 0 or stderr.getvalue():
            raise AssertionError("Valid readonly custody index refused")
        data = json.loads(stdout.getvalue())
        if (data.get("status") != "LOCAL_CUSTODY_PACKAGE_CORRELATED"
                or data.get("artifact_count") != 4
                or data.get("source_files_rechecked") != len(evidence.SOURCE_FILES)
                or data.get("independent_vm_attestation") is not False
                or data.get("operator_cgroup_log_authenticated") is not False
                or data.get("operator_kernel_log_authenticated") is not False):
            raise AssertionError("Custody review contains unsupported claim")
    else:
        if rc != 2 or stdout.getvalue():
            raise AssertionError("Bad custody package unexpectedly passed")
        data = json.loads(stderr.getvalue())
        required = ("independently retained SHA-256"
                    if mode == "wrong-index-pin" else
                    "pinned index")
        if (data.get("status") != "REJECTED_LOCAL_CUSTODY_PACKAGE"
                or required not in data.get("reason", "")):
            raise AssertionError("Unexpected custody rejection result")

    print(json.dumps({
        "status": CUSTODY_EXPECTED[mode],
        "cli_exit_code": rc,
        "source_manifest_files": len(evidence.SOURCE_FILES),
        "actual_readonly_mount": True,
        "four_artifacts": True,
        "git_real_checkout": True,
        "fstatvfs_mocked": False,
        "synthetic_guest_logs": True,
        "independent_arch_vm_attestation": False,
        "windows_binary_executed": False,
    }, sort_keys=True))
    return 0


def _child_observation(mode: str, pin: str, commit: str) -> int:
    import pe_arch_vm_observation_review as reviewer
    import pe_arch_vm_evidence as evidence

    if not all(
            os.statvfs(Path("/audit/source") / file).f_flag & os.ST_RDONLY
            for file in evidence.SOURCE_FILES):
        raise AssertionError("Source view in observation review is writable")
    selected_pin = "f" * 64 if mode == "wrong-index-pin" else pin
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = reviewer.main([
            "--private-dir", "/audit/private",
            "--source-root", "/audit/source",
            "--expected-custody-sha256", selected_pin,
            "--expected-source-commit", commit,
            "--expected-challenge", CHALLENGE,
            "--require-readonly-source-view",
        ])
    if mode == "valid":
        if rc != 0 or err.getvalue():
            raise AssertionError("Correct observation receipt rejected")
        data = json.loads(out.getvalue())
        if (data.get("status") != reviewer.STATUS
                or data.get("source_files_rechecked") != len(evidence.SOURCE_FILES)
                or data.get("operator_logs_authenticated") is not False
                or data.get("independent_vm_attestation") is not False):
            raise AssertionError("Observation result contains ungrounded claims")
    else:
        if rc != 2 or out.getvalue():
            raise AssertionError("Unsafe guest observation accepted")
        data = json.loads(err.getvalue())
        expected_reason = (
            "index hash differs" if mode == "wrong-index-pin"
            else "same local batch")
        if (data.get("status") != "REJECTED_GUEST_OBSERVATION_CUSTODY"
                or expected_reason not in data.get("reason", "")):
            raise AssertionError("Unsafe guest observation rejection missing")
    print(json.dumps({
        "status": OBSERVATION_EXPECTED[mode],
        "source_manifest_files": len(evidence.SOURCE_FILES),
        "actual_readonly_mount": True,
        "git_real_checkout": True,
        "fstatvfs_mocked": False,
        "synthetic_operator_reports": True,
        "independent_arch_vm_attestation": False,
        "windows_binary_executed": False,
        "cli_exit_code": rc,
    }, sort_keys=True))
    return 0


def _host(ghidra_home: Path, *, run_handoff: bool = False,
          run_custody: bool = False, run_observation: bool = False) -> int:
    repository = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository / "tools"))
    import pe_arch_vm_evidence as evidence
    from pe_ghidra_sandbox import build_command

    if os.geteuid() == 0 or not shutil.which("bwrap"):
        raise RuntimeError("Real unprivileged Bubblewrap required (no fallback)")
    with tempfile.TemporaryDirectory(prefix="negresco-pe-s1-44-") as tmp:
        root = Path(tmp)
        source = root / "source"
        for rel in evidence.SOURCE_FILES:
            src = repository / rel
            dst = source / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        alternate = root / "tampered"
        for rel in evidence.SOURCE_FILES:
            src = source / rel
            dst = alternate / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        changed = alternate / evidence.SOURCE_FILES[0]
        original = changed.read_bytes()
        if not original:
            raise AssertionError("Empty fixture source unexpectedly allowed")
        changed.write_bytes(bytes([original[0] ^ 1]) + original[1:])

        if run_handoff or run_custody or run_observation:
            if not shutil.which("git"):
                raise RuntimeError("Real Git unavailable; no handoff fallback")
            for command in (
                    ("init", "-q"),
                    ("config", "user.name", "Synthetic CI Reviewer"),
                    ("config", "user.email", "fixture@example.invalid"),
                    ("add", "--all"),
                    ("commit", "-qm", "Synthetic evidence-only checkout")):
                subprocess.run(
                    ["git", "-C", str(source), *command],
                    stdin=subprocess.DEVNULL, capture_output=True,
                    timeout=20, check=True, close_fds=True)
            head = subprocess.run(
                ["git", "-C", str(source), "rev-parse", "HEAD"],
                stdin=subprocess.DEVNULL, capture_output=True,
                text=True, timeout=10, check=True).stdout.strip()
        overlay = root / "writable-tools"
        shutil.copytree(source / "tools", overlay)
        private = root / "private"
        private.mkdir(mode=0o700)
        dest = private / "acceptance.json"
        native_report = _fixture_report(repository)
        receipt = evidence.write_receipt_no_overwrite(
            native_report, dest, source_root=source,
            reviewer_challenge=CHALLENGE)
        observed_digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        if receipt["receipt_sha256"] != observed_digest:
            raise RuntimeError("Published receipt digest differs from host pin")
        if dest.stat().st_nlink != 1:
            raise RuntimeError("Published private receipt is not a unique link")

        if run_handoff or run_custody or run_observation:
            from pe_arch_vm_checkout_pin import verify_source_checkout_pin
            local_pin = verify_source_checkout_pin(
                source, head, evidence.SOURCE_FILES)
            operator = {
                **native_report, "local_receipt": receipt,
                "local_source_checkout_pin": local_pin}
            operator_file = private / "operator.json"
            operator_file.write_bytes((
                json.dumps(operator, sort_keys=True, separators=(",", ":"))
                + "\n").encode("utf-8"))
            operator_file.chmod(0o600)
            operator_hash = hashlib.sha256(operator_file.read_bytes()).hexdigest()
            corrupted_report = copy.deepcopy(operator)
            corrupted_report["ghidra"]["ghidra_functions"] += 1
            corrupted_file = private / "operator-modified.json"
            corrupted_file.write_bytes((
                json.dumps(corrupted_report, sort_keys=True, separators=(",", ":"))
                + "\n").encode("utf-8"))
            corrupted_file.chmod(0o600)
            changed_hash = hashlib.sha256(corrupted_file.read_bytes()).hexdigest()


        if run_custody or run_observation:
            import pe_arch_vm_custody_review as custody
            # The production handoff name is fixed by the custody schema.
            (private / "operator-run-output.json").write_bytes(
                operator_file.read_bytes())
            (private / "operator-run-output.json").chmod(0o600)
            guest_kernel = private / "guest-kernel-observation.txt"
            guest_cgroup = private / "guest-cgroup-observation.txt"
            guest_kernel.write_bytes(b"synthetic guest uname (untrusted)\\n".replace(
                b"\\n", b"\n"))
            guest_cgroup.write_bytes(
                b"synthetic guest systemd cgroup (untrusted)\\n".replace(
                    b"\\n", b"\n"))
            guest_kernel.chmod(0o600)
            guest_cgroup.chmod(0o600)

            if run_observation:
                # These are explicitly SYNTHETIC guest logs and do not come
                # from a native Arch VM or systemd. Match PE-S1.52 schema.
                stamp = "2026-10-30T04:00:00+00:00"
                common = {
                    "classification":
                        "OPERATOR_SELF_REPORTED_NATIVE_ARCH_OBSERVATION_NOT_ATTESTED",
                    "source_commit": head,
                    "reviewer_challenge": CHALLENGE,
                    "operator_observed_at_utc_not_attested": stamp,
                    "native_arch_vm_gate_local_pass": True,
                    "independent_vm_attestation": False,
                    "native_kernel_execution_independently_verified": False,
                    "real_cgroup_limits_or_cleanup_tested_by_this_command": False,
                    "windows_binary_executed": False,
                }
                guest_kernel.write_bytes((json.dumps({
                    **common,
                    "artifact": "guest_kernel_observation",
                    "kernel_release": "6.15.2-arch1-1",
                    "kernel_machine": "x86_64",
                    "pid1_comm": "systemd",
                    "systemd_version_first_line": "systemd 258",
                    "virtualization_reported_by_local_systemd": "kvm",
                }, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
                guest_cgroup.write_bytes((json.dumps({
                    **common,
                    "artifact": "guest_cgroup_observation",
                    "cgroup_v2_controllers_available": [
                        "cpu", "io", "memory", "pids"],
                    "cgroup_v2_root_subtree_control": ["cpu", "memory", "pids"],
                    "systemd_user_control_group_locally_observed":
                        "/user.slice/user-1000.slice/user@1000.service",
                    "cgroup_quotas_verified_by_this_command": False,
                    "cgroup_descendant_cleanup_verified_by_this_command": False,
                }, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))

            index_path = private / "reviewer-custody-index.json"
            record = {
                "schema": custody.SCHEMA,
                "security_classification": custody.CLASSIFICATION,
                "source_commit": head,
                "reviewer_challenge": CHALLENGE,
                "artifacts": {
                    label: {
                        "filename": name,
                        "sha256": hashlib.sha256(
                            (private / name).read_bytes()).hexdigest(),
                    }
                    for label, name in custody.ARTIFACT_NAMES.items()
                },
            }
            index_path.write_bytes((
                json.dumps(record, sort_keys=True, separators=(",", ":"))
                + "\n").encode("utf-8"))
            index_path.chmod(0o600)
            custody_pin = hashlib.sha256(index_path.read_bytes()).hexdigest()

        work = root / "work"
        (work / "scripts").mkdir(parents=True, mode=0o700)
        (work / "project").mkdir(mode=0o700)
        shutil.copyfile(
            repository / "tools/ghidra_scripts/NegrescoFunctionInventory.java",
            work / "scripts/NegrescoFunctionInventory.java")
        shutil.copyfile(__file__, work / "readonly_receipt_smoke.py")
        code = root / "code"
        code.mkdir()
        # These modules are direct dependencies of pe_arch_vm_evidence.
        # Expose only the smallest explicit reviewed module set, not the
        # working checkout or host Python module search path.
        for module in ("pe_arch_vm_receipt_verify.py", "pe_arch_vm_evidence.py",
                       "pe_arch_vm_checkout_pin.py", "pe_arch_vm_handoff_review.py",
                       "pe_arch_vm_custody_review.py",
                       "pe_arch_vm_observation_review.py",
                       "pe_nofollow_paths.py", "pe_ghidra_integrity.py",
                       "pe_resource_limits.py"):
            shutil.copyfile(repository / "tools" / module, code / module)

        base = build_command(ghidra_home, work, 120)
        boundary = base.index("--")

        if run_handoff:
            for mode in HANDOFF_EXPECTED:
                mounts = [
                    "--dir", "/audit",
                    "--ro-bind", str(code), "/audit/code",
                    "--ro-bind", str(source), "/audit/source",
                    "--ro-bind", str(private), "/audit/private",
                    "--setenv", "PYTHONPATH", "/audit/code",
                    "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                ]
                argv = base[:boundary] + mounts + [
                    "--", "/usr/bin/python3", "/work/readonly_receipt_smoke.py",
                    "--child-handoff", mode,
                    "--pin", observed_digest,
                    "--operator-pin", operator_hash,
                    "--changed-operator-pin", changed_hash,
                    "--commit", head,
                ]
                run = subprocess.run(
                    argv, stdin=subprocess.DEVNULL, capture_output=True,
                    text=True, timeout=90, check=False, close_fds=True)
                if run.returncode != 0:
                    raise RuntimeError(
                        f"Real Bubblewrap handoff {mode} did not fail closed: "
                        f"rc={run.returncode}, stderr={run.stderr[-1700:]!r}, "
                        f"stdout={run.stdout[-1700:]!r}")
                record = json.loads(run.stdout.strip())
                if (record.get("status") != HANDOFF_EXPECTED[mode]
                        or record.get("source_manifest_files")
                           != len(evidence.SOURCE_FILES)
                        or record.get("actual_readonly_mount") is not True
                        or record.get("git_real_checkout") is not True
                        or record.get("fstatvfs_mocked") is not False
                        or record.get("native_arch_vm_attestation") is not False
                        or record.get("windows_binary_executed") is not False):
                    raise RuntimeError("Incomplete real handoff review evidence")
                print(json.dumps(record, sort_keys=True), flush=True)
            print(json.dumps({
                "status": "PASS_PE_S1_47_REAL_READONLY_HANDOFF",
                "cases": len(HANDOFF_EXPECTED),
                "real_readonly_handoff_accepted": True,
                "wrong_operator_pin_rejected": True,
                "operator_report_mismatch_rejected": True,
                "git_real_checkout": True,
                "fstatvfs_mocked": False,
                "native_arch_vm_attestation": False,
                "windows_binary_executed": False,
            }, sort_keys=True))
            return 0

        if run_custody:
            for mode in CUSTODY_EXPECTED:
                if mode == "modified-kernel":
                    guest_kernel.write_bytes(b"tampered guest log after pin\\n".replace(
                        b"\\n", b"\n"))
                mounts = [
                    "--dir", "/audit",
                    "--ro-bind", str(code), "/audit/code",
                    "--ro-bind", str(source), "/audit/source",
                    "--ro-bind", str(private), "/audit/private",
                    "--setenv", "PYTHONPATH", "/audit/code",
                    "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                ]
                argv = base[:boundary] + mounts + [
                    "--", "/usr/bin/python3", "/work/readonly_receipt_smoke.py",
                    "--child-custody", mode,
                    "--custody-pin", custody_pin,
                    "--commit", head,
                ]
                run = subprocess.run(
                    argv, stdin=subprocess.DEVNULL, capture_output=True,
                    text=True, timeout=90, check=False, close_fds=True)
                if run.returncode != 0:
                    raise RuntimeError(
                        f"Real custody {mode} test failed closed: "
                        f"rc={run.returncode}, stderr={run.stderr[-1300:]!r}, "
                        f"stdout={run.stdout[-1300:]!r}")
                record = json.loads(run.stdout.strip())
                if (record.get("status") != CUSTODY_EXPECTED[mode]
                        or record.get("source_manifest_files")
                           != len(evidence.SOURCE_FILES)
                        or record.get("actual_readonly_mount") is not True
                        or record.get("four_artifacts") is not True
                        or record.get("git_real_checkout") is not True
                        or record.get("fstatvfs_mocked") is not False
                        or record.get("synthetic_guest_logs") is not True
                        or record.get("independent_arch_vm_attestation") is not False
                        or record.get("windows_binary_executed") is not False):
                    raise RuntimeError("Missing real custody evidence: " + mode)
                print(json.dumps(record, sort_keys=True), flush=True)
            print(json.dumps({
                "status": "PASS_PE_S1_48_REAL_READONLY_CUSTODY",
                "cases": len(CUSTODY_EXPECTED),
                "real_custody_valid": True,
                "external_index_sha256_mismatch_rejected": True,
                "tampered_guest_log_rejected": True,
                "fstatvfs_mocked": False,
                "native_arch_vm_attestation": False,
                "windows_binary_executed": False,
            }, sort_keys=True))
            return 0

        if run_observation:
            for mode in OBSERVATION_EXPECTED:
                if mode == "different-batch":
                    # Re-pin the modified index as if a dishonest operator
                    # recomputed every SHA. Strict cross-batch validation
                    # must still reject mismatched timestamps.
                    changed = json.loads(guest_cgroup.read_text("utf-8"))
                    changed["operator_observed_at_utc_not_attested"] = (
                        "2026-10-29T04:00:00+00:00")
                    guest_cgroup.write_bytes((
                        json.dumps(changed, sort_keys=True, separators=(",", ":"))
                        + "\n").encode("utf-8"))
                    record["artifacts"]["guest_cgroup_observation"]["sha256"] = (
                        hashlib.sha256(guest_cgroup.read_bytes()).hexdigest())
                    index_path.write_bytes((
                        json.dumps(record, sort_keys=True, separators=(",", ":"))
                        + "\n").encode("utf-8"))
                    custody_pin = hashlib.sha256(index_path.read_bytes()).hexdigest()
                mounts = [
                    "--dir", "/audit",
                    "--ro-bind", str(code), "/audit/code",
                    "--ro-bind", str(source), "/audit/source",
                    "--ro-bind", str(private), "/audit/private",
                    "--setenv", "PYTHONPATH", "/audit/code",
                    "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                ]
                argv = base[:boundary] + mounts + [
                    "--", "/usr/bin/python3", "/work/readonly_receipt_smoke.py",
                    "--child-observation", mode, "--custody-pin", custody_pin,
                    "--commit", head,
                ]
                process = subprocess.run(
                    argv, stdin=subprocess.DEVNULL, capture_output=True,
                    text=True, timeout=90, check=False, close_fds=True)
                if process.returncode != 0:
                    raise RuntimeError(
                        f"PE-S1.53 real readonly observation {mode} failed: "
                        f"rc={process.returncode}, "
                        f"stderr={process.stderr[-1800:]!r}, "
                        f"stdout={process.stdout[-1800:]!r}")
                proof = json.loads(process.stdout.strip())
                if (proof.get("status") != OBSERVATION_EXPECTED[mode]
                        or proof.get("source_manifest_files")
                           != len(evidence.SOURCE_FILES)
                        or proof.get("actual_readonly_mount") is not True
                        or proof.get("git_real_checkout") is not True
                        or proof.get("fstatvfs_mocked") is not False
                        or proof.get("synthetic_operator_reports") is not True
                        or proof.get("independent_arch_vm_attestation") is not False
                        or proof.get("windows_binary_executed") is not False):
                    raise RuntimeError(
                        "Missing actual Bubblewrap observation check")
                print(json.dumps(proof, sort_keys=True), flush=True)
            print(json.dumps({
                "status": "PASS_PE_S1_53_REAL_READONLY_OBSERVATION_CUSTODY",
                "cases": len(OBSERVATION_EXPECTED),
                "rehashed_mismatched_batch_rejected": True,
                "external_index_pin_mismatch_rejected": True,
                "valid_structured_observation_accepted": True,
                "fstatvfs_mocked": False,
                "native_arch_vm_attestation": False,
                "windows_binary_executed": False,
            }, sort_keys=True))
            return 0
        proofs = []
        for mode in CASE_EXPECTED:
            chosen = alternate if mode == "tampered" else source
            mount_type = "--bind" if mode == "writable" else "--ro-bind"
            mounts = [
                "--dir", "/audit",
                "--ro-bind", str(code), "/audit/code",
                mount_type, str(chosen), "/audit/source",
                "--ro-bind", str(private), "/audit/private",
            ]
            if mode == "nested-writable":
                mounts.extend([
                    "--bind", str(overlay), "/audit/source/tools"])
            mounts.extend([
                "--setenv", "PYTHONPATH", "/audit/code",
                "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            ])
            argv = base[:boundary] + mounts + [
                "--", "/usr/bin/python3", "/work/readonly_receipt_smoke.py",
                "--child", mode, "--pin", observed_digest,
            ]
            run = subprocess.run(
                argv, stdin=subprocess.DEVNULL, capture_output=True,
                text=True, timeout=80, check=False, close_fds=True)
            if run.returncode != 0:
                raise RuntimeError(
                    f"Actual full receipt {mode} failed closed "
                    f"rc={run.returncode} stdout={run.stdout[-1400:]!r} "
                    f"stderr={run.stderr[-1400:]!r}")
            proof = json.loads(run.stdout.strip())
            if (proof.get("status") != CASE_EXPECTED[mode]
                    or proof.get("source_manifest_files") != len(evidence.SOURCE_FILES)
                    or proof.get("external_pin_provided_separately") is not True
                    or proof.get("fstatvfs_mocked") is not False
                    or proof.get("synthetic_self_asserted_report") is not True
                    or proof.get("windows_binary_executed") is not False
                    or proof.get("independent_arch_vm_attestation") is not False):
                raise RuntimeError(f"Missing or malformed proof for {mode}")
            proofs.append(proof)
            print(json.dumps(proof, sort_keys=True), flush=True)
        print(json.dumps({
            "status": "PASS_PE_S1_44_REAL_READONLY_FULL_RECEIPT",
            "cases": len(proofs),
            "real_readonly_receipt_approved": True,
            "real_writable_source_rejected": True,
            "real_nested_writable_source_rejected": True,
            "real_readonly_tampered_source_rejected": True,
            "real_wrong_external_pin_rejected": True,
            "real_wrong_challenge_rejected": True,
            "fstatvfs_mocked": False,
            "native_arch_vm_attestation": False,
            "windows_binary_executed": False,
        }, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ghidra-home", type=Path)
    parser.add_argument("--child", choices=tuple(CASE_EXPECTED))
    parser.add_argument("--child-handoff", choices=tuple(HANDOFF_EXPECTED))
    parser.add_argument("--child-custody", choices=tuple(CUSTODY_EXPECTED))
    parser.add_argument("--child-observation", choices=tuple(OBSERVATION_EXPECTED))
    parser.add_argument("--run-handoff", action="store_true")
    parser.add_argument("--run-custody", action="store_true")
    parser.add_argument("--run-observation", action="store_true")
    parser.add_argument("--custody-pin")
    parser.add_argument("--pin")
    parser.add_argument("--operator-pin")
    parser.add_argument("--changed-operator-pin")
    parser.add_argument("--commit")
    args = parser.parse_args()
    if args.child_observation:
        if not args.custody_pin or not args.commit:
            parser.error("Observation child needs external index pin and commit")
        return _child_observation(
            args.child_observation, args.custody_pin, args.commit)
    if args.child_custody:
        if not args.custody_pin or not args.commit:
            parser.error("--custody-pin and --commit required")
        return _child_custody(args.child_custody, args.custody_pin, args.commit)
    if args.child_handoff:
        if not all((args.pin, args.operator_pin, args.changed_operator_pin,
                    args.commit)):
            parser.error("Both external pins and commit required")
        return _child_handoff(
            args.child_handoff, args.pin, args.operator_pin,
            args.commit, args.changed_operator_pin)
    if args.child:
        if not args.pin:
            parser.error("--pin required for the child reviewer")
        return _child(args.child, args.pin)
    if args.ghidra_home is None:
        parser.error("--ghidra-home required for the real mount test")
    if sum((args.run_handoff, args.run_custody, args.run_observation)) > 1:
        parser.error("Select one integration probe at a time")
    return _host(
        args.ghidra_home, run_handoff=args.run_handoff,
        run_custody=args.run_custody, run_observation=args.run_observation)


if __name__ == "__main__":
    raise SystemExit(main())
