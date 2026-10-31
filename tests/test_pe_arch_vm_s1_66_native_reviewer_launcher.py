"""PE-S1.66 reviewer launcher: synthetic-only subprocess mocked, no real VM.

This suite MUST never run native cgroup, Ghidra, a hypervisor, or Windows PE.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_66_native_reviewer_launcher as launcher

COMMIT = "a" * 40
CHALLENGE = "b" * 64


class ReviewerNativeLauncherContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pe-s1-66-")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "review-private"
        self.folder.mkdir(mode=0o700)
        self.receipt = self.folder / "acceptance.json"
        self.home = Path("/trusted/ghidra_12.2_PUBLIC")
        self.zip = Path("/trusted/ghidra_12.2.zip")
        self.options = {
            "expected_source_commit": COMMIT,
            "reviewer_challenge": CHALLENGE,
        }
        self.ready = {
            "status": launcher.preflight.STATUS,
            "source_commit": COMMIT,
            "source_files_rechecked": len(launcher.SOURCE_FILES),
            "native_guest_preflight_locally_passed": True,
            "pinned_ghidra_install_locally_verified": True,
            "receipt_destination_unused_private": True,
            "any_receipt_written": False,
            "independent_vm_attestation": False,
            "apk_or_ota_publication_authorized": False,
        }

    def call(self, **overrides):
        kw = {**self.options, **overrides}
        return launcher.review_native_acceptance(
            self.home, self.zip, self.receipt, **kw)

    def _fake_run(self, argv, **kwargs):
        payload = (json.dumps({
            "reviewer_challenge": CHALLENGE,
            "windows_executable_launched": False,
        }) + "\n").encode("utf-8")
        self.receipt.write_bytes(payload)
        self.receipt.chmod(0o600)
        local = {
            "path": str(self.receipt),
            "receipt_sha256": hashlib.sha256(payload).hexdigest(),
            "record_type": "LOCAL_SELF_REPORT_NOT_SIGNED",
        }
        report = {
            "status": "PASS_PE_S1_5_ARCH_VM",
            "windows_binary_executed": False,
            "local_receipt": local,
            "local_source_checkout_pin": {
                "expected_commit": COMMIT,
                "worktree_status_clean": True,
                "native_vm_or_kernel_verified": False,
            },
        }
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(report).encode("ascii"), stderr=b"")

    def execute_mocked(self, *, fake=None, ready=None, **overrides):
        with (
            mock.patch.object(
                launcher.preflight, "native_readiness",
                return_value=self.ready if ready is None else ready) as pre,
            mock.patch.object(
                launcher.subprocess, "run",
                side_effect=self._fake_run if fake is None else fake) as run,
        ):
            result = self.call(
                execute_synthetic_native_acceptance=True, **overrides)
        return result, pre, run

    def test_default_plan_does_not_probe_vm_or_launch_subprocess(self):
        with (
            mock.patch.object(launcher.preflight, "native_readiness") as pre,
            mock.patch.object(launcher.subprocess, "run") as run,
        ):
            result = self.call()
        pre.assert_not_called()
        run.assert_not_called()
        self.assertEqual(result["status"], launcher.PLAN)
        self.assertFalse(result["synthetic_acceptance_executed"])
        self.assertFalse(result["any_receipt_written"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(self.receipt.exists())

    def test_explicit_run_uses_pinned_native_cli_and_receipt_is_verified(self):
        result, pre, run = self.execute_mocked()
        self.assertEqual(result["status"], launcher.LOCAL_DONE)
        self.assertTrue(result["synthetic_acceptance_executed"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["unknown_windows_pe_execution_authorized"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])
        pre.assert_called_once_with(
            self.home, self.zip, launcher.SOURCE_ROOT, self.receipt,
            expected_source_commit=COMMIT, reviewer_challenge=CHALLENGE)
        self.assertEqual(run.call_count, 1)
        args = run.call_args.args[0]
        self.assertEqual(args[:3], [
            sys.executable, "-B", str(launcher.ACCEPTANCE)])
        self.assertIn("--reviewer-pinned-checkout", args)
        self.assertEqual(args[args.index("--expected-source-commit")+1], COMMIT)
        self.assertEqual(args[args.index("--reviewer-challenge")+1], CHALLENGE)
        self.assertEqual(args[args.index("--evidence-output")+1], str(self.receipt))
        self.assertTrue(run.call_args.kwargs["close_fds"])
        self.assertIs(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertLessEqual(run.call_args.kwargs["timeout"], 1800)

    def test_environment_disables_module_or_git_redirection(self):
        with mock.patch.dict(os.environ, {
            "PYTHONPATH": "/untrusted",
            "GIT_WORK_TREE": "/untrusted",
            "JAVA_TOOL_OPTIONS": "-javaagent:/untrusted/agent",
            "JAVA_HOME": "/trusted/jdk25",
        }):
            result, pre, run = self.execute_mocked()
        env = run.call_args.kwargs["env"]
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("GIT_WORK_TREE", env)
        self.assertNotIn("JAVA_TOOL_OPTIONS", env)
        self.assertEqual(env["JAVA_HOME"], "/trusted/jdk25")
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")

    def test_explicit_run_preflight_rejection_prevents_any_subprocess(self):
        with (
            mock.patch.object(launcher.preflight, "native_readiness",
                              side_effect=launcher.preflight.NativePreflightError(
                                  "not a VM")) as pre,
            mock.patch.object(launcher.subprocess, "run") as run,
        ):
            with self.assertRaises(launcher.ReviewerLaunchError):
                self.call(execute_synthetic_native_acceptance=True)
        pre.assert_called_once()
        run.assert_not_called()
        self.assertFalse(self.receipt.exists())

    def test_preflight_fake_vm_attestation_refuses_before_subprocess(self):
        with (
            mock.patch.object(launcher.preflight, "native_readiness",
                              return_value={
                                  **self.ready, "independent_vm_attestation": True,
                              }),
            mock.patch.object(launcher.subprocess, "run") as run,
        ):
            with self.assertRaises(launcher.ReviewerLaunchError):
                self.call(execute_synthetic_native_acceptance=True)
        run.assert_not_called()

    def test_preflight_wrong_manifest_count_refuses(self):
        with (
            mock.patch.object(launcher.preflight, "native_readiness",
                              return_value={
                                  **self.ready,
                                  "source_files_rechecked": 1,
                              }),
            mock.patch.object(launcher.subprocess, "run") as run,
        ):
            with self.assertRaises(launcher.ReviewerLaunchError):
                self.call(execute_synthetic_native_acceptance=True)
        run.assert_not_called()

    def test_wrong_commit_challenge_refused_before_probe(self):
        for bad in (
            {"expected_source_commit": "g" * 40},
            {"expected_source_commit": "0" * 40},
            {"reviewer_challenge": "0" * 64},
            {"reviewer_challenge": "Z" * 64},
            {"execute_synthetic_native_acceptance": "yes"},
        ):
            with (
                self.subTest(bad=bad),
                mock.patch.object(launcher.preflight, "native_readiness") as pre,
                mock.patch.object(launcher.subprocess, "run") as run,
            ):
                with self.assertRaises(launcher.ReviewerLaunchError):
                    self.call(**bad)
                pre.assert_not_called()
                run.assert_not_called()

    def test_existing_receipt_refused_not_overwritten(self):
        self.receipt.write_text("existing\n", encoding="ascii")
        with (
            mock.patch.object(launcher.preflight, "native_readiness") as pre,
            mock.patch.object(launcher.subprocess, "run") as run,
        ):
            with self.assertRaises(launcher.ReviewerLaunchError):
                self.call(execute_synthetic_native_acceptance=True)
        self.assertEqual(self.receipt.read_text("ascii"), "existing\n")
        pre.assert_not_called()
        run.assert_not_called()

    def test_nonprivate_receipt_directory_refused(self):
        self.folder.chmod(0o755)
        with mock.patch.object(launcher.preflight, "native_readiness") as pre:
            with self.assertRaises(launcher.ReviewerLaunchError):
                self.call()
        pre.assert_not_called()

    def test_receipt_symlink_refused(self):
        self.receipt.symlink_to(self.folder / "missing")
        with mock.patch.object(launcher.preflight, "native_readiness") as pre:
            with self.assertRaises(launcher.ReviewerLaunchError):
                self.call()
        pre.assert_not_called()

    def test_receipt_in_source_or_ghidra_tree_refused(self):
        with mock.patch.object(launcher.preflight, "native_readiness") as pre:
            for path in (
                launcher.SOURCE_ROOT / "proof.json",
                self.home / "proof.json",
            ):
                with self.subTest(path=path):
                    with self.assertRaises(launcher.ReviewerLaunchError):
                        launcher.review_native_acceptance(
                            self.home, self.zip, path, **self.options)
        pre.assert_not_called()

    def test_native_acceptance_nonzero_fails_no_success(self):
        def refuse(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 2, b"", b"REFUSED")
        with self.assertRaises(launcher.ReviewerLaunchError):
            self.execute_mocked(fake=refuse)

    def test_false_windows_execution_flag_rejected(self):
        def fake(argv, **kwargs):
            run = self._fake_run(argv, **kwargs)
            result = json.loads(run.stdout)
            result["windows_binary_executed"] = True
            return subprocess.CompletedProcess(
                argv, 0, json.dumps(result).encode("utf-8"), b"")
        with self.assertRaises(launcher.ReviewerLaunchError):
            self.execute_mocked(fake=fake)

    def test_receipt_mutated_after_acceptance_rejected(self):
        def fake(argv, **kwargs):
            result = self._fake_run(argv, **kwargs)
            self.receipt.write_bytes(self.receipt.read_bytes() + b"CHANGED")
            return result
        with self.assertRaises(launcher.ReviewerLaunchError):
            self.execute_mocked(fake=fake)

    def test_receipt_wrong_challenge_refused(self):
        def fake(argv, **kwargs):
            run = self._fake_run(argv, **kwargs)
            payload = (json.dumps({
                "reviewer_challenge": "c" * 64,
                "windows_executable_launched": False,
            }) + "\n").encode()
            self.receipt.write_bytes(payload)
            record = json.loads(run.stdout)
            record["local_receipt"]["receipt_sha256"] = (
                hashlib.sha256(payload).hexdigest())
            return subprocess.CompletedProcess(
                argv, 0, json.dumps(record).encode(), b"")
        with self.assertRaises(launcher.ReviewerLaunchError):
            self.execute_mocked(fake=fake)

    def test_no_receipt_even_positive_stdout_fails(self):
        def fake(argv, **kwargs):
            report = self._fake_run(argv, **kwargs)
            self.receipt.unlink()
            return report
        with self.assertRaises(launcher.ReviewerLaunchError):
            self.execute_mocked(fake=fake)

    def test_cli_default_planning_only_without_exec(self):
        argv = [
            "--ghidra-home", str(self.home),
            "--ghidra-archive", str(self.zip),
            "--evidence-output", str(self.receipt),
            "--expected-source-commit", COMMIT,
            "--reviewer-challenge", CHALLENGE,
        ]
        out, err = StringIO(), StringIO()
        with (
            redirect_stdout(out), redirect_stderr(err),
            mock.patch.object(launcher.subprocess, "run") as run,
            mock.patch.object(launcher.preflight, "native_readiness") as pre,
        ):
            code = launcher.main(argv)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], launcher.PLAN)
        self.assertEqual(err.getvalue(), "")
        pre.assert_not_called()
        run.assert_not_called()

    def test_cli_execute_rejected_when_preflight_blocks(self):
        argv = [
            "--ghidra-home", str(self.home),
            "--ghidra-archive", str(self.zip),
            "--evidence-output", str(self.receipt),
            "--expected-source-commit", COMMIT,
            "--reviewer-challenge", CHALLENGE,
            "--execute-synthetic-native-acceptance",
        ]
        out, err = StringIO(), StringIO()
        with (
            redirect_stdout(out), redirect_stderr(err),
            mock.patch.object(
                launcher.preflight, "native_readiness",
                side_effect=launcher.preflight.NativePreflightError("NOT VM")),
            mock.patch.object(launcher.subprocess, "run") as run,
        ):
            code = launcher.main(argv)
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), "")
        result = json.loads(err.getvalue())
        self.assertEqual(result["status"], launcher.REJECTED)
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
