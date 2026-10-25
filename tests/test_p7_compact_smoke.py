"""Unit tests for the compact-device viewport calculations."""
import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
from tools.p7_compact_smoke import (
    parse_wm, viewport_pixels, require_accessible_target,
    require_stacked_explorer_summary, capture_compact_failure_diagnostics,
    require_inline_design_header)


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

    def test_compact_design_header_and_chooser_must_share_visible_row(self):
        def node(text=None, desc=None, bounds="[0,0][1,1]",
                 package="com.readroid.app"):
            attrs = {"package": package, "bounds": bounds}
            if text is not None:
                attrs["text"] = text
            if desc is not None:
                attrs["content-desc"] = desc
            return ET.Element("node", attrs)
        title = node(text="Previews de Temas",
                     bounds="[32,210][486,259]")
        chooser = node(desc="Ver todos: Previews de Temas",
                       bounds="[502,184][843,316]")
        require_inline_design_header(
            [title, chooser], "Previews de Temas", (880, 1980))
        for broken in (
            [title], # chooser disappeared
            [title, chooser, chooser], # duplicate accessibility target
            [title, node(desc="Ver todos: Previews de Temas",
                         bounds="[502,330][843,462]")], # wrapped row
            [title, node(desc="Ver todos: Previews de Temas",
                         bounds="[480,184][843,316]")], # horizontal overlap
            [title, node(desc="Ver todos: Previews de Temas",
                         bounds="[502,184][901,316]")], # clipped action
            [title, node(desc="Ver todos: Previews de Temas",
                         bounds="[502,184][843,316]",
                         package="com.android.systemui")],
        ):
            with self.subTest(broken=[n.attrib for n in broken]):
                with self.assertRaises(AssertionError):
                    require_inline_design_header(
                        broken, "Previews de Temas", (880, 1980))
        source = (Path(__file__).resolve().parents[1] /
                  "tools/p7_compact_smoke.py").read_text(encoding="utf-8")
        self.assertIn('require_inline_design_header(\n'
                      '            nodes, "Previews de Temas"', source)

    def test_important_apk_name_cannot_be_obscured_by_plan_chip(self):
        def item(text=None, desc=None, bounds="[0,0][100,100]"):
            fields = {"bounds": bounds}
            if text is not None:
                fields["text"] = text
            if desc is not None:
                fields["content-desc"] = desc
            return ET.Element("node", fields)
        good = [
            item(text="Nenhum APK selecionado", bounds="[15,80][280,145]"),
            item(desc="Abrir plano de edição", bounds="[15,150][290,210]"),
        ]
        require_stacked_explorer_summary(good)
        with self.assertRaises(AssertionError):
            require_stacked_explorer_summary([
                good[0], item(desc="Abrir plano de edição",
                              bounds="[190,80][290,145]")])
        with self.assertRaises(AssertionError):
            require_stacked_explorer_summary(good[:1])

    def test_missing_or_malformed_display_info_fails_closed(self):
        for output in ("", "Override size: 880x1980", "Physical size: 1080",
                       "Physical density: unknown"):
            with self.subTest(output=output):
                with self.assertRaises(AssertionError):
                    parse_wm(output, "density" if "density" in output else "size")
        with self.assertRaises(ValueError):
            parse_wm("Physical size: 1080x2220", "color")


    def test_failure_snapshot_reports_focus_without_approving_or_dismissing(self):
        with tempfile.TemporaryDirectory() as temp:
            old = os.getcwd()
            self.addCleanup(os.chdir, old)
            os.chdir(temp)
            root = ET.Element("hierarchy")
            ET.SubElement(root, "node", {
                "package": "com.android.systemui",
                "text": "System UI dialog",
                "content-desc": ""})
            ET.SubElement(root, "node", {
                "package": "com.readroid.app",
                "text": "",
                "content-desc": "Seção Arquivos, selecionada"})
            ET.ElementTree(root).write(
                "v3-studio-android-hierarchy.xml", encoding="utf-8")
            def adb_stub(*args):
                if args == ("shell", "dumpsys", "window"):
                    return ("some internal state\n"
                            "mCurrentFocus=Window{u0 com.android.systemui/Dialog}\n"
                            "mFocusedApp=ActivityRecord{com.readroid.app/.MainActivity}")
                if args == ("shell", "dumpsys", "activity", "activities"):
                    return "topResumedActivity=ActivityRecord{com.readroid.app/.MainActivity}"
                raise AssertionError(f"Unexpected ADB call: {args}")
            with patch("tools.p7_compact_smoke.smoke.adb", side_effect=adb_stub), \
                 patch("tools.p7_compact_smoke.subprocess.check_output",
                       return_value=b"\x89PNG\r\n\x1a\nfixture"):
                capture_compact_failure_diagnostics(
                    "35", AssertionError("Tab 'Início' not found"))
            contents = Path("p7-diagnostic-compact-android-35.txt").read_text(
                encoding="utf-8")
            self.assertIn("P7_COMPACT_DIAGNOSTIC_ONLY", contents)
            self.assertIn("Tab 'Início' not found", contents)
            self.assertIn("mCurrentFocus=", contents)
            self.assertIn("topResumedActivity=", contents)
            self.assertIn("Seção Arquivos, selecionada", contents)
            self.assertNotIn("some internal state", contents)
            self.assertNotIn("System UI dialog", contents)
            self.assertTrue(Path("p7-diagnostic-compact-android-35.png").exists())
            self.assertFalse(Path("p7-compact-inicio-android-35.png").exists())

    def test_snapshot_adc_failures_do_not_synthesize_success(self):
        with tempfile.TemporaryDirectory() as temp:
            old = os.getcwd()
            self.addCleanup(os.chdir, old)
            os.chdir(temp)
            with patch("tools.p7_compact_smoke.smoke.adb",
                       side_effect=RuntimeError("ADB unavailable")), \
                 patch("tools.p7_compact_smoke.subprocess.check_output",
                       side_effect=RuntimeError("No screenshot")):
                capture_compact_failure_diagnostics(
                    "35", AssertionError("Tab 'Início' not found"))
            report = Path("p7-diagnostic-compact-android-35.txt").read_text(
                encoding="utf-8")
            self.assertIn("[window_focus] unavailable", report)
            self.assertIn("[activity_resumed] unavailable", report)
            self.assertIn("[visible_hierarchy]", report)
            self.assertFalse(Path("p7-diagnostic-compact-android-35.png").exists())
            self.assertFalse(Path("p7-compact-inicio-android-35.png").exists())

    def test_workflow_uploads_compact_failures_but_not_as_pass_evidence(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/p7-brand-validation.yml").read_text(
            encoding="utf-8")
        self.assertIn("p7-diagnostic-compact-android-*.txt", workflow)
        self.assertIn("p7-diagnostic-compact-android-*.png", workflow)
        source = (root / "tools/p7_compact_smoke.py").read_text(
            encoding="utf-8")
        self.assertIn("capture_compact_failure_diagnostics(api, failure)", source)
        self.assertIn("P7_COMPACT_DIAGNOSTIC_ONLY", source)
        self.assertIn("gate=FAILED", source)


if __name__ == "__main__":
    unittest.main()
