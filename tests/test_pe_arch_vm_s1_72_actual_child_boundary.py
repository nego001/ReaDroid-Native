"""PE-S1.72: REAL Linux subprocess/pipe boundary with a fake virsh fixture.

All libvirt replies are fixture data. No VM or host libvirt is contacted.
Unlike PE-S1.70/71 mocked contracts, this executes real bounded subprocesses.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s1_70_readonly_libvirt_host_capture as host
import pe_arch_vm_s1_71_guestinfo_os_capture as guest

COMMIT = "a" * 40
CHALLENGE = "b" * 64
UUID = "12345678-abcd-4ef0-8123-123456789abc"
DOMAIN = "reviewer-native-arch-01"

# Deliberately fixed outputs. Its only side effect is to append audit argv
# into the test's private temp folder; it cannot operate a libvirt service.
STUB = r'''#!/usr/bin/python3
import json
from pathlib import Path
import sys

log = Path(__LOG__)
mode = __MODE__
args = sys.argv[1:]
with log.open("a", encoding="utf-8") as f:
    f.write(json.dumps(args) + "\n")
if args[:4] != ["--readonly", "--connect", "qemu:///system", "--no-pkttyagent"]:
    sys.stderr.write("not read-only\n")
    raise SystemExit(3)
cmd = args[4]
if cmd == "domuuid" and args[5:] == [__DOMAIN__]:
    sys.stdout.write(__UUID__ + "\n")
elif cmd == "domstate" and args[5:] == [__DOMAIN__]:
    sys.stdout.write("running\n")
elif cmd == "dominfo" and args[5:] == [__DOMAIN__]:
    sys.stdout.write("Name: " + __DOMAIN__ + "\nUUID: " + __UUID__
                     + "\nState: running\n")
elif cmd == "guestinfo" and args[5:] == [__DOMAIN__, "--os"]:
    if mode == "deny_guestinfo":
        sys.stderr.write("read-only guest agent unsupported\n")
        raise SystemExit(1)
    if mode == "oversized_guestinfo":
        sys.stdout.write("A" * 9000)
        raise SystemExit(0)
    ident = "ubuntu" if mode == "wrong_guest_os" else "arch"
    sys.stdout.write("os.id : " + ident + "\nos.name : Arch Linux\n"
                     "os.kernel-release : 6.17.5-arch1-1\n"
                     "os.machine : x86_64\n")
else:
    sys.stderr.write("forbidden command\n")
    raise SystemExit(4)
'''


class ActualBoundedChildBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pe-s1-72-child-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.observer = self.root / "observer"
        self.observer.mkdir(mode=0o700)
        self.log = self.root / "stub-invocations.jsonl"
        self.executable = self.root / "virsh-test-fixture"

    def install_fixture(self, mode="ok"):
        script = (STUB.replace("__LOG__", repr(str(self.log)))
                  .replace("__MODE__", repr(mode))
                  .replace("__DOMAIN__", repr(DOMAIN))
                  .replace("__UUID__", repr(UUID)))
        self.executable.write_text(script, encoding="utf-8")
        self.executable.chmod(0o700)

    def calls(self):
        import json
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def capture_first(self):
        return host.capture_host_domain(
            self.observer, domain=DOMAIN, expected_domain_uuid=UUID,
            expected_source_commit=COMMIT, reviewer_challenge=CHALLENGE,
            capture_from_independent_host=True)

    def capture_second(self, digest):
        return guest.capture_guest_kernel_observation(
            self.observer, domain=DOMAIN, expected_domain_uuid=UUID,
            expected_source_commit=COMMIT, reviewer_challenge=CHALLENGE,
            expected_prior_host_sha256=digest,
            capture_from_independent_host=True)

    def test_real_subprocesses_complete_both_readonly_captures(self):
        self.install_fixture()
        # Mock only executable discovery; actual Python subprocesses, pipes,
        # output checks, permission checks and publication are all real.
        with mock.patch.object(host.shutil, "which", return_value=str(self.executable)):
            first = self.capture_first()
            digest = hashlib.sha256((self.observer / host.TARGET).read_bytes()).hexdigest()
            second = self.capture_second(digest)
        self.assertTrue(first["host_queries_executed"])
        self.assertEqual(second["kernel_observation_sha256"],
                         hashlib.sha256((self.observer / guest.TARGET).read_bytes()).hexdigest())
        expected = ["domuuid", "domstate", "dominfo", "domstate", "domuuid",
                    "domuuid", "domstate", "guestinfo", "domstate", "domuuid"]
        invocations = self.calls()
        self.assertEqual([argv[4] for argv in invocations], expected)
        self.assertEqual(len(invocations), 10)
        for argv in invocations:
            self.assertEqual(argv[:4], ["--readonly", "--connect", "qemu:///system", "--no-pkttyagent"])
            self.assertEqual(argv[5], DOMAIN)
        self.assertEqual(invocations[7][6:], ["--os"])
        for name in (host.TARGET, guest.TARGET):
            self.assertEqual((self.observer / name).stat().st_mode & 0o777, 0o600)
        self.assertEqual({x.name for x in self.observer.iterdir()}, {host.TARGET, guest.TARGET})
        self.assertFalse(second["guest_kernel_independently_verified"])
        self.assertFalse(second["independent_vm_attestation"])
        self.assertFalse(second["release_authorized"])
        self.assertFalse(second["unknown_windows_pe_execution_authorized"])
        self.assertFalse(second["apk_or_ota_publication_authorized"])

    def test_real_readonly_guest_agent_refusal_fails_closed(self):
        self.install_fixture("deny_guestinfo")
        with mock.patch.object(host.shutil, "which", return_value=str(self.executable)):
            self.capture_first()
            digest = hashlib.sha256((self.observer / host.TARGET).read_bytes()).hexdigest()
            with self.assertRaises(guest.GuestKernelObservationError):
                self.capture_second(digest)
        self.assertEqual(len(self.calls()), 8)
        self.assertFalse((self.observer / guest.TARGET).exists())

    def test_real_child_oversized_output_rejected_before_publication(self):
        self.install_fixture("oversized_guestinfo")
        with mock.patch.object(host.shutil, "which", return_value=str(self.executable)):
            self.capture_first()
            digest = hashlib.sha256((self.observer / host.TARGET).read_bytes()).hexdigest()
            with self.assertRaises(guest.GuestKernelObservationError):
                self.capture_second(digest)
        self.assertFalse((self.observer / guest.TARGET).exists())

    def test_real_guest_os_mismatch_never_publishes(self):
        self.install_fixture("wrong_guest_os")
        with mock.patch.object(host.shutil, "which", return_value=str(self.executable)):
            self.capture_first()
            digest = hashlib.sha256((self.observer / host.TARGET).read_bytes()).hexdigest()
            with self.assertRaises(guest.GuestKernelObservationError):
                self.capture_second(digest)
        self.assertFalse((self.observer / guest.TARGET).exists())

    def test_external_pin_mismatch_rejected_without_any_new_child(self):
        self.install_fixture()
        with mock.patch.object(host.shutil, "which", return_value=str(self.executable)):
            self.capture_first()
            before = len(self.calls())
            with self.assertRaises(guest.GuestKernelObservationError):
                self.capture_second("f" * 64)
        self.assertEqual(len(self.calls()), before)
        self.assertFalse((self.observer / guest.TARGET).exists())

    def test_default_plan_does_not_start_real_children(self):
        self.install_fixture()
        with mock.patch.object(host.shutil, "which", return_value=str(self.executable)):
            result = host.capture_host_domain(
                self.observer, domain=DOMAIN, expected_domain_uuid=UUID,
                expected_source_commit=COMMIT, reviewer_challenge=CHALLENGE)
        self.assertFalse(result["host_queries_executed"])
        self.assertEqual(self.calls(), [])
        self.assertEqual(list(self.observer.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
