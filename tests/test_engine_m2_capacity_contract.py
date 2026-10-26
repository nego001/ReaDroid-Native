"""M2.4 guards: SQLite index creation must occur after bulk inserts, with metrics only."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app/src/main/java/com/readroid/app/ApkDiskIndex.java"
CI = ROOT / ".github/workflows/engine-m2-admission.yml"
PROFILE = ROOT / "app/src/androidTest/java/com/readroid/app/ApkCapacityProfileInstrumentedTest.java"
EXTRACTOR = ROOT / "tools/extract_m2_capacity_logcat.py"


class EngineM24CapacityContract(unittest.TestCase):
    def test_secondary_index_is_built_only_after_bulk_insert(self):
        src = INDEX.read_text(encoding="utf-8")
        method = src.split("public static Stats build(", 1)[1].split(
            "public static Page page(", 1)[0]
        self.assertEqual(method.count('db.execSQL("CREATE INDEX browse_parent'), 1)
        self.assertLess(method.index("putExplicit(db, path, dir"),
                        method.index('db.execSQL("CREATE INDEX browse_parent'))
        self.assertLess(method.index('db.execSQL("CREATE INDEX browse_parent'),
                        method.index("db.close();"))
        self.assertIn("if (!finished) SQLiteDatabase.deleteDatabase(indexFile);", method)
        self.assertIn("Thread.currentThread().isInterrupted()", method)

    def test_metrics_only_artifacts_and_no_time_based_acceptance(self):
        ci = CI.read_text(encoding="utf-8")
        source = PROFILE.read_text(encoding="utf-8")
        self.assertIn("ApkCapacityProfileInstrumentedTest", ci)
        self.assertIn("m2-capacity-api-*.json", ci)
        self.assertIn("adb logcat -d -s M2Capacity:I '*:S'", ci)
        self.assertIn("tools/extract_m2_capacity_logcat.py", ci)
        self.assertNotIn("run-as com.readroid.app", ci)
        self.assertIn('Log.i(TAG, "RESULT_JSON:" + metrics.toString());', source)
        self.assertIn('if len(matches) != 1:', EXTRACTOR.read_text(encoding="utf-8"))
        self.assertNotIn("app/build/outputs/apk/", ci)
        for field in ("processCpuMs", "wallMs", "javaHeapUsedBytes",
                      "nativeHeapAllocatedBytes", "processPssKib"):
            self.assertIn(field, source)
        self.assertIn("ApkDiskIndex.page(", source)
        self.assertIn("ApkIntegrity.sha256(apk)", source)
        self.assertIn('new File(cache, "m2_capacity_metrics.json")', source)
        self.assertNotIn("assertTimeout", source)


if __name__ == "__main__":
    unittest.main()
