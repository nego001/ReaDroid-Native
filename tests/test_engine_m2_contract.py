"""M2 source contract: archive admission must precede APK parsers.

The Android instrumentation suite exercises behavior; this check prevents
accidental removal/reordering of the guard in future UI or import refactors.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app/src/main/java/com/readroid/app/MainActivity.java"
GUARD = ROOT / "app/src/main/java/com/readroid/app/ApkArchiveSafety.java"
STREAM = ROOT / "app/src/main/java/com/readroid/app/SafImportStream.java"


class M2ImportContract(unittest.TestCase):
    def test_archive_verification_precedes_external_parsers(self):
        source = MAIN.read_text(encoding="utf-8")
        block = source.split("private AnalyzedApk analyze(Uri uri)", 1)[1]
        block = block.split("private String formatReport(", 1)[0]
        copy_complete = block.index("copied = SafImportStream.copyAndHash(in, out,")
        gate = block.index("ApkArchiveSafety.verify(file);")
        manifest = block.index("ManifestInspector.inspect(this, file)")
        explorer = block.index("ApkExplorer.inspect(file)")
        index = block.index("ApkDiskIndex.build(file, candidate)")
        self.assertLess(copy_complete, gate)
        self.assertIn('json.put("sha256", importHash);', block)
        self.assertIn("file.delete();", block.split("catch (Exception error)", 1)[1])
        self.assertLess(gate, manifest)
        self.assertLess(gate, explorer)
        self.assertLess(gate, index)

    def test_saf_copy_is_bounded_and_checks_free_space_at_finish(self):
        source = STREAM.read_text(encoding="utf-8")
        self.assertIn("remaining + 1", source)
        self.assertIn("MAX_ZERO_READS", source)
        self.assertIn("checkInterrupted();", source)
        self.assertIn("ApkImportPreflight.checkProgress(copied, availableCacheBytes.getAsLong());", source)
        self.assertLess(source.index("if (read > remaining)"),
                        source.index("destination.write(buffer, 0, read)"))
        self.assertGreaterEqual(
            source.count("ApkImportPreflight.checkProgress(copied, availableCacheBytes.getAsLong());"), 2)

    def test_guard_streams_and_never_extracts_or_executes(self):
        source = GUARD.read_text(encoding="utf-8")
        self.assertIn("new ZipFile(apk)", source)
        self.assertIn("zip.getInputStream(entry)", source)
        self.assertIn("actualCrc.getValue() != crc", source)
        self.assertIn("measuredTotal > MAX_TOTAL_BYTES - read", source)
        self.assertIn("ApkDiskIndex.validatePath(name)", source)
        self.assertNotIn("ZipInputStream", source)
        self.assertNotIn("Runtime.getRuntime()", source)


if __name__ == "__main__":
    unittest.main()
