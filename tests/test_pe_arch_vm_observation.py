"""PE-S1.52: native Arch metadata self-report, never a VM attestation.

Ubuntu/Arch-userspace CI stubs the native preflight only in unit tests.
The explicit Ubuntu CLI smoke must still reject a real non-native runner.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_observation as observer
from pe_arch_vm_checkout_pin import CheckoutPinError
from pe_arch_vm_gate import ArchVmUnavailable

COMMIT = "aa11bb22" * 5
CHALLENGE = "0123abcd" * 8
PIN = {
    "status": "LOCAL_GIT_CHECKOUT_PIN_MATCHED",
    "expected_commit": COMMIT,
    "worktree_status_clean": True,
}
GATE = {
    "status": "ARCH_VM_PREFLIGHT_PASSED",
    "vm_confirmed": True,
    "container": False,
    "root": False,
}


class OperatorObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)

    def synthetic_collect(self, *, git_responses=None, gate_result=None):
        def command(name, *argv):
            if name == "systemd-detect-virt":
                return "kvm"
            if name == "systemd":
                return "systemd 258"
            if name == "systemctl":
                return "/user.slice/user-1000.slice/user@1000.service"
            raise AssertionError((name, argv))
        def metadata(path, *, limit):
            lookup = {
                "/proc/1/comm": "systemd",
                "/sys/fs/cgroup/cgroup.controllers": "cpu memory pids io",
                "/sys/fs/cgroup/cgroup.subtree_control": "cpu memory pids",
            }
            return lookup[str(path)]
        with (mock.patch.object(observer, "verify_source_checkout_pin",
                                side_effect=git_responses or [PIN, PIN]) as git,
              mock.patch.object(observer, "verify_arch_vm",
                                return_value=gate_result or GATE) as gate,
              mock.patch.object(observer, "_command", side_effect=command) as cmd,
              mock.patch.object(observer, "_read_bounded",
                                side_effect=metadata) as paths):
            output = observer.collect_observations(
                source_commit=COMMIT, reviewer_challenge=CHALLENGE,
                source_root=self.root)
        return output, (git.call_count, gate.call_count,
                        cmd.call_count, paths.call_count)

    def test_s1_52_collects_exactly_bounded_sanitized_self_reports(self):
        (kernel, cgroup), counts = self.synthetic_collect()
        self.assertEqual(counts, (2, 1, 3, 3))
        k, c = json.loads(kernel), json.loads(cgroup)
        self.assertEqual(k["artifact"], "guest_kernel_observation")
        self.assertEqual(c["artifact"], "guest_cgroup_observation")
        self.assertEqual(k["pid1_comm"], "systemd")
        self.assertEqual(k["virtualization_reported_by_local_systemd"], "kvm")
        self.assertEqual(c["cgroup_v2_controllers_available"],
                         ["cpu", "io", "memory", "pids"])
        for data in (k, c):
            self.assertEqual(data["classification"], observer.STATUS)
            self.assertEqual(data["source_commit"], COMMIT)
            self.assertEqual(data["reviewer_challenge"], CHALLENGE)
            self.assertFalse(data["independent_vm_attestation"])
            self.assertFalse(data["native_kernel_execution_independently_verified"])
            self.assertFalse(data["windows_binary_executed"])
            self.assertFalse(
                data["real_cgroup_limits_or_cleanup_tested_by_this_command"])
            self.assertNotIn("hostname", data)
            self.assertNotIn("environment", data)
        self.assertLess(len(kernel), observer.MAX_FILE_BYTES)
        self.assertLess(len(cgroup), observer.MAX_FILE_BYTES)

    def test_s1_52_publishes_two_owner_only_files_with_sha256(self):
        kernel, cgroup = self.synthetic_collect()[0]
        receipt = observer.publish_no_overwrite(self.private, kernel, cgroup)
        self.assertEqual(receipt["status"],
                         "LOCAL_PRIVATE_OBSERVATIONS_PUBLISHED_NOT_ATTESTED")
        self.assertEqual(
            receipt["guest_kernel_observation_sha256"],
            hashlib.sha256(kernel).hexdigest())
        self.assertEqual(
            receipt["guest_cgroup_observation_sha256"],
            hashlib.sha256(cgroup).hexdigest())
        for name, raw in zip(observer.FILENAMES.values(), (kernel, cgroup)):
            p = self.private / name
            self.assertEqual(p.read_bytes(), raw)
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
        self.assertFalse(receipt["independent_vm_attestation"])

    def test_s1_52_no_overwrite_of_prior_evidence_rolls_back_new_file(self):
        old_file = self.private / "guest-cgroup-observation.txt"
        old_file.write_bytes(b"immutable-previous-cgroup-evidence")
        old_file.chmod(0o600)
        with self.assertRaises(observer.ObservationError):
            observer.publish_no_overwrite(self.private, b"new kernel", b"new cgroup")
        self.assertFalse((self.private / "guest-kernel-observation.txt").exists())
        self.assertEqual(old_file.read_bytes(), b"immutable-previous-cgroup-evidence")

    def test_s1_52_refuses_symlinked_ancestor_without_writing(self):
        real = self.root / "real"
        real.mkdir(mode=0o700)
        (self.root / "link").symlink_to(real, target_is_directory=True)
        with self.assertRaises(observer.ObservationError):
            observer.publish_no_overwrite(
                self.root / "link", b"test kernel", b"test cgroup")
        self.assertEqual(list(real.iterdir()), [])

    def test_s1_52_refuses_world_readable_directory(self):
        self.private.chmod(0o755)
        with self.assertRaisesRegex(observer.ObservationError, "owner-only"):
            observer.publish_no_overwrite(self.private, b"kernel", b"cgroup")
        self.assertEqual(list(self.private.iterdir()), [])

    def test_s1_52_refuses_oversized_observations(self):
        with self.assertRaisesRegex(observer.ObservationError, "Bounded"):
            observer.publish_no_overwrite(
                self.private, b"x" * (observer.MAX_FILE_BYTES + 1), b"valid")
        self.assertEqual(list(self.private.iterdir()), [])

    def test_s1_52_rejects_missing_external_challenge_before_git(self):
        with mock.patch.object(
                observer, "verify_source_checkout_pin") as git:
            with self.assertRaisesRegex(observer.ObservationError,
                                        "challenge"):
                observer.collect_observations(
                    source_commit=COMMIT, reviewer_challenge="0" * 64,
                    source_root=self.root)
        git.assert_not_called()

    def test_s1_52_bad_commit_rejected_before_gate(self):
        with mock.patch.object(observer, "verify_arch_vm") as gate:
            with self.assertRaisesRegex(observer.ObservationError, "commit"):
                observer.collect_observations(
                    source_commit="f" * 38, reviewer_challenge=CHALLENGE,
                    source_root=self.root)
        gate.assert_not_called()

    def test_s1_52_dirty_checkout_fails_before_gate_and_output(self):
        with (mock.patch.object(
                observer, "verify_source_checkout_pin",
                side_effect=CheckoutPinError("checkout dirty")),
              mock.patch.object(observer, "verify_arch_vm") as gate,
              mock.patch.object(observer, "_command") as cmd):
            with self.assertRaisesRegex(CheckoutPinError, "dirty"):
                observer.collect_observations(
                    source_commit=COMMIT, reviewer_challenge=CHALLENGE,
                    source_root=self.root)
        gate.assert_not_called()
        cmd.assert_not_called()
        self.assertEqual(list(self.private.iterdir()), [])

    def test_s1_52_container_refusal_never_reads_vm_metadata(self):
        with (mock.patch.object(observer, "verify_source_checkout_pin",
                                return_value=PIN),
              mock.patch.object(
                  observer, "verify_arch_vm",
                  side_effect=ArchVmUnavailable("container rejected")),
              mock.patch.object(observer, "_command") as cmd,
              mock.patch.object(observer, "_read_bounded") as read):
            with self.assertRaisesRegex(ArchVmUnavailable, "container"):
                observer.collect_observations(
                    source_commit=COMMIT, reviewer_challenge=CHALLENGE,
                    source_root=self.root)
        cmd.assert_not_called()
        read.assert_not_called()

    def test_s1_52_vm_claim_inconsistent_with_gate_rejected(self):
        with (mock.patch.object(observer, "verify_source_checkout_pin",
                                return_value=PIN),
              mock.patch.object(observer, "verify_arch_vm",
                                return_value={**GATE, "container": True}),
              mock.patch.object(observer, "_command") as cmd):
            with self.assertRaisesRegex(observer.ObservationError, "preflight"):
                observer.collect_observations(
                    source_commit=COMMIT, reviewer_challenge=CHALLENGE,
                    source_root=self.root)
        cmd.assert_not_called()

    def test_s1_52_cgroup_controllers_missing_fails_closed(self):
        def metadata(path, *, limit):
            if str(path) == "/proc/1/comm":
                return "systemd"
            return "memory"
        with (mock.patch.object(observer, "verify_source_checkout_pin",
                                return_value=PIN),
              mock.patch.object(observer, "verify_arch_vm",
                                return_value=GATE),
              mock.patch.object(observer, "_read_bounded",
                                side_effect=metadata),
              mock.patch.object(observer, "_command") as cmd):
            with self.assertRaisesRegex(observer.ObservationError,
                                        "controllers unavailable"):
                observer.collect_observations(
                    source_commit=COMMIT, reviewer_challenge=CHALLENGE,
                    source_root=self.root)
        cmd.assert_not_called()

    def test_s1_52_source_mutation_after_metadata_blocks_publication(self):
        with (mock.patch.object(observer, "verify_source_checkout_pin",
                                side_effect=[PIN, {**PIN, "unexpected": 1}]),
              mock.patch.object(observer, "verify_arch_vm",
                                return_value=GATE),
              mock.patch.object(observer, "_read_bounded",
                                side_effect=lambda path, *, limit:
                                    "systemd" if str(path) == "/proc/1/comm"
                                    else "cpu memory pids"),
              mock.patch.object(observer, "_command",
                                side_effect=lambda name, *args:
                                    "/user.slice/user-1000.slice"
                                    if name == "systemctl" else "kvm")):
            with self.assertRaisesRegex(observer.ObservationError,
                                        "Source changed"):
                observer.collect_observations(
                    source_commit=COMMIT, reviewer_challenge=CHALLENGE,
                    source_root=self.root)
        self.assertEqual(list(self.private.iterdir()), [])

    def test_s1_52_empty_root_subtree_control_is_recordable(self):
        # Empty subtree_control is valid cgroup-v2 state; it does not prove
        # an absence of cgroup v2 on the guest.
        with mock.patch.object(
                Path, "open", mock.mock_open(read_data=b"")):
            self.assertEqual(
                observer._read_bounded(
                    Path("/sys/fs/cgroup/cgroup.subtree_control"), limit=1024),
                "")
            with self.assertRaises(observer.ObservationError):
                observer._read_bounded(
                    Path("/sys/fs/cgroup/cgroup.controllers"), limit=1024)

    def test_s1_52_whitelist_rejects_environment_dump_command(self):
        with self.assertRaisesRegex(observer.ObservationError,
                                    "Unapproved observation command"):
            observer._command("systemctl", "--user", "show-environment")

    def test_s1_52_cli_rejects_container_preflight_without_output(self):
        errors = StringIO()
        with (mock.patch.object(
                observer, "verify_source_checkout_pin",
                return_value=PIN),
              mock.patch.object(observer, "verify_arch_vm",
                                side_effect=ArchVmUnavailable("not VM")),
              redirect_stderr(errors)):
            status = observer.main([
                "--output-directory", str(self.private),
                "--source-root", str(self.root),
                "--expected-source-commit", COMMIT,
                "--reviewer-challenge", CHALLENGE,
            ])
        self.assertEqual(status, 2)
        self.assertEqual(
            json.loads(errors.getvalue())["status"],
            "REJECTED_NATIVE_OBSERVATION_NOT_HOMOLOGATED")
        self.assertEqual(list(self.private.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
