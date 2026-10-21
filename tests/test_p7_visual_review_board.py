"""P7 visual board: trust real manifests, never fake image approval."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from tools import p7_capture_manifest as capture
from tools import p7_visual_review_board as board


def chunk(name, data=b""):
    return (struct.pack(">I", len(data)) + name + data
            + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff))


def png(width, height):
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = b"\x00" + b"\x20\x40\x80\xff" * width
    return (capture.PNG_MAGIC + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(row * height))
            + chunk(b"IEND"))


def fixture(root):
    for _, scenario, template in capture.SCREENS:
        dims = ((320, 720) if scenario == "compact_320dp_font_130pct"
                else (400, 800))
        (root / template.format(api=29)).write_bytes(png(*dims))
    evidence = capture.build_manifest(root, 29, (400, 800), 160,
                                      reference_dir=root)
    manifest = root / "p7-evidence-android-29.json"
    import json
    manifest.write_text(json.dumps(evidence), encoding="utf-8")
    return manifest


class ReviewBoardTests(unittest.TestCase):
    def test_real_evidence_board_is_blocked_without_official_art(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = fixture(root)
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in root.glob("*.png")}
            content, report = board.render_board(manifest, root, root)
            self.assertEqual("BLOCKED", report["official_references"])
            self.assertIn("BLOQUEADO: ARTES OFICIAIS", content)
            self.assertIn("Visual 1:1:</strong> NÃO APROVADO", content)
            self.assertIn("Teste físico:</strong> NÃO APROVADO", content)
            self.assertEqual(11, content.count("loading='lazy'"))
            self.assertEqual(2, content.count("Imagem oficial não disponível"))
            self.assertNotIn("data:image/png;base64", content)
            self.assertNotIn("<script", content)
            self.assertEqual(before, {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.glob("*.png")})

    def test_mutated_screenshot_blocks_board_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = fixture(root)
            photo = root / "p7-design-android-29.png"
            photo.write_bytes(png(400, 800) + b"extra")
            with self.assertRaises(board.ReviewBoardError):
                board.render_board(manifest, root, root)

    def test_forged_approval_and_mismatched_hash_fail_closed(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = fixture(root)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            for field, value in (("pixel_perfect_approved", True),
                                 ("official_references", "VERIFIED"),
                                 ("source", "unverified image")):
                forged = dict(data)
                forged[field] = value
                manifest.write_text(json.dumps(forged), encoding="utf-8")
                with self.subTest(field=field):
                    with self.assertRaises(board.ReviewBoardError):
                        board.render_board(manifest, root, root)
            data["screenshots"][0]["sha256"] = "0" * 64
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(board.ReviewBoardError):
                board.render_board(manifest, root, root)

    def test_missing_capture_or_oversize_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = fixture(root)
            (root / "p7-logo-workshop-android-29.png").unlink()
            with self.assertRaises(board.ReviewBoardError):
                board.render_board(manifest, root, root)
            manifest.write_bytes(b" " * (board.MAX_MANIFEST_BYTES + 1))
            with self.assertRaises(board.ReviewBoardError):
                board.render_board(manifest, root, root)


if __name__ == "__main__":
    unittest.main()
