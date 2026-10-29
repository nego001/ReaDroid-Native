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


def _host(ghidra_home: Path) -> int:
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

        overlay = root / "writable-tools"
        shutil.copytree(source / "tools", overlay)
        private = root / "private"
        private.mkdir(mode=0o700)
        dest = private / "acceptance.json"
        receipt = evidence.write_receipt_no_overwrite(
            _fixture_report(repository), dest, source_root=source,
            reviewer_challenge=CHALLENGE)
        observed_digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        if receipt["receipt_sha256"] != observed_digest:
            raise RuntimeError("Published receipt digest differs from host pin")
        if dest.stat().st_nlink != 1:
            raise RuntimeError("Published private receipt is not a unique link")

        work = root / "work"
        (work / "scripts").mkdir(parents=True, mode=0o700)
        (work / "project").mkdir(mode=0o700)
        shutil.copyfile(
            repository / "tools/ghidra_scripts/NegrescoFunctionInventory.java",
            work / "scripts/NegrescoFunctionInventory.java")
        shutil.copyfile(__file__, work / "readonly_receipt_smoke.py")
        code = root / "code"
        code.mkdir()
        for module in ("pe_arch_vm_receipt_verify.py", "pe_arch_vm_evidence.py",
                       "pe_nofollow_paths.py"):
            shutil.copyfile(repository / "tools" / module, code / module)

        base = build_command(ghidra_home, work, 120)
        boundary = base.index("--")
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
    parser.add_argument("--pin")
    args = parser.parse_args()
    if args.child:
        if not args.pin:
            parser.error("--pin required for the child reviewer")
        return _child(args.child, args.pin)
    if args.ghidra_home is None:
        parser.error("--ghidra-home required for the real mount test")
    return _host(args.ghidra_home)


if __name__ == "__main__":
    raise SystemExit(main())
