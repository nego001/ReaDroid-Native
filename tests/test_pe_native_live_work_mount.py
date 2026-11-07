"""PE-S2.08: parse/reject unsafe native /work mount evidence.

Everything here is a mocked mount table plus private temporary directory.
It does NOT create a mount, attest a reviewer or execute a native VM/PE.
"""
from __future__ import annotations

import builtins
from io import BytesIO
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_native_workspace_budget as storage


class LiveNativeWorkMountContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pe-s2-08-work-")
        self.addCleanup(self.tmp.cleanup)
        self.mount = Path(self.tmp.name)
        self.work = self.mount / "workspace"
        self.work.mkdir(mode=0o700)
        dev = self.work.stat().st_dev
        self.device = f"{os.major(dev)}:{os.minor(dev)}"

    def mountinfo(self, *, kind="tmpfs", source="tmpfs",
                  options="rw,nosuid,nodev", extras="",
                  super_options="rw,size=524288k", device=None,
                  mount=None, nested=None, subroot="/"):
        place = self.mount if mount is None else mount
        base = (f"77 2 {device or self.device} {subroot} {place} "
                f"{options} {extras} - {kind} {source} {super_options}\n")
        if nested is not None:
            base += (f"78 77 {self.device} / {nested} rw - "
                     f"tmpfs tmpfs rw,size=64k\n")
        return base

    def check(self, contents=None, *, total=512*1024*1024,
              available=448*1024*1024, workspace=None):
        fake_mount = self.mountinfo() if contents is None else contents
        real_open = builtins.open

        def fake_open(path, *args, **kwargs):
            if os.fspath(path) == "/proc/self/mountinfo":
                return BytesIO(fake_mount.encode("ascii"))
            return real_open(path, *args, **kwargs)

        with (mock.patch("builtins.open", side_effect=fake_open),
              mock.patch.object(storage.os, "statvfs",
                                return_value=SimpleNamespace(
                                    f_frsize=4096, f_blocks=total//4096,
                                    f_bavail=available//4096))):
            return storage.require_bounded_work_mount(
                self.work if workspace is None else workspace)

    def test_dedicated_root_owned_private_tmpfs_is_local_only(self):
        proof = self.check()
        self.assertEqual(proof["work_mount_type"], "tmpfs")
        self.assertEqual(proof["mounted_size_bytes"], 512*1024*1024)
        self.assertTrue(proof["kernel_storage_limit_observed_locally"])
        self.assertFalse(proof["journald_budget_verified"])
        self.assertFalse(proof["independent_vm_attested"])

    def test_wrong_filesystem_or_submount_root_is_refused(self):
        for kwargs in ({"kind": "overlay", "source": "overlay"},
                       {"kind": "ext4", "source": "/dev/loop0"},
                       {"subroot": "/other"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(storage.NativeStorageBudgetError):
                    self.check(self.mountinfo(**kwargs))

    def test_no_explicit_size_or_readonly_mount_is_refused(self):
        for kwargs in ({"super_options": "rw"},
                       {"options": "ro,nodev"},
                       {"extras": "shared:11"},
                       {"extras": "master:14"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(storage.NativeStorageBudgetError):
                    self.check(self.mountinfo(**kwargs))

    def test_unbounded_or_too_small_tmpfs_is_refused(self):
        for size in (1*1024*1024, 600*1024*1024):
            with self.subTest(size=size):
                with self.assertRaisesRegex(
                        storage.NativeStorageBudgetError, "size"):
                    self.check(total=size)

    def test_below_32mib_available_space_is_refused(self):
        with self.assertRaises(storage.NativeStorageBudgetError):
            self.check(available=30*1024*1024)

    def test_mount_major_minor_device_mismatch_is_refused(self):
        with self.assertRaises(storage.NativeStorageBudgetError):
            self.check(self.mountinfo(device="999:999"))

    def test_nested_mount_bypass_is_refused(self):
        nested = self.work / "writable-escape"
        with self.assertRaisesRegex(storage.NativeStorageBudgetError,
                                    "Nested mount"):
            self.check(self.mountinfo(nested=nested))

    def test_insecure_mount_or_workspace_permissions_are_refused(self):
        for path in (self.mount, self.work):
            with self.subTest(path=path):
                path.chmod(0o755)
                try:
                    with self.assertRaisesRegex(
                            storage.NativeStorageBudgetError, "private"):
                        self.check()
                finally:
                    path.chmod(0o700)

    def test_workspace_symlink_cannot_be_a_quota_root(self):
        alias = self.mount / "alias"
        alias.symlink_to(self.work, target_is_directory=True)
        with self.assertRaises(storage.NativeStorageBudgetError):
            self.check(workspace=alias)

    def test_forged_or_incomplete_mountinfo_is_refused(self):
        for forged in ("", "77 2 X / /tmp rw - tmpfs tmpfs rw,size=1k\n",
                       "77 2 0:1 / /tmp rw - tmpfs tmpfs rw,size=1k",
                       "77 2 0:1 / /tmp rw - tmpfs tmpfs rw\\invalid\n"):
            with self.subTest(forged=forged):
                with self.assertRaises(storage.NativeStorageBudgetError):
                    self.check(forged)

    def test_mount_table_over_budget_is_refused(self):
        with self.assertRaisesRegex(
                storage.NativeStorageBudgetError, "Incomplete"):
            self.check(self.mountinfo() * 15000)

    def test_relative_path_is_refused_before_probing_proc(self):
        with self.assertRaises(storage.NativeStorageBudgetError):
            storage.require_bounded_work_mount(Path("relative/work"))


if __name__ == "__main__":
    unittest.main()
