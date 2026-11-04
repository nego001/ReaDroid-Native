"""PE-S1.71: all libvirt/guest-agent responses MOCKED; no VM is contacted."""
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
import pe_arch_vm_s1_71_guestinfo_os_capture as guest
import pe_arch_vm_s1_70_readonly_libvirt_host_capture as host
import pe_arch_vm_s1_63_external_observer as external
import pe_arch_vm_s1_69_bounded_native_child as bounded

COMMIT = "a" * 40
CHALLENGE = "b" * 64
UUID = "12345678-abcd-4ef0-8123-123456789abc"
DOMAIN = "reviewer-native-arch-01"
GUESTINFO = (
    b"os.id          : arch\n"
    b"os.name        : Arch Linux\n"
    b"os.kernel-release : 6.17.5-arch1-1\n"
    b"os.kernel-version : #1 SMP PREEMPT_DYNAMIC\n"
    b"os.machine     : x86_64\n"
)


class GuestKernelCaptureContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pe-s1-71-")
        self.addCleanup(self.temp.cleanup)
        self.owner = Path(self.temp.name) / "observer"
        self.owner.mkdir(mode=0o700)
        self.prior = self.owner / guest.PRIOR
        self.target = self.owner / guest.TARGET
        self.record = (
            "observation_type=libvirt_readonly_domain_snapshot\n"
            "classification=HOST_QUERY_OUTPUT_NOT_VM_ATTESTATION\n"
            "source_commit=" + COMMIT + "\n"
            "reviewer_challenge=" + CHALLENGE + "\n"
            "observed_utc_untrusted=2026-11-03T01:23:45+00:00\n"
            "uri=qemu:///system\n"
            "connection=readonly\n"
            "domain_name=" + DOMAIN + "\n"
            "expected_domain_uuid=" + UUID + "\n"
            "initial_domuuid:\n" + UUID + "\n"
            "initial_domstate:\nrunning\n"
            "dominfo:\n"
            "Id: 5\n"
            "Name: " + DOMAIN + "\n"
            "UUID: " + UUID + "\n"
            "State: running\n"
            "final_domstate:\nrunning\n"
            "final_domuuid:\n" + UUID + "\n"
            "independent_vm_attestation=false\n"
            "release_authorized=false\n"
        ).encode()
        self.prior.write_bytes(self.record)
        self.prior.chmod(0o600)
        self.pin = hashlib.sha256(self.record).hexdigest()
        self.kw = {
            "domain": DOMAIN,
            "expected_domain_uuid": UUID,
            "expected_source_commit": COMMIT,
            "reviewer_challenge": CHALLENGE,
            "expected_prior_host_sha256": self.pin,
        }
        self.calls = []

    def fake(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        verb = argv[-2] if argv[-1] != "--os" else "guestinfo"
        stdout = {
            "domuuid": (UUID + "\n").encode(),
            "domstate": b"running\n",
            "guestinfo": GUESTINFO,
        }[verb]
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr=b"")

    def capture(self, *, fake=None, found="/usr/bin/virsh", **changes):
        with (
            mock.patch.object(guest.shutil, "which", return_value=found),
            mock.patch.object(
                guest.bounded, "run_bounded_native",
                side_effect=self.fake if fake is None else fake) as child,
        ):
            result = guest.capture_guest_kernel_observation(
                self.owner, **{**self.kw,
                               "capture_from_independent_host": True, **changes})
            return result, child

    def test_default_is_no_guest_query_or_publication(self):
        with (
            mock.patch.object(guest.shutil, "which") as which,
            mock.patch.object(guest.bounded, "run_bounded_native") as child,
        ):
            result = guest.capture_guest_kernel_observation(self.owner, **self.kw)
        self.assertEqual(result["status"], guest.PLAN)
        self.assertFalse(result["guestinfo_queried"])
        self.assertFalse(result["kernel_observation_created"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(self.target.exists())
        which.assert_not_called()
        child.assert_not_called()

    def test_five_readonly_queries_publish_only_second_log(self):
        result, child = self.capture()
        self.assertEqual(result["status"], guest.CAPTURED)
        self.assertEqual(child.call_count, 5)
        self.assertEqual([call[0][-2] if call[0][-1] != "--os"
                          else "guestinfo" for call in self.calls],
                         ["domuuid", "domstate", "guestinfo", "domstate", "domuuid"])
        for argv, kw in self.calls:
            self.assertEqual(
                argv[1:5],
                ["--readonly", "--connect", "qemu:///system",
                 "--no-pkttyagent"])
            self.assertEqual(kw["timeout"], 15)
            self.assertLessEqual(kw["max_stdout"], 8192)
            self.assertNotIn("PYTHONPATH", kw["env"])
        self.assertEqual(self.calls[2][0][-3:], ["guestinfo", DOMAIN, "--os"])
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        data = self.target.read_bytes()
        self.assertIn(b"guest_agent_self_report=true", data)
        self.assertIn(b"parsed_guest_kernel_release=6.17.5-arch1-1", data)
        self.assertIn(self.pin.encode(), data)
        self.assertIn(b"independent_vm_attestation=false", data)
        self.assertFalse(result["guest_kernel_independently_verified"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         result["kernel_observation_sha256"])
        self.assertEqual(set(os.listdir(self.owner)),
                         {guest.TARGET, guest.PRIOR})

    def test_second_capture_rejected_before_all_virsh(self):
        self.capture()
        original = self.target.read_bytes()
        self.calls.clear()
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.target.read_bytes(), original)

    def test_wrong_prior_pin_prevents_virsh_query(self):
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture(expected_prior_host_sha256="f" * 64)
        self.assertFalse(self.calls)
        self.assertFalse(self.target.exists())

    def test_missing_prior_host_file_prevents_query(self):
        self.prior.unlink()
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture()
        self.assertFalse(self.calls)

    def test_altered_prior_snapshot_identity_rejected(self):
        self.prior.write_bytes(self.record.replace(
            DOMAIN.encode(), b"other-domain"))
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture(expected_prior_host_sha256=hashlib.sha256(
                self.prior.read_bytes()).hexdigest())
        self.assertFalse(self.calls)

    def test_rehashed_conflicting_dominfo_refused_before_guest_agent(self):
        # S1.84 accepted a pinned host record even if its dominfo UUID,
        # name or State contradicted the separately pinned identity.
        for previous, forged in (
            (b"UUID: " + UUID.encode(),
             b"UUID: 11111111-1111-4111-8111-111111111111"),
            (b"Name: " + DOMAIN.encode(), b"Name: other-domain"),
            (b"State: running", b"State: shut off"),
        ):
            with self.subTest(forged=forged):
                bad = self.record.replace(previous, forged)
                self.prior.write_bytes(bad)
                self.prior.chmod(0o600)
                digest = hashlib.sha256(bad).hexdigest()
                self.calls.clear()
                with self.assertRaises(guest.GuestKernelObservationError):
                    self.capture(expected_prior_host_sha256=digest)
                self.assertEqual(self.calls, [])
                self.assertFalse(self.target.exists())
        self.prior.write_bytes(self.record)

    def test_rehashed_missing_or_reordered_host_sections_rejected(self):
        for bad in (
            self.record.replace(b"dominfo:\n", b"dominfo-missing:\n"),
            self.record.replace(b"uri=qemu:///system\n", b""),
            self.record.replace(b"initial_domuuid:\n", b"initial_domuuid=fake\n"),
            self.record.replace(b"observed_utc_untrusted=2026-11-03T01:23:45+00:00",
                                b"observed_utc_untrusted=not-a-time"),
            self.record.replace(b"release_authorized=false\n",
                                b"release_authorized=false\nUNEXPECTED\n"),
            self.record.replace(b"State: running\n",
                                b"State: running\nrelease_authorized=true\n"),
        ):
            with self.subTest(bad=bad[:60]):
                self.prior.write_bytes(bad)
                self.prior.chmod(0o600)
                self.calls.clear()
                with self.assertRaises(guest.GuestKernelObservationError):
                    self.capture(
                        expected_prior_host_sha256=hashlib.sha256(bad).hexdigest())
                self.assertFalse(self.calls)
                self.assertFalse(self.target.exists())
        self.prior.write_bytes(self.record)

    def test_prior_host_snapshot_symlink_rejected(self):
        other = self.owner / "copy"
        self.prior.rename(other)
        self.prior.symlink_to(other)
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture()
        self.assertFalse(self.calls)

    def test_prior_host_snapshot_hardlink_rejected(self):
        os.link(self.prior, self.owner / "other-hardlink")
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture()
        self.assertFalse(self.calls)

    def test_prior_snapshot_changed_during_query_rejected(self):
        def switched(argv, **kw):
            result = self.fake(argv, **kw)
            if len(self.calls) == 3:
                self.prior.write_bytes(self.record + b"altered\n")
            return result
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture(fake=switched)
        self.assertFalse(self.target.exists())

    def test_non_arch_guest_agent_os_refused(self):
        def other_os(argv, **kw):
            result = self.fake(argv, **kw)
            if argv[-1] == "--os":
                return subprocess.CompletedProcess(
                    argv, 0, GUESTINFO.replace(b"arch\n", b"ubuntu\n"), b"")
            return result
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture(fake=other_os)

    def test_missing_or_invalid_guest_kernel_info_refused(self):
        for bad in (
            GUESTINFO.replace(b"6.17.5-arch1-1", b"unknown"),
            GUESTINFO.replace(b"os.machine", b"not-machine"),
            GUESTINFO.replace(b"x86_64", b"unknown"),
        ):
            self.calls.clear()
            def invalid(argv, **kw):
                result = self.fake(argv, **kw)
                if argv[-1] == "--os":
                    return subprocess.CompletedProcess(argv, 0, bad, b"")
                return result
            with self.subTest(bad=bad), self.assertRaises(
                    guest.GuestKernelObservationError):
                self.capture(fake=invalid)
            self.assertFalse(self.target.exists())

    def test_duplicate_guestinfo_field_rejected(self):
        def duplicated(argv, **kw):
            result = self.fake(argv, **kw)
            if argv[-1] == "--os":
                return subprocess.CompletedProcess(
                    argv, 0, GUESTINFO + b"os.id: ubuntu\n", b"")
            return result
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture(fake=duplicated)

    def test_control_or_binary_guestinfo_refused(self):
        for bad in (b"os.id: arch\x00\n", b"\x1b[31m", b"\xff",
                    b"x" * 8193, b"\n"):
            def invalid(argv, **kw):
                result = self.fake(argv, **kw)
                if argv[-1] == "--os":
                    return subprocess.CompletedProcess(argv, 0, bad, b"")
                return result
            with self.subTest(bad=bad[:10]), self.assertRaises(
                    guest.GuestKernelObservationError):
                self.capture(fake=invalid)
            self.assertFalse(self.target.exists())

    def test_guestinfo_nonzero_or_stderr_rejected(self):
        for status, err in ((1, b""), (0, b"permission denied")):
            def failed(argv, **kw):
                result = self.fake(argv, **kw)
                if argv[-1] == "--os":
                    return subprocess.CompletedProcess(
                        argv, status, GUESTINFO, err)
                return result
            with self.subTest(status=status), self.assertRaises(
                    guest.GuestKernelObservationError):
                self.capture(fake=failed)
            self.assertFalse(self.target.exists())

    def test_guestinfo_timeout_rejected(self):
        def failed(argv, **kw):
            if argv[-1] == "--os":
                raise bounded.BoundedNativeChildError("timed out")
            return self.fake(argv, **kw)
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture(fake=failed)
        self.assertFalse(self.target.exists())

    def test_domain_uuid_changed_after_agent_query_refused(self):
        def switched(argv, **kw):
            result = self.fake(argv, **kw)
            if len(self.calls) == 5:
                return subprocess.CompletedProcess(
                    argv, 0, b"11111111-1111-4111-8111-111111111111\n", b"")
            return result
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture(fake=switched)

    def test_domain_state_changed_after_query_refused(self):
        def switched(argv, **kw):
            result = self.fake(argv, **kw)
            if len(self.calls) == 4:
                return subprocess.CompletedProcess(argv, 0, b"paused\n", b"")
            return result
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture(fake=switched)

    def test_manifest_or_signature_present_blocks_queries(self):
        for name in (external.MANIFEST_FILE, external.SIGNATURE_FILE):
            f = self.owner / name
            f.write_bytes(b"already there")
            with self.subTest(name=name), self.assertRaises(
                    guest.GuestKernelObservationError):
                self.capture()
            self.assertFalse(self.calls)
            f.unlink()

    def test_symlink_target_existing_or_dangling_blocks(self):
        self.target.symlink_to(self.owner / "missing")
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture()
        self.assertFalse(self.calls)

    def test_non_private_owner_and_bad_inputs_block_queries(self):
        self.owner.chmod(0o755)
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture()
        self.owner.chmod(0o700)
        for bad in (
            {"domain": "--evil"},
            {"domain": "../escape"},
            {"reviewer_challenge": "0" * 64},
            {"expected_source_commit": "0" * 40},
            {"expected_prior_host_sha256": "NOT_SHA256"},
            {"capture_from_independent_host": "yes"},
        ):
            with self.subTest(bad=bad), self.assertRaises(
                    guest.GuestKernelObservationError):
                self.capture(**bad)
        self.assertFalse(self.calls)

    def test_missing_virsh_blocks_without_publication(self):
        with self.assertRaises(guest.GuestKernelObservationError):
            self.capture(found=None)
        self.assertFalse(self.target.exists())

    def test_cli_default_and_explicit_query(self):
        args = [
            "--observer-dir", str(self.owner),
            "--domain", DOMAIN,
            "--expected-domain-uuid", UUID,
            "--expected-source-commit", COMMIT,
            "--reviewer-challenge", CHALLENGE,
            "--expected-prior-host-sha256", self.pin,
        ]
        stdout, stderr = StringIO(), StringIO()
        with (redirect_stdout(stdout), redirect_stderr(stderr),
              mock.patch.object(guest.shutil, "which") as which,
              mock.patch.object(guest.bounded, "run_bounded_native") as child):
            code = guest.main(args)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], guest.PLAN)
        which.assert_not_called()
        child.assert_not_called()

        stdout, stderr = StringIO(), StringIO()
        with (redirect_stdout(stdout), redirect_stderr(stderr),
              mock.patch.object(guest.shutil, "which",
                                return_value="/usr/bin/virsh"),
              mock.patch.object(guest.bounded, "run_bounded_native",
                                side_effect=self.fake)):
            code = guest.main(args + ["--capture-from-independent-host"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], guest.CAPTURED)

    def test_cli_rejection_never_claims_vm_proof(self):
        args = [
            "--observer-dir", str(self.owner), "--domain", DOMAIN,
            "--expected-domain-uuid", UUID,
            "--expected-source-commit", COMMIT,
            "--reviewer-challenge", CHALLENGE,
            "--expected-prior-host-sha256", "not-a-hash",
            "--capture-from-independent-host",
        ]
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = guest.main(args)
        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        record = json.loads(stderr.getvalue())
        self.assertEqual(record["status"], guest.REJECTED)
        self.assertFalse(record["independent_vm_attestation"])
        self.assertFalse(record["apk_or_ota_publication_authorized"])


if __name__ == "__main__":
    unittest.main()
