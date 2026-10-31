"""PE-S1.65: offline reviewer manifest preparation, no evidence fabrication."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_65_observer_prepare as prep
import pe_arch_vm_s1_63_external_observer as external
from test_pe_arch_vm_s1_63_external_observer import (
    ExternalObserverSigningTests,
)


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH unavailable")
class ExternalHostPackPreparationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ExternalObserverSigningTests(
            "test_three_distinct_real_signers_valid_and_no_release")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.owner = self.fixture.observer
        self.operator = self.fixture.operator
        self.manifest = self.fixture.manifest_path
        self.signature = self.fixture.signature_path
        self.pin = {
            key: self.fixture.pins[key] for key in prep.PINS
        }
        self.manifest.unlink()
        self.signature.unlink()

    def prepare(self, **overrides):
        return prep.prepare_observer_manifest(
            self.owner, self.operator, **{**self.pin, **overrides})

    def test_prepare_new_real_log_inventory_then_real_ssh_verify(self):
        result = self.prepare()
        self.assertEqual(result["status"], prep.STATUS)
        self.assertEqual(result["observation_count"], 4)
        self.assertFalse(result["signature_created"])
        self.assertFalse(result["observer_private_key_accessed"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])
        self.assertEqual(
            hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
            result["manifest_sha256"])
        self.assertEqual(self.manifest.stat().st_mode & 0o777, 0o600)
        actual = json.loads(self.manifest.read_text("ascii"))
        self.assertFalse(actual["release_authorized"])
        self.assertFalse(actual["independent_vm_attestation"])
        # Sign *without replacing the manifest*. Private key only touched
        # by explicit test command, not PE-S1.65.
        subprocess.run(
            ["ssh-keygen", "-Y", "sign",
             "-f", str(self.fixture.private_keys["observer"]),
             "-n", external.NAMESPACE, str(self.manifest)],
            check=True, capture_output=True, timeout=15)
        self.manifest.with_suffix(".json.sig").replace(self.signature)
        self.signature.chmod(0o600)
        reviewed = external.verify_external_observer(
            self.owner, self.operator,
            **{
                **self.pin,
                "expected_manifest_sha256": result["manifest_sha256"],
                "expected_signature_sha256": hashlib.sha256(
                    self.signature.read_bytes()).hexdigest(),
            })
        self.assertEqual(reviewed["status"], external.STATUS)
        self.assertFalse(reviewed["independent_vm_attestation"])

    def test_existing_manifest_remains_unchanged_and_refused(self):
        first = self.prepare()
        existing = self.manifest.read_bytes()
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare()
        self.assertEqual(self.manifest.read_bytes(), existing)
        self.assertEqual(
            hashlib.sha256(existing).hexdigest(), first["manifest_sha256"])

    def test_existing_signature_refuses_before_manifest_creation(self):
        self.signature.write_bytes(b"UNTRUSTED PLACEHOLDER\n")
        self.signature.chmod(0o600)
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare()
        self.assertFalse(self.manifest.exists())

    def test_wrong_pinned_observer_key_refused(self):
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare(expected_observer_signers_sha256="f" * 64)
        self.assertFalse(self.manifest.exists())

    def test_wrong_reviewer_and_witness_key_pins_refused(self):
        for name in ("expected_reviewer_signers_sha256",
                     "expected_witness_signers_sha256"):
            with self.subTest(pin=name), self.assertRaises(
                    prep.ObserverPreparationError):
                self.prepare(**{name: "f" * 64})
            self.assertFalse(self.manifest.exists())

    def test_reused_custody_ssh_public_key_refused(self):
        source = (self.operator / external.REVIEWER_KEY_FILE
                  ).read_text("ascii").split()
        destination = self.owner / external.SIGNERS_FILE
        destination.write_text(
            f"{self.pin['expected_observer_id']} {source[1]} {source[2]}\n",
            encoding="ascii")
        with self.assertRaisesRegex(
                prep.ObserverPreparationError, "must differ"):
            self.prepare(expected_observer_signers_sha256=hashlib.sha256(
                destination.read_bytes()).hexdigest())
        self.assertFalse(self.manifest.exists())

    def test_missing_host_log_not_fabricated(self):
        target = self.owner / external.OBS_FILES["host_vm_launch"]
        target.unlink()
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare()
        self.assertFalse(self.manifest.exists())

    def test_binary_host_log_refused(self):
        target = self.owner / external.OBS_FILES["host_scope_cleanup"]
        target.write_bytes(b"not a text log\x00test")
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare()
        self.assertFalse(self.manifest.exists())

    def test_oversized_host_log_refused(self):
        target = self.owner / external.OBS_FILES["host_scope_cleanup"]
        target.write_bytes(b"X" * (external.MAX_LOG_BYTES + 1))
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare()
        self.assertFalse(self.manifest.exists())

    def test_symlinked_host_log_refused(self):
        original = self.owner / external.OBS_FILES["host_guest_kernel"]
        other = self.owner / "otherfile.txt"
        original.replace(other)
        original.symlink_to(other)
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare()

    def test_hardlinked_host_log_refused(self):
        original = self.owner / external.OBS_FILES["host_vm_launch"]
        os.link(original, self.owner / "unexpected-link")
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare()

    def test_nonprivate_observer_directory_refused(self):
        self.owner.chmod(0o755)
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare()

    def test_same_or_nested_directories_refused(self):
        with self.assertRaises(prep.ObserverPreparationError):
            prep.prepare_observer_manifest(
                self.owner, self.owner, **self.pin)
        with self.assertRaises(prep.ObserverPreparationError):
            prep.prepare_observer_manifest(
                self.owner, self.owner / "child", **self.pin)

    def test_invalid_challenge_commit_and_identity_refused(self):
        for key, value in (
            ("expected_source_commit", "g" * 40),
            ("expected_challenge", "0" * 64),
            ("expected_observer_id", self.pin["expected_reviewer_id"]),
            ("expected_observer_id", "a" * 81),
            ("expected_receipt_sha256", "NOT-SHA256"),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(
                    prep.ObserverPreparationError):
                self.prepare(**{key: value})
            self.assertFalse(self.manifest.exists())

    def test_only_one_manifest_written_no_keys_or_signature(self):
        contents_before = set(os.listdir(self.owner))
        self.prepare()
        self.assertEqual(
            set(os.listdir(self.owner)) - contents_before,
            {external.MANIFEST_FILE})
        self.assertFalse(self.signature.exists())

    def test_cli_success_is_preparation_only(self):
        args = ["--observer-dir", str(self.owner),
                "--custody-dir", str(self.operator)]
        for key, value in self.pin.items():
            args += ["--" + key.replace("_", "-"), value]
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = prep.main(args)
        self.assertEqual(code, 0)
        self.assertEqual(err.getvalue(), "")
        status = json.loads(out.getvalue())
        self.assertEqual(status["status"], prep.STATUS)
        self.assertFalse(status["signature_created"])
        self.assertFalse(status["independent_vm_attestation"])
        self.assertFalse(status["unknown_windows_pe_execution_authorized"])

    def test_cli_second_attempt_rejects_and_does_not_overwrite(self):
        self.prepare()
        original = self.manifest.read_bytes()
        args = ["--observer-dir", str(self.owner),
                "--custody-dir", str(self.operator)]
        for key, value in self.pin.items():
            args += ["--" + key.replace("_", "-"), value]
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = prep.main(args)
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), "")
        report = json.loads(err.getvalue())
        self.assertEqual(report["status"], prep.REJECTED)
        self.assertFalse(report["apk_or_ota_publication_authorized"])
        self.assertEqual(self.manifest.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
