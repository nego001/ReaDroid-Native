"""Static safety regression for the functional native APK file-action dialog.

The genuine E2E Android SAF job separately verifies that the user can click
'Planejar edição' and save a real text replacement.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPLORER = ROOT / "app/src/main/java/com/readroid/app/ExplorerView.java"


class EngineFileActionDialogTests(unittest.TestCase):
    def test_native_action_items_are_never_suppressed_by_dialog_message(self):
        source = EXPLORER.read_text(encoding="utf-8")
        before, rest = source.split("private void showFileActions(", 1)
        method, rest = rest.split("private static String formatBytes(", 1)
        self.assertNotIn(".setMessage(", method,
                         "A native AlertDialog message can hide setItems actions")
        self.assertIn(".setItems(choices", method)
        self.assertIn('"Planejar edição"', method)
        self.assertIn('"Ver texto"', method)
        self.assertIn('"Detalhes técnicos"', method)
        self.assertIn('"Copiar caminho"', method)
        self.assertIn('label + "\\nTipo: "', method)
        self.assertIn('formatBytes(sizeBytes)', method)


if __name__ == "__main__":
    unittest.main()
