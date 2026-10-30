#!/usr/bin/env python3
"""PE-S1.55: signed PE-S1.54 CLI inside a REAL readonly Bubblewrap mount.

Every input is deliberately synthetic. OpenSSH creates two disposable
Ed25519 signers outside the sandbox, which only receives public keys and
signatures. Git and readonly mount checks run for real inside Bubblewrap.
No host Arch VM, Ghidra execution, hostile PE, or key generation in sandbox.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
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
WITNESS_ID = "independent-reviewer@example.invalid"
REVIEWER_ID = "policy-approver@example.invalid"
MODES = (
    "valid", "wrong-index-pin", "rehashed-without-resigning",
    "reviewer-signature-tampered-repinned", "writable-source",
)
STATUSES = {
    "valid": "PASS_PE_S1_55_REAL_READONLY_DUAL_ED25519",
    "wrong-index-pin": "REJECT_PE_S1_55_WRONG_EXTERNAL_INDEX_PIN",
    "rehashed-without-resigning": "REJECT_PE_S1_55_REHASHED_LOG_WITHOUT_SIGNATURE",
    "reviewer-signature-tampered-repinned":
        "REJECT_PE_S1_55_TAMPERED_REVIEWER_SIGNATURE",
    "writable-source": "REJECT_PE_S1_55_WRITABLE_SOURCE",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def publish(path: Path, data: dict) -> None:
    path.write_bytes((json.dumps(data, sort_keys=True, separators=(",", ":"),
                                allow_nan=False) + "\n").encode("utf-8"))
    path.chmod(0o600)


def _cmd(argv: list[str], timeout: int = 20) -> str:
    run = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                         text=True, timeout=timeout, check=True,
                         close_fds=True)
    return run.stdout.strip()


def _sign(key: Path, namespace: str, source: Path, dest: Path) -> None:
    _cmd(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", namespace,
          str(source)])
    signed = source.with_suffix(source.suffix + ".sig")
    signed.replace(dest)
    dest.chmod(0o600)


def _child(mode: str) -> int:
    # Imports intentionally only inside the jailed process. Never mock
    # Git, OpenSSH verification, fstatvfs or the reviewer's CLI.
    import pe_arch_vm_end_to_end_review as full
    import pe_arch_vm_evidence as evidence

    source = Path("/audit/source")
    private = Path("/audit/private")
    source_flags = [bool(os.statvfs(source / f).f_flag & os.ST_RDONLY)
                    for f in evidence.SOURCE_FILES]
    source_ro = bool(os.statvfs(source).f_flag & os.ST_RDONLY)
    private_ro = bool(os.statvfs(private).f_flag & os.ST_RDONLY)
    code_ro = bool(os.statvfs("/audit/code").f_flag & os.ST_RDONLY)
    should_be_ro = mode != "writable-source"
    if (not private_ro or not code_ro or not source_flags
            or source_ro != should_be_ro
            or any(flag != should_be_ro for flag in source_flags)):
        raise RuntimeError("Actual kernel readonly flags do not match case")

    pins = json.loads(Path("/work/test-pins.json").read_text("utf-8"))
    if mode == "wrong-index-pin":
        pins["expected_custody_sha256"] = "f" * 64
        if pins["expected_custody_sha256"] == pins["original_custody_sha256"]:
            raise RuntimeError("Invalid test did not change external pin")
    pins.pop("original_custody_sha256")
    args = ["--private-dir", str(private), "--source-root", str(source)]
    for key, value in pins.items():
        args.extend(["--" + key.replace("_", "-"), str(value)])
    args.append("--require-readonly-source-view")

    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = full.main(args)
    valid = mode == "valid"
    if valid:
        if rc != 0 or err.getvalue():
            raise RuntimeError("Signed readonly CLI unexpectedly rejected: " +
                               err.getvalue()[-900:])
        result = json.loads(out.getvalue())
        if (result.get("status") != full.STATUS
                or result.get("source_files_rechecked") != len(evidence.SOURCE_FILES)
                or result.get("readonly_source_view_verified") is not True
                or result.get("structured_guest_logs_consistent_with_custody") is not True
                or result.get("separate_reviewer_and_witness_signatures_verified") is not True
                or result.get("operator_clock_independently_verified") is not False
                or result.get("operator_logs_authenticated") is not False
                or result.get("independent_vm_attestation") is not False):
            raise RuntimeError("Missing verified readonly/dual-signature proof")
    else:
        if rc != 2 or out.getvalue():
            raise RuntimeError("Negative scenario unexpectedly accepted")
        rejected = json.loads(err.getvalue())
        if (rejected.get("status") != "REJECTED_SIGNED_GUEST_CUSTODY_REVIEW"
                or rejected.get("independent_vm_attestation") is not False):
            raise RuntimeError("Expected fail-closed reviewer rejection")
    print(json.dumps({
        "status": STATUSES[mode], "reviewer_cli_exit_code": rc,
        "source_manifest_files": len(evidence.SOURCE_FILES),
        "source_mount_readonly": source_ro,
        "private_mount_readonly": private_ro,
        "reviewer_code_mount_readonly": code_ro,
        "real_git_checkout_verified_by_cli": valid,
        "two_real_disposable_ed25519_signers_verified": valid,
        "ssh_verifier_mocked": False, "git_verifier_mocked": False,
        "fstatvfs_mocked": False, "synthetic_operator_logs": True,
        "native_arch_vm_attestation": False, "windows_binary_executed": False,
    }, sort_keys=True))
    return 0


def _host(ghidra_home: Path) -> int:
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "tools"))
    from pe_ghidra_sandbox import build_command
    import pe_arch_vm_evidence as evidence
    import pe_arch_vm_custody_review as custody
    import pe_arch_vm_witness_review as witness
    import pe_arch_vm_witness_trust_review as trust
    import pe_arch_vm_dual_control_review as dual
    from pe_arch_vm_checkout_pin import verify_source_checkout_pin
    from pe_readonly_receipt_real_ci import _fixture_report

    if os.geteuid() == 0:
        raise RuntimeError("Refuse to claim real unprivileged sandbox as root")
    for program in ("bwrap", "git", "ssh-keygen"):
        if not shutil.which(program):
            raise RuntimeError("Required real executable unavailable: " + program)

    with tempfile.TemporaryDirectory(prefix="negresco-pe-s1-55-") as name:
        root = Path(name)
        source = root / "source"
        for rel in evidence.SOURCE_FILES:
            dest = source / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / rel, dest)
        for sub in (["init", "-q"],
                    ["config", "user.name", "Synthetic CI Reviewer"],
                    ["config", "user.email", "test@example.invalid"],
                    ["add", "--all"],
                    ["commit", "-qm", "Synthetic local source snapshot"]):
            _cmd(["git", "-C", str(source), *sub])
        commit = _cmd(["git", "-C", str(source), "rev-parse", "HEAD"])
        git_pin = verify_source_checkout_pin(source, commit, evidence.SOURCE_FILES)

        private = root / "private"
        private.mkdir(mode=0o700)
        report = _fixture_report(repo)
        receipt = evidence.write_receipt_no_overwrite(
            report, private / "acceptance.json",
            source_root=source, reviewer_challenge=CHALLENGE)
        operator = {
            **report, "local_receipt": receipt,
            "local_source_checkout_pin": git_pin,
        }
        publish(private / "operator-run-output.json", operator)
        stamp = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        common = {
            "classification":
                "OPERATOR_SELF_REPORTED_NATIVE_ARCH_OBSERVATION_NOT_ATTESTED",
            "source_commit": commit, "reviewer_challenge": CHALLENGE,
            "operator_observed_at_utc_not_attested": stamp,
            "native_arch_vm_gate_local_pass": True,
            "independent_vm_attestation": False,
            "native_kernel_execution_independently_verified": False,
            "real_cgroup_limits_or_cleanup_tested_by_this_command": False,
            "windows_binary_executed": False,
        }
        publish(private / "guest-kernel-observation.txt", {
            **common, "artifact": "guest_kernel_observation",
            "kernel_release": "6.15.2-arch1-1", "kernel_machine": "x86_64",
            "pid1_comm": "systemd", "systemd_version_first_line": "systemd 258",
            "virtualization_reported_by_local_systemd": "kvm",
        })
        publish(private / "guest-cgroup-observation.txt", {
            **common, "artifact": "guest_cgroup_observation",
            "cgroup_v2_controllers_available": ["cpu", "io", "memory", "pids"],
            "cgroup_v2_root_subtree_control": ["cpu", "memory", "pids"],
            "systemd_user_control_group_locally_observed":
                "/user.slice/user-1000.slice/user@1000.service",
            "cgroup_quotas_verified_by_this_command": False,
            "cgroup_descendant_cleanup_verified_by_this_command": False,
        })
        index_path = private / "reviewer-custody-index.json"
        index = {
            "schema": custody.SCHEMA,
            "security_classification": custody.CLASSIFICATION,
            "source_commit": commit, "reviewer_challenge": CHALLENGE,
            "artifacts": {
                label: {
                    "filename": filename,
                    "sha256": sha((private / filename).read_bytes()),
                }
                for label, filename in custody.ARTIFACT_NAMES.items()
            },
        }
        publish(index_path, index)
        witness_statement = {
            "schema": witness.SCHEMA,
            "security_classification": witness.CLASSIFICATION,
            "witness_id": WITNESS_ID, "source_commit": commit,
            "reviewer_challenge": CHALLENGE,
            "custody_index_sha256": sha(index_path.read_bytes()),
            "acknowledgement_utc": stamp, "vm_attestation_claimed": False,
        }
        witness_path = private / witness.FILES["statement"]
        publish(witness_path, witness_statement)
        key_dir = root / "secret-keys-not-mounted"
        key_dir.mkdir(mode=0o700)
        def new_key(name: str, principal: str, output: Path) -> Path:
            key = key_dir / name
            _cmd(["ssh-keygen", "-q", "-t", "ed25519", "-N", "",
                  "-f", str(key)])
            public = key.with_suffix(".pub").read_text("ascii").split()
            output.write_text(
                principal + " " + public[0] + " " + public[1] + "\n",
                encoding="ascii")
            output.chmod(0o600)
            return key

        witness_signers = private / witness.FILES["allowed_signers"]
        witness_key = new_key("witness-ci-only", WITNESS_ID, witness_signers)
        _sign(witness_key, witness.NAMESPACE, witness_path,
              private / witness.FILES["signature"])
        reviewer_signers = private / dual.REVIEWER_SIGNERS
        reviewer_key = new_key("approver-ci-only", REVIEWER_ID, reviewer_signers)
        policy_path = private / trust.TRUST_FILENAME
        publish(policy_path, {
            "schema": trust.SCHEMA,
            "security_classification": trust.CLASSIFICATION,
            "witness_id": WITNESS_ID,
            "signature_namespace": witness.NAMESPACE,
            "policy_revision": 1, "decision": "ACTIVE",
            "active_public_key_sha256": sha(trust._public_key_blob(
                witness_signers.read_bytes(), WITNESS_ID)),
            "revoked_public_key_sha256": [],
        })
        _sign(reviewer_key, dual.NAMESPACE, policy_path,
              private / dual.REVIEWER_SIGNATURE)
        pins = {
            "expected_policy_sha256": sha(policy_path.read_bytes()),
            "expected_policy_revision": 1,
            "expected_reviewer_signers_sha256": sha(reviewer_signers.read_bytes()),
            "expected_reviewer_signature_sha256":
                sha((private / dual.REVIEWER_SIGNATURE).read_bytes()),
            "expected_reviewer_id": REVIEWER_ID,
            "expected_custody_sha256": sha(index_path.read_bytes()),
            "expected_statement_sha256": sha(witness_path.read_bytes()),
            "expected_signature_sha256":
                sha((private / witness.FILES["signature"]).read_bytes()),
            "expected_signers_sha256": sha(witness_signers.read_bytes()),
            "expected_source_commit": commit,
            "expected_challenge": CHALLENGE,
            "expected_witness_id": WITNESS_ID,
        }
        pins["original_custody_sha256"] = pins["expected_custody_sha256"]

        work = root / "work"
        (work / "scripts").mkdir(parents=True, mode=0o700)
        (work / "project").mkdir(mode=0o700)
        shutil.copyfile(repo / "tools/ghidra_scripts/NegrescoFunctionInventory.java",
                        work / "scripts/NegrescoFunctionInventory.java")
        shutil.copyfile(__file__, work / "pe_signed_review_smoke.py")
        code = root / "code"
        code.mkdir(mode=0o700)
        for rel in evidence.SOURCE_FILES:
            if rel.startswith("tools/") and rel.endswith(".py"):
                shutil.copyfile(repo / rel, code / Path(rel).name)

        base = build_command(ghidra_home, work, 120)
        before_command = base.index("--")
        for mode in MODES:
            case_private = root / ("private-" + mode)
            shutil.copytree(private, case_private)
            case_pins = dict(pins)
            if mode == "rehashed-without-resigning":
                target = case_private / "guest-kernel-observation.txt"
                doc = json.loads(target.read_text("utf-8"))
                doc["kernel_release"] = "6.15.3-arch1-1"
                publish(target, doc)
                adjusted = json.loads(
                    (case_private / index_path.name).read_text("utf-8"))
                adjusted["artifacts"]["guest_kernel_observation"]["sha256"] = (
                    sha(target.read_bytes()))
                publish(case_private / index_path.name, adjusted)
                case_pins["expected_custody_sha256"] = sha(
                    (case_private / index_path.name).read_bytes())
                # Deliberately do not update or re-sign witness statement.
            if mode == "reviewer-signature-tampered-repinned":
                signature = case_private / dual.REVIEWER_SIGNATURE
                original = signature.read_bytes()
                if b"BEGIN" not in original:
                    raise RuntimeError("Cannot create meaningful signature tamper")
                signature.write_bytes(original.replace(b"BEGIN", b"FAKED", 1))
                signature.chmod(0o600)
                case_pins["expected_reviewer_signature_sha256"] = sha(
                    signature.read_bytes())
            (work / "test-pins.json").write_text(
                json.dumps(case_pins, sort_keys=True), encoding="ascii")
            (work / "test-pins.json").chmod(0o600)
            source_flag = "--bind" if mode == "writable-source" else "--ro-bind"
            argv = base[:before_command] + [
                "--dir", "/audit",
                "--ro-bind", str(code), "/audit/code",
                source_flag, str(source), "/audit/source",
                "--ro-bind", str(case_private), "/audit/private",
                "--setenv", "PYTHONPATH", "/audit/code",
                "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                "--", "/usr/bin/python3", "/work/pe_signed_review_smoke.py",
                "--child", mode,
            ]
            proc = subprocess.run(
                argv, stdin=subprocess.DEVNULL, capture_output=True,
                text=True, timeout=150, check=False, close_fds=True)
            if proc.returncode:
                raise RuntimeError(
                    "Real Bubblewrap signed review failed: " + mode +
                    " rc=" + str(proc.returncode) +
                    " stderr=" + proc.stderr[-1800:] +
                    " stdout=" + proc.stdout[-1800:])
            proof = json.loads(proc.stdout.strip())
            if (proof.get("status") != STATUSES[mode]
                    or proof.get("private_mount_readonly") is not True
                    or proof.get("reviewer_code_mount_readonly") is not True
                    or proof.get("source_manifest_files") != len(evidence.SOURCE_FILES)
                    or proof.get("fstatvfs_mocked") is not False
                    or proof.get("git_verifier_mocked") is not False
                    or proof.get("ssh_verifier_mocked") is not False
                    or proof.get("native_arch_vm_attestation") is not False
                    or proof.get("windows_binary_executed") is not False):
                raise RuntimeError("Unsigned/incomplete kernel integration evidence")
            print(json.dumps(proof, sort_keys=True), flush=True)
        print(json.dumps({
            "status": "PASS_PE_S1_55_REAL_READONLY_SIGNED_REVIEW_INTEGRATION",
            "cases": len(MODES), "real_bubblewrap": True,
            "real_git": True, "real_openssh_two_ed25519_keys": True,
            "source_and_private_readonly": True,
            "negative_cases_rejected": len(MODES) - 1,
            "mocked_git_or_crypto": False,
            "independent_arch_vm_attestation": False,
            "windows_binary_executed": False,
        }, sort_keys=True))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ghidra-home", type=Path)
    p.add_argument("--child", choices=MODES)
    args = p.parse_args()
    if args.child:
        return _child(args.child)
    if args.ghidra_home is None:
        p.error("--ghidra-home is required")
    return _host(args.ghidra_home)


if __name__ == "__main__":
    raise SystemExit(main())
