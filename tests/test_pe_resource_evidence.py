"""Synthetic private cgroup proof validation tests.

This validates guard evidence only; it does not create a real cgroup.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from pe_resource_evidence import (
    read_scope_proof, corroborate_guard_receipt, InvalidResourceEvidence)

UNIT = "negresco-pe-0123456789abcdef01234567.scope"


class ResourceProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.file = Path(self.temp.name) / "limits.json"
        self.valid = {
            "schema": "negresco_cgroup_v2_proof_v1",
            "scope": UNIT,
            "verified": True,
            "memory_max": 4 * 1024 ** 3,
            "pids_max": 128,
            "cpu_quota": 200000,
            "cpu_period": 100000,
        }

    def tearDown(self):
        self.temp.cleanup()

    def write(self, data):
        self.file.write_text(json.dumps(data), encoding="utf-8")
        self.file.chmod(0o600)

    def test_accepts_private_bounded_scope_proof(self):
        self.write(self.valid)
        values = read_scope_proof(self.file, UNIT)
        self.assertEqual(values["verification"], "guard_verified_before_bwrap")
        self.assertEqual(values["memory_max_bytes"], 4 * 1024 ** 3)
        self.assertEqual(values["tasks_max"], 128)

    def test_fail_closed_if_missing_or_world_readable_or_symlink(self):
        with self.assertRaises(InvalidResourceEvidence):
            read_scope_proof(self.file, UNIT)
        self.write(self.valid)
        self.file.chmod(0o644)
        with self.assertRaises(InvalidResourceEvidence):
            read_scope_proof(self.file, UNIT)
        self.file.chmod(0o600)
        symlink = Path(self.temp.name) / "link.json"
        symlink.symlink_to(self.file)
        with self.assertRaises(InvalidResourceEvidence):
            read_scope_proof(symlink, UNIT)

    def test_rejects_scope_mismatch_and_forged_limits(self):
        mutations = [
            {"scope": "not-our-scope.scope"},
            {"verified": False},
            {"schema": "unknown"},
            {"memory_max": "max"},
            {"pids_max": True},
            {"memory_max": 8 * 1024 ** 3},
            {"pids_max": 256},
            {"cpu_quota": 300000},
            {"cpu_period": 0},
        ]
        for patch in mutations:
            with self.subTest(patch=patch):
                self.write({**self.valid, **patch})
                with self.assertRaises(InvalidResourceEvidence):
                    read_scope_proof(self.file, UNIT)

    def test_refuses_oversized_or_malformed_json(self):
        self.file.write_text("{malformed", encoding="utf-8")
        with self.assertRaises(InvalidResourceEvidence):
            read_scope_proof(self.file, UNIT)
        self.file.write_text(" " * 4097, encoding="utf-8")
        with self.assertRaises(InvalidResourceEvidence):
            read_scope_proof(self.file, UNIT)


    def test_rejects_duplicate_json_keys_and_unknown_security_fields(self):
        self.file.write_text(
            '{"schema":"negresco_cgroup_v2_proof_v1",'
            '"scope":"' + UNIT + '","verified":true,"verified":true,'
            '"memory_max":4294967296,"pids_max":128,'
            '"cpu_quota":200000,"cpu_period":100000}', encoding="utf-8")
        self.file.chmod(0o600)
        with self.assertRaises(InvalidResourceEvidence):
            read_scope_proof(self.file, UNIT)
        self.write({**self.valid, "unexpected": "injected"})
        with self.assertRaises(InvalidResourceEvidence):
            read_scope_proof(self.file, UNIT)

    def test_rejects_parent_symlink_or_shared_permissions(self):
        self.write(self.valid)
        alias = Path(self.temp.name) / "parent-link"
        alias.symlink_to(self.file.parent, target_is_directory=True)
        with self.assertRaises(InvalidResourceEvidence):
            read_scope_proof(alias / self.file.name, UNIT)
        self.file.parent.chmod(0o755)
        with self.assertRaises(InvalidResourceEvidence):
            read_scope_proof(self.file, UNIT)
        self.file.parent.chmod(0o700)

    def test_guard_receipt_must_match_exact_private_quota_values(self):
        self.write(self.valid)
        private = read_scope_proof(self.file, UNIT)
        receipt = {
            "cgroup_verification": "passed", "verified": True,
            "memory_max": 4294967296, "pids_max": 128,
            "cpu_quota": 200000, "cpu_period": 100000,
        }
        self.assertTrue(corroborate_guard_receipt(
            [receipt], private)["corroborated"])
        for field, value in (
                ("memory_max", 4294967295), ("pids_max", 127),
                ("cpu_quota", 199999), ("cpu_period", 99999),
                ("verified", False), ("verified", "true"),
                ("pids_max", True)):
            with self.subTest(field=field, value=value):
                with self.assertRaises(InvalidResourceEvidence):
                    corroborate_guard_receipt(
                        [{**receipt, field: value}], private)
        for records in ([], [receipt, receipt], [{"cgroup_verification": "rejected"}]):
            with self.subTest(records=records):
                with self.assertRaises(InvalidResourceEvidence):
                    corroborate_guard_receipt(records, private)

    def test_guard_receipt_cannot_replace_missing_private_proof(self):
        receipt = {
            "cgroup_verification": "passed", "verified": True,
            "memory_max": 4294967296, "pids_max": 128,
            "cpu_quota": 200000, "cpu_period": 100000,
        }
        with self.assertRaises(InvalidResourceEvidence):
            corroborate_guard_receipt([receipt], {})
        with self.assertRaises(InvalidResourceEvidence):
            read_scope_proof(self.file, UNIT)


if __name__ == "__main__":
    unittest.main()
