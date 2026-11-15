"""Ensure F1's Android matrix covers every production recovery/export path.

This contract runs in Source checks, before expensive Android emulators and on
every PR, so silently narrowing the workflow's path filters is a test failure.
No PyYAML or network access required; the expected scope is an explicit list.
"""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/f1-edit-session-validation.yml"

PRODUCTION = {
    "MainActivity.java",
    "ExplorerView.java",
    "EditPlan.java",
    "RecoveryVault.java",
    "ApkImportPreflight.java",
    "ApkZipIntegrity.java",
    "ApkRebuilder.java",
    "ApkIntegrity.java",
    "RebuildVerifier.java",
    "SafExportVerifier.java",
}
ANDROID_TESTS = {
    "EditPlanStateInstrumentedTest",
    "RecoveryVaultInstrumentedTest",
    "ProjectRecreationInstrumentedTest",
    "ApkImportPreflightInstrumentedTest",
    "ApkZipIntegrityInstrumentedTest",
    "ApkRebuilderInstrumentedTest",
    "SafExportVerifierInstrumentedTest",
}


class FunctionalCIContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_edits_to_any_critical_production_class_start_android_matrix(self):
        required = {
            "app/src/main/java/com/readroid/app/" + name for name in PRODUCTION
        }
        paths = set(re.findall(r"^\s{6}- '([^']+)'\s*$", self.workflow, re.M))
        self.assertTrue(required <= paths, f"Missing production triggers: {required - paths}")
        required_tests = {
            "app/src/androidTest/java/com/readroid/app/" + name + ".java"
            for name in ANDROID_TESTS
        }
        self.assertTrue(required_tests <= paths,
                        f"Missing test change triggers: {required_tests - paths}")
        self.assertIn("tests/test_f1_functional_ci_contract.py", paths)
        self.assertIn(".github/workflows/f1-edit-session-validation.yml", paths)

    def test_all_required_instrumented_suites_are_mandatory(self):
        selectors = re.findall(
            r"-Pandroid\.testInstrumentationRunnerArguments\.class=([^\s]+)",
            self.workflow,
        )
        self.assertEqual(1, len(selectors), "One required instrumentation invocation")
        actual = set(selectors[0].split(","))
        required = {"com.readroid.app." + name for name in ANDROID_TESTS}
        self.assertTrue(required <= actual,
                        f"Missing Android instrumentation: {required - actual}")
        self.assertIn("set -eu", self.workflow)
        self.assertIn("api: [29, 35]", self.workflow)

    def test_pr_scope_and_no_installer_publication(self):
        self.assertIn("pull_request:", self.workflow)
        self.assertIn("branches: [feature/p7-negrecodroid-visual-foundation]",
                      self.workflow)
        self.assertNotIn("assembleQa", self.workflow)
        self.assertNotIn("upload-artifact@", self.workflow)
        self.assertNotIn("major_update_approved: true", self.workflow)
        self.assertNotIn("continue-on-error: true", self.workflow)

    def test_source_checks_enforce_this_contract(self):
        static_check = (ROOT / ".github/workflows/static-check.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("test_f1_functional_ci_contract.py", static_check)


if __name__ == "__main__":
    unittest.main()
