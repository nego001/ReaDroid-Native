"""Contracts for the real Design Studio saved-identity TalkBack preview."""
import unittest
import xml.etree.ElementTree as ET

from tools.p7_design_smoke import saved_identity_preview, applied_theme_preview


class DesignStudioSavedIdentityTests(unittest.TestCase):
    def node(self, description, clickable="false"):
        return ET.Element("node", {
            "content-desc": description,
            "clickable": clickable
        })

    def test_real_name_and_subtitle_are_announced_as_one_item(self):
        label = ("Prévia da identidade visual atual. Nome: NegrecoDroid."
                 " Subtítulo: Análise de aplicativos")
        self.assertEqual(label, saved_identity_preview([self.node(label)]))

    def test_rejects_missing_or_empty_identity_fields(self):
        for description in (
                "Prévia da identidade visual atual",
                "Prévia da identidade visual atual. Nome: ",
                "Prévia da identidade visual atual. Nome: Marca",
                "Prévia da identidade visual atual. Nome: . Subtítulo: Texto",
                "Prévia da identidade visual atual. Nome: Marca. Subtítulo: "):
            with self.subTest(description=description):
                with self.assertRaises(AssertionError):
                    saved_identity_preview([self.node(description)])

    def test_rejects_duplicate_or_clickable_preview(self):
        label = ("Prévia da identidade visual atual. Nome: Marca."
                 " Subtítulo: Identidade")
        with self.assertRaises(AssertionError):
            saved_identity_preview([self.node(label), self.node(label)])
        with self.assertRaises(AssertionError):
            saved_identity_preview([self.node(label, clickable="true")])


class AppliedThemeContractTests(unittest.TestCase):
    def card(self, description, clickable="true"):
        return ET.Element("node", {"content-desc": description,
                                   "clickable": clickable})

    def test_committed_theme_is_unique_clickable_and_announces_glow(self):
        committed = self.card("Negreco Blue, tema aplicado. Neon · Profissional")
        uncommitted = self.card("Matrix Green, selecionar prévia. Neon · Hacker Style")
        self.assertEqual(committed.attrib["content-desc"],
                         applied_theme_preview([committed, uncommitted]))

    def test_pending_old_labels_and_missing_applied_theme_fail_closed(self):
        candidates = [
            self.card("Negreco Blue, prévia selecionada. Neon · Profissional"),
            self.card("Matrix Green, prévia escolhida, ainda não aplicada. Neon · Hacker Style"),
            self.card("Matrix Green, selecionar prévia. Neon · Hacker Style")
        ]
        with self.assertRaisesRegex(AssertionError, "saved theme"):
            applied_theme_preview(candidates)

    def test_duplicate_wrong_role_or_absent_glow_fails_closed(self):
        committed = self.card("Negreco Blue, tema aplicado. Neon · Profissional")
        with self.assertRaises(AssertionError):
            applied_theme_preview([committed, committed])
        with self.assertRaises(AssertionError):
            applied_theme_preview([self.card(committed.attrib["content-desc"],
                                            clickable="false")])
        with self.assertRaises(AssertionError):
            applied_theme_preview([self.card("Negreco Blue, tema aplicado")])
        with self.assertRaises(AssertionError):
            applied_theme_preview([self.card("Negreco Blue, tema aplicado. Estado indefinido")])
