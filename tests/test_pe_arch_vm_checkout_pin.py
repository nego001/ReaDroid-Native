"""PE-S1.45: test the reviewer-selected source pin without native VM runs."""
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
import pe_arch_vm_checkout_pin as pin
import pe_arch_vm_validation as validation

COMMIT = "abc01234" * 5
SOURCES = ("tools/synthetic.py", "tests/fixture.c")
CHALLENGE = "a1bcde23" * 8


class LocalReviewerPinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.calls = []

    def fake_git(self, root, *args):
        self.calls.append(args)
        if args == ("rev-parse", "--show-toplevel"):
            return str(root)
        if args == ("rev-parse", "--verify", "HEAD^{commit}"):
            return COMMIT
        if args[:2] == ("ls-files", "--cached"):
            return "\n".join(SOURCES)
        if args[:2] == ("ls-files", "--stage"):
            return "\n".join(
                "100644 " + "a" * 40 + " 0\t" + path
                for path in SOURCES)
        if args[:2] == ("status", "--porcelain=v1"):
            return ""
        if args[:3] == ("ls-files", "--others", "--ignored"):
            return ""
        raise AssertionError("Unexpected git invocation: " + repr(args))

    def check(self):
        with mock.patch.object(pin, "_git", side_effect=self.fake_git):
            return pin.verify_source_checkout_pin(self.root, COMMIT, SOURCES)

    def test_s1_45_clean_matching_commit_and_full_manifest_accepted(self):
        result = self.check()
        self.assertEqual(result["status"], "LOCAL_GIT_CHECKOUT_PIN_MATCHED")
        self.assertEqual(result["expected_commit"], COMMIT)
        self.assertEqual(result["checked_manifest_entries"], 2)
        self.assertFalse(result["native_vm_or_kernel_verified"])
        self.assertFalse(result["git_authorship_or_signature_verified"])
        self.assertEqual(len(self.calls), 6)

    def test_s1_45_bad_commit_rejected_before_accessing_git(self):
        for commit in ("", "A" * 40, "a" * 39, "z" * 40, None):
            with self.subTest(commit=commit):
                with mock.patch.object(pin, "_git") as git:
                    with self.assertRaisesRegex(
                            pin.CheckoutPinError, "full lowercase"):
                        pin.verify_source_checkout_pin(self.root, commit, SOURCES)
                    git.assert_not_called()

    def test_s1_45_rejects_mismatched_commit_even_if_tree_is_clean(self):
        def bad_commit(root, *args):
            if args == ("rev-parse", "--verify", "HEAD^{commit}"):
                return "f" * 40
            return self.fake_git(root, *args)
        with mock.patch.object(pin, "_git", side_effect=bad_commit):
            with self.assertRaisesRegex(pin.CheckoutPinError, "differs"):
                pin.verify_source_checkout_pin(self.root, COMMIT, SOURCES)

    def test_s1_45_rejects_dirty_worktree(self):
        def changed(root, *args):
            if args[:2] == ("status", "--porcelain=v1"):
                return " M tools/synthetic.py"
            return self.fake_git(root, *args)
        with mock.patch.object(pin, "_git", side_effect=changed):
            with self.assertRaisesRegex(pin.CheckoutPinError, "dirty"):
                pin.verify_source_checkout_pin(self.root, COMMIT, SOURCES)

    def test_s1_45_rejects_missing_tracked_manifest_file(self):
        def missing(root, *args):
            if args[:2] == ("ls-files", "--cached"):
                return "tools/synthetic.py"
            return self.fake_git(root, *args)
        with mock.patch.object(pin, "_git", side_effect=missing):
            with self.assertRaisesRegex(pin.CheckoutPinError, "untracked"):
                pin.verify_source_checkout_pin(self.root, COMMIT, SOURCES)

    def test_s1_45_rejects_root_mismatch_and_symlink_alias(self):
        def nested(root, *args):
            if args == ("rev-parse", "--show-toplevel"):
                return str(root.parent)
            return self.fake_git(root, *args)
        with mock.patch.object(pin, "_git", side_effect=nested):
            with self.assertRaisesRegex(pin.CheckoutPinError, "exact"):
                pin.verify_source_checkout_pin(self.root, COMMIT, SOURCES)
        alias = self.root.parent / (self.root.name + "-alias")
        alias.symlink_to(self.root, target_is_directory=True)
        self.addCleanup(alias.unlink)
        with mock.patch.object(pin, "_git") as git:
            with self.assertRaisesRegex(pin.CheckoutPinError, "absolute"):
                pin.verify_source_checkout_pin(alias, COMMIT, SOURCES)
            git.assert_not_called()

    def test_s1_45_sanitizes_git_environment_before_readonly_inspection(self):
        with (mock.patch.object(pin.shutil, "which", return_value="/usr/bin/git"),
              mock.patch.object(pin.subprocess, "run",
                                return_value=mock.Mock(returncode=0, stdout="ok\n"))
              as run,
              mock.patch.dict(pin.os.environ, {
                  "GIT_DIR": "/host/other",
                  "GIT_WORK_TREE": "/host",
                  "GIT_CONFIG_COUNT": "2"})):
            self.assertEqual(pin._git(self.root, "rev-parse", "HEAD"), "ok")
        options = run.call_args
        self.assertEqual(options.kwargs["env"].get("GIT_DIR"), None)
        self.assertEqual(options.kwargs["env"].get("GIT_CONFIG_COUNT"), None)
        self.assertEqual(options.kwargs["env"]["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(options.kwargs["stdin"], pin.subprocess.DEVNULL)
        self.assertNotIn("shell", options.kwargs)
        self.assertIn("core.fsmonitor=false", options.args[0])

    def test_s1_46_ignored_artifact_is_rejected_after_clean_status(self):
        def ignored(root, *args):
            if args[:3] == ("ls-files", "--others", "--ignored"):
                return "tools/__pycache__/"
            return self.fake_git(root, *args)
        with mock.patch.object(pin, "_git", side_effect=ignored):
            with self.assertRaisesRegex(pin.CheckoutPinError,
                                        "ignored or hidden"):
                pin.verify_source_checkout_pin(self.root, COMMIT, SOURCES)

    def test_s1_46_git_symlink_or_submodule_is_rejected(self):
        for mode in ("120000", "160000", "100644"):
            with self.subTest(mode=mode):
                def staged(root, *args):
                    if args[:2] == ("ls-files", "--stage"):
                        return (
                            f"{mode} " + "a" * 40
                            + " 0\\ttools/synthetic.py\\n"
                            + "100644 " + "b" * 40
                            + " 0\\ttests/fixture.c").replace(
                                "\\t", "\t").replace("\\n", "\n")
                    return self.fake_git(root, *args)
                with mock.patch.object(pin, "_git", side_effect=staged):
                    if mode == "100644":
                        self.assertEqual(pin.verify_source_checkout_pin(
                            self.root, COMMIT, SOURCES)["checked_manifest_entries"], 2)
                    else:
                        with self.assertRaisesRegex(
                                pin.CheckoutPinError, "symlink, gitlink"):
                            pin.verify_source_checkout_pin(
                                self.root, COMMIT, SOURCES)

    def test_s1_46_unmerged_index_entries_are_rejected(self):
        def unmerged(root, *args):
            if args[:2] == ("ls-files", "--stage"):
                return ("100644 " + "a" * 40
                        + " 2\\ttools/synthetic.py\\n"
                        + "100644 " + "b" * 40
                        + " 0\\ttests/fixture.c").replace(
                            "\\t", "\t").replace("\\n", "\n")
            return self.fake_git(root, *args)
        with mock.patch.object(pin, "_git", side_effect=unmerged):
            with self.assertRaisesRegex(
                    pin.CheckoutPinError, "unmerged"):
                pin.verify_source_checkout_pin(self.root, COMMIT, SOURCES)

    def test_s1_45_requires_external_commit_challenge_and_receipt_first(self):
        incomplete = [
            ["--reviewer-pinned-checkout"],
            ["--reviewer-pinned-checkout", "--expected-source-commit", COMMIT],
            ["--reviewer-pinned-checkout", "--reviewer-challenge", CHALLENGE],
            ["--expected-source-commit", COMMIT],
            ["--reviewer-pinned-checkout", "--reviewer-challenge", CHALLENGE,
             "--evidence-output", "/tmp/synthetic-receipt.json"],
        ]
        base = [
            "pe_arch_vm_validation.py", "--ghidra-home", "/no/ghidra",
            "--ghidra-archive", "/no/ghidra.zip",
        ]
        for options in incomplete:
            with self.subTest(options=options):
                with (mock.patch.object(validation.sys, "argv", base + options),
                      mock.patch.object(validation, "run_acceptance") as native,
                      mock.patch.object(validation, "verify_source_checkout_pin") as git,
                      redirect_stderr(StringIO())):
                    self.assertEqual(validation.main(), 2)
                native.assert_not_called()
                git.assert_not_called()

    def test_s1_45_dirty_or_wrong_commit_blocks_native_workloads(self):
        argv = [
            "pe_arch_vm_validation.py", "--ghidra-home", "/no/ghidra",
            "--ghidra-archive", "/no/ghidra.zip",
            "--evidence-output", "/no/private/receipt.json",
            "--reviewer-challenge", CHALLENGE,
            "--reviewer-pinned-checkout", "--expected-source-commit", COMMIT,
        ]
        with (mock.patch.object(validation.sys, "argv", argv),
              mock.patch.object(validation, "verify_source_checkout_pin",
                                side_effect=pin.CheckoutPinError("dirty tree")),
              mock.patch.object(validation, "run_acceptance") as native,
              mock.patch.object(validation, "write_receipt_no_overwrite") as writer,
              redirect_stderr(StringIO())):
            self.assertEqual(validation.main(), 2)
        native.assert_not_called()
        writer.assert_not_called()

    def test_s1_46_post_acceptance_checkout_change_blocks_receipt(self):
        argv = [
            "pe_arch_vm_validation.py", "--ghidra-home", "/no/ghidra",
            "--ghidra-archive", "/no/ghidra.zip",
            "--evidence-output", "/no/private/receipt.json",
            "--reviewer-challenge", CHALLENGE,
            "--reviewer-pinned-checkout", "--expected-source-commit", COMMIT,
        ]
        first = {"status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED",
                 "expected_commit": COMMIT}
        changed = {"status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED",
                   "expected_commit": COMMIT,
                   "unexpected": "different"}
        with (mock.patch.object(validation.sys, "argv", argv),
              mock.patch.object(validation, "verify_source_checkout_pin",
                                side_effect=[first, changed]) as check,
              mock.patch.object(validation, "run_acceptance",
                                return_value={"status": "mocked"}) as native,
              mock.patch.object(validation, "write_receipt_no_overwrite")
              as writer, redirect_stderr(StringIO()) as stderr):
            self.assertEqual(validation.main(), 2)
        self.assertEqual(check.call_count, 2)
        native.assert_called_once()
        writer.assert_not_called()
        self.assertIn("pin changed during native acceptance",
                      stderr.getvalue())

    def test_s1_46_post_acceptance_checkout_rejection_blocks_receipt(self):
        argv = [
            "pe_arch_vm_validation.py", "--ghidra-home", "/no/ghidra",
            "--ghidra-archive", "/no/ghidra.zip",
            "--evidence-output", "/no/private/receipt.json",
            "--reviewer-challenge", CHALLENGE,
            "--reviewer-pinned-checkout", "--expected-source-commit", COMMIT,
        ]
        with (mock.patch.object(validation.sys, "argv", argv),
              mock.patch.object(validation, "verify_source_checkout_pin",
                  side_effect=[
                      {"status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED"},
                      pin.CheckoutPinError("ignored file created during run"),
                  ]),
              mock.patch.object(validation, "run_acceptance",
                                return_value={"status": "mocked"}) as native,
              mock.patch.object(validation, "write_receipt_no_overwrite")
              as writer, redirect_stderr(StringIO()) as stderr):
            self.assertEqual(validation.main(), 2)
        native.assert_called_once()
        writer.assert_not_called()
        self.assertIn("ignored file created during run", stderr.getvalue())

    def test_s1_45_checkout_pin_is_not_in_native_receipt_v2(self):
        argv = [
            "pe_arch_vm_validation.py", "--ghidra-home", "/no/ghidra",
            "--ghidra-archive", "/no/ghidra.zip",
            "--evidence-output", "/no/private/receipt.json",
            "--reviewer-challenge", CHALLENGE,
            "--reviewer-pinned-checkout", "--expected-source-commit", COMMIT,
        ]
        native_report = {"status": "synthetic-test-report"}
        local_pin = {"status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED",
                     "native_vm_or_kernel_verified": False}
        out = StringIO()
        with (mock.patch.object(validation.sys, "argv", argv),
              mock.patch.object(validation, "verify_source_checkout_pin",
                                return_value=local_pin),
              mock.patch.object(validation, "run_acceptance",
                                return_value=native_report),
              mock.patch.object(validation, "write_receipt_no_overwrite",
                                return_value={"receipt_sha256": "1" * 64})
              as writer, redirect_stdout(out)):
            self.assertEqual(validation.main(), 0)
        self.assertEqual(writer.call_args.args[0], native_report)
        published = json.loads(out.getvalue())
        self.assertEqual(published["local_source_checkout_pin"], local_pin)
        self.assertNotIn("local_source_checkout_pin", native_report)
        self.assertIn("local_receipt", published)


class RealLocalGitPinIntegrationTests(unittest.TestCase):
    """Actual Git integration; optional where the Arch container lacks Git."""

    def setUp(self):
        if not __import__("shutil").which("git"):
            self.skipTest("Git binary absent in this userspace")
        import subprocess
        self.git_subprocess = subprocess
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tools").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "tools/synthetic.py").write_text(
            "print('synthetic')\\n", encoding="utf-8")
        (self.root / "tests/fixture.c").write_text(
            "int test(void){return 0;}\\n", encoding="utf-8")
        (self.root / ".gitignore").write_text(
            "*.ignored\\n__pycache__/\\n", encoding="utf-8")
        self.run_git("init", "-q")
        self.run_git("config", "user.email", "ci-fixture@example.invalid")
        self.run_git("config", "user.name", "Synthetic CI Fixture")
        self.run_git("add", "--all")
        self.run_git("commit", "-qm", "Synthetic local-only fixture")
        self.commit = self.run_git("rev-parse", "HEAD").strip()

    def run_git(self, *arguments):
        result = self.git_subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            capture_output=True, text=True, timeout=15, check=True)
        return result.stdout

    def test_s1_46_real_git_clean_checkout_and_ignored_drop_in(self):
        result = pin.verify_source_checkout_pin(
            self.root, self.commit, SOURCES)
        self.assertEqual(result["status"], "LOCAL_GIT_CHECKOUT_PIN_MATCHED")
        (self.root / "tools/injected.ignored").write_bytes(b"unexpected")
        self.assertEqual(self.run_git("status", "--porcelain=v1").strip(), "")
        with self.assertRaisesRegex(
                pin.CheckoutPinError, "ignored or hidden"):
            pin.verify_source_checkout_pin(self.root, self.commit, SOURCES)

    def test_s1_46_real_git_symlink_is_rejected_even_clean(self):
        target = self.root / "source-target.txt"
        target.write_text("synthetic target", encoding="utf-8")
        link = self.root / "tools/synthetic.py"
        link.unlink()
        link.symlink_to("../source-target.txt")
        self.run_git("add", "--all")
        self.run_git("commit", "-qm", "Fixture with tracked symlink")
        commit = self.run_git("rev-parse", "HEAD").strip()
        self.assertEqual(self.run_git("status", "--porcelain=v1").strip(), "")
        with self.assertRaisesRegex(pin.CheckoutPinError, "symlink, gitlink"):
            pin.verify_source_checkout_pin(self.root, commit, SOURCES)


if __name__ == "__main__":
    unittest.main()
