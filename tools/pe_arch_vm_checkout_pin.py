#!/usr/bin/env python3
"""PE-S1.45: fail-closed local Git checkout pin for an independent VM run.

Only checks a local checkout. Does not launch a PE, Ghidra, a scope, a VM or
network access. A matching Git commit and clean tree are NOT VM attestation
and cannot prove an adversarial host or Git executable is trustworthy.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

# Do not create __pycache__ in the pinned source checkout before Git status.
# Existing cache/untracked files are still refused; this is not an ignore rule.
sys.dont_write_bytecode = True

COMMIT_SHA = re.compile(r"[0-9a-f]{40}\Z")


class CheckoutPinError(RuntimeError):
    pass


def _git(source_root: Path, *args: str) -> str:
    git = shutil.which("git")
    if not git:
        raise CheckoutPinError("git unavailable; source pin cannot be checked")
    # Environment variables such as GIT_DIR, GIT_WORK_TREE and GIT_CONFIG_*
    # can redirect Git outside the intended checkout or change behavior.
    env = {name: value for name, value in os.environ.items()
           if not name.startswith("GIT_")}
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    try:
        run = subprocess.run(
            [git, "--no-optional-locks", "-c", "core.fsmonitor=false",
             "-c", "core.untrackedCache=false",
             "-c", "core.hooksPath=/dev/null",
             "-C", str(source_root), *args],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            check=False, timeout=15, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CheckoutPinError("Git checkout inspection unavailable") from exc
    if run.returncode != 0 or len(run.stdout) > 1024 * 1024:
        raise CheckoutPinError("Git checkout inspection failed")
    return run.stdout.strip()


def verify_source_checkout_pin(source_root: Path, expected_commit: str,
                               required_files: tuple[str, ...]) -> dict:
    """Check revision, worktree cleanliness and tracked manifest sources.

    expected_commit comes from a reviewer-controlled channel BEFORE the VM
    execution. This cannot authenticate the Git implementation or host.
    """
    if (not isinstance(expected_commit, str)
            or COMMIT_SHA.fullmatch(expected_commit) is None):
        raise CheckoutPinError("Expected full lowercase 40-hex commit required")
    root = Path(source_root)
    if (not root.is_absolute() or root.is_symlink() or not root.is_dir()):
        raise CheckoutPinError("Canonical absolute checkout directory required")
    # No resolve(): symlink aliases are not an external source identity.
    if any(part in (".", "..", "") for part in root.parts[1:]):
        raise CheckoutPinError("Noncanonical checkout directory")
    if (not isinstance(required_files, tuple) or not required_files
            or any(not isinstance(item, str) or not item
                   or item.startswith("/")
                   or any(part in ("", ".", "..")
                          for part in item.split("/"))
                   for item in required_files)):
        raise CheckoutPinError("Invalid required source manifest")
    toplevel = _git(root, "rev-parse", "--show-toplevel")
    if toplevel != str(root):
        raise CheckoutPinError("Checkout must be at exact Git worktree root")
    observed = _git(root, "rev-parse", "--verify", "HEAD^{commit}")
    if observed != expected_commit:
        raise CheckoutPinError("Checkout commit differs from reviewer pin")
    # Require exact entry names rather than merely assuming git status clean.
    sources = _git(root, "ls-files", "--cached", "--", *required_files)
    if set(sources.splitlines()) != set(required_files):
        raise CheckoutPinError("Source manifest has missing or untracked files")
    # This includes staged and unstaged changes; nonignored untracked files
    # fail closed. Git ignore rules are not evidence of clean ignored files.
    dirty = _git(root, "status", "--porcelain=v1",
                 "--untracked-files=all", "--ignore-submodules=none")
    if dirty:
        raise CheckoutPinError("Source checkout is dirty or has untracked files")
    return {
        "status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED",
        "expected_commit": expected_commit,
        "checked_manifest_entries": len(required_files),
        "worktree_status_clean": True,
        "git_authorship_or_signature_verified": False,
        "native_vm_or_kernel_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline Git source pin check; NOT VM attestation")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args(argv)
    try:
        import pe_arch_vm_evidence as evidence
        result = verify_source_checkout_pin(
            args.source_root, args.expected_commit, evidence.SOURCE_FILES)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (CheckoutPinError, OSError, ValueError) as exc:
        print(json.dumps({
            "status": "REJECTED_SOURCE_CHECKOUT_PIN",
            "reason": str(exc),
            "native_vm_or_kernel_verified": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
