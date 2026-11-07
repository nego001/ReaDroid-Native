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
import test_pe_arch_vm_s1_73_two_record_review as semantic_fixtures
from test_pe_arch_vm_s2_13_runtime_log_chain import make_fixture, SESSION
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
            if key in self.fixture.pins
        }
        self.manifest.unlink()
        self.signature.unlink()
        # Replace the old generic S1.63 placeholder strings with *synthetic*
        # but correctly structured S1.70/71 records. These are test-only;
        # no libvirt or kernel attestation is implied.
        raw_host = semantic_fixtures.first_record().replace(
            semantic_fixtures.CHALLENGE.encode(),
            self.pin["expected_challenge"].encode())
        host_pin = hashlib.sha256(raw_host).hexdigest()
        raw_guest = semantic_fixtures.second_record(host_pin).replace(
            semantic_fixtures.CHALLENGE.encode(),
            self.pin["expected_challenge"].encode())
        for label, raw in (
            ("host_vm_launch", raw_host),
            ("host_guest_kernel", raw_guest),
        ):
            target = self.owner / external.OBS_FILES[label]
            target.write_bytes(raw)
            target.chmod(0o600)
        # The remaining texts are synthetic, but MUST now be structurally
        # chained to the two pinned S1.70/S1.71 snapshots.
        runtime, cleanup = make_fixture(
            commit=self.pin["expected_source_commit"],
            challenge=self.pin["expected_challenge"],
            domain=semantic_fixtures.DOMAIN,
            uuid=semantic_fixtures.UUID,
            host=host_pin, guest=hashlib.sha256(raw_guest).hexdigest())
        for label, raw in (("host_seccomp_cgroups", runtime),
                           ("host_scope_cleanup", cleanup)):
            location = self.owner / external.OBS_FILES[label]
            location.write_bytes(raw)
            location.chmod(0o600)
        self.pin.update({
            "expected_domain": semantic_fixtures.DOMAIN,
            "expected_domain_uuid": semantic_fixtures.UUID,
            "expected_host_sha256": host_pin,
            "expected_guest_sha256": hashlib.sha256(raw_guest).hexdigest(),
            "expected_session_id": SESSION,
        })

    def prepare(self, **overrides):
        return prep.prepare_observer_manifest(
            self.owner, self.operator, **{**self.pin, **overrides})

    def test_prepare_new_real_log_inventory_then_real_ssh_verify(self):
        result = self.prepare()
        self.assertEqual(result["status"], prep.STATUS)
        self.assertEqual(result["observation_count"], 4)
        self.assertTrue(result["two_host_records_semantically_checked"])
        self.assertTrue(result["independently_pinned_host_record_hashes_matched"])
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
                **{key: value for key, value in self.pin.items()
                   if key not in ("expected_domain", "expected_domain_uuid",
                                  "expected_host_sha256", "expected_guest_sha256",
                                  "expected_session_id")},
                "expected_manifest_sha256": result["manifest_sha256"],
                "expected_signature_sha256": hashlib.sha256(
                    self.signature.read_bytes()).hexdigest(),
            })
        self.assertEqual(reviewed["status"], external.STATUS)
        self.assertFalse(reviewed["independent_vm_attestation"])

    def test_old_generic_text_logs_rejected_even_with_new_hash_pins(self):
        # The previous S1.65 accepted generic one-line 'observations'.
        # Signing those strings must no longer pass the stricter gate.
        first = self.owner / external.OBS_FILES["host_vm_launch"]
        first.write_bytes(b"SYNTHETIC HOST host_vm_launch: NO VM WAS EXECUTED\\n")
        first.chmod(0o600)
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare(expected_host_sha256=hashlib.sha256(
                first.read_bytes()).hexdigest())
        self.assertFalse(self.manifest.exists())

    def test_old_generic_runtime_or_cleanup_text_refused_even_if_hashed(self):
        for label in ("host_seccomp_cgroups", "host_scope_cleanup"):
            with self.subTest(label=label):
                target = self.owner / external.OBS_FILES[label]
                original = target.read_bytes()
                try:
                    target.write_bytes(b"PASS: host was secure\\n")
                    with self.assertRaises(prep.ObserverPreparationError):
                        self.prepare()
                    self.assertFalse(self.manifest.exists())
                finally:
                    target.write_bytes(original)

    def test_wrong_session_pin_blocks_unsigned_manifest(self):
        for bad in ("f"*64, "0"*64, "F"*64, "a"*63):
            with self.subTest(bad=bad), self.assertRaises(
                    prep.ObserverPreparationError):
                self.prepare(expected_session_id=bad)
            self.assertFalse(self.manifest.exists())

    def test_wrong_pinned_domain_and_uuid_block_manifest(self):
        for key, value in (
            ("expected_domain", "other-reviewer-vm"),
            ("expected_domain_uuid", "11111111-1111-4111-8111-111111111111"),
        ):
            with self.subTest(key=key), self.assertRaises(
                    prep.ObserverPreparationError):
                self.prepare(**{key: value})
            self.assertFalse(self.manifest.exists())

    def test_wrong_guest_sha_blocks_manifest_before_signature(self):
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare(expected_guest_sha256="f" * 64)
        self.assertFalse(self.manifest.exists())
        self.assertFalse(self.signature.exists())

    def test_forged_guest_claim_rejected_even_after_hash_update(self):
        second = self.owner / external.OBS_FILES["host_guest_kernel"]
        changed = second.read_bytes().replace(
            b"independent_vm_attestation=false",
            b"independent_vm_attestation=true")
        second.write_bytes(changed)
        second.chmod(0o600)
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare(expected_guest_sha256=hashlib.sha256(changed).hexdigest())
        self.assertFalse(self.manifest.exists())

    def test_rehashed_parsed_guest_mismatch_cannot_enter_manifest(self):
        second = self.owner / external.OBS_FILES["host_guest_kernel"]
        changed = second.read_bytes().replace(
            b"parsed_guest_machine=x86_64", b"parsed_guest_machine=aarch64")
        second.write_bytes(changed)
        second.chmod(0o600)
        with self.assertRaises(prep.ObserverPreparationError):
            self.prepare(expected_guest_sha256=hashlib.sha256(changed).hexdigest())
        self.assertFalse(self.manifest.exists())

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
