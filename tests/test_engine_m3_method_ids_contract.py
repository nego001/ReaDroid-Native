"""M3.5 contract: method_id preview cannot become an unbounded DEX decoder."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "app/src/main/java/com/readroid/app/DexMethodProbe.java"
SCANNER = ROOT / "app/src/main/java/com/readroid/app/SecurityScanner.java"
ANDROID = ROOT / "app/src/androidTest/java/com/readroid/app/DexMethodProbeInstrumentedTest.java"
WORKFLOW = ROOT / ".github/workflows/engine-m2-admission.yml"


class M35MethodIdsContract(unittest.TestCase):
    def test_dex_method_ids_are_ordered_and_bounded(self):
        src = PROBE.read_text(encoding="utf-8")
        for required in (
            "static final int MAX_METHODS = 8",
            "static final int MAX_NAME_UTF16 = 128",
            "static final long MAX_OFFSET = 16L * 1024 * 1024",
            "static final long TOTAL_READ_BUDGET = 32L * 1024 * 1024",
            "DexHeaderProbe.inspect(stream, fileBytes)",
            "header.sectionOffsets[4]",
            "header.methodIds",
            "classIdx >= header.typeIds",
            "protoIdx >= header.protoIds",
            "nameIdx >= header.stringIds",
            "classIdx == prevClass && nameIdx == prevName",
            "protoIdx <= prevProto",
            "header.sectionOffsets[0] + row[2] * 4",
            "stringDataAt < header.dataOffset",
            "validateMemberName(name)",
            "Character.isJavaIdentifierPart",
            "MAX_TOTAL_STREAM_BYTES" if False else "TOTAL_READ_BUDGET - consumed",
            "Thread.currentThread().isInterrupted()",
            "Collections.unmodifiableList",
        ):
            self.assertIn(required, src)
        for unsafe in ("readAllBytes(", "DexClassLoader", "Class.forName(",
                       "ZipInputStream", "new byte[(int) fileBytes]"):
            self.assertNotIn(unsafe, src)

    def test_scanner_has_bounded_preview_and_cancellation(self):
        scanner = SCANNER.read_text(encoding="utf-8")
        for part in (
            "dexMethods.length() < 2",
            "DexMethodProbe.inspect(",
            "zip.getInputStream(e)",
            'methodPreview.put("status", "method-ids-preview")',
            'methodPreview.put("status", "unreadable-method-ids")',
            'report.put("dexMethodPreview", dexMethods)',
            'report.put("dexMethodPreviewTruncated"',
            "catch (java.io.InterruptedIOException cancelled)",
            "throw cancelled;",
            "method_ids podem referenciar métodos externos",
        ):
            self.assertIn(part, scanner)

    def test_android_negative_cases_and_prior_probes_stay_active(self):
        tests = ANDROID.read_text(encoding="utf-8")
        for method in (
            "readsSortedMethodsAndActualNamesWithoutModification",
            "returnsAtMostEightMethodIdsAndMarksTruncation",
            "rejectsIndexesOutsideStringTypeAndProtoTables",
            "rejectsUnsortedOrDuplicateMethodIdEntries",
            "rejectsMalformedNamesAndEarlyTerminator",
            "blocksDistantMethodTableBeforeDecompression",
            "truncatedAndCancelledSourcesFailClosed",
            "scannerReportsNamesButDoesNotClaimMethodsAreImplemented",
        ):
            self.assertIn(method, tests)
        ci = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("api: [29, 35]", ci)
        self.assertIn("DexMethodProbeInstrumentedTest", ci)
        self.assertIn("DexClassNameProbeInstrumentedTest", ci)
        self.assertIn("ApkArchiveSafetyInstrumentedTest", ci)
        self.assertNotIn("app/build/outputs/apk/", ci)


if __name__ == "__main__":
    unittest.main()
