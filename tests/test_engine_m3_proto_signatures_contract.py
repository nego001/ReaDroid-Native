"""M3.6 contract: bounded proto_id, parameter list, type strings and shorty."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "app/src/main/java/com/readroid/app/DexPrototypeProbe.java"
SCANNER = ROOT / "app/src/main/java/com/readroid/app/SecurityScanner.java"
ANDROID = ROOT / "app/src/androidTest/java/com/readroid/app/DexPrototypeProbeInstrumentedTest.java"
WORKFLOW = ROOT / ".github/workflows/engine-m2-admission.yml"


class M36PrototypeContract(unittest.TestCase):
    def test_reader_remains_bounded_and_cross_validates_shorty(self):
        code = PROBE.read_text(encoding="utf-8")
        for required in (
            "static final int MAX_METHODS = 4",
            "static final int MAX_PARAMETERS = 8",
            "static final int MAX_UTF16 = 240",
            "static final long MAX_OFFSET = 16L * 1024 * 1024",
            "static final long MAX_STREAMED_BYTES = 64L * 1024 * 1024",
            "DexMethodProbe.inspect(source::open, fileSize)",
            "DexHeaderProbe.inspect(in, fileSize)",
            "h.sectionOffsets[2] + (long) method.prototypeIdx * 12",
            "returnIdx >= h.typeIds",
            "shortyIdx >= h.stringIds",
            "count == 0 || count > MAX_PARAMETERS",
            "typeIdx >= h.typeIds",
            "validateTypeDescriptor(value, allowVoid)",
            "shorty.length() != parameters.size() + 1",
            "shorty.charAt(j + 1) != shortyChar(parameters.get(j))",
            "MAX_STREAMED_BYTES - used",
            "checkInterrupted();",
            "Collections.unmodifiableList",
        ):
            self.assertIn(required, code)
        for forbidden in ("readAllBytes(", "DexClassLoader", "Class.forName(",
                          "ZipInputStream", "new byte[(int) fileSize]"):
            self.assertNotIn(forbidden, code)

    def test_scanner_reports_at_most_two_dex_without_executing_methods(self):
        scanner = SCANNER.read_text(encoding="utf-8")
        for required in (
            "dexPrototypes.length() < 2",
            "DexPrototypeProbe.inspect(",
            "zip.getInputStream(e)",
            'protoPreview.put("status", "prototype-signatures-preview")',
            'protoPreview.put("status", "unreadable-prototypes")',
            'report.put("dexPrototypePreview", dexPrototypes)',
            'report.put("dexPrototypePreviewTruncated"',
            "catch (java.io.InterruptedIOException cancelled)",
            "throw cancelled;",
            "method_ids podem referenciar métodos externos",
        ):
            self.assertIn(required, scanner)

    def test_negative_cases_run_in_both_android_versions(self):
        tests = ANDROID.read_text(encoding="utf-8")
        for method in (
            "resolvesReturnAndIntParameterIntoFullSignature",
            "supportsNoParametersObjectParametersAndFourItemCap",
            "rejectsForgedProtoIndicesAndInvalidReturnTypes",
            "rejectsShortyMismatchAndInvalidTypeDescriptors",
            "rejectsOversizedOrMisalignedParameterLists",
            "rejectsBadMutf8AndTruncatedStreams",
            "cancellationKeepsInterruptFlagAndDoesNotReturnResult",
            "scannerShowsSignaturesButNotClaimedImplementations",
        ):
            self.assertIn(method, tests)
        ci = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("api: [29, 35]", ci)
        self.assertIn("DexPrototypeProbeInstrumentedTest", ci)
        self.assertIn("DexMethodProbeInstrumentedTest", ci)
        self.assertIn("ApkArchiveSafetyInstrumentedTest", ci)
        self.assertNotIn("app/build/outputs/apk/", ci)


if __name__ == "__main__":
    unittest.main()
