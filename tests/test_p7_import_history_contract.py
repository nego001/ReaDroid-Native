"""P7 history is a post-commit side effect, never a pre-commit action.

These static regression guards complement real Android failure/recreation tests
and prevent future refactors from moving history writes before acceptance.
"""
from pathlib import Path
import unittest

APP = (Path(__file__).resolve().parents[1] / "app" / "src" / "main"
       / "java" / "com" / "readroid" / "app" / "MainActivity.java")


class AcceptedImportHistoryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP.read_text(encoding="utf-8")
        cls.import_body = cls.source.split(
            "private void analyzeSelectedApk(Uri uri) {", 1)[1].split(
            "private void recordAcceptedProject(", 1)[0]
        cls.metadata_body = cls.source.split(
            "private void recordAcceptedProject(", 1)[1].split(
            "private void confirmOtaDownload(", 1)[0]

    def test_history_is_not_mutated_in_analyzer_before_ui_acceptance(self):
        before_ui = self.import_body.split("runOnUiThread(() -> {", 1)[0]
        self.assertNotIn("P7ProjectHistory.record(", before_ui)
        self.assertNotIn("P7RecentAppIcons.capture(", before_ui)
        self.assertNotIn("recordAcceptedProject(", before_ui)
        self.assertNotIn("P7ProjectHistory.record(", self.import_body)
        self.assertNotIn("P7RecentAppIcons.capture(", self.import_body)

    def test_schedule_follows_project_commit_not_validation(self):
        for piece in (
            "if (sequence != analysisSequence || isFinishing() || isDestroyed())",
            "currentApk = candidate.file;",
            "selectedApkUri = uri;",
            "pendingApkUri = null;",
            "displayAnalyzedReport(candidate.report);",
            "recordAcceptedProject(uri, packageName, candidate.file, sequence);",
        ):
            self.assertIn(piece, self.import_body)
        positions = [self.import_body.index(piece) for piece in (
            "runOnUiThread(() -> {",
            "if (sequence != analysisSequence || isFinishing() || isDestroyed())",
            "currentApk = candidate.file;",
            "selectedApkUri = uri;",
            "displayAnalyzedReport(candidate.report);",
            "recordAcceptedProject(uri, packageName, candidate.file, sequence);",
        )]
        self.assertEqual(positions, sorted(positions))

    def test_accepted_history_remains_off_ui_and_best_effort(self):
        self.assertIn("executor.execute(() -> {", self.metadata_body)
        self.assertIn("P7ProjectHistory.record(application, uri, packageName)",
                      self.metadata_body)
        self.assertIn("P7RecentAppIcons.capture(application, uri, committedApk)",
                      self.metadata_body)
        self.assertIn("getApplicationContext()", self.metadata_body)
        self.assertIn("acceptedSequence == analysisSequence", self.metadata_body)
        self.assertIn("!isFinishing() && !isDestroyed()", self.metadata_body)
        self.assertIn("catch (RuntimeException metadataFailure)",
                      self.metadata_body)
        self.assertIn("RejectedExecutionException", self.metadata_body)


if __name__ == "__main__":
    unittest.main()
