"""PE-S2.17: two-phase libvirt host text contracts; ZERO actual VM queries."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s2_17_host_two_phase as stage
import pe_arch_vm_s1_63_external_observer as external
from test_pe_arch_vm_s1_73_two_record_review import (
    COMMIT, CHALLENGE, DOMAIN, UUID, first_record, second_record)
from test_pe_arch_vm_s2_15_readonly_host_domstats import STATS

SESSION = "6" * 64
FIRST = STATS.decode("ascii").strip()
SECOND = FIRST.replace("cpu.time=100000000", "cpu.time=150000000")


class TwoPhaseHostCaptureContracts(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pe-s2-17-")
        self.addCleanup(temporary.cleanup)
        self.owner = Path(temporary.name) / "reviewer"
        self.owner.mkdir(mode=0o700)
        # Test-only trust metadata for a synthetic readonly virsh path.
        # Negative S2.60 regressions override this and fail before queries.
        trust = mock.patch.object(
            stage.host, "_trusted_discovered_systemd_binary",
            return_value=True)
        trust.start()
        self.addCleanup(trust.stop)
        host_data = first_record()
        guest_data = second_record(hashlib.sha256(host_data).hexdigest())
        for label, raw in (("host_vm_launch", host_data),
                           ("host_guest_kernel", guest_data)):
            dest = self.owner / external.OBS_FILES[label]
            dest.write_bytes(raw)
            dest.chmod(0o600)
        self.common = dict(
            domain=DOMAIN, expected_domain_uuid=UUID,
            expected_source_commit=COMMIT, reviewer_challenge=CHALLENGE,
            expected_session_id=SESSION,
            expected_host_sha256=hashlib.sha256(host_data).hexdigest(),
            expected_guest_sha256=hashlib.sha256(guest_data).hexdigest(),
        )

    def capture(self, phase, *, text=FIRST, prior=None, read_states=None,
                changed=None):
        with (mock.patch.object(stage.shutil, "which",
                                return_value="/usr/bin/virsh") as which,
              mock.patch.object(stage.host, "_virsh_read",
                                side_effect=read_states or [
                                    UUID, "running", "running", UUID]) as readings,
              mock.patch.object(stage.domstats, "_read_live",
                                return_value=text) as live):
            report = stage.capture_phase(
                self.owner, phase=phase, expected_before_sha256=prior,
                capture_from_independent_host=True,
                **{**self.common, **(changed or {})})
        which.assert_called_once()
        self.assertEqual(readings.call_count, 4)
        live.assert_called_once_with("/usr/bin/virsh", DOMAIN)
        return report

    def pair(self):
        before = self.capture("before")
        after = self.capture("after", text=SECOND, prior=before["sample_sha256"])
        return before, after

    def test_default_does_not_query_libvirt_or_write_evidence(self):
        with (mock.patch.object(stage.shutil, "which") as which,
              mock.patch.object(stage.domstats, "_read_live") as live):
            report = stage.capture_phase(self.owner, phase="before",
                                         **self.common)
        which.assert_not_called()
        live.assert_not_called()
        self.assertEqual(report["status"], stage.STATUS_PLAN)
        self.assertFalse((self.owner / stage.BEFORE).exists())

    def test_s2_60_two_phase_rejects_untrusted_virsh_before_any_query(self):
        for path, trusted in (
                ("/tmp/virsh", True),
                ("/usr/local/bin/virsh", True),
                ("/usr/bin/virsh", False),
                ("/bin/virsh", False),
                (None, False)):
            with self.subTest(path=path, trusted=trusted):
                with (mock.patch.object(stage.shutil, "which",
                                        return_value=path),
                      mock.patch.object(
                          stage.host, "_trusted_discovered_systemd_binary",
                          return_value=trusted) as verifier,
                      mock.patch.object(stage.host, "_virsh_read") as queried,
                      mock.patch.object(stage.domstats, "_read_live") as live,
                      self.assertRaisesRegex(
                          stage.HostTwoPhaseError,
                          "Trusted system virsh required")):
                    stage.capture_phase(
                        self.owner, phase="before",
                        capture_from_independent_host=True, **self.common)
                queried.assert_not_called()
                live.assert_not_called()
                if path in ("/usr/bin/virsh", "/bin/virsh"):
                    verifier.assert_called_once_with(path)
                else:
                    verifier.assert_not_called()
                self.assertFalse((self.owner / stage.BEFORE).exists())

    def test_two_realistic_bounded_samples_and_offline_hold(self):
        before, after = self.pair()
        self.assertEqual(before["phase"], "before")
        self.assertEqual(after["phase"], "after")
        self.assertGreater(
            after["cpu_time_ns_as_reported_by_host"],
            before["cpu_time_ns_as_reported_by_host"])
        for name in (stage.BEFORE, stage.AFTER):
            file = self.owner / name
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        reviewed = stage.review_pair(
            self.owner, expected_before_sha256=before["sample_sha256"],
            expected_after_sha256=after["sample_sha256"], **self.common)
        self.assertEqual(reviewed["status"], stage.STATUS_REVIEWED)
        self.assertTrue(reviewed["host_cpu_time_increased_as_reported_by_libvirt"])
        self.assertFalse(reviewed["samples_signed_in_s1_63_or_s2_16"])
        self.assertFalse(reviewed["independent_vm_attestation"])
        self.assertFalse(reviewed["release_authorized"])

    def test_s2_61_two_phase_rehashed_utc_aliases_rejected(self):
        before = self.capture("before")
        target = self.owner / stage.BEFORE
        record = json.loads(target.read_text("ascii"))
        original = record["host_time_utc_untrusted"]
        for alias in (
                original.replace("T", " ", 1),
                original.replace("+00:00", "Z"),
                "2026-W46-6T01:44:00+00:00",
                "2026-11-14T01:44:00.123+00:00",
                "2026-11-14T01:44:00-03:00",
        ):
            with self.subTest(alias=alias):
                changed = dict(record, host_time_utc_untrusted=alias)
                raw = stage._canonical(changed)
                target.write_bytes(raw)
                with self.assertRaisesRegex(
                        stage.HostTwoPhaseError, "producer-canonical"):
                    stage._decode(
                        raw, phase="before", expected_before_sha256=None,
                        **self.common)
        target.write_bytes(stage._canonical(record))
        self.assertEqual(
            hashlib.sha256(target.read_bytes()).hexdigest(),
            before["sample_sha256"])

    def test_s2_61_two_phase_json_stats_control_separator_rejected(self):
        self.capture("before")
        target = self.owner / stage.BEFORE
        record = json.loads(target.read_text("ascii"))
        for separator in ("\x0b", "\x0c", "\x1c", "\x1d", "\x1e"):
            with self.subTest(separator=hex(ord(separator))):
                forged_stats = record["domstats_raw"].replace(
                    "\n", separator, 1)
                raw = stage._canonical(
                    {**record, "domstats_raw": forged_stats})
                with self.assertRaisesRegex(
                        stage.HostTwoPhaseError,
                        "Host sample raw domstats malformed"):
                    stage._decode(
                        raw, phase="before", expected_before_sha256=None,
                        **self.common)

    def test_s2_62_repinned_json_domstats_padding_refused(self):
        before = self.capture("before")
        target = self.owner / stage.BEFORE
        original = target.read_bytes()
        record = json.loads(original)
        for original_field, padded in (
                (" state.state=1", "  state.state=1"),
                (" cpu.time=100000000", " cpu.time=100000000 "),
                (" state.reason=0", " state.reason=0 "),
        ):
            with self.subTest(padded=padded):
                forged_text = record["domstats_raw"].replace(
                    original_field, padded, 1)
                tampered = stage._canonical(
                    {**record, "domstats_raw": forged_text})
                target.write_bytes(tampered)
                with self.assertRaisesRegex(
                        stage.HostTwoPhaseError,
                        "Host sample raw domstats malformed"):
                    stage._read_private(
                        self.owner, "before",
                        expected_sha256=hashlib.sha256(tampered).hexdigest(),
                        common={**self.common,
                                "expected_before_sha256": None})
        target.write_bytes(original)
        self.assertEqual(hashlib.sha256(original).hexdigest(),
                         before["sample_sha256"])

    def test_s2_62_noncanonical_libvirt_state_fails_before_phase_write(self):
        for state in ("RUNNING", "Running", "running ", "running\n"):
            with self.subTest(state=repr(state)):
                with self.assertRaisesRegex(
                        stage.HostTwoPhaseError,
                        "Domain changed while sampling"):
                    self.capture(
                        "before",
                        read_states=[UUID, state, "running", UUID])
                self.assertFalse((self.owner / stage.BEFORE).exists())
                with self.assertRaisesRegex(
                        stage.HostTwoPhaseError,
                        "Domain changed while sampling"):
                    self.capture(
                        "before",
                        read_states=[UUID, "running", state, UUID])
                self.assertFalse((self.owner / stage.BEFORE).exists())

    def test_s2_63_capture_after_reversed_or_equal_clock_fails_before_write(self):
        first = self.capture("before")
        first_record = json.loads((self.owner / stage.BEFORE).read_bytes())
        stamp = datetime.fromisoformat(
            first_record["host_time_utc_untrusted"])
        for value in (stamp, stamp - timedelta(seconds=1)):
            with self.subTest(utc=value.isoformat()):
                # Only the local *untrusted* clock is simulated here;
                # no libvirt request or guest command is executed.
                class LocalFrozenClock(datetime):
                    @classmethod
                    def now(cls, tz=None):
                        return value

                # Keep the genuine datetime.fromisoformat parser available
                # in the same module while overriding only production now().
                with (mock.patch.object(stage, "datetime", LocalFrozenClock),
                      self.assertRaisesRegex(
                          stage.HostTwoPhaseError,
                          "Nonincreasing untrusted host clock")):
                    self.capture(
                        "after", text=SECOND, prior=first["sample_sha256"])
                self.assertFalse((self.owner / stage.AFTER).exists())

    def test_s2_63_offline_rehashed_after_clock_not_increasing_rejected(self):
        first, second = self.pair()
        path = self.owner / stage.AFTER
        original = path.read_bytes()
        before = json.loads((self.owner / stage.BEFORE).read_bytes())
        after = json.loads(original)
        first_time = datetime.fromisoformat(
            before["host_time_utc_untrusted"])
        for altered in (first_time, first_time - timedelta(seconds=1)):
            with self.subTest(clock=altered.isoformat()):
                forged = stage._canonical({
                    **after,
                    "host_time_utc_untrusted": altered.isoformat()})
                path.write_bytes(forged)
                with self.assertRaisesRegex(
                        stage.HostTwoPhaseError,
                        "Nonincreasing untrusted host clock"):
                    stage.review_pair(
                        self.owner, expected_before_sha256=first["sample_sha256"],
                        expected_after_sha256=hashlib.sha256(forged).hexdigest(),
                        **self.common)
        path.write_bytes(original)
        valid = stage.review_pair(
            self.owner, expected_before_sha256=first["sample_sha256"],
            expected_after_sha256=second["sample_sha256"], **self.common)
        self.assertEqual(valid["status"], stage.STATUS_REVIEWED)
        self.assertFalse(valid["independent_vm_attestation"])

    def test_after_requires_external_before_hash_before_host_query(self):
        with (mock.patch.object(stage.shutil, "which") as which,
              self.assertRaises(stage.HostTwoPhaseError)):
            stage.capture_phase(
                self.owner, phase="after", capture_from_independent_host=True,
                **self.common)
        which.assert_not_called()

    def test_after_wrong_previous_hash_refuses_before_host_query(self):
        self.capture("before")
        with (mock.patch.object(stage.shutil, "which") as which,
              self.assertRaises(stage.HostTwoPhaseError)):
            stage.capture_phase(
                self.owner, phase="after", expected_before_sha256="f"*64,
                capture_from_independent_host=True, **self.common)
        which.assert_not_called()
        self.assertFalse((self.owner / stage.AFTER).exists())

    def test_after_requires_increasing_cpu_counter(self):
        first = self.capture("before")
        with (mock.patch.object(stage.shutil, "which",
                                return_value="/usr/bin/virsh"),
              mock.patch.object(stage.host, "_virsh_read",
                                side_effect=[UUID,"running","running",UUID]),
              mock.patch.object(stage.domstats, "_read_live",
                                return_value=FIRST),
              self.assertRaisesRegex(stage.HostTwoPhaseError, "did not increase")):
            stage.capture_phase(
                self.owner, phase="after",
                expected_before_sha256=first["sample_sha256"],
                capture_from_independent_host=True, **self.common)
        self.assertFalse((self.owner / stage.AFTER).exists())

    def test_domain_swap_or_paused_state_refuses_no_file(self):
        for states in ([UUID, "running", "paused", UUID],
                       [UUID, "running", "running", "bad-uuid"]):
            with self.subTest(states=states), self.assertRaises(
                    stage.HostTwoPhaseError):
                self.capture("before", read_states=states)
            self.assertFalse((self.owner / stage.BEFORE).exists())

    def test_replayed_or_invalid_guest_and_session_pin_refused(self):
        for changed in (
                {"expected_host_sha256": "f"*64},
                {"expected_guest_sha256": "e"*64},
                {"expected_session_id": CHALLENGE},
                {"expected_session_id": "0"*64},
                {"expected_session_id": "F"*64}):
            with self.subTest(changed=changed):
                with (mock.patch.object(stage.shutil,"which") as which,
                      self.assertRaises(stage.HostTwoPhaseError)):
                    stage.capture_phase(self.owner, phase="before",
                        capture_from_independent_host=True,
                        **{**self.common, **changed})
                which.assert_not_called()
                self.assertFalse((self.owner / stage.BEFORE).exists())

    def test_tampered_record_refused_even_with_recomputed_sha(self):
        b, a = self.pair()
        path = self.owner / stage.BEFORE
        raw = path.read_bytes()
        path.write_bytes(raw.replace(
            b'"release_authorized":false', b'"release_authorized":true'))
        with self.assertRaises(stage.HostTwoPhaseError):
            stage.review_pair(
                self.owner,
                expected_before_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                expected_after_sha256=a["sample_sha256"], **self.common)

    def test_after_sample_cannot_be_mixed_with_new_before(self):
        b, a = self.pair()
        before = self.owner / stage.BEFORE
        data=json.loads(before.read_bytes())
        data["cpu_time_ns"]=999999999
        data["domstats_raw"]=data["domstats_raw"].replace(
            "cpu.time=100000000","cpu.time=999999999")
        before.write_bytes(stage._canonical(data))
        with self.assertRaises(stage.HostTwoPhaseError):
            stage.review_pair(self.owner,
                expected_before_sha256=hashlib.sha256(
                    before.read_bytes()).hexdigest(),
                expected_after_sha256=a["sample_sha256"], **self.common)

    def test_bad_raw_stats_no_file(self):
        for text in ("Domain: 'other'\n state.state=1\n cpu.time=10",
                     FIRST.replace("state.state=1", "state.state=5"),
                     FIRST.replace("cpu.time=100000000", "cpu.time=oops")):
            with self.subTest(text=text), self.assertRaises(
                    stage.HostTwoPhaseError):
                self.capture("before", text=text)
            self.assertFalse((self.owner / stage.BEFORE).exists())

    def test_no_overwrite_even_when_new_phase_is_valid(self):
        b = self.capture("before")
        with (mock.patch.object(stage.shutil,"which") as which,
              self.assertRaises(stage.HostTwoPhaseError)):
            stage.capture_phase(self.owner, phase="before",
                capture_from_independent_host=True, **self.common)
        which.assert_not_called()
        self.assertEqual(hashlib.sha256(
            (self.owner/stage.BEFORE).read_bytes()).hexdigest(), b["sample_sha256"])

    def test_signed_legacy_manifest_refuses_new_phase(self):
        legacy = self.owner / external.MANIFEST_FILE
        legacy.write_text("legacy signed\n")
        legacy.chmod(0o600)
        with (mock.patch.object(stage.shutil, "which") as which,
              self.assertRaises(stage.HostTwoPhaseError)):
            stage.capture_phase(self.owner, phase="before",
                                capture_from_independent_host=True,
                                **self.common)
        which.assert_not_called()

    def test_symlinked_prior_sample_never_followed(self):
        other = self.owner / "other.txt"
        other.write_text("{}\n")
        (self.owner / stage.BEFORE).symlink_to(other)
        with (mock.patch.object(stage.shutil, "which") as which,
              self.assertRaises(stage.HostTwoPhaseError)):
            stage.capture_phase(self.owner, phase="after",
                expected_before_sha256=hashlib.sha256(
                    other.read_bytes()).hexdigest(),
                capture_from_independent_host=True, **self.common)
        which.assert_not_called()

    def test_cli_default_and_offline_valid_pair_exit_hold(self):
        args = ["--observer-dir", str(self.owner)]
        for key, val in self.common.items():
            args.extend(["--"+key.replace("_","-"), val])
        stdout=StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(stage.main(args), 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"],
                         stage.STATUS_PLAN)
        before, after = self.pair()
        stdout=StringIO()
        with redirect_stdout(stdout):
            code=stage.main(args + ["--review-existing",
                       "--expected-before-sha256",before["sample_sha256"],
                       "--expected-after-sha256",after["sample_sha256"]])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue())["status"],
                         stage.STATUS_REVIEWED)

    def test_duplicate_json_fields_rejected_even_when_rehashed(self):
        before, after = self.pair()
        path=self.owner / stage.AFTER
        raw=path.read_bytes()
        path.write_bytes(raw.replace(
            b'"schema":', b'"schema":"forged","schema":', 1))
        with self.assertRaises(stage.HostTwoPhaseError):
            stage.review_pair(self.owner,
                expected_before_sha256=before["sample_sha256"],
                expected_after_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                **self.common)


if __name__ == "__main__":
    unittest.main()
