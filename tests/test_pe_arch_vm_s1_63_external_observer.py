"""PE-S1.63: REAL disposable Ed25519 signature checks, NEVER VM attestation."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_63_external_observer as observer

COMMIT = "a" * 40
CHALLENGE = "1" * 64
REVIEWER_ID = "custody-reviewer@example.invalid"
WITNESS_ID = "custody-witness@example.invalid"
OBSERVER_ID = "host-observer@example.invalid"
PINS = {
    "expected_source_commit": COMMIT,
    "expected_challenge": CHALLENGE,
    "expected_request_sha256": "2" * 64,
    "expected_custody_sha256": "3" * 64,
    "expected_receipt_sha256": "4" * 64,
    "expected_reviewer_id": REVIEWER_ID,
    "expected_witness_id": WITNESS_ID,
    "expected_observer_id": OBSERVER_ID,
}


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH unavailable")
class ExternalObserverSigningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pe-s1-63-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.observer = self.root / "separate-observer"
        self.operator = self.root / "operator-custody"
        self.keys = self.root / "temporary-test-keys"
        for folder in (self.observer, self.operator, self.keys):
            folder.mkdir(mode=0o700)
        self.private_keys = {}
        for role, principal, directory, name in (
            ("observer", OBSERVER_ID, self.observer,
             observer.SIGNERS_FILE),
            ("reviewer", REVIEWER_ID, self.operator,
             observer.REVIEWER_KEY_FILE),
            ("witness", WITNESS_ID, self.operator,
             observer.WITNESS_KEY_FILE),
        ):
            key = self.keys / role
            subprocess.run(
                ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
                check=True, capture_output=True, timeout=15)
            public = key.with_suffix(".pub").read_text("ascii").split()
            allowed = directory / name
            allowed.write_text(
                f"{principal} {public[0]} {public[1]}\n", encoding="ascii")
            allowed.chmod(0o600)
            self.private_keys[role] = key
        self.manifest_path = self.observer / observer.MANIFEST_FILE
        self.signature_path = self.observer / observer.SIGNATURE_FILE
        self.record = {
            "schema": observer.SCHEMA,
            "security_classification": observer.CLASSIFICATION,
            "observer_id": OBSERVER_ID,
            "reviewer_id": REVIEWER_ID,
            "witness_id": WITNESS_ID,
            "source_commit": COMMIT,
            "reviewer_challenge": CHALLENGE,
            "request_sha256": PINS["expected_request_sha256"],
            "custody_index_sha256": PINS["expected_custody_sha256"],
            "receipt_sha256": PINS["expected_receipt_sha256"],
            "observer_local_time_utc_not_attested":
                "2026-10-30T22:00:00+00:00",
            "independent_vm_attestation": False,
            "release_authorized": False,
            "observations": {},
        }
        for label, name in observer.OBS_FILES.items():
            source = self.observer / name
            data = f"SYNTHETIC HOST {label}: NO VM WAS EXECUTED\n".encode()
            source.write_bytes(data)
            source.chmod(0o600)
            self.record["observations"][label] = {
                "filename": name, "sha256": hashlib.sha256(data).hexdigest()}
        self.sign()
        self.pins = self.options()

    def sign(self, *, namespace=None):
        self.manifest_path.write_bytes(
            (json.dumps(self.record, sort_keys=True,
                        separators=(",", ":")) + "\n").encode("ascii"))
        self.manifest_path.chmod(0o600)
        subprocess.run(
            ["ssh-keygen", "-Y", "sign",
             "-f", str(self.private_keys["observer"]),
             "-n", namespace or observer.NAMESPACE,
             str(self.manifest_path)],
            check=True, capture_output=True, timeout=15)
        temporary_signature = self.manifest_path.with_suffix(".json.sig")
        temporary_signature.replace(self.signature_path)
        self.signature_path.chmod(0o600)

    def options(self):
        return {
            **PINS,
            "expected_manifest_sha256":
                hashlib.sha256(self.manifest_path.read_bytes()).hexdigest(),
            "expected_signature_sha256":
                hashlib.sha256(self.signature_path.read_bytes()).hexdigest(),
            "expected_observer_signers_sha256": hashlib.sha256(
                (self.observer / observer.SIGNERS_FILE).read_bytes()).hexdigest(),
            "expected_reviewer_signers_sha256": hashlib.sha256(
                (self.operator / observer.REVIEWER_KEY_FILE).read_bytes()).hexdigest(),
            "expected_witness_signers_sha256": hashlib.sha256(
                (self.operator / observer.WITNESS_KEY_FILE).read_bytes()).hexdigest(),
        }

    def verify(self, **overrides):
        return observer.verify_external_observer(
            self.observer, self.operator,
            **{**self.pins, **overrides})

    def test_three_distinct_real_signers_valid_and_no_release(self):
        result = self.verify()
        self.assertEqual(result["status"], observer.STATUS)
        self.assertTrue(result["distinct_observer_reviewer_witness_ssh_keys_verified"])
        self.assertTrue(result["external_observer_detached_signature_verified"])
        self.assertEqual(result["host_observation_file_count"], 4)
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["observer_host_independently_authenticated"])
        self.assertFalse(result["native_arch_kernel_independently_verified"])
        self.assertFalse(result["unknown_windows_pe_execution_authorized"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])

    def test_bad_signature_refused_even_when_sha_repinned(self):
        self.signature_path.write_bytes(
            self.signature_path.read_bytes().replace(b"BEGIN", b"FAKED", 1))
        with self.assertRaises(observer.ExternalObserverError):
            self.verify(**{
                "expected_signature_sha256":
                    hashlib.sha256(self.signature_path.read_bytes()).hexdigest()
            })

    def test_wrong_signature_namespace_rejected_even_with_repin(self):
        self.sign(namespace="negresco-wrong-namespace")
        with self.assertRaises(observer.ExternalObserverError):
            self.verify(**self.options())

    def test_reused_custody_key_refused_even_with_repin(self):
        observer_key = self.observer / observer.SIGNERS_FILE
        reviewer_key = self.operator / observer.REVIEWER_KEY_FILE
        allowed = reviewer_key.read_text("ascii").split()
        observer_key.write_text(
            f"{OBSERVER_ID} {allowed[1]} {allowed[2]}\n", encoding="ascii")
        self.sign()
        with self.assertRaisesRegex(
                observer.ExternalObserverError, "reused custody"):
            self.verify(**self.options())

    def test_wrong_external_pin_refused_before_signature_verifier(self):
        with mock.patch.object(observer.witness, "_ssh_verify") as ssh:
            with self.assertRaises(observer.ExternalObserverError):
                self.verify(expected_manifest_sha256="f" * 64)
        ssh.assert_not_called()

    def test_tampered_observation_rejected_even_with_valid_signature(self):
        path = self.observer / observer.OBS_FILES["host_scope_cleanup"]
        path.write_bytes(b"FORGED CLEANUP LOG\n")
        with self.assertRaisesRegex(
                observer.ExternalObserverError, "Observer log differs"):
            self.verify()

    def test_rehashed_observation_does_not_override_external_manifest_pin(self):
        name = observer.OBS_FILES["host_seccomp_cgroups"]
        path = self.observer / name
        path.write_bytes(b"FORGED CROUP CLAIMS\n")
        self.record["observations"]["host_seccomp_cgroups"]["sha256"] = (
            hashlib.sha256(path.read_bytes()).hexdigest())
        self.sign()
        with self.assertRaises(observer.ExternalObserverError):
            self.verify()

    def test_false_vm_attestation_rejected_even_if_resigned(self):
        self.record["independent_vm_attestation"] = True
        self.sign()
        with self.assertRaises(observer.ExternalObserverError):
            self.verify(**self.options())

    def test_extra_release_claim_rejected_even_if_resigned(self):
        self.record["unknown_windows_pe_execution_authorized"] = True
        self.sign()
        with self.assertRaises(observer.ExternalObserverError):
            self.verify(**self.options())

    def test_missing_observation_inventory_entry_rejected(self):
        del self.record["observations"]["host_vm_launch"]
        self.sign()
        with self.assertRaises(observer.ExternalObserverError):
            self.verify(**self.options())

    def test_non_utc_observer_claim_refused(self):
        self.record["observer_local_time_utc_not_attested"] = (
            "2026-10-30T22:00:00-03:00")
        self.sign()
        with self.assertRaises(observer.ExternalObserverError):
            self.verify(**self.options())

    def test_different_reviewer_challenge_refused_after_resigning(self):
        self.record["reviewer_challenge"] = "e" * 64
        self.sign()
        with self.assertRaises(observer.ExternalObserverError):
            self.verify(**self.options())

    def test_untrusted_observer_directory_refused(self):
        self.observer.chmod(0o755)
        with self.assertRaises(observer.ExternalObserverError):
            self.verify()

    def test_linked_log_refused(self):
        source = self.observer / observer.OBS_FILES["host_vm_launch"]
        linked = self.observer / "extra-hardlink"
        os.link(source, linked)
        with self.assertRaises(observer.ExternalObserverError):
            self.verify()

    def test_changed_file_during_ssh_verification_refused(self):
        real = observer.witness._ssh_verify
        target = self.observer / observer.OBS_FILES["host_guest_kernel"]
        def mutate(*args, **kwargs):
            real(*args, **kwargs)
            target.write_bytes(target.read_bytes() + b"MUTATED\n")
        with mock.patch.object(observer.witness, "_ssh_verify",
                               side_effect=mutate):
            with self.assertRaisesRegex(
                    observer.ExternalObserverError, "changed during"):
                self.verify()

    def test_cli_valid_signed_pack_exit_two_with_no_release(self):
        args = [
            "--observer-dir", str(self.observer),
            "--custody-dir", str(self.operator),
        ]
        for name, value in self.pins.items():
            args += ["--" + name.replace("_", "-"), value]
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = observer.main(args)
        self.assertEqual(result, 2)
        self.assertEqual(stderr.getvalue(), "")
        parsed = json.loads(stdout.getvalue())
        self.assertEqual(parsed["status"], observer.STATUS)
        self.assertFalse(parsed["independent_vm_attestation"])

    def test_cli_bad_pin_is_rejected_with_no_release(self):
        args = [
            "--observer-dir", str(self.observer),
            "--custody-dir", str(self.operator),
        ]
        for name, value in self.pins.items():
            args += ["--" + name.replace("_", "-"), value]
        args[args.index("--expected-manifest-sha256") + 1] = "f" * 64
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = observer.main(args)
        self.assertEqual(result, 2)
        self.assertEqual(stdout.getvalue(), "")
        parsed = json.loads(stderr.getvalue())
        self.assertEqual(parsed["status"], observer.REJECTED)
        self.assertFalse(parsed["independent_vm_attestation"])
        self.assertFalse(parsed["unknown_windows_pe_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
