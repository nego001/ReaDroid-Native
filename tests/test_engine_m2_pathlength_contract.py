"""M2.8 contract: realistic lengths, paired instrumentation and safe export."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "app/src/androidTest/java/com/readroid/app/ApkPathLengthProfileInstrumentedTest.java"
EXTRACTOR = ROOT / "tools/extract_m2_pathlength_logcat.py"
WORKFLOW = ROOT / ".github/workflows/engine-m2-admission.yml"


class M28PathLengthContract(unittest.TestCase):
    def test_three_exact_lengths_and_paired_samples(self):
        src = TEST.read_text(encoding="utf-8")
        for expected in (
            "private static final int NAMES = 4096;",
            "private static final int[] PATH_LENGTHS = {32, 128, 768};",
            'trial(false, common, "A1", length)',
            'trial(true, common, "B1", length)',
            'trial(true, common, "B2", length)',
            'trial(false, common, "A2", length)',
            'Log.i(TAG, "RESULT_JSON:" + report.toString())',
            "ApkDiskIndex.validatePath(value);",
            "set.requireUnique(value);",
            "assertEquals(length, value.length());",
        ):
            self.assertIn(expected, src)
        self.assertNotIn("assertTimeout", src)

    def test_extractor_validates_schema_and_all_cohorts(self):
        src = EXTRACTOR.read_text(encoding="utf-8")
        for expected in ("PATH_LENGTHS = (32, 128, 768)",
                         'if set(profiles) != set(PATH_LENGTHS):',
                         'set(sample) != SAMPLE_FIELDS',
                         'if length in profiles:',
                         'm2_path_length_collection_v1'):
            self.assertIn(expected, src)

    def test_emulators_collect_only_synthetic_json_and_keep_regressions(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("api: [29, 35]", src)
        self.assertIn("ApkPathLengthProfileInstrumentedTest", src)
        self.assertIn("extract_m2_pathlength_logcat.py", src)
        self.assertIn("m2-pathlength-api-*.json", src)
        self.assertIn("ApkArchiveSafetyInstrumentedTest", src)
        self.assertIn("ApkPrimitiveFingerprintInstrumentedTest", src)
        self.assertNotIn("app/build/outputs/apk/", src)


if __name__ == "__main__":
    unittest.main()
