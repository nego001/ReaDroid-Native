"""Structural tests for P7 screenshot inventory. Synthetic PNGs are test-only."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from tools import p7_capture_manifest as capture


def chunk(tag, payload=b""):
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff))


def png(width, height):
    # Valid synthetic pixels only for a unit fixture, NEVER visual references.
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = b"\x00" + b"\x00\x00\x00\xff" * width
    return (capture.PNG_MAGIC + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(row * height))
            + chunk(b"IEND"))


def populate(directory, api=29, size=(400, 800), density=160):
    compact = (320, 720)
    for _, scenario, template in capture.SCREENS:
        width, height = (compact if scenario ==
                         "compact_320dp_font_130pct" else size)
        (directory / template.format(api=api)).write_bytes(png(width, height))


class P7ScreenshotInventoryTests(unittest.TestCase):
    def test_all_eleven_named_screens_and_hashes_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            populate(root)
            result = capture.build_manifest(
                root, 29, (400, 800), 160, reference_dir=root)
            self.assertEqual(1, result["schema_version"])
            self.assertEqual(11, len(result["screenshots"]))
            self.assertEqual("BLOCKED", result["official_references"])
            self.assertFalse(result["pixel_perfect_approved"])
            self.assertFalse(result["physical_device_approved"])
            self.assertEqual({"normal", "compact_320dp_font_130pct",
                              "normal_font_200pct"},
                             {s["scenario"] for s in result["screenshots"]})
            sample = result["screenshots"][0]
            self.assertEqual(hashlib.sha256(
                (root / sample["filename"]).read_bytes()).hexdigest(),
                sample["sha256"])

    def test_missing_scene_fails_without_creating_a_success_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            populate(root)
            (root / "p7-logo-workshop-android-29.png").unlink()
            with self.assertRaisesRegex(
                    capture.ScreenshotEvidenceError, "missing"):
                capture.build_manifest(
                    root, 29, (400, 800), 160, reference_dir=root)

    def test_mislabelled_viewport_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            populate(root)
            (root / "p7-compact-design-android-29.png").write_bytes(
                png(400, 800))
            with self.assertRaisesRegex(
                    capture.ScreenshotEvidenceError, "does not match"):
                capture.build_manifest(
                    root, 29, (400, 800), 160, reference_dir=root)

    def test_bad_crc_missing_iend_duplicate_header_and_trailing_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "damaged.png"
            original = png(4, 3)
            duplicates = original[:33] + chunk(b"IHDR",
                struct.pack(">IIBBBBB", 4, 3, 8, 6, 0, 0, 0)) + original[33:]
            for corrupted in (
                    b"not a png", original[:-12], original + b"trailing",
                    duplicates, original[:48] + bytes(
                        [original[48] ^ 1]) + original[49:]):
                path.write_bytes(corrupted)
                with self.subTest(size=len(corrupted)):
                    with self.assertRaises(capture.ScreenshotEvidenceError):
                        capture.inspect_png(path)

    def test_invalid_api_and_density_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            for api, density in ((33, 160), (29, 0)):
                with self.subTest(api=api, density=density):
                    with self.assertRaises(capture.ScreenshotEvidenceError):
                        capture.build_manifest(
                            Path(tmp), api, (400, 800), density,
                            reference_dir=Path(tmp))


if __name__ == "__main__":
    unittest.main()
