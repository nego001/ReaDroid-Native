"""M3.4: only bounded, read-only DEX class-name resolution is allowed."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "app/src/main/java/com/readroid/app/DexClassNameProbe.java"
SCANNER = ROOT / "app/src/main/java/com/readroid/app/SecurityScanner.java"
TEST = ROOT / "app/src/androidTest/java/com/readroid/app/DexClassNameProbeInstrumentedTest.java"
WORKFLOW = ROOT / ".github/workflows/engine-m2-admission.yml"


class M34ClassNameContract(unittest.TestCase):
    def test_bounded_streams_unicode_and_descriptor_verification(self):
        code = PROBE.read_text(encoding="utf-8")
        for required in (
            "static final int MAX_NAMES = 6",
            "static final int MAX_UTF16_UNITS = 240",
            "static final long MAX_SINGLE_OFFSET = 16L * 1024 * 1024",
            "static final long MAX_TOTAL_STREAM_BYTES = 64L * 1024 * 1024",
            "DexClassDefProbe.inspect(first, expectedBytes)",
            "DexHeaderProbe.inspect(second, expectedBytes)",
            "descriptorStringIdx >= header.stringIds",
            "dataLocation - header.dataOffset >= header.dataBytes",
            "length > MAX_UTF16_UNITS",
            "takeContinuation(stream, budget)",
            "checkClassDescriptor(descriptor)",
            "Character.isHighSurrogate(ch)",
            "MAX_TOTAL_STREAM_BYTES - used",
            "try (InputStream stream = requireStream(source))",
            "Thread.currentThread().isInterrupted()",
        ):
            self.assertIn(required, code)
        for unsafe in ("readAllBytes(", "DexClassLoader", "Class.forName(",
                       "ZipInputStream", "new byte[(int) expectedBytes]"):
            self.assertNotIn(unsafe, code)

    def test_scanner_only_shows_two_dex_with_six_names_each(self):
        code = SCANNER.read_text(encoding="utf-8")
        for required in (
            "dexNames.length() < 2",
            "DexClassNameProbe.inspect(",
            "zip.getInputStream(e)",
            'namePreview.put("status", "class-names-preview")',
            'namePreview.put("status", "unreadable-class-names")',
            'report.put("dexClassNamePreview", dexNames)',
            'report.put("dexClassNamePreviewTruncated"',
            "catch (java.io.InterruptedIOException cancelled)",
            "throw cancelled;",
        ):
            self.assertIn(required, code)

    def test_android_negative_tests_and_previous_suite_preserved(self):
        tests = TEST.read_text(encoding="utf-8")
        for name in (
            "resolvesClassNamesThroughBothTablesAndKeepsZipUntouched",
            "unicodeMutf8InClassDescriptorsIsAccepted",
            "onlySixNamesAreResolvedAndTruncationIsExplicit",
            "rejectsForgedTypeOrStringIndices",
            "rejectsMalformedMutf8LengthOrClassDescriptor",
            "truncationAndInterruptedStreamsFailClosed",
            "scannerAddsRealNamePreviewWithoutTrustingMalformedDex",
        ):
            self.assertIn(name, tests)
        ci = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("api: [29, 35]", ci)
        self.assertIn("DexClassNameProbeInstrumentedTest", ci)
        self.assertIn("DexClassDefProbeInstrumentedTest", ci)
        self.assertIn("ApkArchiveSafetyInstrumentedTest", ci)


if __name__ == "__main__":
    unittest.main()
