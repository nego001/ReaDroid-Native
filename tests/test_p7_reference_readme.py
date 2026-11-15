"""Prevent QA documentation from claiming obsolete screenshot coverage.

The official PNG binaries are intentionally NOT substituted by CI fixtures.
"""
from pathlib import Path
import unittest

from tools.p7_capture_manifest import SCREENS
from tools.p7_reference_assets import REFERENCES

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "design" / "reference" / "p7" / "README.md"


class P7ReferenceReadmeContracts(unittest.TestCase):
    def test_readme_matches_live_screenshot_inventory(self):
        content = README.read_text(encoding="utf-8")
        count = len(SCREENS)
        self.assertEqual(14, count)
        self.assertIn(f"{count} capturas reais por API", content)
        self.assertIn(f"{count * 2} nas APIs 29 e 35", content)
        self.assertIn(f"{count * 2} imagens", content)
        self.assertNotIn("13 capturas", content)
        self.assertNotIn("treze screenshots", content)
        self.assertEqual(8, sum(scenario == "normal" for _, scenario, _ in SCREENS))
        self.assertEqual(3, sum(scenario == "compact_320dp_font_130pct"
                                for _, scenario, _ in SCREENS))
        self.assertEqual(3, sum(scenario == "normal_font_200pct"
                                for _, scenario, _ in SCREENS))
        self.assertIn("Explorador com ZIP", content)

    def test_no_false_approval_or_unverified_reference_assets(self):
        content = README.read_text(encoding="utf-8")
        for name, digest in REFERENCES.items():
            self.assertIn(name, content)
            self.assertIn(digest, content)
        self.assertIn("BLOCKED", content)
        self.assertIn("NOT_APPROVED", content)
        self.assertIn("Galaxy A55", content)
        self.assertIn("não transforma", content)
        self.assertIn("não de release", content)


if __name__ == "__main__":
    unittest.main()
