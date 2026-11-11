#!/usr/bin/env python3
"""PE-S2.20: REAL readonly mount/Git/receipt + REAL V1/V2/V3 SSH signatures.

Host-side fixture preparation uses MOCKED libvirt counters and a SYNTHETIC
native acceptance report. Inside the actual unprivileged Bubblewrap child,
NONE of the signature, Git, receipt, filesystem-stat or mount checks is
mocked. This is NOT a native Arch VM and never executes Windows PE or Ghidra.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest import mock

sys.dont_write_bytecode = True

CASES = {
    "readonly": "PASS_PE_S2_20_REAL_READONLY_JOINT_HANDOFF_HOLD",
    "writable": "REJECT_PE_S2_20_REAL_WRITABLE_SOURCE",
    "tampered": "REJECT_PE_S2_20_REAL_TAMPERED_SOURCE",
    "wrong-v3": "REJECT_PE_S2_20_WRONG_SIGNED_V3_PIN",
}


def _child(mode: str) -> int:
    import pe_arch_vm_evidence as evidence
    import pe_arch_vm_s2_19_reviewer_session_handoff as handoff

    root = Path("/audit/source")
    # No host /etc/passwd or SSH config crosses the boundary. OpenSSH
    # needs getpwuid(), so only a synthetic local identity is exposed.
    import pwd
    passwd_file = Path("/etc/passwd")
    synthetic_identity = (
        pwd.getpwuid(os.geteuid()).pw_name == "ci-reviewer"
        and passwd_file.read_text("ascii").count("\n") == 1
        and passwd_file.read_text("ascii").startswith("ci-reviewer:x:")
        and bool(os.statvfs(passwd_file).f_flag & os.ST_RDONLY)
        and not Path("/etc/shadow").exists()
        and not Path("/etc/ssh").exists()
    )
    if not synthetic_identity:
        raise AssertionError("Host account data leaked or synthetic SSH identity absent")
    mount_ro = bool(os.statvfs(root).f_flag & os.ST_RDONLY)
    files_ro = all(
        os.statvfs(root / name).f_flag & os.ST_RDONLY
        for name in evidence.SOURCE_FILES)
    if mount_ro is not (mode != "writable"):
        raise AssertionError("Real source root mount flag differs from test case")
    if files_ro is not (mode != "writable"):
        raise AssertionError("Real source file mount flags differ from test case")
    data = json.loads(Path("/audit/custody/pins.json").read_bytes())
    if type(data) is not dict or set(data) != (
            set(handoff.v3.PINS) | {
                "expected_v3_manifest_sha256", "expected_v3_signature_sha256",
                "expected_native_receipt_sha256"}):
        raise AssertionError("Synthetic external pins do not have exact schema")
    if mode == "wrong-v3":
        data["expected_v3_signature_sha256"] = "f" * 64
        if data["expected_v3_signature_sha256"] == json.loads(
                Path("/audit/custody/pins.json").read_bytes())[
                    "expected_v3_signature_sha256"]:
            raise AssertionError("Bad V3 pin accidentally matched")
    try:
        result = handoff.verify_reviewer_session(
            Path("/audit/observer"), Path("/audit/custody"),
            Path("/audit/custody/acceptance.json"), root, **data)
    except handoff.SessionHandoffError as exc:
        if mode == "readonly":
            # CI-only diagnostic for synthetic test data. Never leak raw
            # signatures or a user's actual host evidence into logs.
            chain = []
            cause = exc
            while cause is not None and len(chain) < 10:
                chain.append(type(cause).__name__ + ": " + str(cause)[:240])
                cause = cause.__cause__
            raise AssertionError(
                "S2.20 genuine readonly review rejected: " + " | ".join(chain)
            ) from exc
    else:
        if mode != "readonly":
            raise AssertionError("Unsafe joint host/guest package was accepted")
        if (result.get("status") != handoff.STATUS
                or result.get("v1_v2_v3_detached_signatures_verified") is not True
                or result.get("native_receipt_sha256_equals_v1_signed_receipt_pin")
                   is not True
                or result.get("source_commit_checkout_locally_rechecked")
                   is not True
                or result.get("independent_vm_attestation") is not False
                or result.get("release_authorized") is not False):
            raise AssertionError("Joint review returned inaccurate security status")
    print(json.dumps({
        "status": CASES[mode], "actual_readonly_mount": mount_ro,
        "actual_readonly_source_files": bool(files_ro),
        "actual_git_and_local_receipt_validators_mocked": False,
        "actual_ed25519_verifiers_mocked": False,
        "libvirt_capture_mocked": True, "native_acceptance_report_synthetic": True,
        "host_passwd_synthetic_and_readonly": synthetic_identity,
        "external_native_arch_vm_attested": False,
        "release_authorized": False, "windows_pe_executed": False,
    }, sort_keys=True))
    return 0


def _git_checkout(repo: Path, source: Path) -> str:
    import pe_arch_vm_evidence as evidence

    source.mkdir(mode=0o700)
    for relative in evidence.SOURCE_FILES:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / relative, target)
    commands = [
        ["init", "-q"],
        ["add", "--all"],
        ["-c", "user.name=Synthetic CI Reviewer",
         "-c", "user.email=fixture@example.invalid",
         "commit", "-qm", "Synthetic reviewer source snapshot"],
    ]
    for command in commands:
        subprocess.run(["git", "-C", str(source), *command],
                       check=True, capture_output=True, timeout=25,
                       stdin=subprocess.DEVNULL)
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--verify", "HEAD^{commit}"],
        check=True, capture_output=True, text=True, timeout=10,
        stdin=subprocess.DEVNULL)
    return result.stdout.strip()


def _host(ghidra_home: Path) -> int:
    if (os.geteuid() == 0 or not shutil.which("bwrap")
            or not shutil.which("git") or not shutil.which("ssh-keygen")):
        raise RuntimeError("Unprivileged real Bubblewrap, Git and OpenSSH required")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "tools"))
    sys.path.insert(0, str(root / "tests"))

    from pe_ghidra_sandbox import build_command
    import pe_arch_vm_evidence as evidence
    import pe_arch_vm_s1_63_external_observer as obs
    import pe_arch_vm_s2_15_readonly_host_domstats as domstats
    import pe_arch_vm_s2_17_host_two_phase as pair
    from test_pe_arch_vm_s2_18_signed_host_pair import SignedHostPairV3Contracts
    from test_pe_arch_vm_s1_73_two_record_review import (
        COMMIT as OLD_COMMIT, CHALLENGE as OLD_CHALLENGE,
        DOMAIN, UUID, first_record, second_record)
    from test_pe_arch_vm_s2_13_runtime_log_chain import make_fixture
    from test_pe_arch_vm_s2_15_readonly_host_domstats import STATS
    from test_pe_arch_vm_s2_16_signed_domstats_extension import (
        CHALLENGE_V1, SESSION)
    from test_pe_arch_vm_s2_17_host_two_phase import FIRST, SECOND
    from pe_readonly_receipt_real_ci import _fixture_report

    fixture = SignedHostPairV3Contracts(
        "test_three_valid_signatures_and_pair_still_hold")
    fixture.setUp()
    try:
        old = fixture.old
        observer = fixture.owner
        custody = fixture.custody
        source = old.f.root / "source-checkout"
        commit = _git_checkout(root, source)
        if not len(commit) == 40 or commit == OLD_COMMIT:
            raise RuntimeError("Real synthetic Git commit must differ from fixture")
        native = custody / "acceptance.json"
        report = _fixture_report(root)
        receipt_meta = evidence.write_receipt_no_overwrite(
            report, native, source_root=source, reviewer_challenge=CHALLENGE_V1)
        native_hash = hashlib.sha256(native.read_bytes()).hexdigest()
        if receipt_meta["receipt_sha256"] != native_hash:
            raise RuntimeError("Real receipt has unexpected SHA256")

        # Rebuild the FULL chain with an ACTUAL Git HEAD and a genuine
        # synthetic receipt SHA. Only the libvirt counter acquisition is
        # simulated; no localhost/guest/hypervisor is contacted.
        stale = [
            old.f.manifest_path, old.f.signature_path,
            old.v2_manifest, old.v2_signature,
            observer / domstats.TARGET, observer / pair.BEFORE,
            observer / pair.AFTER,
        ]
        for path in stale:
            path.unlink()
        raw_host = (first_record().replace(OLD_COMMIT.encode(), commit.encode())
                    .replace(OLD_CHALLENGE.encode(), CHALLENGE_V1.encode()))
        host_sha = hashlib.sha256(raw_host).hexdigest()
        raw_guest = (second_record(host_sha).replace(
            OLD_COMMIT.encode(), commit.encode()).replace(
            OLD_CHALLENGE.encode(), CHALLENGE_V1.encode()))
        guest_sha = hashlib.sha256(raw_guest).hexdigest()
        runtime, cleanup = make_fixture(
            commit=commit, challenge=CHALLENGE_V1, domain=DOMAIN,
            uuid=UUID, host=host_sha, guest=guest_sha, session=SESSION)
        for key, raw in (
                ("host_vm_launch", raw_host),
                ("host_guest_kernel", raw_guest),
                ("host_seccomp_cgroups", runtime),
                ("host_scope_cleanup", cleanup)):
            path = observer / obs.OBS_FILES[key]
            path.write_bytes(raw)
            path.chmod(0o600)
            old.f.record["observations"][key]["sha256"] = (
                hashlib.sha256(raw).hexdigest())
        old.f.record["source_commit"] = commit
        old.f.record["receipt_sha256"] = native_hash

        with (mock.patch.object(domstats.shutil, "which",
                                return_value="/usr/bin/virsh"),
              mock.patch.object(domstats.host, "_virsh_read",
                                side_effect=[UUID, "running", "running", UUID]),
              mock.patch.object(domstats.bounded, "run_bounded_native",
                                return_value=SimpleNamespace(
                                    returncode=0, stdout=STATS, stderr=b""))):
            sidecar = domstats.capture_host_domstats(
                observer, domain=DOMAIN, expected_domain_uuid=UUID,
                expected_source_commit=commit,
                reviewer_challenge=CHALLENGE_V1,
                expected_session_id=SESSION, expected_host_sha256=host_sha,
                expected_guest_sha256=guest_sha,
                capture_from_independent_host=True)
        with mock.patch.object(
                pair, "_live_sample", side_effect=[
                    (FIRST, 100000000), (SECOND, 150000000)]):
            before = pair.capture_phase(
                observer, phase="before", domain=DOMAIN,
                expected_domain_uuid=UUID, expected_source_commit=commit,
                reviewer_challenge=CHALLENGE_V1,
                expected_session_id=SESSION, expected_host_sha256=host_sha,
                expected_guest_sha256=guest_sha,
                capture_from_independent_host=True)
            after = pair.capture_phase(
                observer, phase="after", domain=DOMAIN,
                expected_domain_uuid=UUID, expected_source_commit=commit,
                reviewer_challenge=CHALLENGE_V1,
                expected_session_id=SESSION, expected_host_sha256=host_sha,
                expected_guest_sha256=guest_sha,
                expected_before_sha256=before["sample_sha256"],
                capture_from_independent_host=True)

        old.f.sign()
        old_v1_pins = old.f.options()
        old.pins.update({
            "expected_source_commit": commit,
            "expected_host_sha256": host_sha,
            "expected_guest_sha256": guest_sha,
            "expected_domstats_sha256": sidecar["sidecar_sha256"],
            "expected_receipt_sha256": native_hash,
            "expected_v1_manifest_sha256": old_v1_pins["expected_manifest_sha256"],
            "expected_v1_signature_sha256": old_v1_pins["expected_signature_sha256"],
        })
        old.prepare()
        old.sign()
        fixture.pins.update(old.pins)
        fixture.pins.update({
            "expected_before_sha256": before["sample_sha256"],
            "expected_after_sha256": after["sample_sha256"],
            "expected_v2_manifest_sha256": hashlib.sha256(
                old.v2_manifest.read_bytes()).hexdigest(),
            "expected_v2_signature_sha256": hashlib.sha256(
                old.v2_signature.read_bytes()).hexdigest(),
        })
        fixture.prepare()
        fixture.sign()
        pins = {
            **fixture.pins,
            "expected_v3_manifest_sha256": hashlib.sha256(
                fixture.file.read_bytes()).hexdigest(),
            "expected_v3_signature_sha256": hashlib.sha256(
                fixture.sig.read_bytes()).hexdigest(),
            "expected_native_receipt_sha256": native_hash,
        }
        pin_file = custody / "pins.json"
        pin_file.write_bytes((json.dumps(pins, sort_keys=True,
                                         separators=(",", ":")) + "\n").encode())
        pin_file.chmod(0o600)

        tampered = old.f.root / "tampered-source"
        shutil.copytree(source, tampered)
        candidate = tampered / evidence.SOURCE_FILES[0]
        original = candidate.read_bytes()
        if not original:
            raise RuntimeError("Cannot tamper empty source manifest entry")
        candidate.write_bytes(bytes([original[0] ^ 1]) + original[1:])

        work = old.f.root / "work"
        (work / "scripts").mkdir(parents=True, mode=0o700)
        (work / "project").mkdir(mode=0o700)
        shutil.copyfile(
            root / "tools/ghidra_scripts/NegrescoFunctionInventory.java",
            work / "scripts/NegrescoFunctionInventory.java")
        shutil.copyfile(__file__, work / "s2_20_real_mount.py")
        base = build_command(ghidra_home, work, 160)
        boundary = base.index("--")
        # Never mount the runner's real login database. ssh-keygen -Y
        # verify may require a working getpwuid() even for offline checks.
        passwd_fixture = old.f.root / "synthetic-passwd"
        group_fixture = old.f.root / "synthetic-group"
        passwd_fixture.write_text(
            f"ci-reviewer:x:{os.geteuid()}:{os.getegid()}:"
            "Synthetic CI Reviewer:/work:/usr/bin/false\n", encoding="ascii")
        group_fixture.write_text(
            f"ci-reviewer:x:{os.getegid()}:\n", encoding="ascii")
        passwd_fixture.chmod(0o600)
        group_fixture.chmod(0o600)
        for mode in CASES:
            selected_source = tampered if mode == "tampered" else source
            mount = "--bind" if mode == "writable" else "--ro-bind"
            mounts = [
                "--dir", "/audit",
                "--ro-bind", str(passwd_fixture), "/etc/passwd",
                "--ro-bind", str(group_fixture), "/etc/group",
                "--ro-bind", str(root), "/audit/code",
                mount, str(selected_source), "/audit/source",
                "--ro-bind", str(observer), "/audit/observer",
                "--ro-bind", str(custody), "/audit/custody",
                "--setenv", "PYTHONPATH", "/audit/code/tools",
                "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            ]
            command = base[:boundary] + mounts + [
                "--", "/usr/bin/python3", "/work/s2_20_real_mount.py",
                "--child", mode]
            result = subprocess.run(
                command, capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=160, check=False,
                close_fds=True)
            if result.returncode != 0:
                raise RuntimeError(
                    f"Real Bubblewrap S2.20 {mode}: rc={result.returncode} "
                    f"stderr={result.stderr[-6000:]!r}, "
                    f"stdout={result.stdout[-1800:]!r}")
            observed = json.loads(result.stdout.strip())
            if (observed.get("status") != CASES[mode]
                    or observed.get("actual_readonly_mount")
                       is not (mode != "writable")
                    or observed.get("actual_git_and_local_receipt_validators_mocked")
                       is not False
                    or observed.get("actual_ed25519_verifiers_mocked") is not False
                    or observed.get("host_passwd_synthetic_and_readonly") is not True
                    or observed.get("external_native_arch_vm_attested") is not False
                    or observed.get("release_authorized") is not False):
                raise RuntimeError("Real readonly review result inconsistent")
            print(json.dumps(observed, sort_keys=True), flush=True)
        print(json.dumps({
            "status": "PASS_PE_S2_20_REAL_OFFLINE_JOINT_CHAIN_HOLD",
            "cases": len(CASES),
            "real_bubblewrap_readonly": True,
            "real_unmocked_git_receipt_and_signatures": True,
            "only_libvirt_and_native_execution_mocked": True,
            "native_arch_vm_independently_attested": False,
            "release_authorized": False,
        }, sort_keys=True))
    finally:
        fixture.doCleanups()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ghidra-home", type=Path)
    parser.add_argument("--child", choices=tuple(CASES))
    args = parser.parse_args()
    if args.child:
        return _child(args.child)
    if args.ghidra_home is None:
        parser.error("--ghidra-home required for actual mount test")
    return _host(args.ghidra_home)


if __name__ == "__main__":
    raise SystemExit(main())
