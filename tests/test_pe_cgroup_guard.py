"""Synthetic cgroup v2 filesystem tests: never create or join real cgroups."""
from pathlib import Path
import sys
import tempfile
import json
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from pe_cgroup_guard import verify_cgroup_limits, CgroupVerificationError
import pe_cgroup_guard as guard


class CgroupVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "cgroup"
        self.group = self.root / "user.slice" / "run-negresco.scope"
        self.group.mkdir(parents=True)
        self.proc = Path(self.temp.name) / "proc-cgroup"
        self.proc.write_text("0::/user.slice/run-negresco.scope\n", encoding="utf-8")
        (self.group / "memory.max").write_text("4294967296\n")
        (self.group / "pids.max").write_text("128\n")
        (self.group / "cpu.max").write_text("200000 100000\n")

    def tearDown(self):
        self.temp.cleanup()

    def verify(self):
        return verify_cgroup_limits(
            4 * 1024 ** 3, 128, 200,
            expected_scope="run-negresco.scope",
            proc_cgroup=self.proc, mount_root=self.root)

    def test_accepts_actual_finite_scope_budgets(self):
        proof = self.verify()
        self.assertTrue(proof["verified"])
        self.assertEqual(proof["memory_max"], 4 * 1024 ** 3)
        self.assertEqual(proof["pids_max"], 128)

    def test_rejects_unbounded_or_excessive_resources(self):
        cases = [
            ("memory.max", "max\n"),
            ("memory.max", "8589934592\n"),
            ("pids.max", "max\n"),
            ("pids.max", "256\n"),
            ("cpu.max", "max 100000\n"),
            ("cpu.max", "300000 100000\n"),
            ("cpu.max", "1 0\n"),
        ]
        for filename, value in cases:
            with self.subTest(filename=filename, value=value):
                file = self.group / filename
                original = file.read_text()
                file.write_text(value)
                with self.assertRaises(CgroupVerificationError):
                    self.verify()
                file.write_text(original)

    def test_rejects_wrong_scope_identity(self):
        with self.assertRaisesRegex(CgroupVerificationError, "assigned scope"):
            verify_cgroup_limits(4 * 1024 ** 3, 128, 200,
                                 expected_scope="unrelated.scope",
                                 proc_cgroup=self.proc, mount_root=self.root)

    def test_rejects_missing_scope_or_non_v2_membership(self):
        for line in ("0::/user.slice/unrestricted.service\n",
                     "1:cpu:/user.slice/run-negresco.scope\n",
                     "0::/\n"):
            with self.subTest(line=line):
                self.proc.write_text(line)
                with self.assertRaises(CgroupVerificationError):
                    self.verify()

    def test_guard_writes_private_exclusive_proof_before_exec(self):
        proof = Path(self.temp.name) / "proof.json"
        argv = ["guard.py", "4294967296", "128", "200",
                "run-negresco.scope", str(proof), "--", "/usr/bin/true"]
        evidence = {"verified": True, "memory_max": 4294967296,
                    "pids_max": 128, "cpu_quota": 200000,
                    "cpu_period": 100000}
        with mock.patch.object(guard, "verify_cgroup_limits", return_value=evidence):
            with mock.patch.object(guard.os, "execvpe",
                                   side_effect=OSError("mock never executes")) as execute:
                self.assertEqual(guard.main(argv), 2)
        execute.assert_called_once()
        data = json.loads(proof.read_text())
        self.assertEqual(data["scope"], "run-negresco.scope")
        self.assertEqual(data["schema"], "negresco_cgroup_v2_proof_v1")
        self.assertEqual(proof.stat().st_mode & 0o077, 0)
        proof.write_text("existing", encoding="utf-8")
        with mock.patch.object(guard, "verify_cgroup_limits", return_value=evidence):
            with mock.patch.object(guard.os, "execvpe") as execute:
                self.assertEqual(guard.main(argv), 2)
                execute.assert_not_called()
        self.assertEqual(proof.read_text(), "existing")

    def test_rejects_unreadable_control_file_and_invalid_budget(self):
        (self.group / "memory.max").unlink()
        with self.assertRaises(CgroupVerificationError):
            self.verify()
        with self.assertRaises(CgroupVerificationError):
            verify_cgroup_limits(0, 128, 200,
                                 proc_cgroup=self.proc, mount_root=self.root)


if __name__ == "__main__":
    unittest.main()
