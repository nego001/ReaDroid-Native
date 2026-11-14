#!/usr/bin/env python3
"""PE-S1.43: actual Bubblewrap mount-view smoke for the offline source policy.

Runs only a synthetic Python text fixture. Uses the existing real Ghidra
Bubblewrap profile to test the same user/mount namespaces; does NOT launch
Ghidra or any Windows executable. Does not assert host/VM immutability.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

FIXTURE = b"negresco synthetic readonly mount fixture\n"
CHILD_STATUSES = {
    "readonly": "PASS_ACTUAL_RO_BIND",
    "writable": "REJECTED_ACTUAL_RW_BIND",
    "nested-writable": "REJECTED_ACTUAL_NESTED_RW_BIND",
}


def child(mode: str) -> int:
    # Unlike unit tests, do not patch or fake os.fstatvfs: the real Linux
    # kernel reports flags for these actual Bubblewrap bind mounts.
    from pe_arch_vm_receipt_verify import ReceiptReviewError, _read_source

    root = Path("/audit/source")
    directory = root / "tools"
    target = directory / "synthetic.txt"
    flags = {
        "root_readonly": bool(os.statvfs(root).f_flag & os.ST_RDONLY),
        "directory_readonly": bool(os.statvfs(directory).f_flag & os.ST_RDONLY),
        "file_readonly": bool(os.statvfs(target).f_flag & os.ST_RDONLY),
    }
    if mode == "readonly":
        if not all(flags.values()):
            raise AssertionError("The actual --ro-bind is not readonly")
        content = _read_source(
            root, "tools/synthetic.txt",
            require_readonly_source_view=True)
        if content != FIXTURE:
            raise AssertionError("Readonly source bytes changed")
    else:
        if mode == "writable" and any(flags.values()):
            raise AssertionError("Expected an actual writable bind mount")
        if mode == "nested-writable" and flags != {
                "root_readonly": True,
                "directory_readonly": False,
                "file_readonly": False}:
            raise AssertionError("Nested writable bind not actually mounted")
        try:
            _read_source(
                root, "tools/synthetic.txt",
                require_readonly_source_view=True)
        except ReceiptReviewError as exc:
            if "readonly mount required" not in str(exc):
                raise AssertionError("Unexpected policy rejection") from exc
        else:
            raise AssertionError("Writable source unexpectedly approved")
    print(json.dumps({
        "status": CHILD_STATUSES[mode],
        "mount_view_flags_from_kernel": flags,
        "python_fixture_only": True,
        "windows_binary_executed": False,
        "native_arch_vm_attestation": False,
    }, sort_keys=True))
    return 0


def run_real_smoke(ghidra_home: Path) -> int:
    repository = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository / "tools"))
    from pe_ghidra_sandbox import build_command

    if os.geteuid() == 0:
        raise RuntimeError("Real Bubblewrap smoke must run unprivileged")
    if not shutil.which("bwrap"):
        raise RuntimeError("Bubblewrap missing: cannot claim a real mount test")
    with tempfile.TemporaryDirectory(prefix="negresco-pe-s1-43-") as name:
        root = Path(name)
        source = root / "source"
        (source / "tools").mkdir(parents=True, mode=0o700)
        fixture = source / "tools" / "synthetic.txt"
        fixture.write_bytes(FIXTURE)
        # chmod alone is deliberately insufficient: writable bind must fail.
        fixture.chmod(0o444)
        overlay = root / "writable-tools"
        overlay.mkdir(mode=0o700)
        (overlay / "synthetic.txt").write_bytes(FIXTURE)
        workspace = root / "work"
        (workspace / "scripts").mkdir(parents=True, mode=0o700)
        (workspace / "project").mkdir(mode=0o700)
        shutil.copyfile(
            repository / "tools/ghidra_scripts/NegrescoFunctionInventory.java",
            workspace / "scripts/NegrescoFunctionInventory.java")
        shutil.copyfile(__file__, workspace / "readonly_mount_smoke.py")

        # Reuse the same Bubblewrap profile as real Ghidra CI, replacing only
        # the executable after "--" with harmless Python. No sandbox bypass.
        base = build_command(ghidra_home, workspace, 120)
        boundary = base.index("--")
        proof = []
        for mode in CHILD_STATUSES:
            mount_flag = "--bind" if mode == "writable" else "--ro-bind"
            mounts = [
                "--dir", "/audit",
                "--ro-bind", str(repository / "tools"), "/audit/code",
                mount_flag, str(source), "/audit/source",
            ]
            if mode == "nested-writable":
                mounts += ["--bind", str(overlay), "/audit/source/tools"]
            mounts += [
                "--setenv", "PYTHONPATH", "/audit/code",
                "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            ]
            argv = base[:boundary] + mounts + [
                "--", "/usr/bin/python3", "/work/readonly_mount_smoke.py",
                "--child", mode,
            ]
            result = subprocess.run(
                argv, stdin=subprocess.DEVNULL, capture_output=True,
                text=True, timeout=50, check=False, close_fds=True)
            if result.returncode != 0:
                raise RuntimeError(
                    f"Actual Bubblewrap {mode} probe failed closed: "
                    f"rc={result.returncode} "
                    f"stderr={result.stderr[-1200:]!r} "
                    f"stdout={result.stdout[-1200:]!r}")
            record = json.loads(result.stdout.strip())
            if (record.get("status") != CHILD_STATUSES[mode]
                    or record.get("python_fixture_only") is not True
                    or record.get("windows_binary_executed") is not False
                    or record.get("native_arch_vm_attestation") is not False):
                raise RuntimeError(
                    f"Actual Bubblewrap {mode} probe evidence invalid")
            proof.append(record)
            print(json.dumps(record, sort_keys=True), flush=True)

        print(json.dumps({
            "status": "PASS_PE_S1_43_ACTUAL_BWRAP_READONLY_MOUNT_POLICY",
            "mount_tests": len(proof),
            "actual_readonly_bind_accepted": True,
            "actual_writable_bind_rejected": True,
            "actual_nested_writable_bind_rejected": True,
            "fstatvfs_mocked": False,
            "linux_host_ubuntu_only": True,
            "native_arch_vm_attestation": False,
            "windows_binary_executed": False,
        }, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ghidra-home", type=Path)
    parser.add_argument("--child", choices=tuple(CHILD_STATUSES))
    args = parser.parse_args(argv)
    if args.child:
        return child(args.child)
    if args.ghidra_home is None:
        parser.error("--ghidra-home required for the real host smoke")
    return run_real_smoke(args.ghidra_home)


if __name__ == "__main__":
    raise SystemExit(main())
