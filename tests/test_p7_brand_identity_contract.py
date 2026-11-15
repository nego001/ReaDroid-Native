"""Keep the native brand source consistent with the approved P7 identity.

This is a resource and naming contract, NOT a claim of 1:1 visual approval.
"""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FOREGROUND = ROOT / "app/src/main/res/drawable/ic_negrecodroid_foreground.xml"
MONOCHROME = ROOT / "app/src/main/res/drawable/ic_negrecodroid_monochrome.xml"
ADAPTIVE = ROOT / "app/src/main/res/mipmap-anydpi-v26/ic_negrecodroid.xml"
SVG = ROOT / "design/brand/negrecodroid-mark-master.svg"
ANDROID = "{http://schemas.android.com/apk/res/android}"


class P7BrandIdentityTests(unittest.TestCase):
    def test_vector_sources_parse_and_keep_circuit_shield(self):
        foreground = ET.parse(FOREGROUND).getroot()
        monochrome = ET.parse(MONOCHROME).getroot()
        adaptive = ET.parse(ADAPTIVE).getroot()
        mark = ET.parse(SVG).getroot()
        self.assertTrue(foreground.tag.endswith("vector"))
        self.assertTrue(monochrome.tag.endswith("vector"))
        self.assertTrue(mark.tag.endswith("svg"))
        self.assertEqual("108", foreground.attrib[ANDROID + "viewportWidth"])
        self.assertEqual("108", foreground.attrib[ANDROID + "viewportHeight"])
        self.assertGreaterEqual(len(foreground.findall("path")), 13)
        paths = [p.attrib.get(ANDROID + "pathData", "") for p
                 in foreground.findall("path")]
        self.assertTrue(any("M54,11 L91,30" in p for p in paths))
        self.assertTrue(any("M34,34 L76,71" in p for p in paths))
        self.assertGreaterEqual(sum(" a5,5 " in p for p in paths), 3)
        self.assertEqual("@drawable/ic_negrecodroid_foreground",
                         adaptive.find("foreground").attrib[ANDROID + "drawable"])
        self.assertEqual("@drawable/ic_negrecodroid_monochrome",
                         adaptive.find("monochrome").attrib[ANDROID + "drawable"])
        self.assertGreaterEqual(len(monochrome.findall("path")), 2)

    def test_wordmark_matches_reference_not_preliminary_placeholder(self):
        text = SVG.read_text(encoding="utf-8")
        self.assertIn("NegrecoDroid", text)
        self.assertIn(">Negreco</text>", text)
        self.assertIn(">Droid</text>", text)
        self.assertIn(">DESIGN STUDIO</text>", text)
        self.assertNotIn("NATIVE STUDIO", text)
        self.assertNotIn("pixel-perfect approved", text.lower())
        self.assertGreaterEqual(text.count("linearGradient"), 4)
        # Source must stay vector and text: never embed a full screenshot.
        self.assertNotIn("data:image/", text)
        self.assertNotIn("<image", text)


if __name__ == "__main__":
    unittest.main()
