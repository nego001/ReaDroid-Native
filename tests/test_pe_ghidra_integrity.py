"""Synthetic miniature ZIP/tree tests; never download or run Ghidra."""
import hashlib
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_ghidra_integrity as integrity


class GhidraReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.install = self.root / "ghidra_12.2_PUBLIC"
        self.install.mkdir()
        (self.install / "Ghidra").mkdir()
        self.manifest = {
            "Ghidra/application.properties": b"application.name=Ghidra\napplication.version=12.2\n",
            "support/analyzeHeadless": b"#!/bin/bash\necho synthetic\n",
        }
        (self.install / "support").mkdir()
        for name, payload in self.manifest.items():
            (self.install / name).write_bytes(payload)
        self.archive = self.root / "official-test.zip"
        with zipfile.ZipFile(self.archive, "w") as zipped:
            for name, payload in self.manifest.items():
                zipped.writestr("ghidra_12.2_PUBLIC/" + name, payload)
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def verify(self):
        with mock.patch.object(integrity, "GHIDRA_RELEASE_SHA256", self.digest):
            return integrity.verify_pinned_ghidra_tree(self.install, self.archive)

    def test_accepts_matching_pinned_package_only(self):
        proof = self.verify()
        self.assertTrue(proof["verified"])
        self.assertEqual(proof["matched_files"], len(self.manifest))
        self.assertEqual(proof["release_sha256"], self.digest)

    def test_rejects_different_zip_even_if_tree_still_matches(self):
        with self.assertRaisesRegex(integrity.GhidraIntegrityError, "SHA-256"):
            integrity.verify_pinned_ghidra_tree(self.install, self.archive)

    def test_rejects_mutated_extracted_file(self):
        (self.install / "Ghidra/application.properties").write_text("tampered")
        with self.assertRaisesRegex(integrity.GhidraIntegrityError, "differs"):
            self.verify()

    def test_rejects_extra_file_and_symlink(self):
        unlisted = self.install / "payload.so"
        unlisted.write_text("not in pinned archive")
        with self.assertRaisesRegex(integrity.GhidraIntegrityError, "Unlisted"):
            self.verify()
        unlisted.unlink()
        link = self.install / "unlisted-link"
        link.symlink_to(self.archive)
        with self.assertRaisesRegex(integrity.GhidraIntegrityError, "file type"):
            self.verify()

    def test_rejects_symlinked_ghidra_ancestor_directory(self):
        alias = self.root / "indirect-source"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(integrity.GhidraIntegrityError):
            with mock.patch.object(integrity, "GHIDRA_RELEASE_SHA256", self.digest):
                integrity.verify_pinned_ghidra_tree(
                    alias / self.install.name, self.archive)

    def test_rejects_symlinked_release_zip_ancestor_directory(self):
        alias = self.root / "indirect-archive"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(integrity.GhidraIntegrityError):
            with mock.patch.object(integrity, "GHIDRA_RELEASE_SHA256", self.digest):
                integrity.verify_pinned_ghidra_tree(
                    self.install, alias / self.archive.name)

    def test_rejects_fifo_and_special_installed_tree_nodes(self):
        import os
        named_pipe = self.install / "unlisted-pipe"
        os.mkfifo(named_pipe)
        with self.assertRaisesRegex(
                integrity.GhidraIntegrityError, "Unexpected file type"):
            self.verify()

    def test_rejects_symlinked_intermediate_directory(self):
        original = self.install / "support"
        actual = self.install / "real-support"
        original.rename(actual)
        original.symlink_to(actual, target_is_directory=True)
        with self.assertRaises(integrity.GhidraIntegrityError):
            self.verify()

    def test_rejects_changed_file_symlink(self):
        target = self.install / "support/analyzeHeadless"
        target.unlink()
        target.symlink_to(self.archive)
        with self.assertRaisesRegex(integrity.GhidraIntegrityError, "Symlink"):
            self.verify()

    def test_rejects_unsafe_member_with_patched_pin(self):
        unsafe = self.root / "unsafe.zip"
        with zipfile.ZipFile(unsafe, "w") as zipped:
            zipped.writestr("ghidra_12.2_PUBLIC/../escape", b"evil")
        digest = hashlib.sha256(unsafe.read_bytes()).hexdigest()
        with mock.patch.object(integrity, "GHIDRA_RELEASE_SHA256", digest):
            with self.assertRaisesRegex(integrity.GhidraIntegrityError, "Unsafe"):
                integrity.verify_pinned_ghidra_tree(self.install, unsafe)


if __name__ == "__main__":
    unittest.main()
