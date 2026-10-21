"""P7 official-reference validator: synthetic PNGs never substitute artwork."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from tools import p7_reference_assets as assets


def chunk(tag, payload=b""):
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff))


def png(width=3, height=2):
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = b"\x00" + b"\x00\x80\xff\xff" * width
    return (assets.PNG_MAGIC + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(row * height))
            + chunk(b"IEND"))


class ApprovedArtTests(unittest.TestCase):
    def test_canonical_names_hashes_and_dimensions_are_frozen(self):
        self.assertEqual((1448, 1086), assets.DIMENSIONS)
        self.assertEqual({
            "negrecodroid_controle_total_de_apks.png",
            "identidade_negrecodroid_em_neon_azul.png",
        }, set(assets.REFERENCES))
        self.assertEqual(64, len(next(iter(assets.REFERENCES.values()))))
        self.assertEqual(64, len(list(assets.REFERENCES.values())[1]))

    def test_valid_png_checks_all_bytes_and_crc(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.png"
            data = png()
            path.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.assertEqual(digest, assets.validate_png(path, digest, (3, 2)))
            with self.assertRaisesRegex(assets.ReferenceValidationError,
                                        "SHA-256"):
                assets.validate_png(path, "0" * 64, (3, 2))
            with self.assertRaisesRegex(assets.ReferenceValidationError,
                                        "Dimensões"):
                assets.validate_png(path, digest, (1448, 1086))

    def test_crc_trailing_data_or_bad_structure_fail_closed(self):
        data = png()
        cases = [
            data[:40] + bytes([data[40] ^ 1]) + data[41:],
            data + b"extra",
            data[:-12],
            b"not a png",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrupted.png"
            for damaged in cases:
                with self.subTest(sample=damaged[:12]):
                    path.write_bytes(damaged)
                    with self.assertRaises(assets.ReferenceValidationError):
                        assets.validate_png(path,
                            hashlib.sha256(damaged).hexdigest(), (3, 2))

    def test_both_official_files_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = png()
            digest = hashlib.sha256(data).hexdigest()
            names = {"ref_one.png": digest, "ref_two.png": digest}
            Path(tmp, "ref_one.png").write_bytes(data)
            ok, messages = assets.check_references(tmp, names)
            self.assertFalse(ok)
            self.assertEqual(2, len(messages))
            self.assertIn("P7_REFERENCE_BLOCKED ref_two.png", messages[1])
            Path(tmp, "ref_two.png").write_bytes(data)
            ok, messages = assets.check_references(tmp, names)
            self.assertTrue(ok)
            self.assertTrue(all(x.startswith("P7_REFERENCE_PASS") for x in messages))


if __name__ == "__main__":
    unittest.main()
