"""Offline review must accept genuine matching manifests and reject forgeries."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from tools import p7_capture_manifest as capture
from tools import p7_cross_api_review as review


def chunk(tag, payload=b""):
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff))


def fake_png(width, height):
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = b"\x00" + b"\x20\x40\x80\xff" * width
    return (capture.PNG_MAGIC + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(row * height))
            + chunk(b"IEND"))


def fixture(root, api, reference_dir):
    root.mkdir(parents=True, exist_ok=True)
    for _, scenario, template in capture.SCREENS:
        dimensions = ((320, 720) if scenario ==
                      "compact_320dp_font_130pct" else (400, 800))
        (root / template.format(api=api)).write_bytes(fake_png(*dimensions))
    evidence = capture.build_manifest(
        root, api, (400, 800), 160, reference_dir=reference_dir)
    (root / f"p7-evidence-android-{api}.json").write_text(
        json.dumps(evidence), encoding="utf-8")


class CrossApiReviewTests(unittest.TestCase):
    def test_two_verified_emulator_inventories_generate_blocked_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a, b = root / "29", root / "35"
            fixture(a, 29, root)
            fixture(b, 35, root)
            content, report = review.render_review(a, b, root)
            self.assertEqual(28, report["verified_screenshots"])
            self.assertEqual("BLOCKED", report["references"])
            self.assertFalse(report["pixel_perfect_approved"])
            self.assertFalse(report["physical_device_approved"])
            self.assertIn("Android API 29", content)
            self.assertIn("Android API 35", content)
            self.assertIn("NÃO APROVADA", content)
            self.assertNotIn("<script", content)
            self.assertNotIn("VERIFICADAS</strong>", content)

    def test_forged_approval_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a, b = root / "29", root / "35"
            fixture(a, 29, root)
            fixture(b, 35, root)
            manifest = b / "p7-evidence-android-35.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["pixel_perfect_approved"] = True
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(review.board.ReviewBoardError):
                review.render_review(a, b, root)

    def test_missing_android_35_image_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a, b = root / "29", root / "35"
            fixture(a, 29, root)
            fixture(b, 35, root)
            (b / "p7-design-android-35.png").unlink()
            with self.assertRaises(review.board.ReviewBoardError):
                review.render_review(a, b, root)


if __name__ == "__main__":
    unittest.main()
