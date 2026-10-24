"""Contracts for the real Design Studio saved-identity TalkBack preview."""
import unittest
import xml.etree.ElementTree as ET

from tools.p7_design_smoke import saved_identity_preview


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
