"""Regression contract: installable QA APKs are a major-update-only action."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MajorApkPolicyTest(unittest.TestCase):
    def test_installable_apk_requires_manual_major_update_confirmation(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(
            encoding="utf-8")
        event_configuration = workflow.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", event_configuration)
        self.assertNotIn("\n  push:", event_configuration)
        self.assertNotIn("\n  pull_request:", event_configuration)
        self.assertIn("major_update_approved:", event_configuration)
        self.assertIn("default: false", event_configuration)
        self.assertIn("if: ${{ inputs.major_update_approved == true }}", workflow)
        self.assertIn("app/build/outputs/apk/qa/app-qa.apk", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertNotIn("ReaDroid-Native-debug", workflow)

    def test_daily_android_emulators_do_not_build_or_upload_qa_installer(self):
        workflow = (ROOT / ".github/workflows/p7-brand-validation.yml").read_text(
            encoding="utf-8")
        self.assertIn("connectedDebugAndroidTest", workflow)
        self.assertNotIn("assembleQa", workflow)
        self.assertNotIn("app-qa.apk", workflow)
        self.assertNotIn("outputs/apk/qa/", workflow)
        self.assertIn("p7-explorer-android-", workflow)


if __name__ == "__main__":
    unittest.main()
