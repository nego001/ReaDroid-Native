"""PE-S2.16: real disposable OpenSSH signatures, synthetic libvirt only."""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace
import shutil
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_63_external_observer as v1
import pe_arch_vm_s2_15_readonly_host_domstats as domstats
import pe_arch_vm_s2_16_signed_domstats_extension as extension
from test_pe_arch_vm_s1_63_external_observer import (
    ExternalObserverSigningTests, CHALLENGE as CHALLENGE_V1,
)
from test_pe_arch_vm_s1_73_two_record_review import (
    DOMAIN, UUID, CHALLENGE as CHALLENGE_HOST, first_record, second_record,
)
from test_pe_arch_vm_s2_15_readonly_host_domstats import STATS

SESSION = "6"*64


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH required")
class SignedSidecarV2Contracts(unittest.TestCase):
    def setUp(self):
        fixture = ExternalObserverSigningTests(
            "test_three_distinct_real_signers_valid_and_no_release")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f = fixture
        self.owner = fixture.observer
        self.operator = fixture.operator
        host_record = first_record().replace(
            CHALLENGE_HOST.encode("ascii"), CHALLENGE_V1.encode("ascii"))
        host_sha = hashlib.sha256(host_record).hexdigest()
        guest_record = second_record(host_sha).replace(
            CHALLENGE_HOST.encode("ascii"), CHALLENGE_V1.encode("ascii"))
        guest_sha = hashlib.sha256(guest_record).hexdigest()
        # No signed package while an opt-in host sidecar is collected.
        fixture.manifest_path.unlink()
        fixture.signature_path.unlink()
        for key, data in (
                ("host_vm_launch", host_record),
                ("host_guest_kernel", guest_record)):
            target = self.owner / v1.OBS_FILES[key]
            target.write_bytes(data)
            target.chmod(0o600)
            fixture.record["observations"][key]["sha256"] = (
                hashlib.sha256(data).hexdigest())
        with (mock.patch.object(domstats.shutil, "which",
                                return_value="/usr/bin/virsh"),
              mock.patch.object(domstats.host, "_virsh_read",
                                side_effect=[UUID, "running", "running", UUID]),
              mock.patch.object(domstats.bounded, "run_bounded_native",
                                return_value=SimpleNamespace(
                                    returncode=0, stdout=STATS, stderr=b""))):
            sidecar = domstats.capture_host_domstats(
                self.owner, domain=DOMAIN, expected_domain_uuid=UUID,
                expected_source_commit=fixture.record["source_commit"],
                reviewer_challenge=CHALLENGE_V1,
                expected_session_id=SESSION, expected_host_sha256=host_sha,
                expected_guest_sha256=guest_sha,
                capture_from_independent_host=True)
        self.assertEqual(sidecar["status"], domstats.CAPTURED)
        fixture.sign()
        old = fixture.options()
        self.pins = {
            "expected_source_commit": fixture.record["source_commit"],
            "expected_challenge": CHALLENGE_V1,
            "expected_session_id": SESSION,
            "expected_domain": DOMAIN,
            "expected_domain_uuid": UUID,
            "expected_host_sha256": host_sha,
            "expected_guest_sha256": guest_sha,
            "expected_domstats_sha256": sidecar["sidecar_sha256"],
            "expected_v1_manifest_sha256": old["expected_manifest_sha256"],
            "expected_v1_signature_sha256": old["expected_signature_sha256"],
            "expected_observer_signers_sha256":
                old["expected_observer_signers_sha256"],
            "expected_reviewer_signers_sha256":
                old["expected_reviewer_signers_sha256"],
            "expected_witness_signers_sha256":
                old["expected_witness_signers_sha256"],
            "expected_observer_id": fixture.record["observer_id"],
            "expected_reviewer_id": fixture.record["reviewer_id"],
            "expected_witness_id": fixture.record["witness_id"],
            "expected_request_sha256": old["expected_request_sha256"],
            "expected_custody_sha256": old["expected_custody_sha256"],
            "expected_receipt_sha256": old["expected_receipt_sha256"],
        }
        self.v2_manifest = self.owner / extension.MANIFEST
        self.v2_signature = self.owner / extension.SIGNATURE

    def prepare(self, **changed):
        return extension.prepare_signed_domstats_extension(
            self.owner, self.operator, **{**self.pins, **changed})

    def sign(self, *, namespace=None):
        subprocess.run([
            "ssh-keygen", "-Y", "sign",
            "-f", str(self.f.private_keys["observer"]),
            "-n", namespace or extension.NAMESPACE, str(self.v2_manifest),
        ], capture_output=True, timeout=15, check=True)
        actual_sig = self.v2_manifest.with_suffix(".json.sig")
        actual_sig.replace(self.v2_signature)
        self.v2_signature.chmod(0o600)

    def verify(self, **changed):
        options = {
            "expected_extension_manifest_sha256":
                hashlib.sha256(self.v2_manifest.read_bytes()).hexdigest(),
            "expected_extension_signature_sha256":
                hashlib.sha256(self.v2_signature.read_bytes()).hexdigest(),
        }
        return extension.verify_signed_domstats_extension(
            self.owner, self.operator, **{**self.pins, **options, **changed})

    def test_two_real_valid_signatures_and_hold_without_release(self):
        first = self.prepare()
        self.assertEqual(first["status"], extension.PREPARED)
        self.assertFalse(first["observer_private_key_accessed"])
        self.assertFalse(first["detached_signature_created"])
        self.assertFalse(self.v2_signature.exists())
        self.assertEqual(self.v2_manifest.stat().st_mode & 0o777, 0o600)
        content = json.loads(self.v2_manifest.read_text("ascii"))
        self.assertEqual(content["schema"], extension.SCHEMA)
        self.assertEqual(content["host_domstats_sidecar_sha256"],
                         self.pins["expected_domstats_sha256"])
        self.assertFalse(content["independent_vm_attestation"])
        self.assertFalse(content["release_authorized"])
        self.sign()
        approved = self.verify()
        self.assertEqual(approved["status"], extension.VERIFIED)
        self.assertTrue(approved["v2_detached_ed25519_signature_verified"])
        self.assertTrue(approved["v1_detached_signature_rechecked"])
        self.assertFalse(approved["host_hypervisor_independently_attested"])
        self.assertFalse(approved["independent_vm_attestation"])
        self.assertFalse(approved["release_authorized"])
        self.assertEqual(
            hashlib.sha256(self.f.manifest_path.read_bytes()).hexdigest(),
            self.pins["expected_v1_manifest_sha256"])

    def test_wrong_ssh_namespace_refused_even_if_repinned(self):
        self.prepare()
        self.sign(namespace=v1.NAMESPACE)
        with self.assertRaises(extension.SignedDomstatsExtensionError):
            self.verify()

    def test_previous_v1_signature_cannot_be_reused_for_v2(self):
        self.prepare()
        self.v2_signature.write_bytes(self.f.signature_path.read_bytes())
        self.v2_signature.chmod(0o600)
        with self.assertRaises(extension.SignedDomstatsExtensionError):
            self.verify()

    def test_tampered_counters_refused_even_with_new_sidecar_sha(self):
        self.prepare()
        self.sign()
        path = self.owner / domstats.TARGET
        path.write_bytes(path.read_bytes().replace(
            b"cpu.time=100000000", b"cpu.time=100000001"))
        with self.assertRaises(extension.SignedDomstatsExtensionError):
            self.verify(expected_domstats_sha256=hashlib.sha256(
                path.read_bytes()).hexdigest())

    def test_changed_v1_signed_manifest_refused_after_v2_signing(self):
        self.prepare()
        self.sign()
        self.f.manifest_path.write_bytes(
            self.f.manifest_path.read_bytes().replace(
                b'"release_authorized":false', b'"release_authorized":true'))
        with self.assertRaises(extension.SignedDomstatsExtensionError):
            self.verify()

    def test_wrong_reviewer_session_nonce_refused_before_preparation(self):
        for value in ("0"*64, "f"*64, CHALLENGE_V1):
            with self.subTest(value=value):
                with self.assertRaises(extension.SignedDomstatsExtensionError):
                    self.prepare(expected_session_id=value)
                self.assertFalse(self.v2_manifest.exists())

    def test_no_manifest_overwrite_or_second_preparation(self):
        first = self.prepare()
        original = self.v2_manifest.read_bytes()
        with self.assertRaises(extension.SignedDomstatsExtensionError):
            self.prepare()
        self.assertEqual(self.v2_manifest.read_bytes(), original)
        self.assertEqual(first["manifest_sha256"],
                         hashlib.sha256(original).hexdigest())

    def test_preexisting_v2_signature_refuses_publication(self):
        self.v2_signature.write_bytes(b"untrusted old signature\n")
        self.v2_signature.chmod(0o600)
        with self.assertRaises(extension.SignedDomstatsExtensionError):
            self.prepare()
        self.assertFalse(self.v2_manifest.exists())

    def test_signed_v2_extra_field_rejected_even_if_resigned(self):
        self.prepare()
        data = json.loads(self.v2_manifest.read_text("ascii"))
        data["release_intent"] = "yes"
        self.v2_manifest.write_bytes(
            extension._canonical(data))
        self.sign()
        with self.assertRaises(extension.SignedDomstatsExtensionError):
            self.verify()

    def test_missing_v2_signature_refused(self):
        self.prepare()
        with self.assertRaises(extension.SignedDomstatsExtensionError):
            extension.verify_signed_domstats_extension(
                self.owner, self.operator,
                expected_extension_manifest_sha256=hashlib.sha256(
                    self.v2_manifest.read_bytes()).hexdigest(),
                expected_extension_signature_sha256="f"*64,
                **self.pins)

    def test_reused_observer_id_or_signer_pin_refused(self):
        with self.assertRaises(extension.SignedDomstatsExtensionError):
            self.prepare(expected_observer_id=self.pins["expected_reviewer_id"])
        with self.assertRaises(extension.SignedDomstatsExtensionError):
            self.prepare(expected_observer_signers_sha256="f"*64)
        self.assertFalse(self.v2_manifest.exists())

    def test_cli_preparation_only_then_signed_review_exit_hold(self):
        args = ["--observer-dir", str(self.owner),
                "--custody-dir", str(self.operator)]
        for key in extension.PINS:
            args.extend(["--"+key.replace("_","-"),self.pins[key]])
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(extension.main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["status"],
                         extension.PREPARED)
        self.sign()
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(extension.main(args+[
                "--verify-existing",
                "--expected-extension-manifest-sha256",
                hashlib.sha256(self.v2_manifest.read_bytes()).hexdigest(),
                "--expected-extension-signature-sha256",
                hashlib.sha256(self.v2_signature.read_bytes()).hexdigest()
            ]), 2)
        self.assertEqual(json.loads(output.getvalue())["status"],
                         extension.VERIFIED)

    def test_symlinked_v2_manifest_refused(self):
        self.prepare()
        original = self.owner / "v2-untrusted"
        self.v2_manifest.replace(original)
        self.v2_manifest.symlink_to(original)
        self.v2_signature.write_bytes(b"sig\n")
        self.v2_signature.chmod(0o600)
        with self.assertRaises(extension.SignedDomstatsExtensionError):
            self.verify()


if __name__ == "__main__":
    unittest.main()
