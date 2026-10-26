"""M3.1 safeguards: DEX header reading must remain bounded and read-only."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "app/src/main/java/com/readroid/app/DexHeaderProbe.java"
SCANNER = ROOT / "app/src/main/java/com/readroid/app/SecurityScanner.java"
TEST = ROOT / "app/src/androidTest/java/com/readroid/app/DexHeaderProbeInstrumentedTest.java"
WORKFLOW = ROOT / ".github/workflows/engine-m2-admission.yml"


class DexHeaderReaderContract(unittest.TestCase):
    def test_parser_checks_structure_and_never_reads_body(self):
        code = PROBE.read_text(encoding="utf-8")
        for name in (
            "static final int HEADER_BYTES = 112",
            "new byte[HEADER_BYTES]",
            "read < bytes.length",
            "0x12345678L",
            "if (v < 35 || v > 40)",
            "fileSize != expectedBytes",
            "headerSize != HEADER_BYTES",
            'requireSection("classes"',
            "count > (fileSize - offset) / itemBytes",
            "Thread.currentThread().isInterrupted()",
        ):
            self.assertIn(name, code)
        self.assertNotIn("readAllBytes()", code)
        self.assertNotIn("ZipInputStream", code)
        self.assertNotIn("DexClassLoader", code)
        self.assertNotIn("Class.forName", code)

    def test_scanner_limits_preview_and_preserves_cancellation(self):
        code = SCANNER.read_text(encoding="utf-8")
        self.assertIn("dexHeaders.length() < 12", code)
        self.assertIn("DexHeaderProbe.inspect(input, e.getSize())", code)
        self.assertIn('report.put("dexHeaderPreviewTruncated"', code)
        self.assertIn("catch (java.io.InterruptedIOException cancelled)", code)
        self.assertIn("throw cancelled;", code)
        self.assertIn("unreadable-header", code)

    def test_android_10_and_15_regressions_cover_version_and_mutations(self):
        tests = TEST.read_text(encoding="utf-8")
        for case in (
            "supportedVersionsExposeOnlyBoundedNumericMetadata",
            "bogusFileSizeHeaderSizeAndSectionsFailClosed",
            "scannerReportsValidAndRejectedDexWithoutCrashing",
            "interruptionPreservesThreadFlag",
        ):
            self.assertIn(case, tests)
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("feature/engine-m3-*", workflow)
        self.assertIn("DexHeaderProbeInstrumentedTest", workflow)
        self.assertIn("api: [29, 35]", workflow)


if __name__ == "__main__":
    unittest.main()
