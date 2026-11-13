"""PE-S2.15: host libvirt stats capture/review contracts, synthetic virsh only."""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import os
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s2_15_readonly_host_domstats as telemetry
import pe_arch_vm_s1_63_external_observer as external
from test_pe_arch_vm_s1_73_two_record_review import (
    COMMIT, CHALLENGE, DOMAIN, UUID, first_record, second_record,
)

SESSION = "6" * 64
STATS = ("Domain: '" + DOMAIN + "'\n"
         " state.state=1\n"
         " state.reason=0\n"
         " cpu.time=100000000\n"
         " cpu.user=70000000\n"
         " cpu.system=30000000\n").encode("ascii")


class HostDomstatsContracts(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pe-s2-15-host-")
        self.addCleanup(temporary.cleanup)
        self.owner = Path(temporary.name) / "reviewer-owned"
        self.owner.mkdir(mode=0o700)
        first = first_record()
        self.first_sha = hashlib.sha256(first).hexdigest()
        guest = second_record(self.first_sha)
        self.guest_sha = hashlib.sha256(guest).hexdigest()
        for label, data in (("host_vm_launch", first),
                            ("host_guest_kernel", guest)):
            path = self.owner / external.OBS_FILES[label]
            path.write_bytes(data)
            path.chmod(0o600)
        self.args = dict(
            domain=DOMAIN, expected_domain_uuid=UUID,
            expected_source_commit=COMMIT, reviewer_challenge=CHALLENGE,
            expected_session_id=SESSION,
            expected_host_sha256=self.first_sha,
            expected_guest_sha256=self.guest_sha,
        )

    def fake_capture(self, *, stats=STATS, states=None, query_result=None,
                     changes=None):
        if states is None:
            states = [UUID, "running", "running", UUID]
        result = query_result or SimpleNamespace(
            returncode=0, stdout=stats, stderr=b"")
        with (mock.patch.object(telemetry.shutil, "which",
                                return_value="/usr/bin/virsh") as find,
              mock.patch.object(telemetry.host, "_virsh_read",
                                side_effect=states) as state,
              mock.patch.object(telemetry.bounded, "run_bounded_native",
                                return_value=result) as run):
            report = telemetry.capture_host_domstats(
                self.owner, capture_from_independent_host=True,
                **{**self.args, **(changes or {})})
        find.assert_called_once()
        self.assertEqual(state.call_count, 4)
        self.assertEqual(run.call_count, 1)
        argv = run.call_args.args[0]
        self.assertEqual(argv, [
            "/usr/bin/virsh", "--readonly", "--connect", "qemu:///system",
            "--no-pkttyagent", "domstats", "--raw", "--state",
            "--cpu-total", DOMAIN,
        ])
        return report

    # PE-S2.45 tests inject only upstream return shapes. They do not
    # simulate a real independent hypervisor or guest kernel.
    @staticmethod
    def _s1_73_verdict():
        return {
            "status": telemetry.semantic.STATUS,
            "host_record_sha256_matched": True,
            "guest_record_sha256_matched": True,
            "guest_record_bound_to_host_sha256": True,
            "domain_uuid_correlated": True,
            "source_commit_correlated": True,
            "reviewer_challenge_correlated": True,
            "guest_os_id_self_reported": "arch",
            "guest_kernel_release_self_reported": "6.10.0-arch1-1",
            "semantic_records_checked": 2,
            "other_unverified_records": list(telemetry.semantic.UNVERIFIED),
            "libvirt_queried": False,
            "independent_host_control_verified": False,
            "guest_kernel_independently_verified": False,
            "seccomp_cgroups_independently_verified": False,
            "scope_cleanup_independently_verified": False,
            "independent_vm_attestation": False,
            "release_authorized": False,
            "unknown_windows_pe_execution_authorized": False,
            "apk_or_ota_publication_authorized": False,
        }

    def _s1_73_review(self, result):
        with mock.patch.object(
                telemetry.semantic, "review_two_records",
                return_value=result) as upstream:
            telemetry._offline_pins(
                self.owner, domain=DOMAIN, uuid=UUID, commit=COMMIT,
                challenge=CHALLENGE, host_sha=self.first_sha,
                guest_sha=self.guest_sha)
        upstream.assert_called_once()

    def test_s2_45_s1_73_complete_schema_and_real_fixture_remain_hold(self):
        good = self._s1_73_verdict()
        self.assertEqual(set(good), telemetry.S1_73_VERDICT_FIELDS)
        self._s1_73_review(good)
        # Actual S1.73 offline parser still checks the two synthetic files.
        telemetry._offline_pins(
            self.owner, domain=DOMAIN, uuid=UUID, commit=COMMIT,
            challenge=CHALLENGE, host_sha=self.first_sha,
            guest_sha=self.guest_sha)
        self.assertFalse(good["independent_vm_attestation"])
        self.assertFalse(good["libvirt_queried"])

    def test_s2_45_s1_73_extra_missing_and_false_authority_fail(self):
        good = self._s1_73_verdict()
        bad_reports = (
            dict(good, external_attestation=True),
            dict(good, external_attestation=False),
            {k: v for k, v in good.items()
             if k != "guest_kernel_independently_verified"},
            dict(good, independent_host_control_verified=True),
            dict(good, guest_kernel_independently_verified=True),
            dict(good, seccomp_cgroups_independently_verified=True),
            dict(good, scope_cleanup_independently_verified=True),
            dict(good, independent_vm_attestation=True),
            dict(good, release_authorized=True),
            dict(good, unknown_windows_pe_execution_authorized=True),
            dict(good, apk_or_ota_publication_authorized=True),
            dict(good, libvirt_queried=True),
            dict(good, host_record_sha256_matched=1),
        )
        for bad in bad_reports:
            with self.subTest(report=bad), self.assertRaises(
                    telemetry.HostDomstatsError):
                self._s1_73_review(bad)

    def test_s2_45_s1_73_count_guest_fields_and_pending_list_fail(self):
        good = self._s1_73_verdict()
        bad_reports = (
            dict(good, semantic_records_checked=True),
            dict(good, semantic_records_checked=3),
            dict(good, other_unverified_records=tuple(
                telemetry.semantic.UNVERIFIED)),
            dict(good, other_unverified_records=[]),
            dict(good, other_unverified_records=list(reversed(
                telemetry.semantic.UNVERIFIED))),
            dict(good, guest_os_id_self_reported=""),
            dict(good, guest_os_id_self_reported=42),
            dict(good, guest_kernel_release_self_reported="6.10\nspoof"),
            dict(good, guest_kernel_release_self_reported="A" * 129),
        )
        for bad in bad_reports:
            with self.subTest(report=bad), self.assertRaises(
                    telemetry.HostDomstatsError):
                self._s1_73_review(bad)

    def test_s2_45_wrong_upstream_types_reject_before_virsh(self):
        for bad in (None, [], "", True, 1):
            with self.subTest(result=bad):
                with self.assertRaises(telemetry.HostDomstatsError):
                    self._s1_73_review(bad)
                with (mock.patch.object(
                        telemetry.semantic, "review_two_records",
                        return_value=bad),
                      mock.patch.object(telemetry.shutil, "which") as virsh,
                      self.assertRaises(telemetry.HostDomstatsError)):
                    telemetry.capture_host_domstats(
                        self.owner, capture_from_independent_host=True,
                        **self.args)
                virsh.assert_not_called()
                self.assertFalse((self.owner / telemetry.TARGET).exists())

    def test_default_is_plan_no_host_queries_no_publication(self):
        with (mock.patch.object(telemetry.shutil, "which") as lookup,
              mock.patch.object(telemetry.bounded, "run_bounded_native") as child):
            output = telemetry.capture_host_domstats(self.owner, **self.args)
        self.assertEqual(output["status"], telemetry.PLAN)
        self.assertFalse(output["libvirt_queried"])
        self.assertFalse((self.owner / telemetry.TARGET).exists())
        lookup.assert_not_called()
        child.assert_not_called()

    def test_actual_readonly_virsh_contract_publishes_one_private_sidecar(self):
        output = self.fake_capture()
        target = self.owner / telemetry.TARGET
        self.assertTrue(target.is_file())
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),
                         output["sidecar_sha256"])
        self.assertEqual(output["cpu_time_ns_observed"], 100000000)
        self.assertFalse(output["included_in_s1_63_signed_manifest"])
        self.assertFalse(output["guest_cgroups_seccomp_verified"])
        self.assertFalse(output["release_authorized"])
        self.assertFalse((self.owner / external.MANIFEST_FILE).exists())
        reviewed = telemetry.review_host_domstats(
            self.owner, expected_record_sha256=output["sidecar_sha256"],
            **self.args)
        self.assertEqual(reviewed["status"], telemetry.REVIEWED)
        self.assertFalse(reviewed["actual_hypervisor_independently_authenticated"])
        self.assertFalse(reviewed["independent_vm_attestation"])

    def test_host_counter_record_cannot_be_rewritten(self):
        self.fake_capture()
        with (mock.patch.object(telemetry.shutil, "which") as find,
              self.assertRaises(telemetry.HostDomstatsError)):
            telemetry.capture_host_domstats(
                self.owner, capture_from_independent_host=True, **self.args)
        find.assert_not_called()

    def test_signed_manifest_prevents_late_sidecar(self):
        marker = self.owner / external.MANIFEST_FILE
        marker.write_bytes(b"not a signature\n")
        marker.chmod(0o600)
        with (mock.patch.object(telemetry.shutil, "which") as find,
              self.assertRaises(telemetry.HostDomstatsError)):
            telemetry.capture_host_domstats(
                self.owner, capture_from_independent_host=True, **self.args)
        find.assert_not_called()

    def test_prior_host_guest_pin_refuses_before_running_virsh(self):
        for changed in (
            {"expected_host_sha256": "f" * 64},
            {"expected_guest_sha256": "e" * 64},
            {"expected_session_id": CHALLENGE},
            {"expected_session_id": "0" * 64},
            {"expected_session_id": self.first_sha},
            {"expected_session_id": "F" * 64},
        ):
            with self.subTest(changed=changed):
                with (mock.patch.object(telemetry.shutil, "which") as find,
                      self.assertRaises(telemetry.HostDomstatsError)):
                    telemetry.capture_host_domstats(
                        self.owner, capture_from_independent_host=True,
                        **{**self.args, **changed})
                find.assert_not_called()
                self.assertFalse((self.owner / telemetry.TARGET).exists())

    def test_multi_domain_or_wrong_state_refused_without_file(self):
        bad = [
            STATS.replace(b"Domain: '"+DOMAIN.encode()+b"'",
                          b"Domain: 'other'"),
            STATS + b"Domain: 'other'\n state.state=1\n",
            STATS.replace(b"state.state=1", b"state.state=5"),
            STATS.replace(b"cpu.time=100000000", b"cpu.time=0"),
            STATS.replace(b"cpu.user=70000000", b"cpu.time=1"),
            b"state.state=1\n cpu.time=100\n",
            STATS.replace(b"cpu.user=70000000", b"cpu.user=abc"),
        ]
        for payload in bad:
            with self.subTest(payload=payload[-48:]):
                with (mock.patch.object(telemetry.shutil, "which",
                                        return_value="/usr/bin/virsh"),
                      mock.patch.object(telemetry.host, "_virsh_read",
                                        side_effect=[UUID, "running", "running", UUID]),
                      mock.patch.object(telemetry.bounded, "run_bounded_native",
                                        return_value=SimpleNamespace(
                                            returncode=0, stdout=payload,
                                            stderr=b""))):
                    with self.assertRaises(telemetry.HostDomstatsError):
                        telemetry.capture_host_domstats(
                            self.owner, capture_from_independent_host=True,
                            **self.args)
                self.assertFalse((self.owner / telemetry.TARGET).exists())

    def test_host_domain_changes_after_stats_refused(self):
        with (mock.patch.object(telemetry.shutil, "which",
                                return_value="/usr/bin/virsh"),
              mock.patch.object(telemetry.host, "_virsh_read",
                                side_effect=[UUID, "running", "paused", UUID]),
              mock.patch.object(telemetry.bounded, "run_bounded_native",
                                return_value=SimpleNamespace(
                                    returncode=0, stdout=STATS, stderr=b""))):
            with self.assertRaises(telemetry.HostDomstatsError):
                telemetry.capture_host_domstats(
                    self.owner, capture_from_independent_host=True,
                    **self.args)

    def test_virsh_nonzero_or_stderr_refused(self):
        for child in (SimpleNamespace(returncode=1, stdout=STATS, stderr=b""),
                      SimpleNamespace(returncode=0, stdout=STATS,
                                      stderr=b"warning\n")):
            with self.subTest(child=child):
                with (mock.patch.object(telemetry.shutil, "which",
                                        return_value="/usr/bin/virsh"),
                      mock.patch.object(telemetry.host, "_virsh_read",
                                        side_effect=[UUID, "running", "running", UUID]),
                      mock.patch.object(telemetry.bounded, "run_bounded_native",
                                        return_value=child)):
                    with self.assertRaises(telemetry.HostDomstatsError):
                        telemetry.capture_host_domstats(
                            self.owner, capture_from_independent_host=True,
                            **self.args)
        self.assertFalse((self.owner / telemetry.TARGET).exists())

    def test_tampered_file_or_wrong_external_pin_refuses_offline_review(self):
        proof = self.fake_capture()
        target = self.owner / telemetry.TARGET
        with self.assertRaises(telemetry.HostDomstatsError):
            telemetry.review_host_domstats(
                self.owner, expected_record_sha256="f"*64, **self.args)
        target.write_bytes(target.read_bytes().replace(
            b"release_authorized=false", b"release_authorized=true"))
        with self.assertRaises(telemetry.HostDomstatsError):
            telemetry.review_host_domstats(
                self.owner, expected_record_sha256=proof["sidecar_sha256"],
                **self.args)
        with self.assertRaises(telemetry.HostDomstatsError):
            telemetry.review_host_domstats(
                self.owner, expected_record_sha256=hashlib.sha256(
                    target.read_bytes()).hexdigest(), **self.args)

    def test_symlinked_sidecar_never_reviewed(self):
        destination = self.owner / "untrusted"
        destination.write_bytes(b"FAKE\n")
        (self.owner / telemetry.TARGET).symlink_to(destination)
        with self.assertRaises(telemetry.HostDomstatsError):
            telemetry.review_host_domstats(
                self.owner, expected_record_sha256="f" * 64, **self.args)

    def test_missing_guest_observation_refuses_before_query(self):
        (self.owner / external.OBS_FILES["host_guest_kernel"]).unlink()
        with (mock.patch.object(telemetry.shutil, "which") as find,
              self.assertRaises(telemetry.HostDomstatsError)):
            telemetry.capture_host_domstats(
                self.owner, capture_from_independent_host=True, **self.args)
        find.assert_not_called()

    def test_cli_default_no_capture_and_review_always_hold_exit_two(self):
        args = ["--observer-dir", str(self.owner)]
        for key, value in self.args.items():
            args.extend(["--" + key.replace("_", "-"), value])
        stream = StringIO()
        with redirect_stdout(stream):
            result = telemetry.main(args)
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stream.getvalue())["status"], telemetry.PLAN)
        captured = self.fake_capture()
        output = StringIO()
        with redirect_stdout(output):
            result = telemetry.main(args + [
                "--review-existing", "--expected-record-sha256",
                captured["sidecar_sha256"]])
        self.assertEqual(result, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], telemetry.REVIEWED)


if __name__ == "__main__":
    unittest.main()
