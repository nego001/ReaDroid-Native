"""M3.3 contract for read-only, bounded DEX class_def index preview."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "app/src/main/java/com/readroid/app/DexClassDefProbe.java"
SCANNER = ROOT / "app/src/main/java/com/readroid/app/SecurityScanner.java"
TEST = ROOT / "app/src/androidTest/java/com/readroid/app/DexClassDefProbeInstrumentedTest.java"
CI = ROOT / ".github/workflows/engine-m2-admission.yml"


class M33ClassDefContract(unittest.TestCase):
    def test_reader_is_bounded_and_does_not_decode_code_or_names(self):
        code = PROBE.read_text(encoding="utf-8")
        for part in (
            "static final int MAX_PREVIEW_CLASSES = 24",
            "static final long MAX_CLASS_TABLE_OFFSET = 16L * 1024 * 1024",
            "private static final int CLASS_DEF_BYTES = 32",
            "DexHeaderProbe.inspect(input, expectedBytes)",
            "Math.min(h.classDefs, MAX_PREVIEW_CLASSES)",
            "type >= h.typeIds || type <= previousClassType",
            "superType != NO_INDEX && superType >= h.typeIds",
            "sourceFile != NO_INDEX && sourceFile >= h.stringIds",
            'requireDataOffset("interfaces", interfaces, 4, h)',
            'requireDataOffset("class_data", data, 1, h)',
            "Thread.currentThread().isInterrupted()",
            "Collections.unmodifiableList",
        ):
            self.assertIn(part, code)
        for forbidden in ("readAllBytes(", "DexClassLoader",
                          "Class.forName(", "ZipInputStream",
                          "new byte[(int) expectedBytes]"):
            self.assertNotIn(forbidden, code)

    def test_scanner_is_bounded_and_propagates_cancellation(self):
        code = SCANNER.read_text(encoding="utf-8")
        self.assertIn("dexClasses.length() < 4", code)
        self.assertIn("DexClassDefProbe.inspect(classInput, e.getSize())", code)
        self.assertIn('report.put("dexClassPreview", dexClasses)', code)
        self.assertIn('report.put("dexClassPreviewTruncated"', code)
        self.assertIn("unreadable-class-index", code)
        self.assertIn("catch (java.io.InterruptedIOException cancelled)", code)
        self.assertIn("throw cancelled;", code)

    def test_android_tests_remain_in_both_api_matrix(self):
        code = TEST.read_text(encoding="utf-8")
        for name in ("validSortedClassIndicesStayNumericAndReadOnly",
                     "emptyClassTableAndPreviewCapAreExplicit",
                     "rejectedTypeIndicesAndUnsortedOrDuplicateClasses",
                     "rejectedDataOffsetsAndMisalignedInterfaces",
                     "truncatedClassRecordIsRejectedAndReaderStopsAtPreview",
                     "distantClassTableRejectedBeforeStreamingBody",
                     "cancellationPreservesInterruptFlag",
                     "scannerSurvivesMalformedDexAndBoundsClassPreview"):
            self.assertIn(name, code)
        ci = CI.read_text(encoding="utf-8")
        self.assertIn("api: [29, 35]", ci)
        self.assertIn("DexClassDefProbeInstrumentedTest", ci)
        self.assertIn("DexMapProbeInstrumentedTest", ci)
        self.assertIn("ApkArchiveSafetyInstrumentedTest", ci)


if __name__ == "__main__":
    unittest.main()
