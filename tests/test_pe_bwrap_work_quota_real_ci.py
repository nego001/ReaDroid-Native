"""PE-S2.10 CLI transformation contracts, no Bubblewrap process is started."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pe_bwrap_work_quota_real_ci as probe

WORK = Path("/host/untrusted/work")
ORIGINAL = ["bwrap", "--die-with-parent", "--dir", "/work",
            "--bind", str(WORK), "/work",
            "--size", str(256*1024*1024), "--tmpfs", "/tmp",
            "--size", str(16*1024*1024), "--tmpfs", "/home",
            "--chdir", "/work", "--", "/example/ghidra"]


class WorkQuotaProfileContracts(unittest.TestCase):
    def test_ci_only_profile_removes_host_bind(self):
        with mock.patch.object(probe.MODULE.__class__, "is_file", return_value=True):
            result = probe.build_isolated_work_command(
                ORIGINAL, WORK, "bounded")
        self.assertEqual(ORIGINAL[-1], "/example/ghidra")
        self.assertEqual(result[-1], "bounded")
        self.assertNotIn(str(WORK), result)
        self.assertIn("/work/limited", result)
        self.assertIn("--ro-bind", result)
        self.assertIn("0700", result)
        self.assertEqual(result.count("--tmpfs"), 3)
        self.assertEqual(result.count("--"), 1)

    def test_undersized_and_nested_variants_only_inside_ci(self):
        with mock.patch.object(probe.MODULE.__class__, "is_file", return_value=True):
            low = probe.build_isolated_work_command(ORIGINAL, WORK, "undersized")
            nested = probe.build_isolated_work_command(ORIGINAL, WORK, "nested")
        self.assertIn(str(probe.UNDERSIZED_BYTES), low)
        self.assertNotIn(str(probe.BOUNDED_BYTES), low)
        self.assertIn("/work/limited/escape", nested)
        self.assertEqual(nested.count("--tmpfs"), 4)

    def test_changed_production_profile_refused(self):
        bad = ORIGINAL.copy()
        bad[bad.index("--bind")] = "--ro-bind"
        with self.assertRaisesRegex(RuntimeError, "profile changed"):
            probe.build_isolated_work_command(bad, WORK, "bounded")

    def test_duplicate_host_bind_refused(self):
        duplicate = ORIGINAL[:7] + ORIGINAL[2:7] + ORIGINAL[7:]
        with self.assertRaisesRegex(RuntimeError, "profile changed"):
            probe.build_isolated_work_command(duplicate, WORK, "bounded")

    def test_unsupported_modes_refused(self):
        with self.assertRaisesRegex(RuntimeError, "Unsupported"):
            probe.build_isolated_work_command(ORIGINAL, WORK, "unbounded")

    def test_missing_pin_refused(self):
        with mock.patch.object(probe.MODULE.__class__, "is_file", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                probe.build_isolated_work_command(ORIGINAL, WORK, "bounded")


if __name__ == "__main__":
    unittest.main()
