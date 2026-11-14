"""PE-S2.11 contracts. No actual disk allocation or native VM is tested here."""
from __future__ import annotations

import errno
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_native_work_enospc as proof

CAPACITY = 64 * 1024 * 1024
FREE = 60 * 1024 * 1024
MOUNT = {
    "work_mount_type": "tmpfs",
    "mounted_size_bytes": CAPACITY,
    "mount_source_kind": "dedicated_reviewer_prepared",
    "kernel_storage_limit_observed_locally": True,
    "journald_budget_verified": False,
    "independent_vm_attested": False,
}


class NativeEnospcContracts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="pe-s2-11-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.fallocate_calls = []

    def check(self, **overrides):
        values = {**MOUNT, **overrides}
        usage = [
            (CAPACITY, FREE),
            (CAPACITY, FREE - proof.INITIAL_RESERVATION),
        ]
        def fake_fallocate(fd, start, length):
            self.fallocate_calls.append((start, length))
            if length > CAPACITY:
                raise OSError(errno.ENOSPC, "synthetic ENOSPC")
        with (mock.patch.object(proof.os, "geteuid", return_value=os.geteuid()),
              mock.patch.object(proof.storage, "require_bounded_work_mount",
                                return_value=values),
              mock.patch.object(proof, "_capacity_and_free",
                                side_effect=usage),
              mock.patch.object(proof.os, "posix_fallocate",
                                side_effect=fake_fallocate),
              mock.patch.object(proof.os, "statvfs",
                                return_value=mock.Mock(
                                    f_frsize=4096, f_bavail=FREE // 4096))):
            return proof.require_native_work_enospc(self.root)

    def test_excess_allocation_fails_enospc_then_cleanup(self):
        result = self.check()
        self.assertEqual(result["status"], "LOCAL_NATIVE_WORK_TMPFS_FALLOCATE_ENOSPC")
        self.assertEqual(self.fallocate_calls, [
            (0, proof.INITIAL_RESERVATION), (0, CAPACITY + proof.EXCESS_BYTES)])
        self.assertTrue(result["enospc_observed_on_oversize_reservation"])
        self.assertFalse(result["native_arch_vm_independently_attested"])
        self.assertFalse(result["release_authorized"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_mount_prerequisite_must_be_strict(self):
        for values in (
            {"work_mount_type": "ext4"},
            {"kernel_storage_limit_observed_locally": False},
            {"independent_vm_attested": True},
            {"mounted_size_bytes": "64M"},
        ):
            with self.subTest(values=values):
                self.fallocate_calls.clear()
                with self.assertRaises(proof.NativeWorkEnospcError):
                    self.check(**values)
                self.assertFalse(self.fallocate_calls)
                self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_prerequisite_refuses_before_allocation(self):
        with (mock.patch.object(proof.storage, "require_bounded_work_mount",
                                side_effect=proof.storage.NativeStorageBudgetError("not tmpfs")),
              mock.patch.object(proof.os, "posix_fallocate") as fallocate):
            with self.assertRaises(proof.NativeWorkEnospcError):
                proof.require_native_work_enospc(self.root)
            fallocate.assert_not_called()

    def test_missing_oversize_enospc_rejected_and_file_removed(self):
        def fake_fallocate(fd, start, length):
            self.fallocate_calls.append(length)
        with (mock.patch.object(proof.storage, "require_bounded_work_mount",
                                return_value=MOUNT),
              mock.patch.object(proof, "_capacity_and_free",
                                side_effect=[(CAPACITY, FREE), (
                                    CAPACITY, FREE-proof.INITIAL_RESERVATION)]),
              mock.patch.object(proof.os, "posix_fallocate",
                                side_effect=fake_fallocate)):
            with self.assertRaisesRegex(proof.NativeWorkEnospcError, "did not enforce"):
                proof.require_native_work_enospc(self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_non_enospc_failure_rejected_and_file_removed(self):
        with (mock.patch.object(proof.storage, "require_bounded_work_mount",
                                return_value=MOUNT),
              mock.patch.object(proof, "_capacity_and_free",
                                side_effect=[(CAPACITY, FREE),
                                             (CAPACITY, FREE-proof.INITIAL_RESERVATION)]),
              mock.patch.object(proof.os, "posix_fallocate",
                                side_effect=[None, OSError(errno.EINVAL, "invalid")])):
            with self.assertRaisesRegex(proof.NativeWorkEnospcError, "unexpected errno"):
                proof.require_native_work_enospc(self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_initial_reservation_must_consume_kernel_space(self):
        with (mock.patch.object(proof.storage, "require_bounded_work_mount",
                                return_value=MOUNT),
              mock.patch.object(proof, "_capacity_and_free",
                                side_effect=[(CAPACITY, FREE), (CAPACITY, FREE)]),
              mock.patch.object(proof.os, "posix_fallocate", return_value=None)):
            with self.assertRaisesRegex(proof.NativeWorkEnospcError, "did not consume"):
                proof.require_native_work_enospc(self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_recovery_failure_refuses_after_file_removed(self):
        with (mock.patch.object(proof.storage, "require_bounded_work_mount",
                                return_value=MOUNT),
              mock.patch.object(proof, "_capacity_and_free",
                                side_effect=[(CAPACITY, FREE),
                                             (CAPACITY, FREE-proof.INITIAL_RESERVATION)]),
              mock.patch.object(proof.os, "posix_fallocate",
                                side_effect=[None, OSError(errno.ENOSPC, "full")]),
              mock.patch.object(proof.os, "statvfs",
                                return_value=mock.Mock(
                                    f_frsize=4096, f_bavail=(
                                        FREE - 8*1024*1024)//4096))):
            with self.assertRaisesRegex(proof.NativeWorkEnospcError, "did not free"):
                proof.require_native_work_enospc(self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_relative_or_root_user_refused(self):
        with mock.patch.object(proof.os, "geteuid", return_value=0):
            with self.assertRaises(proof.NativeWorkEnospcError):
                proof.require_native_work_enospc(self.root)
        with self.assertRaises(proof.NativeWorkEnospcError):
            proof.require_native_work_enospc(Path("relative"))

    def test_failure_cleanup_does_not_overwrite_older_files(self):
        prior = self.root / ".negresco-pe-s2-11-existing"
        prior.write_text("safe")
        self.check()
        self.assertEqual(prior.read_text(), "safe")


if __name__ == "__main__":
    unittest.main()
