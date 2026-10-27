"""PE-A4: evidence-driven offline hypotheses; no claims beyond static evidence."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location(
    "pe_auto_behavior", ROOT / "tools/pe_auto_behavior.py")
behavior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(behavior)


def sample(code="int f(void) { return 0; }", *, status="ok", truncated=False,
           address="00401000", name="FUN_00401000"):
    return {
        "schema": "ghidra_deep_preview_v2",
        "provenance": "ghidra_heuristic_not_original_source",
        "functions": [{
            "entry_point": address, "name": name,
            "decompile_status": status, "pseudocode": code,
            "pseudocode_truncated": truncated,
        }],
    }


def pe_imports(*names):
    return {
        "schema": "pe_symbol_inventory_v1",
        "imports": [{
            "dll": "KERNEL32.dll",
            "functions": [{"by": "name", "name": name} for name in names],
        }],
    }


class ConservativeBehaviorTests(unittest.TestCase):
    def test_unknown_is_default_even_with_suggestive_method_name(self):
        result = behavior.classify(sample(name="UninstallEverything"))
        self.assertEqual(result["functions"][0]["status"], "unidentified")
        self.assertEqual(result["functions_unidentified"], 1)
        self.assertEqual(result["engine"], "deterministic_local_rules_not_ai")

    def test_import_table_alone_does_not_infer_local_calls(self):
        result = behavior.classify(sample(), pe_imports(
            "DeleteFileW", "RegDeleteKeyW", "DeleteService"))
        self.assertEqual(result["functions_with_hypotheses"], 0)
        self.assertEqual(result["functions"][0]["hypotheses"], [])

    def test_direct_api_call_supports_only_low_confidence_without_corroboration(self):
        result = behavior.classify(
            sample('void f(void) { DeleteFileW((LPCWSTR)path); }'))
        h = result["functions"][0]["hypotheses"]
        self.assertEqual(len(h), 1)
        self.assertEqual(h[0]["category"], "filesystem_modification")
        self.assertEqual(h[0]["confidence"], "baixa")
        self.assertEqual(h[0]["evidence"][0]["kind"], "pseudocode_api_call")
        self.assertFalse(h[0]["evidence"][0]["import_table_corrob"])
        self.assertEqual(h[0]["inference"], "static_call_pattern_not_runtime_proof")

    def test_confirmed_external_callee_can_support_low_confidence_inference(self):
        data = sample("void f(void) { return; }")
        data["functions"][0]["api_call_references"] = ["GetFileAttributesA"]
        inferred = behavior.classify(data)
        record = inferred["functions"][0]
        self.assertEqual(record["status"], "hypotheses")
        item = record["hypotheses"][0]
        self.assertEqual(item["category"], "filesystem_inspection")
        self.assertEqual(item["confidence"], "baixa")
        self.assertEqual(item["evidence"][0]["kind"], "ghidra_external_callee")

    def test_imports_do_not_become_calls_even_with_fake_name(self):
        data = sample(name="DeleteFileW")
        inferred = behavior.classify(data, pe_imports("DeleteFileW"))
        self.assertEqual(inferred["functions_with_hypotheses"], 0)

    def test_unrecognized_or_duplicate_external_refs_fail_closed(self):
        for names in (["FunctionPretendingToBeDeleteFileW"],
                      ["DeleteFileW", "deletefilew"], ["NoApi()"]):
            with self.subTest(names=names):
                data = sample()
                data["functions"][0]["api_call_references"] = names
                with self.assertRaises(ValueError):
                    behavior.classify(data)

    def test_multiple_apis_and_matching_imports_raise_only_moderate_confidence(self):
        src = ("int worker(void) {\n"
               "  GetFileAttributesW(file);\n"
               "  FindFirstFileW(pattern, &data);\n"
               "  return 1;\n}")
        result = behavior.classify(sample(src), pe_imports(
            "GetFileAttributesW", "FindFirstFileW"))
        h = result["functions"][0]["hypotheses"][0]
        self.assertEqual(h["category"], "filesystem_inspection")
        self.assertEqual(h["confidence"], "moderada")
        self.assertEqual(h["evidence_count"], 2)
        self.assertTrue(all(item["import_table_corrob"] for item in h["evidence"]))

    def test_truncated_c_never_gets_moderate_confidence(self):
        src = "void f(void) { DeleteFileW(file); RemoveDirectoryW(folder); }"
        result = behavior.classify(sample(src, truncated=True), pe_imports(
            "DeleteFileW", "RemoveDirectoryW"))
        self.assertEqual(result["functions"][0]["hypotheses"][0]["confidence"], "baixa")
        self.assertEqual(result["functions"][0]["evidence_quality"], "partial_pseudocode")

    def test_allows_registry_services_process_network_and_msi_only_from_calls(self):
        cases = (
            ("RegOpenKeyExW", "registry_read"),
            ("RegDeleteValueW", "registry_write"),
            ("OpenSCManagerW", "service_management"),
            ("CreateProcessW", "process_management"),
            ("WinHttpSendRequest", "network_request"),
            ("MsiConfigureProductW", "msi_package_management"),
        )
        for api, category in cases:
            with self.subTest(api=api):
                h = behavior.classify(sample("void f(void) { " + api + "(arg); }"))
                self.assertEqual(h["functions"][0]["hypotheses"][0]["category"], category)

    def test_strings_are_context_not_behavioral_proof(self):
        data = sample("int f(void) { return 0; }", name="DeleteAll")
        data["functions"][0]["strings"] = [{
            "text": "delete registry entries",
            "data_address": "00407000",
            "reference_from": "00401004",
        }]
        result = behavior.classify(data)
        record = result["functions"][0]
        self.assertEqual(record["status"], "unidentified")
        self.assertFalse(record["strings_are_behavior_evidence"])
        self.assertEqual(record["string_context"][0]["reference_from"], "00401004")
        self.assertEqual(record["context_provenance"],
                         "ghidra_direct_static_references_only")

    def test_links_only_selected_function_addresses_not_random_callees(self):
        data = sample("int f(void) { return 0; }")
        data["functions"][0]["calls"] = ["00402000", "00403000"]
        data["functions"].append({
            "entry_point": "00402000",
            "name": "known_helper",
            "decompile_status": "unavailable",
            "pseudocode": "",
            "pseudocode_truncated": False,
            "calls": [],
        })
        result = behavior.classify(data)
        self.assertEqual(
            result["functions"][0]["linked_selected_callees"],
            [{"entry_point": "00402000", "name": "known_helper"}],
        )
        self.assertEqual(result["functions_with_hypotheses"], 0)

    def test_computed_call_sites_remain_unresolved_not_behavior(self):
        data = sample("int f(void) { return 1; }")
        data["functions"][0].update({
            "computed_call_sites": ["0040100a"],
            "computed_call_count": 1,
            "computed_calls_truncated": False,
        })
        result = behavior.classify(data)
        function = result["functions"][0]
        self.assertEqual(function["status"], "unidentified")
        self.assertEqual(function["indirect_call_context"]["sites"],
                         ["0040100a"])
        self.assertEqual(function["indirect_call_context"]["targets"],
                         "not_inferred")

    def test_rejects_fabricated_computed_site_locations(self):
        for site in ("EXTERNAL:001", "/tmp/a", "0xBAD") :
            with self.subTest(site=site):
                data = sample()
                data["functions"][0]["computed_call_sites"] = [site]
                data["functions"][0]["computed_call_count"] = 1
                with self.assertRaises(ValueError):
                    behavior.classify(data)

    def test_explicit_computed_target_is_context_not_behavioral_proof(self):
        data = sample("int f(void) { return 1; }")
        data["functions"][0].update({
            "computed_call_sites": ["0040100a", "0040100f"],
            "computed_call_count": 2,
            "computed_calls_truncated": False,
            "explicit_computed_targets": [{
                "site": "0040100a", "entry_point": "00402000",
                "name": "helper",
                "basis": "ghidra_unique_explicit_internal_call_reference",
            }],
        })
        result = behavior.classify(data)
        record = result["functions"][0]
        self.assertEqual(record["status"], "unidentified")
        context = record["indirect_call_context"]
        self.assertEqual(context["targets"], "explicit_references_only")
        self.assertEqual(context["explicit_reference_candidates"][0]["entry_point"],
                         "00402000")
        self.assertEqual(context["unknown_destination_sites"], ["0040100f"])

    def test_rejects_fabricated_computed_target(self):
        data = sample()
        data["functions"][0].update({
            "computed_call_sites": ["0040100a"],
            "computed_call_count": 1,
            "computed_calls_truncated": False,
            "explicit_computed_targets": [{
                "site": "0040100b", "entry_point": "00402000",
                "name": "helper",
                "basis": "ghidra_unique_explicit_internal_call_reference",
            }],
        })
        with self.assertRaises(ValueError):
            behavior.classify(data)

    def test_lexer_removes_literals_comments_and_function_signature(self):
        src = (r'''void DeleteFileW(void) {
            /* DeleteFileW(old); */
            // RegDeleteValueW(name);
            const char *text = "DeleteFileW(file);";
            char x = 'Q';
            return;
        }''')
        data = behavior.classify(sample(src))
        self.assertEqual(data["functions_with_hypotheses"], 0)

    def test_no_classification_when_decompilation_is_unavailable(self):
        for status in ("unavailable", "timed_out"):
            with self.subTest(status=status):
                data = behavior.classify(sample(
                    "void f(void) { RegDeleteKeyW(arg); }", status=status))
                self.assertEqual(data["functions"][0]["status"], "unidentified")

    def test_api_name_occurrence_without_invocation_is_insufficient(self):
        for source in (
            "void f(void) { void *fn = DeleteFileW; }",
            'void f(void) { char *str = "RegSetValueExW("; }',
            "void f(void) { // DeleteService()\n return; }",
        ):
            with self.subTest(source=source):
                self.assertEqual(
                    behavior.classify(sample(source))["functions_with_hypotheses"], 0)

    def test_categories_are_independent_and_truncated_at_three(self):
        source = """void f(void) {
            DeleteFileW(a); RegSetValueExW(b); CreateProcessW(c);
            MsiConfigureProductW(d); WinHttpSendRequest(e);
        }"""
        data = behavior.classify(sample(source))
        record = data["functions"][0]
        self.assertEqual(len(record["hypotheses"]), 3)
        self.assertTrue(record["hypotheses_truncated"])
        self.assertEqual(record["status"], "hypotheses")

    def test_names_and_binaries_never_leave_process_and_output_is_bounded(self):
        src = (ROOT / "tools/pe_auto_behavior.py").read_text("utf-8")
        for disallowed in ("requests.post", "urllib.request", "subprocess.",
                           "os.system(", "openai.", "eval(", "exec("):
            self.assertNotIn(disallowed, src)
        self.assertIn("MAX_FUNCTIONS = 16", src)
        self.assertIn("MAX_SNIPPET_CHARS = 1800", src)
        self.assertIn("MAX_EVIDENCE_PER_CATEGORY = 4", src)

    def test_refuses_missing_provenance_and_out_of_budget(self):
        data = sample()
        data["provenance"] = "trusted_source"
        with self.assertRaises(ValueError):
            behavior.classify(data)
        data = sample("int f(void) {" + "x" * 1801 + "}")
        with self.assertRaises(ValueError):
            behavior.classify(data)
        data = sample()
        data["functions"] *= 17
        with self.assertRaises(ValueError):
            behavior.classify(data)


if __name__ == "__main__":
    unittest.main()
