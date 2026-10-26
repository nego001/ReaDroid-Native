"""M2.5 guard: cryptographic path fingerprints reject duplicates without retaining names."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "app/src/main/java/com/readroid/app/ApkArchiveSafety.java"
PATHS = ROOT / "app/src/main/java/com/readroid/app/ApkPathFingerprintSet.java"
CI = ROOT / ".github/workflows/engine-m2-admission.yml"


class M25PathFingerprintContract(unittest.TestCase):
    def test_admission_preserves_original_limits_but_does_not_retain_names(self):
        source = GUARD.read_text(encoding="utf-8")
        self.assertIn("new ApkPathFingerprintSet()", source)
        self.assertIn("paths.requireUnique(name)", source)
        self.assertIn("ApkDiskIndex.validatePath(name)", source)
        self.assertIn("pathChars > MAX_PATH_CHARS_TOTAL", source)
        self.assertIn("MAX_ENTRIES", source)
        self.assertNotIn("Set<String> paths", source)
        self.assertNotIn("paths.add(name)", source)

    def test_128_bit_fingerprints_are_conservative_on_collision(self):
        source = PATHS.read_text(encoding="utf-8")
        self.assertIn('MessageDigest.getInstance("SHA-256")', source)
        self.assertIn("sha256.digest(path.getBytes(StandardCharsets.UTF_8))",
                      source)
        self.assertIn("new Fingerprint(readLong(digest, 0)", source)
        self.assertIn("FINGERPRINT_BYTES / 2", source)
        self.assertIn("private final Set<Fingerprint> seen", source)
        self.assertIn("if (!seen.add(fingerprint))", source)
        self.assertIn("throw new IOException", source)
        self.assertNotIn("Set<String>", source)
        # No raw source path retained in the Fingerprint object.
        record = source.split("private static final class Fingerprint", 1)[1]
        self.assertIn("final long high;", record)
        self.assertIn("final long low;", record)
        self.assertNotIn("final String", record)

    def test_android_10_and_15_exercise_long_paths(self):
        workflow = CI.read_text(encoding="utf-8")
        self.assertIn("api: [29, 35]", workflow)
        self.assertIn("ApkPathFingerprintInstrumentedTest", workflow)
        self.assertNotIn("app/build/outputs/apk/", workflow)


if __name__ == "__main__":
    unittest.main()
