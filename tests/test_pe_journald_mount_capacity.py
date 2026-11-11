"""PE-S2.26: synthetic mountinfo/statvfs contracts, no Arch VM attestation."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_journald_mount_capacity as mod

VALID = (b"99 1 0:2 / /run rw,nosuid,nodev - tmpfs tmpfs rw\n"
         b"101 99 0:20 / /run/log/journal rw,nosuid,nodev,relatime "
         b"- tmpfs tmpfs rw,size=33554432\n")
NESTED = b"102 101 0:21 / /run/log/journal/other rw - tmpfs tmpfs rw\n"


def fs(blocks=8192, frsize=4096, free=8000, avail=7800,
       flags=0):
    return SimpleNamespace(f_blocks=blocks, f_frsize=frsize,
                           f_bfree=free, f_bavail=avail, f_flag=flags)


class JournalMountContracts(unittest.TestCase):
    def test_dedicated_volatitle_tmpfs_parsed(self):
        observed = mod._journal_mount(VALID, mod.TARGET)
        self.assertEqual(observed["mount_id"], "101")
        self.assertEqual(observed["filesystem"], "tmpfs")
        self.assertEqual(observed["root"], "/")

    def test_missing_mount_overlay_nested_and_duplicate_refused(self):
        bad = (
            VALID.replace(b" - tmpfs tmpfs ", b" - ext4 /dev/vda "),
            VALID.replace(b"/ /run/log/journal rw", b"/old /run/log/journal rw"),
            VALID.replace(b"journal rw,nosuid", b"journal ro,nosuid"),
            # VFS rw does NOT guarantee a writable tmpfs superblock.
            VALID.replace(b"- tmpfs tmpfs rw,size=33554432",
                          b"- tmpfs tmpfs ro,size=33554432"),
            VALID.replace(b"- tmpfs tmpfs rw,size=33554432",
                          b"- tmpfs tmpfs size=33554432"),
            VALID.replace(b"/run/log/journal rw", b"/run/log/journal-extra rw"),
            VALID + NESTED,
            VALID + VALID.splitlines()[-1] + b"\n",
            b"99 1 0:1 / /run rw - tmpfs tmpfs rw\n",
        )
        for record in bad:
            with self.subTest(record=record):
                with self.assertRaises(mod.JournalMountError):
                    mod._journal_mount(record, mod.TARGET)

    def test_unsafe_mount_escape_and_control_characters_refused(self):
        for token in (r"/run/log/journal\777", r"/run/log/journal\011",
                      r"/run/log/journal\x", "/run/log/journal\x01"):
            with self.subTest(token=token):
                with self.assertRaises(mod.JournalMountError):
                    mod._unescape_mount_field(token)

    def test_statvfs_hard_cap_must_be_kernel_reported_and_bounded(self):
        with mock.patch.object(mod.os, "statvfs", return_value=fs()):
            self.assertEqual(mod._filesystem_size(mod.TARGET), 32 * 1024 * 1024)
        bad = (fs(blocks=8193), fs(blocks=0),
               fs(avail=9000), fs(free=9000, avail=9500),
               fs(frsize=0), fs(blocks=-1),
               fs(flags=os.ST_RDONLY), fs(flags=-1),
               fs(flags=True))
        for value in bad:
            with self.subTest(value=value):
                with (mock.patch.object(mod.os, "statvfs", return_value=value),
                      self.assertRaises(mod.JournalMountError)):
                    mod._filesystem_size(mod.TARGET)

    def test_statvfs_rejects_missing_flags_or_mismatched_readonly_state(self):
        # A writeable mountinfo line is not enough if statvfs reports ro.
        candidates = (SimpleNamespace(
            f_blocks=8192, f_frsize=4096, f_bfree=8000, f_bavail=7800),
            fs(flags=os.ST_RDONLY))
        for record in candidates:
            with self.subTest(record=record):
                with (mock.patch.object(mod.os, "statvfs", return_value=record),
                      self.assertRaises(mod.JournalMountError)):
                    mod._filesystem_size(mod.TARGET)

    def test_root_owned_nonwritable_directory_chain(self):
        safe = SimpleNamespace(st_mode=(stat.S_IFDIR | 0o755), st_uid=0,
                               st_dev=22, st_ino=55)
        with mock.patch.object(Path, "lstat", return_value=safe) as lookup:
            self.assertEqual(mod._secure_root_owned_path(mod.TARGET), (22, 55))
        self.assertEqual(lookup.call_count, 3)
        for bad in (
            SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=0),
            SimpleNamespace(st_mode=stat.S_IFDIR | 0o777, st_uid=0),
            SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=1000),
        ):
            with (mock.patch.object(Path, "lstat", return_value=bad),
                  self.assertRaises(mod.JournalMountError)):
                mod._secure_root_owned_path(mod.TARGET)

    def test_same_mount_local_observation_does_not_attest_journald_or_vm(self):
        with (mock.patch.object(mod.os, "geteuid", return_value=1000),
              mock.patch.object(mod, "_secure_root_owned_path",
                                return_value=(22, 55)) as dirs,
              mock.patch.object(mod, "_kernel_mountinfo",
                                return_value=VALID) as mounts,
              mock.patch.object(mod, "_filesystem_size",
                                return_value=32 * 1024 * 1024) as capacity):
            result = mod.observe_local_mount()
        self.assertEqual(dirs.call_count, 2)
        self.assertEqual(mounts.call_count, 2)
        self.assertEqual(capacity.call_count, 2)
        self.assertEqual(result["status"], mod.OBSERVED)
        self.assertTrue(result["journal_store_separate_tmpfs_locally_observed"])
        for key in ("journald_uses_this_storage_independently_verified",
                    "journald_effective_runtime_policy_verified",
                    "journald_storage_quota_independently_verified",
                    "native_arch_vm_attested", "independent_vm_attestation",
                    "release_authorized", "apk_or_ota_publication_authorized",
                    "unknown_windows_pe_execution_authorized"):
            self.assertIs(result[key], False)

    def test_mount_replacement_during_observation_rejected(self):
        replacement = VALID.replace(b"101 99", b"123 99")
        with (mock.patch.object(mod.os, "geteuid", return_value=1000),
              mock.patch.object(mod, "_secure_root_owned_path",
                                return_value=(22, 55)),
              mock.patch.object(mod, "_kernel_mountinfo",
                                side_effect=[VALID, replacement]),
              mock.patch.object(mod, "_filesystem_size",
                                return_value=32 * 1024 * 1024),
              self.assertRaisesRegex(mod.JournalMountError, "changed")):
            mod.observe_local_mount()

    def test_inode_replacement_during_observation_rejected(self):
        with (mock.patch.object(mod.os, "geteuid", return_value=1000),
              mock.patch.object(mod, "_secure_root_owned_path",
                                side_effect=[(22, 55), (22, 77)]),
              mock.patch.object(mod, "_kernel_mountinfo", return_value=VALID),
              mock.patch.object(mod, "_filesystem_size",
                                return_value=32 * 1024 * 1024),
              self.assertRaisesRegex(mod.JournalMountError, "changed")):
            mod.observe_local_mount()

    def test_capacity_change_during_observation_rejected(self):
        with (mock.patch.object(mod.os, "geteuid", return_value=1000),
              mock.patch.object(mod, "_secure_root_owned_path",
                                return_value=(22, 55)),
              mock.patch.object(mod, "_kernel_mountinfo", return_value=VALID),
              mock.patch.object(mod, "_filesystem_size",
                                side_effect=[32 * 1024 * 1024, 64 * 1024 * 1024]),
              self.assertRaisesRegex(mod.JournalMountError, "capacity changed")):
            mod.observe_local_mount()

    def test_default_cli_no_filesystem_reads(self):
        out = StringIO()
        with (mock.patch.object(mod, "_kernel_mountinfo") as read,
              mock.patch.object(mod, "observe_local_mount") as inspect,
              redirect_stdout(out)):
            self.assertEqual(mod.main([]), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], mod.PLAN)
        self.assertFalse(json.loads(out.getvalue())["kernel_mount_files_read"])
        read.assert_not_called()
        inspect.assert_not_called()

    def test_explicit_cli_positive_still_hold_exit_two(self):
        out = StringIO()
        with (mock.patch.object(mod, "observe_local_mount",
                                return_value={"status": mod.OBSERVED,
                                              "release_authorized": False}) as inspect,
              redirect_stdout(out)):
            self.assertEqual(mod.main(["--inspect-local-journal-mount"]), 2)
        inspect.assert_called_once()
        self.assertEqual(json.loads(out.getvalue())["status"], mod.OBSERVED)

    def test_explicit_cli_rejection_has_no_false_pass(self):
        out, err = StringIO(), StringIO()
        with (mock.patch.object(mod, "observe_local_mount",
                                side_effect=mod.JournalMountError("no quota")),
              redirect_stdout(out), redirect_stderr(err)):
            self.assertEqual(mod.main(["--inspect-local-journal-mount"]), 2)
        self.assertFalse(out.getvalue())
        result = json.loads(err.getvalue())
        self.assertEqual(result["status"], mod.REJECTED)
        self.assertIs(result["independent_vm_attestation"], False)
        self.assertIs(result["release_authorized"], False)

    def test_root_guest_refused_before_any_mount_access(self):
        with (mock.patch.object(mod.os, "geteuid", return_value=0),
              mock.patch.object(mod, "_kernel_mountinfo") as info,
              self.assertRaises(mod.JournalMountError)):
            mod.observe_local_mount()
        info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
