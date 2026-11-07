"""PE-S2.06: native bounded file staging / observed workspace footprint.

Tests use only private temporary files, no real Arch VM, scope or Ghidra.
A successful post-run audit is NOT an enforced filesystem/journald quota.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_native_workspace_budget as storage


class NativeStorageBudgetContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / "work"
        self.work.mkdir(mode=0o700)
        self.script = self.root / "script.java"
        self.script.write_bytes(b"synthetic-script" * 4)
        self.pe = self.root / "synthetic.exe"
        self.pe.write_bytes(b"MZ-synthetic-PE" * 10)

    def test_staged_files_are_complete_exclusive_private_and_counted(self):
        targets = [
            (self.script, self.work / "script.java", 512),
            (self.pe, self.work / "input.exe", 512),
        ]
        total = storage.stage_bounded_fixtures(targets)
        self.assertEqual(total, self.script.stat().st_size + self.pe.stat().st_size)
        for source, target, _ in targets:
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_source_over_budget_is_rejected_before_any_destination_write(self):
        target = self.work / "input.exe"
        with self.assertRaisesRegex(storage.NativeStorageBudgetError, "bounded"):
            storage.stage_bounded_fixtures([(self.pe, target, 32)])
        self.assertFalse(target.exists())

    def test_shared_aggregate_budget_rolls_back_earlier_complete_files(self):
        self.script.write_bytes(b"1" * 30)
        self.pe.write_bytes(b"2" * 30)
        with mock.patch.object(storage, "MAX_STAGE_TOTAL_BYTES", 50):
            with self.assertRaises(storage.NativeStorageBudgetError):
                storage.stage_bounded_fixtures([
                    (self.script, self.work / "first", 30),
                    (self.pe, self.work / "second", 30),
                ])
        self.assertFalse((self.work / "first").exists())
        self.assertFalse((self.work / "second").exists())

    def test_existing_file_or_symlink_is_never_clobbered(self):
        target = self.work / "input.exe"
        target.write_bytes(b"EXISTING")
        with self.assertRaises(storage.NativeStorageBudgetError):
            storage.stage_bounded_fixtures([(self.pe, target, 1024)])
        self.assertEqual(target.read_bytes(), b"EXISTING")
        target.unlink()
        target.symlink_to(self.pe)
        with self.assertRaises(storage.NativeStorageBudgetError):
            storage.stage_bounded_fixtures([(self.pe, target, 1024)])
        self.assertTrue(target.is_symlink())
        self.assertEqual(self.pe.read_bytes(), b"MZ-synthetic-PE" * 10)

    def test_symlink_source_rejected_without_following(self):
        alias = self.root / "alias.exe"
        alias.symlink_to(self.pe)
        with self.assertRaises(storage.NativeStorageBudgetError):
            storage.stage_bounded_fixtures(
                [(alias, self.work / "input.exe", 1024)])
        self.assertFalse((self.work / "input.exe").exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "Linux FIFO required")
    def test_fifo_source_is_refused_without_blocking(self):
        fifo = self.root / "synthetic.fifo"
        os.mkfifo(fifo)
        with self.assertRaises(storage.NativeStorageBudgetError):
            storage.stage_bounded_fixtures(
                [(fifo, self.work / "input.exe", 1024)])
        self.assertFalse((self.work / "input.exe").exists())

    def test_midstream_growth_refuses_and_removes_partial_copy(self):
        self.pe.write_bytes(b"MZ" * 20)
        reader = os.read
        grown = False

        def change_source(fd, size):
            nonlocal grown
            data = reader(fd, size)
            if not grown:
                grown = True
                with self.pe.open("ab") as stream:
                    stream.write(b"X" * 200)
            return data

        with mock.patch.object(storage.os, "read", side_effect=change_source):
            with self.assertRaises(storage.NativeStorageBudgetError):
                storage.stage_bounded_fixtures([
                    (self.pe, self.work / "input.exe", 100),
                ])
        self.assertTrue(grown)
        self.assertFalse((self.work / "input.exe").exists())

    def test_metadata_mutation_even_same_size_is_rejected(self):
        self.pe.write_bytes(b"MZ" * 30)
        reader = os.read
        changed = False

        def mutate(fd, size):
            nonlocal changed
            data = reader(fd, size)
            if not changed:
                changed = True
                original = self.pe.stat()
                os.utime(self.pe, ns=(
                    original.st_atime_ns,
                    original.st_mtime_ns + 2_000_000_000))
            return data

        with mock.patch.object(storage.os, "read", side_effect=mutate):
            with self.assertRaisesRegex(
                    storage.NativeStorageBudgetError, "changed"):
                storage.stage_bounded_fixtures([
                    (self.pe, self.work / "input.exe", 100),
                ])
        self.assertFalse((self.work / "input.exe").exists())

    def test_insecure_destination_directory_is_rejected(self):
        self.work.chmod(0o755)
        with self.assertRaisesRegex(
                storage.NativeStorageBudgetError, "owner-only"):
            storage.stage_bounded_fixtures([
                (self.script, self.work / "script.java", 1024),
            ])
        self.assertFalse((self.work / "script.java").exists())

    def test_postrun_audit_counts_both_logical_and_allocated_bytes(self):
        (self.work / "one").write_bytes(b"X" * 10)
        (self.work / "two").write_bytes(b"Y" * 15)
        report = storage.audit_postrun_workspace(self.work)
        self.assertGreaterEqual(report, 25)

    def test_postrun_rejects_oversized_synthetic_log(self):
        (self.work / "analyzer.log").write_bytes(b"X" * 8193)
        with self.assertRaisesRegex(
                storage.NativeStorageBudgetError, "footprint"):
            storage.audit_postrun_workspace(self.work, max_bytes=8192)

    def test_postrun_rejects_sparse_file_using_logical_size(self):
        path = self.work / "sparse-output"
        with path.open("wb") as stream:
            stream.seek(65536)
            stream.write(b"X")
        with self.assertRaisesRegex(
                storage.NativeStorageBudgetError, "footprint"):
            storage.audit_postrun_workspace(self.work, max_bytes=65536)

    def test_postrun_never_follows_workspace_symlinks_or_hardlinks(self):
        symlink = self.work / "link"
        symlink.symlink_to(self.pe)
        with self.assertRaisesRegex(
                storage.NativeStorageBudgetError, "link or special"):
            storage.audit_postrun_workspace(self.work)
        symlink.unlink()
        original = self.work / "original"
        original.write_bytes(b"X")
        os.link(original, self.work / "hardlink")
        with self.assertRaisesRegex(
                storage.NativeStorageBudgetError, "link or special"):
            storage.audit_postrun_workspace(self.work)

    def test_postrun_rejects_fifo(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO unsupported")
        os.mkfifo(self.work / "fifo")
        with self.assertRaises(storage.NativeStorageBudgetError):
            storage.audit_postrun_workspace(self.work)

    def test_postrun_rejects_excessive_entry_count(self):
        for number in range(6):
            (self.work / str(number)).write_bytes(b"X")
        with mock.patch.object(storage, "MAX_WORKSPACE_ENTRIES", 4):
            with self.assertRaisesRegex(
                    storage.NativeStorageBudgetError, "too many"):
                storage.audit_postrun_workspace(self.work)

    def test_postrun_rejects_excessive_depth(self):
        nested = self.work
        for _ in range(4):
            nested = nested / "sub"
            nested.mkdir(mode=0o700)
        with mock.patch.object(storage, "MAX_WORKSPACE_DEPTH", 2):
            with self.assertRaisesRegex(
                    storage.NativeStorageBudgetError, "nesting"):
                storage.audit_postrun_workspace(self.work)

    def test_private_audit_root_required(self):
        self.work.chmod(0o755)
        with self.assertRaisesRegex(
                storage.NativeStorageBudgetError, "not private"):
            storage.audit_postrun_workspace(self.work)


if __name__ == "__main__":
    unittest.main()
