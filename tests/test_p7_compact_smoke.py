"""Unit tests for the compact-device viewport calculations."""
import unittest
import xml.etree.ElementTree as ET
from tools.p7_compact_smoke import (
    parse_wm, viewport_pixels, require_accessible_target)


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

    def test_accessible_design_target_respects_48dp_and_screen_bounds(self):
        label = "Temas, aba selecionada"
        def node(bounds, description=label, clickable="true"):
            return ET.Element("node", {
                "content-desc": description, "clickable": clickable,
                "bounds": bounds})
        good = node("[0,0][132,132]")
        require_accessible_target([good], label, 440, (880, 1980))
        for bad in (
                node("[0,0][131,132]"),  # < 48dp width
                node("[0,0][132,131]"),  # < 48dp height
                node("[750,0][910,140]"),  # clipped outside the screen
                node("[0,0][132,132]", clickable="false")):
            with self.subTest(bad=bad.attrib):
                with self.assertRaises(AssertionError):
                    require_accessible_target([bad], label, 440, (880, 1980))
        with self.assertRaises(AssertionError):
            require_accessible_target([good, good], label, 440, (880, 1980))
        with self.assertRaises(AssertionError):
            require_accessible_target([], label, 440, (880, 1980))

    def test_all_four_design_subtabs_must_be_fully_on_screen(self):
        # A fourth subtab outside the 320dp viewport is not a valid
        # accessibility workaround, even if horizontal scroll exists.
        names = ("Temas, aba selecionada", "Layout, selecionar aba",
                 "Ícones, selecionar aba", "Logotipo, selecionar aba")
        bounds = ("[0,0][145,140]", "[145,0][290,140]",
                  "[290,0][435,140]", "[435,0][580,140]")
        width = 880
        for title, bound in zip(names, bounds):
            node = ET.Element("node", {
                "content-desc": title, "clickable": "true",
                "bounds": bound})
            require_accessible_target([node], title, 440, (width, 1980))
        offscreen = ET.Element("node", {
            "content-desc": names[-1], "clickable": "true",
            "bounds": "[810,0][910,140]"})
        with self.assertRaises(AssertionError):
            require_accessible_target([offscreen], names[-1],
                                      440, (width, 1980))

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
