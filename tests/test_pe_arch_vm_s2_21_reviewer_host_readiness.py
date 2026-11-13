"""PE-S2.21 reviewer host negative gate: all hypervisor queries MOCKED.

No CI tests an independently controlled host. Only readonly probe argv and
explicit HOLD/negative logic are tested.
"""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s2_21_reviewer_host_readiness as readiness


COMMIT = "abcdef0123456789" * 2 + "deadbeef"
CHALLENGE = "0123456789abcdef" * 4
SESSION = "fedcba9876543210" * 4
UUID = "12345678-abcd-4ef0-8123-123456789abc"
DOMAIN = "reviewer-native-arch-01"
# Simulate S1.70's _virsh_read() result, which strips terminal LF.
INFO = (f"Id: 7\nName: {DOMAIN}\nUUID: {UUID}\n"
        "OS Type: hvm\nState: running")


class ReviewerHostReadinessContracts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="pe-s2-21-host-")
        self.addCleanup(temp.cleanup)
        self.owner = Path(temp.name) / "observer"
        self.owner.mkdir(mode=0o700)
        self.opts = dict(
            domain=DOMAIN, expected_domain_uuid=UUID,
            expected_source_commit=COMMIT, reviewer_challenge=CHALLENGE,
            reviewer_session_id=SESSION)

    def evaluate(self, **updates):
        return readiness.reviewer_host_readiness(
            self.owner, **{**self.opts, **updates})

    def probe(self, answers=None, *, virsh="/usr/bin/virsh"):
        values = (answers if answers is not None else
                  [UUID, "running", INFO, "running", UUID])
        with (mock.patch.object(readiness, "_host_prerequisites",
                                return_value=virsh) as pre,
              mock.patch.object(readiness.host, "_virsh_read",
                                side_effect=values) as query):
            output = self.evaluate(probe_reviewer_host=True)
        return output, pre, query

    def test_default_is_no_executable_no_libvirt_and_no_record(self):
        with (mock.patch.object(readiness, "_host_prerequisites") as pre,
              mock.patch.object(readiness.host, "_virsh_read") as query):
            response = self.evaluate()
        self.assertEqual(response["status"], readiness.PLAN)
        self.assertFalse(response["libvirt_queried"])
        self.assertFalse(response["independent_vm_attestation"])
        pre.assert_not_called()
        query.assert_not_called()
        self.assertEqual(list(self.owner.iterdir()), [])

    def test_synthetic_readonly_domain_candidate_never_attests_vm(self):
        result, pre, query = self.probe()
        self.assertEqual(result["status"], readiness.CANDIDATE)
        self.assertFalse(result["independent_host_control_attested"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["independent_vm_attestation"])
        self.assertTrue(result["libvirt_queried"])
        pre.assert_called_once_with(self.owner)
        self.assertEqual(query.call_args_list, [
            mock.call("/usr/bin/virsh", "domuuid", DOMAIN),
            mock.call("/usr/bin/virsh", "domstate", DOMAIN),
            mock.call("/usr/bin/virsh", "dominfo", DOMAIN),
            mock.call("/usr/bin/virsh", "domstate", DOMAIN),
            mock.call("/usr/bin/virsh", "domuuid", DOMAIN),
        ])
        self.assertEqual(list(self.owner.iterdir()), [])

    def test_changed_domain_uuid_and_state_are_rejected(self):
        for replies in (
                ["ffffffff-ffff-4fff-8fff-ffffffffffff", "running",
                 INFO, "running", UUID],
                [UUID, "running", INFO, "paused", UUID],
                [UUID, "running", INFO, "running",
                 "ffffffff-ffff-4fff-8fff-ffffffffffff"],
                [UUID, "shut off", INFO, "running", UUID]):
            with self.subTest(replies=replies):
                with self.assertRaises(readiness.ReviewerHostReadinessError):
                    self.probe(replies)

    def test_duplicate_or_mismatched_dominfo_rejected(self):
        for info in (
                INFO.replace(f"Name: {DOMAIN}", "Name: another"),
                INFO + f"\nUUID: {UUID}",
                INFO.replace("State: running", "State: paused"),
                "Domain guest is running but no complete fields"):
            with self.subTest(info=info):
                with self.assertRaises(readiness.ReviewerHostReadinessError):
                    self.probe([UUID, "running", info, "running", UUID])

    # PE-S2.50: preflight must not return CANDIDATE for text the
    # subsequent S1.70 producer rejects before recording evidence.
    def test_s2_50_disguised_or_duplicate_dominfo_rejected_as_candidate(self):
        forged = (
            INFO + "\nrelease_authorized=true",
            INFO + "\n release_authorized=true",
            INFO + "\nname: other-host",
            INFO + "\nId: 8",
            INFO + "\nName : other-host",
            INFO + "\nUnlabelled report",
            INFO.replace("State: running", "State: RUNNING"),
            INFO.replace("OS Type: hvm", "OS Type: hvm\n\n"),
        )
        for info in forged:
            with self.subTest(info=info):
                with self.assertRaises(readiness.ReviewerHostReadinessError):
                    self.probe([UUID, "running", info, "running", UUID])
                self.assertEqual(list(self.owner.iterdir()), [])

    def test_s2_50_initial_or_final_mixed_case_state_blocks_candidate(self):
        for index in (1, 3):
            for spelling in ("RUNNING", "Running"):
                with self.subTest(index=index, spelling=spelling):
                    answers = [UUID, "running", INFO, "running", UUID]
                    answers[index] = spelling
                    with self.assertRaises(readiness.ReviewerHostReadinessError):
                        self.probe(answers)
                    self.assertEqual(list(self.owner.iterdir()), [])

    def test_s2_50_extended_canonical_dominfo_remains_candidate_hold(self):
        info = INFO + ("\nCPU(s): 2\nCPU time: 3.2s"
                       "\nMax memory: 2097152 KiB\nPersistent: yes")
        result, _, _ = self.probe([UUID, "running", info, "running", UUID])
        self.assertEqual(result["status"], readiness.CANDIDATE)
        self.assertFalse(result["independent_vm_attestation"])
        self.assertFalse(result["release_authorized"])
        self.assertEqual(list(self.owner.iterdir()), [])

    def test_s2_50_preflight_reuses_s1_70_validator(self):
        with mock.patch.object(
                readiness.host, "_validate_dominfo_shape",
                side_effect=readiness.host.HostCaptureError(
                    "synthetic strict policy refusal")) as validator:
            with self.assertRaises(readiness.ReviewerHostReadinessError):
                self.probe()
        validator.assert_called_once_with(INFO)
        self.assertEqual(list(self.owner.iterdir()), [])

    def test_s2_50_nonstring_dominfo_never_claims_candidate(self):
        for value in (None, True, [], b"Name: host", ""):
            with self.subTest(value=value):
                with self.assertRaises(readiness.ReviewerHostReadinessError):
                    self.probe([UUID, "running", value, "running", UUID])

    def test_weak_replayed_or_invalid_reviewer_session_is_blocked(self):
        for values in (
            {"reviewer_challenge": "b" * 64},
            {"reviewer_session_id": "6" * 64},
            {"reviewer_session_id": CHALLENGE},
            {"reviewer_session_id": "f" * 63},
            {"reviewer_session_id": "F" * 64},
            {"reviewer_challenge": "0" * 64},
            {"reviewer_session_id": None},
        ):
            with self.subTest(values=values):
                with (mock.patch.object(readiness, "_host_prerequisites") as pre,
                      self.assertRaises(readiness.ReviewerHostReadinessError)):
                    self.evaluate(**values)
                pre.assert_not_called()

    def test_bad_uuid_or_commit_refused_pre_probe(self):
        for update in ({"expected_domain_uuid":"f"*36},
                       {"expected_source_commit":"a"*39},
                       {"domain":"--inject"}):
            with self.subTest(update=update):
                with (mock.patch.object(readiness, "_host_prerequisites") as pre,
                      self.assertRaises(readiness.ReviewerHostReadinessError)):
                    self.evaluate(probe_reviewer_host=True, **update)
                pre.assert_not_called()

    def test_runner_marker_blocks_before_kvm_or_libvirt(self):
        with (mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True),
              mock.patch.object(readiness, "_require_kvm_device") as kvm,
              mock.patch.object(readiness.gate, "_trusted_vm_tool") as syscmd,
              self.assertRaisesRegex(
                  readiness.ReviewerHostReadinessError, "CI runner")):
            self.evaluate(probe_reviewer_host=True)
        kvm.assert_not_called()
        syscmd.assert_not_called()

    def test_container_marker_blocks_before_kvm(self):
        with (mock.patch.dict(os.environ, {}, clear=True),
              mock.patch.object(readiness, "_has_known_container_marker",
                                return_value=True),
              mock.patch.object(readiness, "_require_kvm_device") as kvm,
              self.assertRaisesRegex(
                  readiness.ReviewerHostReadinessError, "container marker")):
            self.evaluate(probe_reviewer_host=True)
        kvm.assert_not_called()

    def test_true_kvm_major_minor_candidate_only(self):
        device = mock.Mock(st_mode=stat.S_IFCHR | 0o660,
                           st_rdev=os.makedev(10, 232),
                           st_dev=8, st_ino=1234)
        with (mock.patch.object(readiness.os, "lstat",
                                return_value=device) as looked,
              mock.patch.object(readiness.os, "open",
                                return_value=87) as opened,
              mock.patch.object(readiness.os, "fstat",
                                return_value=device) as inspected,
              mock.patch.object(readiness.fcntl, "ioctl",
                                return_value=12) as query,
              mock.patch.object(readiness.os, "close") as closed):
            self.assertIsNone(readiness._require_kvm_device())
        looked.assert_called_once_with("/dev/kvm")
        opened.assert_called_once()
        self.assertEqual(opened.call_args.args[0], "/dev/kvm")
        flags = opened.call_args.args[1]
        for required in (os.O_RDONLY, os.O_CLOEXEC, os.O_NOFOLLOW, os.O_NONBLOCK):
            self.assertEqual(flags & required, required)
        self.assertFalse(flags & os.O_RDWR)
        self.assertFalse(flags & os.O_CREAT)
        inspected.assert_called_once_with(87)
        query.assert_called_once_with(87, readiness.KVM_GET_API_VERSION)
        closed.assert_called_once_with(87)

    def test_symlink_and_other_character_devices_are_not_kvm(self):
        examples = (
            ("symlink_to_char", stat.S_IFLNK, os.makedev(10, 232)),
            ("null_char", stat.S_IFCHR, os.makedev(1, 3)),
            ("wrong_kvm_minor", stat.S_IFCHR, os.makedev(10, 231)),
            ("wrong_major", stat.S_IFCHR, os.makedev(12, 232)),
            ("ordinary_file", stat.S_IFREG, os.makedev(10, 232)),
            ("directory", stat.S_IFDIR, os.makedev(10, 232)),
        )
        for label, mode, dev in examples:
            with self.subTest(label=label):
                result = mock.Mock(st_mode=mode | 0o600, st_rdev=dev)
                with (mock.patch.object(readiness.os, "lstat",
                                        return_value=result),
                      self.assertRaisesRegex(
                          readiness.ReviewerHostReadinessError,
                          "10:232")):
                    readiness._require_kvm_device()

    def test_unreadable_or_missing_kvm_device_fails_closed(self):
        for exc in (FileNotFoundError("missing"), PermissionError("denied")):
            with self.subTest(error=type(exc).__name__):
                with (mock.patch.object(readiness.os, "lstat",
                                        side_effect=exc),
                      self.assertRaisesRegex(
                          readiness.ReviewerHostReadinessError,
                          "unavailable")):
                    readiness._require_kvm_device()

    def test_swapped_opened_inode_rejected_before_ioctl(self):
        before = mock.Mock(st_mode=stat.S_IFCHR | 0o660,
                           st_rdev=os.makedev(10, 232),
                           st_dev=8, st_ino=1234)
        variants = (
            mock.Mock(st_mode=stat.S_IFCHR | 0o660,
                      st_rdev=os.makedev(10, 232),
                      st_dev=8, st_ino=9999),
            mock.Mock(st_mode=stat.S_IFCHR | 0o660,
                      st_rdev=os.makedev(10, 232),
                      st_dev=9, st_ino=1234),
            mock.Mock(st_mode=stat.S_IFCHR | 0o660,
                      st_rdev=os.makedev(1, 3),
                      st_dev=8, st_ino=1234),
            mock.Mock(st_mode=stat.S_IFREG | 0o600,
                      st_rdev=os.makedev(10, 232),
                      st_dev=8, st_ino=1234),
        )
        for changed in variants:
            with self.subTest(changed=changed):
                with (mock.patch.object(readiness.os, "lstat",
                                        return_value=before),
                      mock.patch.object(readiness.os, "open",
                                        return_value=87),
                      mock.patch.object(readiness.os, "fstat",
                                        return_value=changed),
                      mock.patch.object(readiness.fcntl, "ioctl") as query,
                      mock.patch.object(readiness.os, "close") as closed,
                      self.assertRaisesRegex(
                          readiness.ReviewerHostReadinessError, "replaced")):
                    readiness._require_kvm_device()
                query.assert_not_called()
                closed.assert_called_once_with(87)

    def test_unknown_or_malformed_kvm_api_version_rejected(self):
        node = mock.Mock(st_mode=stat.S_IFCHR | 0o660,
                         st_rdev=os.makedev(10, 232),
                         st_dev=8, st_ino=1234)
        for answer in (0, 11, 13, True, 12.0, None):
            with self.subTest(answer=answer):
                with (mock.patch.object(readiness.os, "lstat",
                                        return_value=node),
                      mock.patch.object(readiness.os, "open",
                                        return_value=87),
                      mock.patch.object(readiness.os, "fstat",
                                        return_value=node),
                      mock.patch.object(readiness.fcntl, "ioctl",
                                        return_value=answer) as query,
                      mock.patch.object(readiness.os, "close") as closed,
                      self.assertRaisesRegex(
                          readiness.ReviewerHostReadinessError, "not 12")):
                    readiness._require_kvm_device()
                query.assert_called_once_with(87, readiness.KVM_GET_API_VERSION)
                closed.assert_called_once_with(87)

    def test_kvm_open_fstat_and_ioctl_failures_close_when_open(self):
        node = mock.Mock(st_mode=stat.S_IFCHR | 0o660,
                         st_rdev=os.makedev(10, 232),
                         st_dev=8, st_ino=1234)
        failures = ("open", "fstat", "ioctl")
        for failed in failures:
            with self.subTest(failed=failed):
                opener = dict(side_effect=PermissionError("denied")) if failed == "open" else dict(return_value=87)
                metadata = dict(side_effect=OSError("bad fstat")) if failed == "fstat" else dict(return_value=node)
                ioctl = dict(side_effect=OSError("not a KVM API")) if failed == "ioctl" else dict(return_value=12)
                with (mock.patch.object(readiness.os, "lstat",
                                        return_value=node),
                      mock.patch.object(readiness.os, "open", **opener),
                      mock.patch.object(readiness.os, "fstat", **metadata),
                      mock.patch.object(readiness.fcntl, "ioctl", **ioctl),
                      mock.patch.object(readiness.os, "close") as closed,
                      self.assertRaisesRegex(
                          readiness.ReviewerHostReadinessError,
                          "Cannot query read-only KVM")):
                    readiness._require_kvm_device()
                if failed == "open":
                    closed.assert_not_called()
                else:
                    closed.assert_called_once_with(87)

    def test_bad_kvm_api_cannot_reach_virsh(self):
        node = mock.Mock(st_mode=stat.S_IFCHR | 0o660,
                         st_rdev=os.makedev(10, 232),
                         st_dev=8, st_ino=1234)
        with (mock.patch.object(readiness.os, "geteuid", return_value=1000),
              mock.patch.dict(os.environ, {}, clear=True),
              mock.patch.object(readiness, "_has_known_container_marker",
                                return_value=False),
              mock.patch.object(readiness.os, "lstat",
                                return_value=node),
              mock.patch.object(readiness.os, "open",
                                return_value=87),
              mock.patch.object(readiness.os, "fstat",
                                return_value=node),
              mock.patch.object(readiness.fcntl, "ioctl",
                                return_value=11),
              mock.patch.object(readiness.os, "close") as closed,
              mock.patch.object(readiness.gate, "_trusted_vm_tool") as virsh,
              self.assertRaisesRegex(
                  readiness.ReviewerHostReadinessError, "not 12")):
            readiness._host_prerequisites(self.owner)
        virsh.assert_not_called()
        closed.assert_called_once_with(87)

    def test_missing_kvm_is_hard_rejection(self):
        with (mock.patch.dict(os.environ, {}, clear=True),
              mock.patch.object(readiness, "_has_known_container_marker",
                                return_value=False),
              mock.patch.object(readiness, "_require_kvm_device",
                                side_effect=readiness.ReviewerHostReadinessError(
                                    "Real KVM character device unavailable")),
              mock.patch.object(readiness.gate, "_trusted_vm_tool") as syscmd,
              self.assertRaisesRegex(
                  readiness.ReviewerHostReadinessError, "KVM")):
            self.evaluate(probe_reviewer_host=True)
        syscmd.assert_not_called()

    def test_preexisting_evidence_blocks_before_any_command(self):
        (self.owner / "old-evidence.txt").write_text("fake\n")
        with (mock.patch.dict(os.environ, {}, clear=True),
              mock.patch.object(readiness, "_has_known_container_marker",
                                return_value=False),
              mock.patch.object(readiness, "_require_kvm_device"),
              mock.patch.object(readiness.gate, "_trusted_vm_tool") as trusted,
              self.assertRaisesRegex(
                  readiness.ReviewerHostReadinessError, "empty")):
            self.evaluate(probe_reviewer_host=True)
        trusted.assert_not_called()

    def test_real_check_command_rc0_container_is_hard_rejection(self):
        with (mock.patch.dict(os.environ, {}, clear=True),
              mock.patch.object(readiness, "_has_known_container_marker",
                                return_value=False),
              mock.patch.object(readiness, "_require_kvm_device"),
              mock.patch.object(readiness.gate, "_trusted_vm_tool",
                                return_value="/usr/bin/systemd-detect-virt"),
              mock.patch.object(readiness.subprocess, "run",
                                return_value=subprocess.CompletedProcess([], 0))
              as child,
              self.assertRaisesRegex(
                  readiness.ReviewerHostReadinessError, "Container detected")):
            self.evaluate(probe_reviewer_host=True)
        self.assertEqual(child.call_args.args[0], [
            "/usr/bin/systemd-detect-virt", "--container", "--quiet"])
        self.assertEqual(child.call_args.kwargs["timeout"], 8)
        self.assertIs(child.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_inconclusive_container_exit_code_also_rejects(self):
        with (mock.patch.dict(os.environ, {}, clear=True),
              mock.patch.object(readiness, "_has_known_container_marker",
                                return_value=False),
              mock.patch.object(readiness, "_require_kvm_device"),
              mock.patch.object(readiness.gate, "_trusted_vm_tool",
                                return_value="/usr/bin/systemd-detect-virt"),
              mock.patch.object(readiness.subprocess, "run",
                                return_value=subprocess.CompletedProcess([], 2)),
              self.assertRaises(readiness.ReviewerHostReadinessError)):
            self.evaluate(probe_reviewer_host=True)

    def test_bounded_host_checks_success_without_libvirt_execution(self):
        with (mock.patch.dict(os.environ, {}, clear=True),
              mock.patch.object(readiness, "_has_known_container_marker",
                                return_value=False),
              mock.patch.object(readiness, "_require_kvm_device"),
              mock.patch.object(
                  readiness.gate, "_trusted_vm_tool",
                  side_effect=lambda name: "/usr/bin/" + name) as trusted,
              mock.patch.object(readiness.subprocess, "run",
                                return_value=subprocess.CompletedProcess([], 1))
              as detect):
            tool = readiness._host_prerequisites(self.owner)
        self.assertEqual(tool, "/usr/bin/virsh")
        self.assertEqual(trusted.call_count, 2)
        detect.assert_called_once()
        self.assertEqual(list(self.owner.iterdir()), [])

    def test_run_as_root_never_queries(self):
        with (mock.patch.object(readiness.os, "geteuid", return_value=0),
              mock.patch.object(readiness.gate, "_trusted_vm_tool") as syscmd,
              self.assertRaises(readiness.ReviewerHostReadinessError)):
            self.evaluate(probe_reviewer_host=True)
        syscmd.assert_not_called()

    def test_cli_plan_exit_zero_and_probe_hold_exit_two(self):
        opts=["--observer-dir", str(self.owner)]
        for key, value in self.opts.items():
            opts.extend(["--"+key.replace("_","-"),value])
        output = StringIO()
        with (redirect_stdout(output),
              mock.patch.object(readiness, "_host_prerequisites") as pre):
            self.assertEqual(readiness.main(opts), 0)
        pre.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"], readiness.PLAN)
        output = StringIO()
        with (redirect_stdout(output),
              mock.patch.object(readiness, "_host_prerequisites",
                                return_value="/usr/bin/virsh"),
              mock.patch.object(readiness.host, "_virsh_read",
                                side_effect=[UUID, "running", INFO, "running", UUID])):
            self.assertEqual(readiness.main(opts+["--probe-reviewer-host"]), 2)
        self.assertEqual(json.loads(output.getvalue())["status"],
                         readiness.CANDIDATE)

    def test_cli_failed_probe_exit_two_with_no_stdout(self):
        args=["--observer-dir",str(self.owner)]
        for key,value in self.opts.items():
            args += ["--"+key.replace("_","-"),value]
        stdout, stderr = StringIO(), StringIO()
        with (mock.patch.dict(os.environ, {"GITHUB_ACTIONS":"true"}, clear=True),
              redirect_stdout(stdout), redirect_stderr(stderr)):
            self.assertEqual(readiness.main(args+["--probe-reviewer-host"]),2)
        self.assertFalse(stdout.getvalue())
        self.assertEqual(json.loads(stderr.getvalue())["status"],
                         readiness.REJECTED)


if __name__ == "__main__":
    unittest.main()
