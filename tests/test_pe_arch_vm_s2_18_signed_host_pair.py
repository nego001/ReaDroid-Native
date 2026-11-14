"""PE-S2.18: V3 separately signed host pair, synthetic virsh and real SSH keys.

All cryptographic signatures use fresh disposable Ed25519 test keys. There is
no externally managed QEMU/libvirt host or real independent Arch VM.
"""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_63_external_observer as v1
import pe_arch_vm_s2_16_signed_domstats_extension as v2
import pe_arch_vm_s2_17_host_two_phase as pair
import pe_arch_vm_s2_18_signed_host_pair as v3
from test_pe_arch_vm_s2_16_signed_domstats_extension import (
    SignedSidecarV2Contracts)
from test_pe_arch_vm_s2_17_host_two_phase import FIRST, SECOND

@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH required")
class SignedHostPairV3Contracts(unittest.TestCase):
    def setUp(self):
        older = SignedSidecarV2Contracts(
            "test_two_real_valid_signatures_and_hold_without_release")
        older.setUp()
        self.addCleanup(older.doCleanups)
        self.old = older
        self.owner, self.custody = older.owner, older.operator

        # To emulate real chronology, host readings happen BEFORE the
        # old signed manifest is sealed. This never touches real libvirt.
        older.f.manifest_path.unlink()
        older.f.signature_path.unlink()
        args = {
            "domain": older.pins["expected_domain"],
            "expected_domain_uuid": older.pins["expected_domain_uuid"],
            "expected_source_commit": older.pins["expected_source_commit"],
            "reviewer_challenge": older.pins["expected_challenge"],
            "expected_session_id": older.pins["expected_session_id"],
            "expected_host_sha256": older.pins["expected_host_sha256"],
            "expected_guest_sha256": older.pins["expected_guest_sha256"],
        }
        with mock.patch.object(
                pair, "_live_sample",
                side_effect=[(FIRST, 100000000), (SECOND, 150000000)]):
            before = pair.capture_phase(
                self.owner, phase="before",
                capture_from_independent_host=True, **args)
            after = pair.capture_phase(
                self.owner, phase="after",
                expected_before_sha256=before["sample_sha256"],
                capture_from_independent_host=True, **args)

        # Sign V1, then V2, then prepare V3. V1/V2 bytes are preserved.
        older.f.sign()
        p = older.f.options()
        older.pins["expected_v1_manifest_sha256"] = p[
            "expected_manifest_sha256"]
        older.pins["expected_v1_signature_sha256"] = p[
            "expected_signature_sha256"]
        older.prepare()
        older.sign()
        self.pins = {
            **older.pins,
            "expected_before_sha256": before["sample_sha256"],
            "expected_after_sha256": after["sample_sha256"],
            "expected_v2_manifest_sha256": hashlib.sha256(
                older.v2_manifest.read_bytes()).hexdigest(),
            "expected_v2_signature_sha256": hashlib.sha256(
                older.v2_signature.read_bytes()).hexdigest(),
        }
        self.file = self.owner / v3.MANIFEST
        self.sig = self.owner / v3.SIGNATURE

    def prepare(self, **changed):
        return v3.prepare_signed_domstats_extension(
            self.owner, self.custody, **{**self.pins, **changed})

    def sign(self, *, namespace=None):
        subprocess.run([
            "ssh-keygen", "-Y", "sign",
            "-f", str(self.old.f.private_keys["observer"]),
            "-n", namespace or v3.NAMESPACE, str(self.file)
        ], check=True, timeout=15, capture_output=True)
        self.file.with_suffix(".json.sig").replace(self.sig)
        self.sig.chmod(0o600)

    def verify(self, **changed):
        opts = {
            **self.pins,
            "expected_extension_manifest_sha256": hashlib.sha256(
                self.file.read_bytes()).hexdigest(),
            "expected_extension_signature_sha256": hashlib.sha256(
                self.sig.read_bytes()).hexdigest(),
            **changed,
        }
        return v3.verify_signed_domstats_extension(
            self.owner, self.custody, **opts)

    @staticmethod
    def _v2_result():
        # Simulated *return value* of verified V2, not real host evidence.
        return {
            "status": v2.VERIFIED,
            "v2_detached_ed25519_signature_verified": True,
            "v2_namespace_distinct_from_v1": True,
            "v1_detached_signature_rechecked": True,
            "sidecar_sha256_bound_to_signed_v2_only": True,
            "v1_four_observation_manifest_unchanged": True,
            "host_hypervisor_independently_attested": False,
            "guest_cgroups_seccomp_verified": False,
            "independent_vm_attestation": False,
            "release_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }

    @staticmethod
    def _pair_result():
        return {
            "status": pair.STATUS_REVIEWED,
            "before_after_sha256_pins_matched": True,
            "external_session_and_domain_correlated": True,
            "host_cpu_time_increased_as_reported_by_libvirt": True,
            "host_provenance_independently_attested": False,
            "guest_process_or_seccomp_cgroup_verified": False,
            "samples_signed_in_s1_63_or_s2_16": False,
            "independent_vm_attestation": False,
            "release_authorized": False,
        }

    def _upstream(self, signed=None, samples=None):
        if signed is None:
            signed = self._v2_result()
        if samples is None:
            samples = self._pair_result()
        with (mock.patch.object(v3.v2, "verify_signed_domstats_extension",
                                return_value=signed) as check_v2,
              mock.patch.object(v3.pair, "review_pair",
                                return_value=samples) as check_pair):
            v3._verified_upstream(self.owner, self.custody, self.pins)
        check_v2.assert_called_once()
        check_pair.assert_called_once()

    def test_upstream_v2_and_pair_exact_shapes_preserve_hold(self):
        self.assertEqual(set(self._v2_result()), v3.V2_VERDICT_FIELDS)
        self.assertEqual(set(self._pair_result()), v3.PAIR_VERDICT_FIELDS)
        self._upstream()
        self.assertFalse(self._v2_result()["independent_vm_attestation"])
        self.assertFalse(self._pair_result()["release_authorized"])

    def test_v2_extra_missing_and_changed_claims_fail_closed(self):
        good = self._v2_result()
        negative = (
            dict(good, independent_reviewer_approved=True),
            dict(good, independent_reviewer_approved=False),
            {key: val for key, val in good.items()
             if key != "v2_namespace_distinct_from_v1"},
            dict(good, host_hypervisor_independently_attested=True),
            dict(good, guest_cgroups_seccomp_verified=True),
            dict(good, apk_or_ota_publication_authorized=True),
            dict(good, sidecar_sha256_bound_to_signed_v2_only=1),
        )
        for bad in negative:
            with self.subTest(changed=bad):
                with self.assertRaises(v3.SignedDomstatsExtensionError):
                    self._upstream(signed=bad)

    def test_pair_extra_missing_and_false_provenance_claims_rejected(self):
        good = self._pair_result()
        negative = (
            dict(good, guest_execution_verified=True),
            dict(good, guest_execution_verified=False),
            {key: val for key, val in good.items()
             if key != "external_session_and_domain_correlated"},
            dict(good, host_provenance_independently_attested=True),
            dict(good, guest_process_or_seccomp_cgroup_verified=True),
            dict(good, samples_signed_in_s1_63_or_s2_16=True),
            dict(good, before_after_sha256_pins_matched=1),
        )
        for bad in negative:
            with self.subTest(changed=bad):
                with self.assertRaises(v3.SignedDomstatsExtensionError):
                    self._upstream(samples=bad)

    def test_non_dict_upstream_verdicts_cannot_pass(self):
        for bad in (None, [], "", True, 1):
            with self.subTest(value=bad):
                with (mock.patch.object(v3.v2, "verify_signed_domstats_extension",
                                        return_value=bad),
                      mock.patch.object(v3.pair, "review_pair",
                                        return_value=self._pair_result()),
                      self.assertRaises(v3.SignedDomstatsExtensionError)):
                    v3._verified_upstream(self.owner, self.custody, self.pins)
                with (mock.patch.object(v3.v2, "verify_signed_domstats_extension",
                                        return_value=self._v2_result()),
                      mock.patch.object(v3.pair, "review_pair",
                                        return_value=bad),
                      self.assertRaises(v3.SignedDomstatsExtensionError)):
                    v3._verified_upstream(self.owner, self.custody, self.pins)

    def test_three_valid_signatures_and_pair_still_hold(self):
        old_m = self.old.f.manifest_path.read_bytes()
        old_v2 = self.old.v2_manifest.read_bytes()
        prepared = self.prepare()
        self.assertFalse(prepared["detached_signature_created"])
        self.assertFalse(prepared["observer_private_key_accessed"])
        self.assertFalse(self.sig.exists())
        data = json.loads(self.file.read_bytes())
        self.assertEqual(data["schema"], v3.SCHEMA)
        self.assertEqual(data["before_sha256"], self.pins["expected_before_sha256"])
        self.assertEqual(data["after_sha256"], self.pins["expected_after_sha256"])
        self.assertTrue(data["pair_is_not_in_v1_or_v2_signed_manifest"])
        self.sign()
        approved = self.verify()
        self.assertEqual(approved["status"], v3.VERIFIED)
        self.assertTrue(approved["v3_detached_ed25519_signature_verified"])
        self.assertTrue(approved["v2_detached_signature_rechecked"])
        self.assertTrue(approved["v1_detached_signature_rechecked"])
        self.assertTrue(approved["two_phase_hashes_bound_to_signed_v3_only"])
        self.assertFalse(approved["independent_vm_attestation"])
        self.assertFalse(approved["release_authorized"])
        self.assertEqual(self.old.f.manifest_path.read_bytes(), old_m)
        self.assertEqual(self.old.v2_manifest.read_bytes(), old_v2)

    def test_v1_or_v2_signature_replay_rejected(self):
        self.prepare()
        for old_signature in (
                self.old.f.signature_path.read_bytes(),
                self.old.v2_signature.read_bytes()):
            with self.subTest(signature=old_signature[:40]):
                self.sig.write_bytes(old_signature)
                self.sig.chmod(0o600)
                with self.assertRaises(v3.SignedDomstatsExtensionError):
                    self.verify()

    def test_v2_namespace_reuse_refused_even_if_validly_signed(self):
        self.prepare()
        self.sign(namespace=v2.NAMESPACE)
        with self.assertRaises(v3.SignedDomstatsExtensionError):
            self.verify()

    def test_rehashed_before_capture_refused_without_new_session(self):
        self.prepare()
        self.sign()
        file = self.owner / pair.BEFORE
        data = json.loads(file.read_bytes())
        data["cpu_time_ns"] = data["cpu_time_ns"] + 1
        data["domstats_raw"] = data["domstats_raw"].replace(
            "cpu.time=100000000", "cpu.time=100000001")
        file.write_bytes(pair._canonical(data))
        with self.assertRaises(v3.SignedDomstatsExtensionError):
            self.verify(expected_before_sha256=hashlib.sha256(
                file.read_bytes()).hexdigest())

    def test_rehashed_after_capture_refused(self):
        self.prepare()
        self.sign()
        path = self.owner / pair.AFTER
        raw = path.read_bytes().replace(
            b'"release_authorized":false', b'"release_authorized":true')
        path.write_bytes(raw)
        with self.assertRaises(v3.SignedDomstatsExtensionError):
            self.verify(expected_after_sha256=hashlib.sha256(raw).hexdigest())

    def test_s2_63_v3_cannot_package_rehashed_backward_clock(self):
        before = json.loads((self.owner / pair.BEFORE).read_bytes())
        after_path = self.owner / pair.AFTER
        after = json.loads(after_path.read_bytes())
        forged = pair._canonical({
            **after,
            "host_time_utc_untrusted": before["host_time_utc_untrusted"]})
        after_path.write_bytes(forged)
        changed_pin = hashlib.sha256(forged).hexdigest()
        self.assertNotEqual(
            changed_pin, self.pins["expected_after_sha256"])
        with self.assertRaisesRegex(
                v3.SignedDomstatsExtensionError,
                "V1/V2 signatures or both host session measurements"):
            self.prepare(expected_after_sha256=changed_pin)
        self.assertFalse(self.file.exists())
        self.assertFalse(self.sig.exists())

    def test_v2_manifest_tamper_refused_and_v3_cannot_repin(self):
        self.prepare()
        self.sign()
        file = self.old.v2_manifest
        raw = file.read_bytes().replace(
            b'"release_authorized":false', b'"release_authorized":true')
        file.write_bytes(raw)
        with self.assertRaises(v3.SignedDomstatsExtensionError):
            self.verify(expected_v2_manifest_sha256=hashlib.sha256(raw).hexdigest())

    def test_wrong_external_before_or_after_digest_blocks_preparation(self):
        for changed in (
                {"expected_before_sha256":"f"*64},
                {"expected_after_sha256":"e"*64},
                {"expected_session_id":"9"*64},
                {"expected_v2_signature_sha256":"d"*64},
                {"expected_after_sha256":self.pins["expected_before_sha256"]},
                {"expected_before_sha256":"F"*64}):
            with self.subTest(changed=changed):
                with self.assertRaises(v3.SignedDomstatsExtensionError):
                    self.prepare(**changed)
                self.assertFalse(self.file.exists())

    def test_second_preparation_cannot_overwrite_manifest(self):
        self.prepare()
        old = self.file.read_bytes()
        with self.assertRaises(v3.SignedDomstatsExtensionError):
            self.prepare()
        self.assertEqual(self.file.read_bytes(), old)

    def test_old_or_preexisting_v3_signature_blocks_publication(self):
        self.sig.write_bytes(b"untrusted old signature\n")
        self.sig.chmod(0o600)
        with self.assertRaises(v3.SignedDomstatsExtensionError):
            self.prepare()
        self.assertFalse(self.file.exists())

    def test_resigned_extra_field_cannot_change_canonical_manifest(self):
        self.prepare()
        data=json.loads(self.file.read_bytes())
        data["release_granted"]="true"
        self.file.write_bytes(v3._canonical(data))
        self.sign()
        with self.assertRaises(v3.SignedDomstatsExtensionError):
            self.verify()

    def test_missing_v3_signature_refused(self):
        self.prepare()
        with self.assertRaises(v3.SignedDomstatsExtensionError):
            v3.verify_signed_domstats_extension(
                self.owner, self.custody,
                expected_extension_manifest_sha256=hashlib.sha256(
                    self.file.read_bytes()).hexdigest(),
                expected_extension_signature_sha256="f"*64,
                **self.pins)

    def test_symlinked_v3_manifest_never_followed(self):
        self.prepare()
        other=self.owner/"saved-v3"
        self.file.replace(other)
        self.file.symlink_to(other)
        self.sig.write_bytes(b"not a signature\n")
        self.sig.chmod(0o600)
        with self.assertRaises(v3.SignedDomstatsExtensionError):
            self.verify()

    def test_cli_prepare_then_valid_review_still_exit_two(self):
        args=["--observer-dir",str(self.owner),
              "--custody-dir",str(self.custody)]
        for key in v3.PINS:
            args.extend(["--"+key.replace("_","-"),self.pins[key]])
        output=StringIO()
        with redirect_stdout(output):
            self.assertEqual(v3.main(args),0)
        self.assertEqual(json.loads(output.getvalue())["status"],v3.PREPARED)
        self.sign()
        output=StringIO()
        with redirect_stdout(output):
            code=v3.main(args+[
                "--verify-existing",
                "--expected-extension-manifest-sha256",
                hashlib.sha256(self.file.read_bytes()).hexdigest(),
                "--expected-extension-signature-sha256",
                hashlib.sha256(self.sig.read_bytes()).hexdigest()])
        self.assertEqual(code,2)
        self.assertEqual(json.loads(output.getvalue())["status"],v3.VERIFIED)


if __name__ == "__main__":
    unittest.main()
