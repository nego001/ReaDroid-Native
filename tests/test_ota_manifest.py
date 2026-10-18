"""Self-contained regression tests for offline OTA signature generation."""
import base64
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "sign_ota_manifest.py"


class OtaManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.temp.name)
        cls.private = cls.dir / "test-only.pem"
        cls.public = cls.dir / "test-only.pub.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
             "-out", str(cls.private)], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(cls.private), "-pubout",
                        "-out", str(cls.public)], check=True, capture_output=True)
        cls.apk = cls.dir / "test.apk"
        cls.apk.write_bytes(b"APK placeholder used only for metadata signing regression")
        cls.manifest = cls.dir / "manifest.json"

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def sign(self, *overrides):
        cmd = [sys.executable, str(SCRIPT), "--apk", str(self.apk),
               "--url", "https://github.com/nego001/ReaDroid-Native/releases/download/test/test.apk",
               "--version-code", "2", "--version-name", "0.2.0",
               "--channel", "beta", "--private-key", str(self.private),
               "--output", str(self.manifest)]
        return subprocess.run(cmd + list(overrides), capture_output=True, text=True)

    def test_signature_and_hash_match_android_contract(self):
        result = self.sign()
        self.assertEqual(result.returncode, 0, result.stderr)
        wrapper = json.loads(self.manifest.read_text(encoding="utf-8"))
        payload = wrapper["payload"].encode("utf-8")
        signature = base64.b64decode(wrapper["signature"], validate=True)
        data = json.loads(wrapper["payload"])
        self.assertEqual(data["versionCode"], 2)
        self.assertEqual(data["sizeBytes"], len(self.apk.read_bytes()))
        self.assertEqual(len(data["sha256"]), 64)
        signature_file = self.dir / "signature.bin"
        signature_file.write_bytes(signature)
        check = subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(self.public),
                                "-signature", str(signature_file)], input=payload, capture_output=True)
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_disallows_non_https_download_url(self):
        result = self.sign("--url", "http://example.com/test.apk")
        self.assertNotEqual(result.returncode, 0)

    def test_rejects_invalid_version_code(self):
        result = self.sign("--version-code", "0")
        self.assertNotEqual(result.returncode, 0)

    def test_rejects_embedded_credentials(self):
        result = self.sign("--url", "https://user:password@example.com/test.apk")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
