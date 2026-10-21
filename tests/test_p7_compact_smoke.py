"""Unit tests for the compact-device viewport calculations."""
import unittest
from tools.p7_compact_smoke import parse_wm, viewport_pixels


class P7CompactViewportTests(unittest.TestCase):
    def test_density_and_size_overrides_are_read_without_guesswork(self):
        self.assertEqual(((1080, 2220), None), parse_wm(
            "Physical size: 1080x2220", "size"))
        self.assertEqual(((840, 1890), (840, 1890)), parse_wm(
            "Physical size: 1080x2220\nOverride size: 840x1890", "size"))
        self.assertEqual(((420,), None), parse_wm(
            "Physical density: 420", "density"))
        self.assertEqual(((440,), (440,)), parse_wm(
            "Physical density: 420\nOverride density: 440", "density"))

    def test_width_is_320dp_and_never_uses_fixed_pixel_guess(self):
        self.assertEqual((840, 1890), viewport_pixels(320, 720, 420))
        self.assertEqual((880, 1980), viewport_pixels(320, 720, 440))
        self.assertEqual((640, 1440), viewport_pixels(320, 720, 320))
        with self.assertRaises(AssertionError):
            viewport_pixels(320, 720, 0)

    def test_missing_or_malformed_display_info_fails_closed(self):
        for output in ("", "Override size: 880x1980", "Physical size: 1080",
                       "Physical density: unknown"):
            with self.subTest(output=output):
                with self.assertRaises(AssertionError):
                    parse_wm(output, "density" if "density" in output else "size")
        with self.assertRaises(ValueError):
            parse_wm("Physical size: 1080x2220", "color")


if __name__ == "__main__":
    unittest.main()
