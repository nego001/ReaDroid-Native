"""PE-S1.70 libvirt host observation workflow. All virsh calls mocked.

CI MUST NEVER connect to a real hypervisor, start a VM, ask a guest agent
anything, forge guest kernel/seccomp/scope records or execute Windows PE.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_70_readonly_libvirt_host_capture as capture
import pe_arch_vm_s1_63_external_observer as external
import pe_arch_vm_s1_69_bounded_native_child as bounded

COMMIT = "a" * 40
CHALLENGE = "b" * 64
DOMAIN = "reviewer-native-arch-01"
UUID = "12345678-abcd-4ef0-8123-123456789abc"


class LibvirtHostCaptureContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pe-s1-70-host-")
        self.addCleanup(self.tmp.cleanup)
        self.owner = Path(self.tmp.name) / "owner"
        self.owner.mkdir(mode=0o700)
        self.target = self.owner / external.OBS_FILES["host_vm_launch"]
        self.opts = {
            "domain": DOMAIN,
            "expected_domain_uuid": UUID,
            "expected_source_commit": COMMIT,
            "reviewer_challenge": CHALLENGE,
        }
        self.calls = []

    def fake(self, argv, **kw):
        self.calls.append((argv, kw))
        command = argv[-2]
        data = {
            "domuuid": (UUID + "\n").encode(),
            "domstate": b"running\n",
            "dominfo": (
                b"Id: 5\nName: reviewer-native-arch-01\n"
                b"State: running\nUUID: 12345678-abcd-4ef0-8123-123456789abc\n"),
        }[command]
        return subprocess.CompletedProcess(argv, 0, stdout=data, stderr=b"")

    def capture(self, *, fake=None, found="/usr/bin/virsh", **changes):
        with (
            mock.patch.object(
                capture.shutil, "which", return_value=found) as which,
            mock.patch.object(
                capture.bounded, "run_bounded_native",
                side_effect=self.fake if fake is None else fake) as child,
        ):
            result = capture.capture_host_domain(
                self.owner, **{**self.opts,
                               "capture_from_independent_host": True,
                               **changes})
            return result, which, child

    def test_dry_run_never_executes_virsh_or_writes_log(self):
        with (
            mock.patch.object(capture.shutil, "which") as which,
            mock.patch.object(capture.bounded, "run_bounded_native") as child,
        ):
            result = capture.capture_host_domain(self.owner, **self.opts)
        self.assertEqual(result["status"], capture.PLAN)
        self.assertFalse(result["host_queries_executed"])
        self.assertFalse(result["host_log_created"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(self.target.exists())
        which.assert_not_called()
        child.assert_not_called()

    def test_real_bounded_virsh_readonly_five_calls_publish_one_log(self):
        result, which, child = self.capture()
        self.assertEqual(result["status"], capture.CAPTURED)
        self.assertEqual(child.call_count, 5)
        self.assertEqual(len(self.calls), 5)
        self.assertEqual(
            [a[-2] for a, _ in self.calls],
            ["domuuid", "domstate", "dominfo", "domstate", "domuuid"])
        for argv, kw in self.calls:
            self.assertEqual(
                argv[1:5],
                ["--readonly", "--connect", "qemu:///system", "--no-pkttyagent"])
            self.assertEqual(argv[-1], DOMAIN)
            self.assertEqual(kw["timeout"], 15)
            self.assertLessEqual(kw["max_stdout"], 8192)
            self.assertNotIn("PYTHONPATH", kw["env"])
        data = self.target.read_bytes()
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        self.assertIn(b"source_commit=" + COMMIT.encode(), data)
        self.assertIn(b"reviewer_challenge=" + CHALLENGE.encode(), data)
        self.assertIn(b"connection=readonly", data)
        self.assertIn(b"independent_vm_attestation=false", data)
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         result["host_log_sha256"])
        self.assertFalse(result["independent_host_control_verified"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])
        self.assertEqual(len(result["required_other_host_records_not_created"]), 3)
        self.assertEqual(set(os.listdir(self.owner)), {self.target.name})

    # PE-S2.46: a captured host log must already be acceptable to the
    # subsequent S1.71 parser; hashing unsafe data is not enough.
    def test_s2_46_capture_matches_downstream_host_snapshot_policy(self):
        import pe_arch_vm_s1_71_guestinfo_os_capture as guest
        report, _, _ = self.capture()
        guest._check_snapshot(
            self.target.read_bytes(), commit=COMMIT,
            challenge=CHALLENGE, domain=DOMAIN, uuid=UUID)
        self.assertEqual(report["status"], capture.CAPTURED)
        self.assertIs(guest.host.DOMINFO_RESERVED_PREFIXES,
                      capture.DOMINFO_RESERVED_PREFIXES)

    def test_s2_46_reserved_host_envelope_markers_block_publication(self):
        for injected in (
            b"release_authorized=true",
            b"independent_vm_attestation=true",
            b"source_commit=" + b"f" * 40,
            b"domain_name=other-vm",
            b"initial_domstate:",
            b"uri=qemu:///session",
        ):
            with self.subTest(injected=injected):
                def forged(argv, **kw):
                    original = self.fake(argv, **kw)
                    if argv[-2] != "dominfo":
                        return original
                    raw = original.stdout + injected + b"\n"
                    return subprocess.CompletedProcess(argv, 0, raw, b"")
                with self.assertRaises(capture.HostCaptureError):
                    self.capture(fake=forged)
                self.assertFalse(self.target.exists())

    def test_s2_46_empty_dominfo_line_is_never_published(self):
        def extra_blank(argv, **kw):
            original = self.fake(argv, **kw)
            if argv[-2] != "dominfo":
                return original
            raw = original.stdout.replace(b"State: running\n",
                                          b"State: running\n\n")
            return subprocess.CompletedProcess(argv, 0, raw, b"")
        with self.assertRaises(capture.HostCaptureError):
            self.capture(fake=extra_blank)
        self.assertFalse(self.target.exists())

    def test_s2_46_noncanonical_cr_tab_del_control_bytes_rejected(self):
        for control in (b"\r", b"\t", b"\x7f"):
            with self.subTest(control=control):
                def malformed(argv, **kw):
                    original = self.fake(argv, **kw)
                    if argv[-2] != "dominfo":
                        return original
                    raw = original.stdout.replace(b"Id: 5", b"Id: 5"+control)
                    return subprocess.CompletedProcess(argv, 0, raw, b"")
                with self.assertRaises(capture.HostCaptureError):
                    self.capture(fake=malformed)
                self.assertFalse(self.target.exists())

    # PE-S2.47: reject misleading variations that the earlier exact
    # startswith() policy did not see, before issuing a publication.
    def test_s2_47_disguised_authority_and_duplicate_dominfo_fields_refused(self):
        bad_lines = (
            b" release_authorized=true",
            b"ReLeAsE_AuThOrIzEd=true",
            b"release_authorized = true",
            b"Name : alternative",
            b"name: alternative",
            b"NAME: alternative",
            b"Id: 99",
            b"State: running=verified",
            b"unlabelled text",
        )
        for extra in bad_lines:
            with self.subTest(extra=extra):
                def forged(argv, **kw):
                    original = self.fake(argv, **kw)
                    if argv[-2] != "dominfo":
                        return original
                    return subprocess.CompletedProcess(
                        argv, 0, original.stdout + extra + b"\n", b"")
                with self.assertRaises(capture.HostCaptureError):
                    self.capture(fake=forged)
                self.assertFalse(self.target.exists())

    def test_s2_47_valid_standard_extended_dominfo_still_accepted(self):
        def extended(argv, **kw):
            original = self.fake(argv, **kw)
            if argv[-2] != "dominfo":
                return original
            lines = (b"CPU(s): 2\nCPU time: 3.2s\n"
                     b"Max memory: 2097152 KiB\n"
                     b"Persistent: yes\nAutostart: disable\n"
                     b"Security model: none\n")
            return subprocess.CompletedProcess(
                argv, 0, original.stdout + lines, b"")
        result, _, _ = self.capture(fake=extended)
        self.assertEqual(result["status"], capture.CAPTURED)
        import pe_arch_vm_s1_71_guestinfo_os_capture as guest
        guest._check_snapshot(self.target.read_bytes(), commit=COMMIT,
                              challenge=CHALLENGE, domain=DOMAIN, uuid=UUID)

    def test_s2_47_shared_dominfo_parser_rejects_non_string_input(self):
        for value in (None, [], True, b"Name: fake", ""):
            with self.subTest(value=value):
                with self.assertRaises(capture.HostCaptureError):
                    capture._validate_dominfo_shape(value)

    # PE-S2.48: S1.71/S1.73 require exact lowercase running in
    # initial/final domstate and in the embedded dominfo field.
    def test_s2_48_host_mixed_case_domstate_refused_before_publication(self):
        for ordinal in (1, 2):
            for spelling in (b"RUNNING\n", b"Running\n"):
                with self.subTest(ordinal=ordinal, spelling=spelling):
                    state_index = [0]
                    def changed(argv, **kw):
                        original = self.fake(argv, **kw)
                        if argv[-2] == "domstate":
                            state_index[0] += 1
                            if state_index[0] == ordinal:
                                return subprocess.CompletedProcess(
                                    argv, 0, spelling, b"")
                        return original
                    with self.assertRaises(capture.HostCaptureError):
                        self.capture(fake=changed)
                    self.assertEqual(state_index[0], 2)
                    self.assertFalse(self.target.exists())

    def test_s2_48_host_mixed_case_dominfo_refused_before_publication(self):
        for spelling in (b"RUNNING", b"Running"):
            with self.subTest(spelling=spelling):
                def changed(argv, **kw):
                    original = self.fake(argv, **kw)
                    if argv[-2] != "dominfo":
                        return original
                    raw = original.stdout.replace(
                        b"State: running", b"State: " + spelling)
                    return subprocess.CompletedProcess(argv, 0, raw, b"")
                with self.assertRaises(capture.HostCaptureError):
                    self.capture(fake=changed)
                self.assertFalse(self.target.exists())

    def test_second_capture_refuses_no_overwrite_and_no_new_commands(self):
        self.capture()
        first = self.target.read_bytes()
        self.calls.clear()
        with self.assertRaises(capture.HostCaptureError):
            self.capture()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.target.read_bytes(), first)

    def test_wrong_guest_uuid_rejected_without_publication(self):
        def counterfeit(argv, **kw):
            result = self.fake(argv, **kw)
            if argv[-2] == "domuuid":
                return subprocess.CompletedProcess(
                    argv, 0,
                    stdout=b"11111111-1111-4111-8111-111111111111\n",
                    stderr=b"")
            return result
        with self.assertRaises(capture.HostCaptureError):
            self.capture(fake=counterfeit)
        self.assertFalse(self.target.exists())

    def test_guest_uuid_changes_after_commands_rejected(self):
        seen = 0
        def switch(argv, **kw):
            nonlocal seen
            seen += 1
            if seen == 5:
                return subprocess.CompletedProcess(
                    argv, 0,
                    stdout=b"11111111-1111-4111-8111-111111111111\n",
                    stderr=b"")
            return self.fake(argv, **kw)
        with self.assertRaises(capture.HostCaptureError):
            self.capture(fake=switch)
        self.assertFalse(self.target.exists())

    def test_nonrunning_domain_rejected(self):
        def paused(argv, **kw):
            result = self.fake(argv, **kw)
            if argv[-2] == "domstate":
                return subprocess.CompletedProcess(argv, 0, b"paused\n", b"")
            return result
        with self.assertRaises(capture.HostCaptureError):
            self.capture(fake=paused)
        self.assertFalse(self.target.exists())

    def test_domain_stops_after_initial_query_rejected(self):
        n = 0
        def stop(argv, **kw):
            nonlocal n
            n += 1
            if n == 4:
                return subprocess.CompletedProcess(argv, 0, b"shut off\n", b"")
            return self.fake(argv, **kw)
        with self.assertRaises(capture.HostCaptureError):
            self.capture(fake=stop)

    def test_virsh_missing_fails_without_files(self):
        with self.assertRaises(capture.HostCaptureError):
            self.capture(found=None)
        self.assertFalse(self.target.exists())

    def test_virsh_nonzero_or_stderr_fails_closed(self):
        for code, stderr in ((1,b""),(0,b"permission denied")):
            with self.subTest(code=code, stderr=stderr):
                def fail(argv, **kw):
                    return subprocess.CompletedProcess(
                        argv, code, b"running\n", stderr)
                with self.assertRaises(capture.HostCaptureError):
                    self.capture(fake=fail)
                self.assertFalse(self.target.exists())

    def test_virsh_timeout_or_output_limit_refuses(self):
        with self.assertRaises(capture.HostCaptureError):
            self.capture(fake=mock.Mock(
                side_effect=bounded.BoundedNativeChildError("timeout")))
        self.assertFalse(self.target.exists())

    def test_virsh_binary_or_control_output_refuses(self):
        for raw in (b"RUNNING\0\n", b"\x1b[0m", b"x" * 8193, b"\xff"):
            with self.subTest(raw=raw[:10]):
                def malformed(argv, **kw):
                    return subprocess.CompletedProcess(argv, 0, raw, b"")
                with self.assertRaises(capture.HostCaptureError):
                    self.capture(fake=malformed)
                self.assertFalse(self.target.exists())

    def test_domain_argument_injection_refused_before_host_query(self):
        for name in ("--help", "x;rm -rf /", "x y", "", "../bad", "x\nfoo", "a" * 90):
            with self.subTest(name=name):
                with self.assertRaises(capture.HostCaptureError):
                    self.capture(domain=name)
                self.assertFalse(self.target.exists())

    def test_invalid_pins_refused_before_host_query(self):
        for opts in (
            {"expected_domain_uuid": "0" * 36},
            {"expected_domain_uuid": "00000000-0000-0000-0000-000000000000"},
            {"expected_source_commit": "0" * 40},
            {"expected_source_commit": "A" * 40},
            {"reviewer_challenge": "0" * 64},
            {"reviewer_challenge": "Z" * 64},
            {"capture_from_independent_host": "yes"},
        ):
            with self.subTest(opts=opts):
                with self.assertRaises(capture.HostCaptureError):
                    self.capture(**opts)
                self.assertFalse(self.target.exists())

    def test_folder_not_private_refuses_before_virsh(self):
        self.owner.chmod(0o755)
        with self.assertRaises(capture.HostCaptureError):
            self.capture()
        self.assertFalse(self.target.exists())

    def test_existing_manifest_prevents_new_host_log(self):
        (self.owner / external.MANIFEST_FILE).write_text("existing",encoding="ascii")
        with self.assertRaises(capture.HostCaptureError):
            self.capture()
        self.assertFalse(self.target.exists())

    def test_existing_signature_prevents_new_host_log(self):
        (self.owner / external.SIGNATURE_FILE).write_text("existing",encoding="ascii")
        with self.assertRaises(capture.HostCaptureError):
            self.capture()
        self.assertFalse(self.target.exists())

    def test_existing_dangling_symlink_log_refused(self):
        self.target.symlink_to(self.owner / "missing")
        with self.assertRaises(capture.HostCaptureError):
            self.capture()
        self.assertTrue(self.target.is_symlink())

    def test_dominfo_inconsistent_identity_rejected(self):
        for field, before, after in (
            ("uuid", b"UUID: 12345678-abcd-4ef0-8123-123456789abc",
             b"UUID: 11111111-1111-4111-8111-111111111111"),
            ("name", b"Name: reviewer-native-arch-01", b"Name: other"),
            ("state", b"State: running", b"State: paused"),
        ):
            with self.subTest(field=field):
                def inconsistent(argv, **kw):
                    res = self.fake(argv, **kw)
                    if argv[-2] == "dominfo":
                        return subprocess.CompletedProcess(
                            argv, 0, res.stdout.replace(before, after), b"")
                    return res
                with self.assertRaises(capture.HostCaptureError):
                    self.capture(fake=inconsistent)
                self.assertFalse(self.target.exists())

    def test_empty_but_nonzero_length_virsh_output_rejected(self):
        def empty(argv, **kw):
            return subprocess.CompletedProcess(argv, 0, b"\n  \r", b"")
        with self.assertRaises(capture.HostCaptureError):
            self.capture(fake=empty)
        self.assertFalse(self.target.exists())

    def test_cli_no_capture_default_and_explicit_flag(self):
        args = [
            "--observer-dir", str(self.owner),
            "--domain", DOMAIN, "--expected-domain-uuid", UUID,
            "--expected-source-commit", COMMIT,
            "--reviewer-challenge", CHALLENGE,
        ]
        stdout, stderr = StringIO(), StringIO()
        with (redirect_stdout(stdout),redirect_stderr(stderr),
              mock.patch.object(capture.shutil,"which") as which):
            result = capture.main(args)
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], capture.PLAN)
        which.assert_not_called()
        stdout, stderr = StringIO(), StringIO()
        with (redirect_stdout(stdout), redirect_stderr(stderr),
              mock.patch.object(capture.shutil, "which",return_value="/usr/bin/virsh"),
              mock.patch.object(capture.bounded,"run_bounded_native",
                                side_effect=self.fake)):
            result = capture.main(args+["--capture-from-independent-host"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], capture.CAPTURED)

    def test_cli_capture_rejected_and_no_release(self):
        args = [
            "--observer-dir", str(self.owner),
            "--domain", "--help", "--expected-domain-uuid", UUID,
            "--expected-source-commit", COMMIT,
            "--reviewer-challenge", CHALLENGE,
            "--capture-from-independent-host",
        ]
        # A domain beginning with an option is rejected at argparse.
        args[3] = "bad;command"
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = capture.main(args)
        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue(), "")
        result = json.loads(stderr.getvalue())
        self.assertEqual(result["status"], capture.REJECTED)
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["apk_or_ota_publication_authorized"])


if __name__ == "__main__":
    unittest.main()
