"""PE-S1.58 safety contracts. CI MUST NOT impersonate a native Arch VM."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pe_arch_vm_s1_58_preflight as pre
from pe_arch_vm_evidence import SOURCE_FILES
from pe_ghidra_integrity import GHIDRA_RELEASE_SHA256
from pe_arch_vm_gate import ArchVmUnavailable

COMMIT = "a" * 40
CHALLENGE = "b" * 64


class ReadOnlyArchVmPreflightContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="s1-58-native-readiness-")
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name) / "evidence"
        self.parent.mkdir(mode=0o700)
        self.receipt = self.parent / "new-receipt.json"
        self.home = Path("/trusted/ghidra_12.2_PUBLIC")
        self.zip = Path("/trusted/ghidra_12.2.zip")

    def call(self, **options):
        options = {"expected_source_commit": COMMIT,
                   "reviewer_challenge": CHALLENGE, **options}
        return pre.native_readiness(
            self.home, self.zip, pre.WORKSPACE, self.receipt, **options)

    def proof(self):
        return {
            "status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED",
            "expected_commit": COMMIT,
            "checked_manifest_entries": len(SOURCE_FILES),
            "worktree_status_clean": True,
            "git_authorship_or_signature_verified": False,
            "native_vm_or_kernel_verified": False,
        }

    def test_valid_mocked_contract_remains_local_not_independent(self):
        with (
            mock.patch.object(pre, "verify_arch_vm", return_value={
                "status": "ARCH_VM_PREFLIGHT_PASSED",
                "vm_confirmed": True, "container": False, "root": False,
                "systemd_user_bus": True,
                "real_cgroup_test_executed": False}),
            mock.patch.object(pre, "verify_source_checkout_pin",
                              side_effect=[self.proof(), self.proof()]) as git,
            mock.patch.object(pre, "java25_preflight") as java,
            mock.patch.object(pre, "validate_ghidra_122_install") as metadata,
            mock.patch.object(pre, "verify_pinned_ghidra_tree",
                              return_value={
                "verified": True, "release_sha256": GHIDRA_RELEASE_SHA256,
                "matched_files": 250, "symlinks_allowed": False,
                "unexpected_files_allowed": False}) as integrity,
        ):
            result = self.call()
        self.assertEqual(git.call_count, 2)
        java.assert_called_once_with()
        metadata.assert_called_once_with(self.home)
        integrity.assert_called_once_with(self.home, self.zip)
        self.assertEqual(result["status"], pre.STATUS)
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["native_seccomp_and_cgroups_execution_verified"])
        self.assertFalse(result["any_receipt_written"])
        self.assertFalse(result["any_cgroup_scope_created"])
        self.assertFalse(result["ghidra_or_windows_binary_executed"])
        self.assertFalse(result["unknown_windows_pe_execution_authorized"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])
        self.assertFalse(self.receipt.exists())

    def test_wrong_commit_refused_before_guest_probe(self):
        for commit in ("", "0" * 40, "g" * 40, "A" * 40, "a" * 39):
            with self.subTest(commit=commit):
                with mock.patch.object(pre, "verify_arch_vm") as guest:
                    with self.assertRaises(pre.NativePreflightError):
                        self.call(expected_source_commit=commit)
                    guest.assert_not_called()

    def test_challenge_malformed_refused_before_guest_probe(self):
        for challenge in ("", "0" * 64, "z" * 64, "b" * 63):
            with self.subTest(challenge=challenge):
                with mock.patch.object(pre, "verify_arch_vm") as guest:
                    with self.assertRaises(pre.NativePreflightError):
                        self.call(reviewer_challenge=challenge)
                    guest.assert_not_called()

    def test_nonabsolute_archive_refused_before_guest_probe(self):
        with mock.patch.object(pre, "verify_arch_vm") as guest:
            with self.assertRaises(pre.NativePreflightError):
                pre.native_readiness(
                    self.home, Path("local.zip"),
                    pre.WORKSPACE, self.receipt,
                    expected_source_commit=COMMIT, reviewer_challenge=CHALLENGE)
            guest.assert_not_called()

    def test_other_source_tree_refused_before_guest_probe(self):
        with mock.patch.object(pre, "verify_arch_vm") as guest:
            with self.assertRaises(pre.NativePreflightError):
                pre.native_readiness(
                    self.home, self.zip, self.parent,
                    self.receipt, expected_source_commit=COMMIT,
                    reviewer_challenge=CHALLENGE)
            guest.assert_not_called()

    def test_receipt_existing_refused_never_overwritten(self):
        self.receipt.write_text("preexisting\n", encoding="ascii")
        with mock.patch.object(pre, "verify_arch_vm") as guest:
            with self.assertRaises(pre.NativePreflightError):
                self.call()
            guest.assert_not_called()
        self.assertEqual(self.receipt.read_text("ascii"), "preexisting\n")

    def test_receipt_symlink_refused_even_dangling(self):
        self.receipt.symlink_to(self.parent / "missing")
        with mock.patch.object(pre, "verify_arch_vm") as guest:
            with self.assertRaises(pre.NativePreflightError):
                self.call()
            guest.assert_not_called()

    def test_private_directory_requires_0700(self):
        self.parent.chmod(0o750)
        with mock.patch.object(pre, "verify_arch_vm") as guest:
            with self.assertRaises(pre.NativePreflightError):
                self.call()
            guest.assert_not_called()

    def test_parent_symlink_refused(self):
        link = Path(self.temp.name) / "private-link"
        link.symlink_to(self.parent, target_is_directory=True)
        output = link / "result.json"
        with mock.patch.object(pre, "verify_arch_vm") as guest:
            with self.assertRaises(pre.NativePreflightError):
                pre.native_readiness(
                    self.home, self.zip, pre.WORKSPACE, output,
                    expected_source_commit=COMMIT, reviewer_challenge=CHALLENGE)
            guest.assert_not_called()

    def test_receipt_under_source_tree_refused(self):
        candidate = pre.WORKSPACE / "evidence.json"
        with self.assertRaises(pre.NativePreflightError):
            pre._private_new_receipt(candidate, pre.WORKSPACE, self.home)

    def test_receipt_under_ghidra_tree_refused(self):
        with self.assertRaises(pre.NativePreflightError):
            pre._private_new_receipt(
                self.home / "evidence.json", pre.WORKSPACE, self.home)

    def test_ubuntu_not_vm_refuses_before_git_java_and_integrity(self):
        with (
            mock.patch.object(pre, "verify_arch_vm",
                              side_effect=ArchVmUnavailable("Ubuntu host")) as guest,
            mock.patch.object(pre, "verify_source_checkout_pin") as git,
            mock.patch.object(pre, "java25_preflight") as java,
            mock.patch.object(pre, "verify_pinned_ghidra_tree") as integrity,
        ):
            with self.assertRaises(pre.NativePreflightError):
                self.call()
        guest.assert_called_once_with()
        git.assert_not_called()
        java.assert_not_called()
        integrity.assert_not_called()
        self.assertFalse(self.receipt.exists())

    def test_ambiguous_vm_selfreport_never_promoted(self):
        with mock.patch.object(pre, "verify_arch_vm", return_value={
                "status": "ARCH_VM_PREFLIGHT_PASSED",
                "vm_confirmed": True, "container": False,
                "root": False, "real_cgroup_test_executed": True}):
            with mock.patch.object(pre, "verify_source_checkout_pin") as git:
                with self.assertRaises(pre.NativePreflightError):
                    self.call()
                git.assert_not_called()

    def test_git_checkout_refusal_blocks_java_and_ghidra(self):
        with (
            mock.patch.object(pre, "verify_arch_vm", return_value={
                "status": "ARCH_VM_PREFLIGHT_PASSED", "vm_confirmed": True,
                "container": False, "root": False,
                "systemd_user_bus": True, "real_cgroup_test_executed": False}),
            mock.patch.object(pre, "verify_source_checkout_pin",
                              return_value={"status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED"}),
            mock.patch.object(pre, "java25_preflight") as java,
            mock.patch.object(pre, "verify_pinned_ghidra_tree") as integrity,
        ):
            with self.assertRaises(pre.NativePreflightError):
                self.call()
        java.assert_not_called()
        integrity.assert_not_called()

    def test_git_tree_changed_during_preflight_refused(self):
        changed = {**self.proof(), "expected_commit": "f" * 40}
        with (
            mock.patch.object(pre, "verify_arch_vm", return_value={
                "status": "ARCH_VM_PREFLIGHT_PASSED", "vm_confirmed": True,
                "container": False, "root": False,
                "systemd_user_bus": True, "real_cgroup_test_executed": False}),
            mock.patch.object(pre, "verify_source_checkout_pin",
                              side_effect=[self.proof(), changed]),
            mock.patch.object(pre, "java25_preflight"),
            mock.patch.object(pre, "validate_ghidra_122_install"),
            mock.patch.object(pre, "verify_pinned_ghidra_tree",
                              return_value={
                "verified": True, "release_sha256": GHIDRA_RELEASE_SHA256,
                "matched_files": 250, "symlinks_allowed": False,
                "unexpected_files_allowed": False}),
        ):
            with self.assertRaises(pre.NativePreflightError):
                self.call()

    def test_ghidra_invalid_hash_rejected(self):
        with (
            mock.patch.object(pre, "verify_arch_vm", return_value={
                "status": "ARCH_VM_PREFLIGHT_PASSED", "vm_confirmed": True,
                "container": False, "root": False,
                "systemd_user_bus": True, "real_cgroup_test_executed": False}),
            mock.patch.object(pre, "verify_source_checkout_pin",
                              side_effect=[self.proof(), self.proof()]),
            mock.patch.object(pre, "java25_preflight"),
            mock.patch.object(pre, "validate_ghidra_122_install"),
            mock.patch.object(pre, "verify_pinned_ghidra_tree",
                              return_value={
                "verified": True, "release_sha256": "f" * 64,
                "matched_files": 250, "symlinks_allowed": False,
                "unexpected_files_allowed": False}),
        ):
            with self.assertRaises(pre.NativePreflightError):
                self.call()

    def test_receipt_appearing_during_hashing_blocks_preflight(self):
        def race(*_):
            self.receipt.write_text("concurrent\n", encoding="ascii")
            return {"verified": True, "release_sha256": GHIDRA_RELEASE_SHA256,
                    "matched_files": 250, "symlinks_allowed": False,
                    "unexpected_files_allowed": False}
        with (
            mock.patch.object(pre, "verify_arch_vm", return_value={
                "status": "ARCH_VM_PREFLIGHT_PASSED", "vm_confirmed": True,
                "container": False, "root": False,
                "systemd_user_bus": True, "real_cgroup_test_executed": False}),
            mock.patch.object(pre, "verify_source_checkout_pin",
                              side_effect=[self.proof(), self.proof()]),
            mock.patch.object(pre, "java25_preflight"),
            mock.patch.object(pre, "validate_ghidra_122_install"),
            mock.patch.object(pre, "verify_pinned_ghidra_tree", side_effect=race),
        ):
            with self.assertRaises(pre.NativePreflightError):
                self.call()
        self.assertEqual(self.receipt.read_text("ascii"), "concurrent\n")

    def test_cli_ubuntu_refusal_returns_two_without_output_file(self):
        args = [
            "--source-root", str(pre.WORKSPACE),
            "--ghidra-home", str(self.home),
            "--ghidra-archive", str(self.zip),
            "--evidence-output", str(self.receipt),
            "--expected-source-commit", COMMIT,
            "--reviewer-challenge", CHALLENGE,
        ]
        stderr, stdout = StringIO(), StringIO()
        with (mock.patch.object(pre, "verify_arch_vm",
                                side_effect=ArchVmUnavailable("Ubuntu")),
              redirect_stderr(stderr), redirect_stdout(stdout)):
            rc = pre.main(args)
        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(json.loads(stderr.getvalue())["status"], pre.REJECTED)
        self.assertFalse(self.receipt.exists())


if __name__ == "__main__":
    unittest.main()
