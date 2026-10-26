"""M2.6 quality gates for paired synthetic measurements and ZIP path bounds."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "app/src/androidTest/java/com/readroid/app/ApkPathBenchmarkInstrumentedTest.java"
BUDGET = ROOT / "app/src/androidTest/java/com/readroid/app/ApkPathBudgetInstrumentedTest.java"
EXTRACTOR = ROOT / "tools/extract_m2_fingerprint_logcat.py"
CI = ROOT / ".github/workflows/engine-m2-admission.yml"


class M26FingerprintBenchmarkContract(unittest.TestCase):
    def test_abba_design_collects_cpu_and_memory_without_declared_winners(self):
        code = TEST.read_text(encoding="utf-8")
        for item in (
            'private static final int PATHS = 8192',
            'sample(false, common, "A1")',
            'sample(true, common, "B1")',
            'sample(true, common, "B2")',
            'sample(false, common, "A2")',
            '"processCpuMs"', '"heapDeltaBytes"', '"processPssKib"',
            '"schema", "m2_path_fingerprint_abba_v1"',
            'Log.i(TAG, "RESULT_JSON:" + result.toString())',
        ):
            self.assertIn(item, code)
        self.assertIn("ApkDiskIndex.validatePath(path)", code)
        self.assertNotIn("assertTrue(useFingerprint", code)
        self.assertNotIn("assertTimeout", code)

    def test_path_budget_tests_include_real_zip_and_metadata_upper_limit(self):
        test = BUDGET.read_text(encoding="utf-8")
        self.assertIn("final int names = 16385", test)
        self.assertIn("final int charCount = 1024", test)
        self.assertIn("ApkArchiveSafety.verify(apk)", test)
        self.assertIn('contains("orçamento de memória")', test)
        self.assertIn('repeated(4097)', test)

    def test_emulator_ci_keeps_only_strictly_filtered_json_artifacts(self):
        ci = CI.read_text(encoding="utf-8")
        extractor = EXTRACTOR.read_text(encoding="utf-8")
        self.assertIn("api: [29, 35]", ci)
        self.assertIn("ApkPathBenchmarkInstrumentedTest", ci)
        self.assertIn("ApkPathBudgetInstrumentedTest", ci)
        self.assertIn("extract_m2_fingerprint_logcat.py", ci)
        self.assertIn("m2-fingerprint-api-*.json", ci)
        self.assertNotIn("app/build/outputs/apk/", ci)
        self.assertIn("if len(found) != 1", extractor)
        self.assertIn("set(obj) != FIELDS", extractor)
        self.assertIn("set(value) != SAMPLE_FIELDS", extractor)


if __name__ == "__main__":
    unittest.main()
