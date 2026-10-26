"""PE-A3 structural contract: malformed, oversized and invented decompiler data."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location(
    "pe_auto_ghidra", ROOT / "tools/pe_auto_ghidra.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def sample():
    return {
        "schema": "ghidra_deep_preview_v1",
        "functions": [{
            "entry_point": "00401000", "name": "add_numbers",
            "calls": ["00402000"], "calls_truncated": False,
            "decompile_status": "ok",
            "pseudocode": "int add_numbers(int a, int b) { return a + b; }",
            "pseudocode_truncated": False,
        }],
        "candidates_scanned": 1, "eligible_non_thunks": 1,
        "sample_truncated": False,
        "provenance": "ghidra_heuristic_not_original_source",
    }


class DeepPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "deep.json"

    def tearDown(self):
        self.temp.cleanup()

    def load(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")
        return runner._validated_deep_evidence(self.path)

    def rejected(self, data):
        with self.assertRaises(runner.HeadlessError):
            self.load(data)

    def test_retains_pseudocode_and_direct_callee_evidence(self):
        data = self.load(sample())
        self.assertEqual(data["functions"][0]["name"], "add_numbers")
        self.assertIn("return a + b", data["functions"][0]["pseudocode"])
        self.assertEqual(data["functions"][0]["calls"], ["00402000"])
        self.assertEqual(data["provenance"],
                         "ghidra_heuristic_not_original_source")

    def test_rejects_fake_provenance_or_schema(self):
        data = sample()
        data["schema"] = "invented_source_code"
        self.rejected(data)
        data = sample()
        data["provenance"] = "original_verified"
        self.rejected(data)

    def test_rejects_out_of_budget_samples_and_calls(self):
        data = sample()
        data["functions"] *= 9
        self.rejected(data)
        data = sample()
        data["functions"][0]["calls"] = [f"{i:08x}" for i in range(13)]
        self.rejected(data)
        data = sample()
        data["functions"][0]["pseudocode"] = "x" * 1801
        self.rejected(data)

    def test_rejects_duplicated_or_forged_function_addresses(self):
        data = sample()
        data["functions"][0]["entry_point"] = "/etc/passwd"
        self.rejected(data)
        data = sample()
        data["functions"][0]["calls"] = ["00402000", "00402000"]
        self.rejected(data)
        data = sample()
        first = dict(data["functions"][0])
        data["functions"].append(first)
        data["eligible_non_thunks"] = 2
        self.rejected(data)

    def test_rejects_status_that_claims_c_when_unavailable(self):
        data = sample()
        data["functions"][0]["decompile_status"] = "unavailable"
        self.rejected(data)
        data = sample()
        data["functions"][0]["decompile_status"] = "timed_out"
        self.rejected(data)
        data = sample()
        data["functions"][0]["pseudocode"] = ""
        self.rejected(data)

    def test_accepts_explicit_failure_without_inventing_code(self):
        data = sample()
        data["functions"][0].update({
            "decompile_status": "unavailable",
            "pseudocode": "",
            "pseudocode_truncated": False,
        })
        self.assertEqual(self.load(data)["functions"][0]["pseudocode"], "")

    def test_rejects_wrong_counts_and_missing_truncation(self):
        data = sample()
        data["eligible_non_thunks"] = 0
        self.rejected(data)
        data = sample()
        data["eligible_non_thunks"] = 9
        self.rejected(data)
        data = sample()
        data["sample_truncated"] = True
        self.rejected(data)

    def test_rejects_missing_or_oversized_evidence(self):
        with self.assertRaises(runner.HeadlessError):
            runner._validated_deep_evidence(self.path)
        self.path.write_text("x" * (runner.MAX_DEEP_BYTES + 1))
        with self.assertRaises(runner.HeadlessError):
            runner._validated_deep_evidence(self.path)

    def test_exporter_source_limits_and_no_behavior_claim(self):
        script = (ROOT / "tools/ghidra_scripts/NegrescoDeepPreview.java").read_text()
        source = (ROOT / "tools/pe_auto_ghidra.py").read_text()
        for expected in (
            "MAX_SCANNED = 256", "MAX_DECOMPILED = 8",
            "MAX_CALLEES = 12", "MAX_PSEUDOCODE_CHARS = 1800",
            "DECOMPILE_SECONDS = 12", "analysisTimeoutOccurred()",
            "getCalledFunctions(monitor)", "decompileFunction(",
            "decompiler.dispose()",
        ):
            self.assertIn(expected, script)
        self.assertIn('"provenance": "ghidra_heuristic_not_original_source"',
                      source)
        self.assertIn("deep_preview=args.deep_preview", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system(", source)


if __name__ == "__main__":
    unittest.main()
