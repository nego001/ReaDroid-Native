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
        "schema": "ghidra_deep_preview_v4",
        "selection_method": "bounded_api_references_and_call_connectivity_v2",
        "functions": [{
            "entry_point": "00401000", "name": "add_numbers",
            "calls": ["00402000"], "calls_truncated": False,
            "calls_status": "ok", "direct_callee_count": 1,
            "api_call_references": [],
            "api_call_reference_count": 0,
            "api_call_references_truncated": False,
            "sample_inbound_count": 0, "selection_score": 7,
            "selection_rank": 1,
            "decompile_status": "ok",
            "pseudocode": "int add_numbers(int a, int b) { return a + b; }",
            "pseudocode_truncated": False,
            "strings": [],
            "strings_truncated": False,
            "string_scan_truncated": False,
            "instructions_scanned_for_strings": 0,
            "computed_call_sites": [],
            "computed_call_count": 0,
            "computed_calls_truncated": False,
            "computed_call_destinations": "not_inferred",
        }],
        "candidates_scanned": 1, "eligible_non_thunks": 1,
        "sample_truncated": False, "scan_truncated": False,
        "graph_scope": "scanned_functions_only",
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
        data["functions"][1]["selection_rank"] = 2
        data["sample_truncated"] = False
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

    def test_rejects_forged_ranking_and_call_counters(self):
        for field, replacement in (
            ("selection_score", 100),
            ("selection_rank", 0),
            ("sample_inbound_count", 385),
            ("direct_callee_count", 25),
            ("calls_status", "guessed"),
        ):
            with self.subTest(field=field):
                item = sample()
                item["functions"][0][field] = replacement
                self.rejected(item)

    def test_rejects_wrong_graph_scope_and_selection_method(self):
        for key, replacement in (
            ("graph_scope", "complete"),
            ("selection_method", "ai_classified"),
            ("scan_truncated", True),
        ):
            with self.subTest(key=key):
                item = sample()
                item[key] = replacement
                self.rejected(item)

    def test_rejects_unsorted_ranks_or_duplicate_calls(self):
        item = sample()
        another = dict(item["functions"][0])
        another["entry_point"] = "00401001"
        another["selection_rank"] = 2
        another["selection_score"] = 8  # should precede the lower score
        item["functions"].append(another)
        item["candidates_scanned"] = 2
        item["eligible_non_thunks"] = 2
        self.rejected(item)

    def test_external_api_references_are_strictly_validated(self):
        item = sample()
        record = item["functions"][0]
        record["api_call_references"] = ["GetFileAttributesA"]
        record["api_call_reference_count"] = 1
        record["selection_score"] = 135
        self.assertEqual(self.load(item)["functions"][0]["api_call_references"],
                         ["GetFileAttributesA"])
        for corrupt in ("UninstallAll", "DeleteFileW; rm -rf", "NotAnApi"):
            with self.subTest(corrupt=corrupt):
                bad = sample()
                bad["functions"][0]["api_call_references"] = [corrupt]
                bad["functions"][0]["api_call_reference_count"] = 1
                bad["functions"][0]["selection_score"] = 135
                self.rejected(bad)
        bad = sample()
        bad["functions"][0]["api_call_references"] = ["GetFileAttributesA"]
        bad["functions"][0]["api_call_reference_count"] = 1
        self.rejected(bad)  # missing priority bonus must not pass

    def test_accepts_attributed_bounded_string_evidence(self):
        value = sample()
        func = value["functions"][0]
        func["strings"] = [{
            "text": "negresco_evidence_2026.txt",
            "data_address": "00408000",
            "reference_from": "00401006",
        }]
        func["instructions_scanned_for_strings"] = 12
        report = self.load(value)
        self.assertEqual(report["functions"][0]["strings"][0]["data_address"], "00408000")

    def test_rejects_forged_string_references_and_truncation(self):
        def valid():
            v = sample()
            v["functions"][0]["strings"] = [{
                "text": "sample-string",
                "data_address": "00408000",
                "reference_from": "00401006",
            }]
            v["functions"][0]["instructions_scanned_for_strings"] = 8
            return v
        for bad_key, replacement in (
            ("data_address", "/etc/passwd"),
            ("reference_from", "EXTERNAL:001"),
            ("text", "hi"),
            ("text", "x" * 97),
            ("text", "line" + chr(10) + "attack"),
        ):
            with self.subTest(key=bad_key):
                v = valid()
                v["functions"][0]["strings"][0][bad_key] = replacement
                self.rejected(v)
        v = valid()
        v["functions"][0]["strings_truncated"] = True
        self.rejected(v)
        v = valid()
        v["functions"][0]["strings"].append(v["functions"][0]["strings"][0].copy())
        self.rejected(v)
        v = valid()
        v["functions"][0]["instructions_scanned_for_strings"] = 0
        self.rejected(v)

    def test_annotates_indirect_call_sites_without_target_guesses(self):
        item = sample()
        record = item["functions"][0]
        record["computed_call_sites"] = ["0040100a"]
        record["computed_call_count"] = 1
        record["instructions_scanned_for_strings"] = 10
        result = self.load(item)["functions"][0]
        self.assertEqual(result["computed_call_sites"], ["0040100a"])
        self.assertEqual(result["computed_call_destinations"], "not_inferred")

    def test_rejects_fabricated_indirect_call_sites(self):
        def good():
            item = sample()
            record = item["functions"][0]
            record["computed_call_sites"] = ["0040100a"]
            record["computed_call_count"] = 1
            record["instructions_scanned_for_strings"] = 10
            return item
        for key, replacement in (
            ("computed_call_sites", ["EXTERNAL:0"]),
            ("computed_call_count", 0),
            ("computed_call_count", 100),
            ("computed_calls_truncated", True),
            ("computed_call_destinations", "add_numbers"),
        ):
            with self.subTest(key=key):
                sample_bad = good()
                sample_bad["functions"][0][key] = replacement
                self.rejected(sample_bad)

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
            "MAX_SCANNED = 512", "MAX_DECOMPILED = 16",
            "MAX_CALLEES = 24", "MAX_PSEUDOCODE_CHARS = 1800",
            "DECOMPILE_SECONDS = 10", "analysisTimeoutOccurred()",
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
