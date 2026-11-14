"""PE-S1.8 seccomp cBPF compiler contracts, no filter installed on CI host."""
import fcntl
import os
from pathlib import Path
import platform
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_seccomp_filter as policy


class SeccompPolicyTests(unittest.TestCase):
    def test_narrow_policy_never_blocks_java_required_syscalls(self):
        forbidden_to_block = ("clone", "clone3", "execve", "execveat",
                              "futex", "mmap", "mprotect", "openat",
                              "openat2", "read", "write", "socket", "connect")
        for syscall in forbidden_to_block:
            self.assertNotIn(syscall, policy.DENIED_SYSCALLS)
        self.assertIn("ptrace", policy.DENIED_SYSCALLS)
        self.assertIn("bpf", policy.DENIED_SYSCALLS)
        self.assertEqual(len(set(policy.DENIED_SYSCALLS)),
                         len(policy.DENIED_SYSCALLS))

    def test_architecture_fails_closed(self):
        with mock.patch.object(platform, "machine", return_value="aarch64"):
            with self.assertRaisesRegex(policy.SeccompUnavailable, "x86_64"):
                policy.compile_seccomp_bpf_fd()

    def test_attach_requires_real_bwrap_argv_and_fd(self):
        argv = ["/usr/bin/bwrap", "--unshare-all", "--", "/usr/bin/python3"]
        self.assertEqual(policy.attach_seccomp_fd(argv, 17),
                         ["/usr/bin/bwrap", "--unshare-all", "--seccomp",
                          "17", "--", "/usr/bin/python3"])
        self.assertEqual(argv[-2:], ["--", "/usr/bin/python3"])
        for bad in ([argv[0], "--"], ["bash", "--", "/usr/bin/python"],
                    argv + ["--"], argv[:-2] + ["--seccomp", "4", "--", "python"]):
            with self.subTest(bad=bad):
                with self.assertRaises(policy.SeccompUnavailable):
                    policy.attach_seccomp_fd(bad, 17)
        with self.assertRaises(policy.SeccompUnavailable):
            policy.attach_seccomp_fd(argv, 0)

    @unittest.skipUnless(platform.system() == "Linux" and
                         platform.machine() == "x86_64", "Linux x86_64 only")
    def test_real_libseccomp_compiles_sealed_kernel_bpf_without_loading(self):
        try:
            fd = policy.compile_seccomp_bpf_fd()
        except policy.SeccompUnavailable as exc:
            self.fail("libseccomp prerequisite missing: " + str(exc))
        try:
            current = os.fstat(fd)
            self.assertTrue(8 <= current.st_size <= policy.MAX_BPF_BYTES)
            self.assertEqual(current.st_size % 8, 0)
            seals = fcntl.fcntl(fd, fcntl.F_GET_SEALS)
            self.assertEqual(seals & (fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW |
                                      fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL),
                             fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW |
                             fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
            self.assertFalse(os.get_inheritable(fd))
            self.assertGreaterEqual(policy.seccomp_filter_count(), 0)
        finally:
            os.close(fd)


if __name__ == "__main__":
    unittest.main()
