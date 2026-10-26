"""PE-A2 tests fake the Ghidra executable. No Ghidra install or Windows
binary is executed in CI. The fixture file is a nonexecuting synthetic PE.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import os
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from test_pe_auto_inventory import make_pe
spec = importlib.util.spec_from_file_location(
    "pe_auto_ghidra", ROOT / "tools/pe_auto_ghidra.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class HeadlessRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.input = self.workspace / "potentially_untrusted.exe"
        self.input.write_bytes(make_pe())
        self.output = self.workspace / "report.json"
        self.home = self.workspace / "ghidra"
        (self.home / "support").mkdir(parents=True)
        self.launcher = self.home / "support" / "analyzeHeadless"
        self._fake("success")

    def tearDown(self):
        self.temp.cleanup()

    def run_synthetic(self, *args, **kwargs):
        return runner.inspect_functions(
            *args, sandbox_mode="trusted-fixture", **kwargs)

    def _fake(self, mode):
        # Arguments are parsed exactly like Ghidra -import/-postScript.
        # The mock never executes or loads the synthetic PE.
        source = r"""#!/usr/bin/env python3
import json
import pathlib
import sys
import time

args = sys.argv[1:]
if "-import" not in args or "-postScript" not in args:
    sys.exit(12)
binary = pathlib.Path(args[args.index("-import") + 1])
if binary.name != "input.exe" or binary.read_bytes()[:2] != b"MZ":
    sys.exit(13)
if "-readOnly" not in args or "-deleteProject" not in args:
    sys.exit(14)
if "-analysisTimeoutPerFile" not in args or "-max-cpu" not in args:
    sys.exit(15)
if "-scriptPath" not in args or "NegrescoFunctionInventory.java" not in args:
    sys.exit(16)
output = pathlib.Path(args[args.index("-postScript") + 2])
MODE = @MODE@
if MODE == "exit":
    sys.exit(4)
if MODE == "sleep":
    time.sleep(5)
if MODE == "missing":
    sys.exit(0)
if MODE == "badjson":
    output.write_text("not JSON", encoding="utf-8")
    sys.exit(0)
data = {
  "schema": "ghidra_function_preview_v1",
  "total_discovered": 2,
  "preview_truncated": False,
  "name_provenance": "original_or_generated_not_verified",
  "functions": [
    {"entry_point": "00401000", "name": "FUN_00401000", "is_thunk": False},
    {"entry_point": "00402000", "name": "UninstallRoutine", "is_thunk": True}
  ]
}
if MODE == "duplicate":
    data["functions"][1]["entry_point"] = "00401000"
if MODE == "wrongcount":
    data["total_discovered"] = 1
if MODE == "incomplete":
    data["preview_truncated"] = True
if MODE == "schema":
    data["schema"] = "wrong_schema"
output.write_text(json.dumps(data), encoding="utf-8")
if args.count("-postScript") == 2:
    deep_index = [i for i, value in enumerate(args) if value == "-postScript"][1]
    if args[deep_index + 1] != "NegrescoDeepPreview.java":
        sys.exit(18)
    deep_path = pathlib.Path(args[deep_index + 2])
    deep = {
        "schema": "ghidra_deep_preview_v1",
        "functions": [{
            "entry_point": "00401000",
            "name": "add_numbers",
            "calls": ["00402000"],
            "calls_truncated": False,
            "decompile_status": "ok",
            "pseudocode": "int add_numbers(int a, int b) {return a+b;}",
            "pseudocode_truncated": False,
        }],
        "candidates_scanned": 1, "eligible_non_thunks": 1,
        "sample_truncated": False,
        "provenance": "ghidra_heuristic_not_original_source",
    }
    deep_path.write_text(json.dumps(deep), encoding="utf-8")
"""
        self.launcher.write_text(source.replace("@MODE@", repr(mode)), encoding="utf-8")
        self.launcher.chmod(self.launcher.stat().st_mode | stat.S_IXUSR)

    def test_full_offline_handoff_returns_bounded_function_evidence(self):
        report = self.run_synthetic(self.input, self.home, self.output, 3)
        self.assertEqual(report["schema"], "pe_ghidra_headless_v1")
        self.assertEqual(report["format"], "PE32")
        self.assertEqual(report["architecture"], "x86")
        self.assertEqual(report["evidence"]["total_discovered"], 2)
        self.assertEqual(report["evidence"]["functions"][0]["name"], "FUN_00401000")
        self.assertEqual(report["evidence"]["functions"][1]["name"], "UninstallRoutine")
        self.assertFalse(report["limitations"]["executable_launched"])
        self.assertEqual(report["limitations"]["pseudocode"], "not_implemented")
        self.assertEqual(json.loads(self.output.read_text()), report)
        self.assertEqual(len(report["source_sha256"]), 64)
        self.assertEqual(list(self.workspace.glob("negresco-pe-a2-*")), [])

    def test_deep_preview_end_to_end_with_trusted_synthetic_mock(self):
        report = self.run_synthetic(self.input, self.home, self.output,
                                    3, deep_preview=True)
        self.assertEqual(report["limitations"]["pseudocode"],
                         "bounded_heuristic_preview")
        self.assertEqual(report["limitations"]["call_graph"],
                         "bounded_direct_references")
        self.assertEqual(report["deep_preview"]["functions"][0]["name"],
                         "add_numbers")
        self.assertEqual(report["deep_preview"]["functions"][0]["calls"],
                         ["00402000"])
        self.assertTrue(self.output.is_file())

    def test_never_overwrites_existing_report(self):
        self.output.write_text("existing-user-data", encoding="utf-8")
        with self.assertRaisesRegex(runner.HeadlessError, "Destino já existe"):
            self.run_synthetic(self.input, self.home, self.output, 2)
        self.assertEqual(self.output.read_text(), "existing-user-data")

    def test_rejects_input_symlink_before_analyzing(self):
        link = self.workspace / "symlink.exe"
        link.symlink_to(self.input)
        with self.assertRaisesRegex(runner.HeadlessError, "link simbólico"):
            self.run_synthetic(link, self.home, self.output, 2)
        self.assertFalse(self.output.exists())

    def test_rejects_missing_or_untrusted_launcher(self):
        self.launcher.unlink()
        with self.assertRaisesRegex(runner.HeadlessError, "Ghidra Headless"):
            self.run_synthetic(self.input, self.home, self.output, 2)
        self.launcher.symlink_to(self.input)
        with self.assertRaisesRegex(runner.HeadlessError, "Ghidra Headless"):
            self.run_synthetic(self.input, self.home, self.output, 2)

    def test_refuses_invalid_pe_before_mock_ghidra_exec(self):
        self.input.write_bytes(b"THIS IS NOT A PE HEADER"*15)
        with self.assertRaises(Exception):
            self.run_synthetic(self.input, self.home, self.output, 2)
        self.assertFalse(self.output.exists())

    def test_fails_closed_on_invalid_or_missing_evidence(self):
        for mode in ("badjson", "missing", "duplicate", "wrongcount",
                     "incomplete", "schema"):
            with self.subTest(mode=mode):
                self._fake(mode)
                with self.assertRaises(runner.HeadlessError):
                    self.run_synthetic(self.input, self.home, self.output, 2)
                self.assertFalse(self.output.exists())

    def test_nonzero_ghidra_status_is_not_a_success(self):
        self._fake("exit")
        with self.assertRaisesRegex(runner.HeadlessError, "não concluiu"):
            self.run_synthetic(self.input, self.home, self.output, 2)
        self.assertFalse(self.output.exists())

    def test_timeout_kills_ghidra_process_group_and_does_not_write_report(self):
        self._fake("sleep")
        with self.assertRaisesRegex(runner.HeadlessError, "excedeu o tempo"):
            self.run_synthetic(self.input, self.home, self.output, 1)
        self.assertFalse(self.output.exists())

    def test_timeout_range_and_output_parent(self):
        for seconds in (0, 1801, -1, "1"):
            with self.subTest(seconds=seconds):
                with self.assertRaises(runner.HeadlessError):
                    self.run_synthetic(self.input, self.home, self.output, seconds)
        with self.assertRaisesRegex(runner.HeadlessError, "Diretório de saída"):
            self.run_synthetic(self.input, self.home,
                                     self.workspace / "missing" / "result.json", 2)

    def test_default_runner_requires_isolation_for_unknown_files(self):
        from unittest import mock
        with mock.patch("pe_ghidra_sandbox.shutil.which", return_value=None):
            with self.assertRaisesRegex(runner.HeadlessError, "Isolamento Bubblewrap"):
                runner.inspect_functions(self.input, self.home, self.output, 2)
        self.assertFalse(self.output.exists())

    def test_postscript_is_pinned_and_no_shell_invocation(self):
        source = (ROOT / "tools/pe_auto_ghidra.py").read_text("utf-8")
        self.assertIn('"-postScript", SCRIPT_NAME, str(raw_result)', source)
        self.assertIn("start_new_session=True", source)
        self.assertIn("os.killpg(process.pid, signal.SIGKILL)", source)
        self.assertIn("subprocess.DEVNULL", source)
        self.assertIn('"os_sandbox": ("bubblewrap_profile"', source)
        self.assertIn('else "not_implemented"', source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("subprocess.run(", source)
        self.assertNotIn("os.system(", source)
        java = (ROOT / "tools/ghidra_scripts/NegrescoFunctionInventory.java").read_text("utf-8")
        self.assertIn("MAX_FUNCTIONS = 256", java)
        self.assertIn("getFunctionManager().getFunctions(true)", java)
        self.assertIn("extends HeadlessScript", java)
        self.assertIn("analysisTimeoutOccurred()", java)
        self.assertNotIn("getDecompiler", java)
        self.assertNotIn("getPcode", java)


if __name__ == "__main__":
    unittest.main()
