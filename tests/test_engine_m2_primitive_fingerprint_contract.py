"""M2.7 guard: primitive table enforces 128-bit equality and bounded growth."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "app/src/main/java/com/readroid/app/ApkPathFingerprintSet.java"
ANDROID = ROOT / "app/src/androidTest/java/com/readroid/app/ApkPrimitiveFingerprintInstrumentedTest.java"
WORKFLOW = ROOT / ".github/workflows/engine-m2-admission.yml"


class M27PrimitiveFingerprintContract(unittest.TestCase):
    def test_primitive_storage_and_sha256_are_required(self):
        source = TABLE.read_text(encoding="utf-8")
        for requirement in (
            "private long[] high",
            "private long[] low",
            "private byte[] occupied",
            "private static final int MAX_ENTRIES = 150000;",
            'MessageDigest.getInstance("SHA-256")',
            "sha256.digest(digestBuffer, 0, DIGEST_BYTES)",
            "if (high[index] == first && low[index] == second)",
            "if (count >= MAX_ENTRIES)",
            "if ((count + 1L) * 10 > occupied.length * 7L)",
            "private void grow() throws IOException",
        ):
            self.assertIn(requirement, source)
        for forbidden in ("HashSet", "Set<Fingerprint>", "HashMap",
                          "new Fingerprint(", "Set<String>"):
            self.assertNotIn(forbidden, source)

    def test_growth_rehashes_both_words_with_explicit_occupancy(self):
        source = TABLE.read_text(encoding="utf-8")
        method = source.split("private void grow() throws IOException", 1)[1]
        self.assertIn("long[] oldHigh = high;", method)
        self.assertIn("long[] oldLow = low;", method)
        self.assertIn("byte[] oldOccupied = occupied;", method)
        self.assertIn("if (oldOccupied[i] == 0) continue;", method)
        self.assertIn("occupied[index] = 1;", method)
        self.assertIn("high[index] = oldHigh[i];", method)
        self.assertIn("low[index] = oldLow[i];", method)
        self.assertNotIn("count++", method)
        self.assertIn("(index + 1) & (enlarged - 1)", method)

    def test_android_matrix_exercises_capacity_ceiling_and_original_integrity(self):
        code = ANDROID.read_text(encoding="utf-8")
        self.assertIn("for (int i = 0; i < 150000; i++)", code)
        self.assertIn("paths.capacity()", code)
        self.assertIn("item_19999.json", code)
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("api: [29, 35]", workflow)
        self.assertIn("ApkPrimitiveFingerprintInstrumentedTest", workflow)
        self.assertIn("ApkArchiveSafetyInstrumentedTest", workflow)
        self.assertIn("ApkPathBenchmarkInstrumentedTest", workflow)


if __name__ == "__main__":
    unittest.main()
