"""Synthetic evidence contracts for seccomp status measured by Ghidra JVM."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from pe_seccomp_runtime_evidence import (
    read_ghidra_seccomp_proof, baseline_from_scope_receipts,
    SeccompRuntimeEvidenceError)


class GhidraRuntimeAttestationTests(unittest.TestCase):
    UNIT = "negresco-pe-0123456789abcdef01234567.scope"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "jvm-proof.json"
        self.good = {
            "schema": "negresco_ghidra_seccomp_runtime_v1",
            "seccomp_mode": 2,
            "seccomp_filters": 3,
            "measurement_source": "/proc/self/status",
            "measured_process": "ghidra_headless_jvm",
        }

    def write(self, obj):
        self.path.write_text(json.dumps(obj), encoding="utf-8")
        self.path.chmod(0o600)

    def test_accepts_real_kernel_mode_and_increased_filter_count(self):
        self.write(self.good)
        record = read_ghidra_seccomp_proof(self.path, 2)
        self.assertTrue(record["verified"])
        self.assertEqual(record["filters_before_bwrap"], 2)
        self.assertEqual(record["filters_in_ghidra"], 3)
        self.assertEqual(record["additional_filters_observed"], 1)

    def test_does_not_accept_existing_filter_only(self):
        self.write(self.good)
        for baseline in (3, 4):
            with self.subTest(baseline=baseline):
                with self.assertRaises(SeccompRuntimeEvidenceError):
                    read_ghidra_seccomp_proof(self.path, baseline)

    def test_rejects_wrong_kernel_mode_and_fake_identity(self):
        for field, value in (
                ("seccomp_mode", 0), ("seccomp_mode", True),
                ("seccomp_filters", True), ("seccomp_filters", "3"),
                ("measured_process", "independent_python_probe"),
                ("measurement_source", "untrusted-json")):
            bad = dict(self.good)
            bad[field] = value
            self.write(bad)
            with self.subTest(field=field, value=value):
                with self.assertRaises(SeccompRuntimeEvidenceError):
                    read_ghidra_seccomp_proof(self.path, 1)

    def test_rejects_symlink_unsafe_mode_and_extra_keys(self):
        self.write(self.good)
        link = Path(self.temp.name) / "sym.json"
        link.symlink_to(self.path)
        with self.assertRaises(SeccompRuntimeEvidenceError):
            read_ghidra_seccomp_proof(link, 1)
        self.path.chmod(0o666)
        with self.assertRaises(SeccompRuntimeEvidenceError):
            read_ghidra_seccomp_proof(self.path, 1)
        extra = dict(self.good)
        extra["unexpected"] = "false confidence"
        self.write(extra)
        with self.assertRaises(SeccompRuntimeEvidenceError):
            read_ghidra_seccomp_proof(self.path, 1)

    def test_rejects_duplicate_keys_and_oversized_proof(self):
        self.path.write_text(
            '{"schema":"negresco_ghidra_seccomp_runtime_v1",'
            '"seccomp_mode":2,"seccomp_mode":2,"seccomp_filters":4,'
            '"measurement_source":"/proc/self/status",'
            '"measured_process":"ghidra_headless_jvm"}', encoding="utf-8")
        self.path.chmod(0o600)
        with self.assertRaises(SeccompRuntimeEvidenceError):
            read_ghidra_seccomp_proof(self.path, 1)
        self.path.write_bytes(b"x" * 2048)
        with self.assertRaises(SeccompRuntimeEvidenceError):
            read_ghidra_seccomp_proof(self.path, 1)

    def test_s1_25_rejects_symlinked_ancestor_above_jvm_proof(self):
        self.write(self.good)
        outer = Path(self.temp.name) / "real-container"
        workspace = outer / "workspace"
        workspace.mkdir(parents=True, mode=0o700)
        copied = workspace / "jvm-proof.json"
        copied.write_bytes(self.path.read_bytes())
        copied.chmod(0o600)
        self.assertTrue(read_ghidra_seccomp_proof(copied, 2)["verified"])
        alias = Path(self.temp.name) / "linked-container"
        alias.symlink_to(outer, target_is_directory=True)
        with self.assertRaises(SeccompRuntimeEvidenceError):
            read_ghidra_seccomp_proof(alias / "workspace" / copied.name, 2)

    def test_s1_25_rejects_fifo_without_waiting_for_writer(self):
        named_pipe = Path(self.temp.name) / "not-jvm.json"
        os.mkfifo(named_pipe, 0o600)
        with self.assertRaises(SeccompRuntimeEvidenceError):
            read_ghidra_seccomp_proof(named_pipe, 2)

    def test_s1_25_rejects_modified_jvm_inode_during_read(self):
        from unittest import mock
        self.write(self.good)
        original_read = os.read

        def mutate(fd, count):
            raw = original_read(fd, count)
            os.utime(self.path, None)
            return raw

        with mock.patch("pe_seccomp_runtime_evidence.os.read",
                        side_effect=mutate):
            with self.assertRaisesRegex(
                    SeccompRuntimeEvidenceError, "changed during read"):
                read_ghidra_seccomp_proof(self.path, 2)

    def test_s1_25_rejects_world_writable_jvm_parent(self):
        self.write(self.good)
        self.path.parent.chmod(0o777)
        with self.assertRaises(SeccompRuntimeEvidenceError):
            read_ghidra_seccomp_proof(self.path, 2)
        self.path.parent.chmod(0o700)

    def test_requires_one_matching_scope_receipt(self):
        receipt = {"scope_seccomp_guard": "passed",
                   "scope": self.UNIT,
                   "filters_compiled_inside_scope": True,
                   "seccomp_filters_before_bwrap": 2}
        self.assertEqual(baseline_from_scope_receipts([receipt], self.UNIT), 2)
        for records in ([], [receipt, receipt],
                        [{**receipt, "scope": "other.scope"}],
                        [{**receipt, "seccomp_filters_before_bwrap": True}],
                        [{**receipt, "seccomp_filters_before_bwrap": -1}]):
            with self.subTest(records=records):
                with self.assertRaises(SeccompRuntimeEvidenceError):
                    baseline_from_scope_receipts(records, self.UNIT)


if __name__ == "__main__":
    unittest.main()
