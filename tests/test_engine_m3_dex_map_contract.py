"""M3.2 source contracts: bounded streaming DEX map parser, no code execution."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "app/src/main/java/com/readroid/app/DexMapProbe.java"
SCANNER = ROOT / "app/src/main/java/com/readroid/app/SecurityScanner.java"
ANDROID = ROOT / "app/src/androidTest/java/com/readroid/app/DexMapProbeInstrumentedTest.java"
CI = ROOT / ".github/workflows/engine-m2-admission.yml"


class DexMapReaderContract(unittest.TestCase):
    def test_map_parser_streaming_limits_and_consistency_checks(self):
        code = PROBE.read_text(encoding="utf-8")
        for item in (
            "static final int MAX_MAP_ITEMS = 64",
            "static final long MAX_MAP_OFFSET = 16L * 1024 * 1024",
            "DexHeaderProbe.inspect(input, expectedBytes)",
            "skipExactly(input, h.mapOffset - DexHeaderProbe.HEADER_BYTES)",
            "4 + declared * ITEM_BYTES > expectedBytes - h.mapOffset",
            "offset <= previousOffset",
            "!types.add(type)",
            "entry.offset != h.mapOffset",
            "found.count != headerCounts[i]",
            "found.offset != h.sectionOffsets[i]",
            "private static void checkInterrupted()",
        ):
            self.assertIn(item, code)
        self.assertNotIn("readAllBytes", code)
        self.assertNotIn("DexClassLoader", code)
        self.assertNotIn("ZipInputStream", code)
        self.assertNotIn("new byte[(int) expectedBytes]", code)

    def test_preview_is_bounded_and_cancellation_is_propagated(self):
        code = SCANNER.read_text(encoding="utf-8")
        self.assertIn("dexMaps.length() < 4", code)
        self.assertIn("DexMapProbe.inspect(mapInput, e.getSize())", code)
        self.assertIn('report.put("dexMapPreview", dexMaps)', code)
        self.assertIn('report.put("dexMapPreviewTruncated"', code)
        self.assertIn('mapPreview.put("status", "unreadable-map")', code)
        self.assertIn("catch (java.io.InterruptedIOException cancelled)", code)
        self.assertIn("throw cancelled;", code)

    def test_android_matrix_and_negative_cases_remain(self):
        code = ANDROID.read_text(encoding="utf-8")
        for required in (
            "headerAndMapMustAgreeOnTableCountsAndOffsets",
            "rejectDuplicateTypeUnsortedOffsetsOrMissingMap",
            "rejectTruncatedMapAndForgedCountWithoutAllocation",
            "mapBeyondReadBudgetIsRejectedWithoutAllocatingItsBody",
            "interruptedMapReadPropagatesAndPreservesFlag",
            "scannerListsOnlySafeMapMetadataAndSurvivesBadDex",
        ):
            self.assertIn(required, code)
        workflow = CI.read_text(encoding="utf-8")
        self.assertIn("api: [29, 35]", workflow)
        self.assertIn("DexMapProbeInstrumentedTest", workflow)
        self.assertIn("DexHeaderProbeInstrumentedTest", workflow)
        self.assertIn("ApkArchiveSafetyInstrumentedTest", workflow)


if __name__ == "__main__":
    unittest.main()
