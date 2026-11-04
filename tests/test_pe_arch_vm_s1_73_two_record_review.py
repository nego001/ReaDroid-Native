"""PE-S1.73: synthetic private-log contracts only. Never contacts libvirt."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_73_two_record_review as review
import pe_arch_vm_s1_70_readonly_libvirt_host_capture as host
import pe_arch_vm_s1_71_guestinfo_os_capture as guest

COMMIT = "a" * 40
CHALLENGE = "b" * 64
UUID = "12345678-abcd-4ef0-8123-123456789abc"
DOMAIN = "reviewer-native-arch-01"
CLOCK = "2026-11-02T16:00:00+00:00"
GUEST_OS = (
    "os.id : arch\n"
    "os.name : Arch Linux\n"
    "os.kernel-release : 6.17.5-arch1-1\n"
    "os.machine : x86_64"
)


def first_record():
    return (
        "observation_type=libvirt_readonly_domain_snapshot\n"
        "classification=HOST_QUERY_OUTPUT_NOT_VM_ATTESTATION\n"
        f"source_commit={COMMIT}\n"
        f"reviewer_challenge={CHALLENGE}\n"
        f"observed_utc_untrusted={CLOCK}\n"
        "uri=qemu:///system\nconnection=readonly\n"
        f"domain_name={DOMAIN}\nexpected_domain_uuid={UUID}\n"
        f"initial_domuuid:\n{UUID}\ninitial_domstate:\nrunning\n"
        f"dominfo:\nName: {DOMAIN}\nUUID: {UUID}\nState: running\n"
        f"final_domstate:\nrunning\nfinal_domuuid:\n{UUID}\n"
        "independent_vm_attestation=false\nrelease_authorized=false\n"
    ).encode("utf-8")


def second_record(first_sha):
    return (
        "observation_type=libvirt_readonly_guest_agent_os_kernel\n"
        "classification=GUEST_AGENT_SELF_REPORT_NOT_KERNEL_ATTESTATION\n"
        f"source_commit={COMMIT}\n"
        f"reviewer_challenge={CHALLENGE}\n"
        f"observed_utc_untrusted={CLOCK}\n"
        "uri=qemu:///system\nconnection=readonly\n"
        f"domain_name={DOMAIN}\nexpected_domain_uuid={UUID}\n"
        f"prior_host_record_sha256={first_sha}\n"
        f"initial_domuuid:\n{UUID}\ninitial_domstate:\nrunning\n"
        f"virsh_guestinfo_os_guest_agent_self_report:\n{GUEST_OS}\n"
        "parsed_guest_os_id=arch\n"
        "parsed_guest_kernel_release=6.17.5-arch1-1\n"
        "parsed_guest_machine=x86_64\n"
        f"final_domstate:\nrunning\nfinal_domuuid:\n{UUID}\n"
        "guest_agent_self_report=true\nindependent_vm_attestation=false\n"
        "release_authorized=false\n"
    ).encode("utf-8")


class TwoRecordReviewContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pe-s1-73-review-")
        self.addCleanup(self.tmp.cleanup)
        self.owner = Path(self.tmp.name) / "observer"
        self.owner.mkdir(mode=0o700)
        self.first = self.owner / host.TARGET
        self.second = self.owner / guest.TARGET
        raw1 = first_record()
        raw2 = second_record(hashlib.sha256(raw1).hexdigest())
        self.first.write_bytes(raw1)
        self.second.write_bytes(raw2)
        self.first.chmod(0o600)
        self.second.chmod(0o600)
        self.pins = {
            "domain": DOMAIN,
            "expected_domain_uuid": UUID,
            "expected_source_commit": COMMIT,
            "reviewer_challenge": CHALLENGE,
            "expected_host_sha256": hashlib.sha256(raw1).hexdigest(),
            "expected_guest_sha256": hashlib.sha256(raw2).hexdigest(),
        }

    def verify(self, **changes):
        return review.review_two_records(self.owner, **{**self.pins, **changes})

    def replace(self, path, old, new):
        raw = path.read_bytes()
        assert old in raw
        path.write_bytes(raw.replace(old, new))
        path.chmod(0o600)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_two_matching_records_are_only_hold(self):
        with (mock.patch.object(host.shutil, "which") as which,
              mock.patch.object(host.bounded, "run_bounded_native") as child):
            report = self.verify()
        self.assertEqual(report["status"], review.STATUS)
        self.assertEqual(report["semantic_records_checked"], 2)
        self.assertTrue(report["guest_record_bound_to_host_sha256"])
        self.assertEqual(report["guest_os_id_self_reported"], "arch")
        self.assertEqual(report["guest_kernel_release_self_reported"], "6.17.5-arch1-1")
        self.assertEqual(len(report["other_unverified_records"]), 2)
        for name in ("libvirt_queried", "independent_host_control_verified",
                     "guest_kernel_independently_verified",
                     "seccomp_cgroups_independently_verified",
                     "scope_cleanup_independently_verified",
                     "independent_vm_attestation", "release_authorized",
                     "unknown_windows_pe_execution_authorized",
                     "apk_or_ota_publication_authorized"):
            self.assertIs(report[name], False, name)
        self.assertEqual({p.name for p in self.owner.iterdir()},
                         {host.TARGET, guest.TARGET})
        which.assert_not_called()
        child.assert_not_called()

    def test_wrong_external_sha_rejected(self):
        for changes in (
            {"expected_host_sha256": "f" * 64},
            {"expected_guest_sha256": "f" * 64},
            {"expected_host_sha256": "A" * 64},
            {"expected_guest_sha256": ""},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(review.TwoRecordReviewError):
                    self.verify(**changes)

    def test_prior_host_sha_repin_does_not_bypass_binding(self):
        changed = self.replace(self.second,
                               self.pins["expected_host_sha256"].encode(),
                               b"f" * 64)
        with self.assertRaises(review.TwoRecordReviewError):
            self.verify(expected_guest_sha256=changed)

    def test_forged_independence_claim_rejected_even_if_rehashed(self):
        changed = self.replace(
            self.second, b"independent_vm_attestation=false",
            b"independent_vm_attestation=true")
        with self.assertRaises(review.TwoRecordReviewError):
            self.verify(expected_guest_sha256=changed)

    def test_both_records_must_match_pinned_domain_uuid(self):
        changed = self.replace(
            self.first, UUID.encode(),
            b"11111111-1111-4111-8111-111111111111")
        with self.assertRaises(review.TwoRecordReviewError):
            self.verify(expected_host_sha256=changed)

    def test_guest_parsed_kernel_must_match_raw(self):
        changed = self.replace(
            self.second, b"parsed_guest_kernel_release=6.17.5-arch1-1",
            b"parsed_guest_kernel_release=9.9.9-test")
        with self.assertRaises(review.TwoRecordReviewError):
            self.verify(expected_guest_sha256=changed)

    def test_wrong_guest_os_rejected_even_when_rehashed(self):
        changed = self.replace(
            self.second, b"os.id : arch", b"os.id : ubuntu")
        with self.assertRaises(review.TwoRecordReviewError):
            self.verify(expected_guest_sha256=changed)

    def test_duplicate_guest_key_rejected(self):
        changed = self.replace(
            self.second, b"os.id : arch\n",
            b"os.id : arch\nos.id : arch\n")
        with self.assertRaises(review.TwoRecordReviewError):
            self.verify(expected_guest_sha256=changed)

    def test_untrusted_clock_is_not_a_certificate(self):
        changed = self.replace(
            self.first, CLOCK.encode(), b"2026-11-02T13:00:00-03:00")
        with self.assertRaises(review.TwoRecordReviewError):
            self.verify(expected_host_sha256=changed)

    def test_host_dominfo_reserved_marker_rejected(self):
        changed = self.replace(
            self.first, b"State: running\n",
            b"State: running\nrelease_authorized=true\n")
        with self.assertRaises(review.TwoRecordReviewError):
            self.verify(expected_host_sha256=changed)

    def test_rehashed_both_records_reject_forbidden_host_dominfo_markers(self):
        # In S1.85, the S1.71 capture gate refused these injected claims.
        # S1.73 used to accept them when BOTH records were rehashed and
        # the guest's prior-host hash was adjusted to match the forgery.
        # The offline HOLD report must never claim identity correlation
        # for a snapshot that the earlier gate considers inconsistent.
        original = first_record()
        for forged in (
            b"domain_name=second-domain",
            b"expected_domain_uuid=11111111-1111-4111-8111-111111111111",
            b"uri=qemu:///session",
            b"initial_domstate:\\nshut off",
            b"observation_type=independent_vm_attestation",
        ):
            with self.subTest(forged=forged):
                new_host = original.replace(
                    b"State: running\\n", b"State: running\\n" + forged + b"\\n")
                self.first.write_bytes(new_host)
                host_sha = hashlib.sha256(new_host).hexdigest()
                new_guest = second_record(host_sha)
                self.second.write_bytes(new_guest)
                with self.assertRaisesRegex(
                        review.TwoRecordReviewError,
                        "strict pre-guestinfo policy"):
                    self.verify(
                        expected_host_sha256=host_sha,
                        expected_guest_sha256=hashlib.sha256(
                            new_guest).hexdigest())

    def test_review_uses_shared_s1_71_snapshot_validator(self):
        # Guard against a later drift that silently drops the earlier
        # check while keeping a superficially equivalent local parser.
        with mock.patch.object(
                review.guest, "_check_snapshot",
                side_effect=guest.GuestKernelObservationError(
                    "intentional strict policy failure")) as check:
            with self.assertRaisesRegex(
                    review.TwoRecordReviewError, "strict pre-guestinfo"):
                self.verify()
        check.assert_called_once_with(
            first_record(), commit=COMMIT, challenge=CHALLENGE,
            domain=DOMAIN, uuid=UUID)

    def test_missing_log_refused(self):
        self.second.unlink()
        with self.assertRaises(review.TwoRecordReviewError):
            self.verify()

    def test_symlink_refused(self):
        raw = self.second.read_bytes()
        alt = self.owner / "other"
        alt.write_bytes(raw)
        alt.chmod(0o600)
        self.second.unlink()
        self.second.symlink_to(alt)
        with self.assertRaises(review.TwoRecordReviewError):
            self.verify()

    def test_world_readable_record_refused(self):
        self.first.chmod(0o644)
        with self.assertRaises(review.TwoRecordReviewError):
            self.verify()

    def test_changed_second_read_refused(self):
        first = self.first.read_bytes()
        second = self.second.read_bytes()
        with mock.patch.object(review.prepare, "_read_file",
                               side_effect=[first, second, first + b"tamper\n"]):
            with self.assertRaises(review.TwoRecordReviewError):
                self.verify()

    def test_cli_returns_hold_exit_code_two_with_no_success_claim(self):
        args = [
            "--observer-dir", str(self.owner),
            "--domain", DOMAIN,
            "--expected-domain-uuid", UUID,
            "--expected-source-commit", COMMIT,
            "--reviewer-challenge", CHALLENGE,
            "--expected-host-sha256", self.pins["expected_host_sha256"],
            "--expected-guest-sha256", self.pins["expected_guest_sha256"],
        ]
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = review.main(args)
        self.assertEqual(rc, 2)
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(json.loads(out.getvalue())["status"], review.STATUS)
        self.assertFalse(json.loads(out.getvalue())["release_authorized"])

    def test_cli_rejects_wrong_pin_without_json_success(self):
        args = [
            "--observer-dir", str(self.owner),
            "--domain", DOMAIN,
            "--expected-domain-uuid", UUID,
            "--expected-source-commit", COMMIT,
            "--reviewer-challenge", CHALLENGE,
            "--expected-host-sha256", "f" * 64,
            "--expected-guest-sha256", self.pins["expected_guest_sha256"],
        ]
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = review.main(args)
        self.assertEqual(rc, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(json.loads(err.getvalue())["status"], review.REJECTED)


if __name__ == "__main__":
    unittest.main()
