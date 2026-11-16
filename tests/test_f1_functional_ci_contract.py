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
    "RecoveryResumeGate.java",
    "ApkImportPreflight.java",
    "ApkZipIntegrity.java",
    "ApkExplorer.java",
    "ApkDiskIndex.java",
    "ImportCacheAudit.java",
    "ApkCacheAdmission.java",
    "SavedProjectResume.java",
    "ApkRebuilder.java",
    "RebuildTempJanitor.java",
    "RebuildStorageBudget.java",
    "ApkIntegrity.java",
    "RebuildVerifier.java",
    "SafExportVerifier.java",
    "ExportSessionGuard.java",
}
ANDROID_TESTS = {
    "EditPlanStateInstrumentedTest",
    "RecoveryVaultInstrumentedTest",
    "RecoveryResumeGateInstrumentedTest",
    "ProjectRecreationInstrumentedTest",
    "ApkImportPreflightInstrumentedTest",
    "ApkZipIntegrityInstrumentedTest",
    "ApkCacheAdmissionInstrumentedTest",
    "SavedProjectResumeInstrumentedTest",
    "ImportCacheAuditInstrumentedTest",
    "ApkRebuilderInstrumentedTest",
    "RebuildTempJanitorInstrumentedTest",
    "RebuildStorageBudgetInstrumentedTest",
    "SafExportVerifierInstrumentedTest",
    "ExportSessionGuardInstrumentedTest",
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

    def test_f114_export_picker_bound_to_project_and_lifecycle(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8"
        )
        saf = (ROOT / "app/src/main/java/com/readroid/app/SafExportVerifier.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("pendingExport = new PendingExport(", activity)
        self.assertIn("analysisAtPrompt != analysisSequence", activity)
        self.assertIn("sourceAtPrompt != currentApk", activity)
        self.assertIn("intent.source != currentApk", activity)
        self.assertIn("exportSessions.invalidate();", activity)
        self.assertIn("session.requireActive();", activity)
        self.assertIn("SafExportVerifier.copyAndVerifyBound(", activity)
        self.assertIn("checkToken(token);", saf)
        self.assertIn('readWithProgress(verify, buffer, zeros, "Releitura SAF", token)', saf)

    def test_f115_token_reaches_archive_hash_and_verifier(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8"
        )
        rebuild = (ROOT / "app/src/main/java/com/readroid/app/ApkRebuilder.java").read_text(
            encoding="utf-8"
        )
        integrity = (ROOT / "app/src/main/java/com/readroid/app/ApkIntegrity.java").read_text(
            encoding="utf-8"
        )
        zipcheck = (ROOT / "app/src/main/java/com/readroid/app/ApkZipIntegrity.java").read_text(
            encoding="utf-8"
        )
        verifier = (ROOT / "app/src/main/java/com/readroid/app/RebuildVerifier.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("ApkRebuilder.rebuild(source, temp, changes, session)", activity)
        self.assertIn("ApkZipIntegrity.verify(original, token)", rebuild)
        self.assertIn("ApkZipIntegrity.verify(staged, token)", rebuild)
        self.assertIn("RebuildVerifier.verifyAgainstOriginal(original, staged, safeEdits, token)", rebuild)
        self.assertIn("ExportSessionGuard.check(token)", integrity)
        self.assertIn("ExportSessionGuard.check(token)", zipcheck)
        self.assertIn("ExportSessionGuard.check(token)", verifier)

    def test_f116_orphan_pruning_limited_to_private_cache(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8"
        )
        rebuilder = (ROOT / "app/src/main/java/com/readroid/app/ApkRebuilder.java").read_text(
            encoding="utf-8"
        )
        janitor = (ROOT / "app/src/main/java/com/readroid/app/RebuildTempJanitor.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("RebuildTempJanitor.sweep(privateCache)", activity)
        self.assertIn('File.createTempFile("readroid_unsigned_", ".apk", getCacheDir())', activity)
        self.assertIn("RebuildTempJanitor.track(temp)", activity)
        self.assertIn("RebuildTempJanitor.release(temp)", activity)
        self.assertIn('File.createTempFile("readroid-rebuild-", ".tmp"', rebuilder)
        self.assertIn("RebuildTempJanitor.track(staged)", rebuilder)
        self.assertIn("RebuildTempJanitor.release(staged)", rebuilder)
        self.assertIn("LinkOption.NOFOLLOW_LINKS", janitor)
        self.assertIn("MIN_STALE_AGE_MS", janitor)

    def test_f117_import_index_audit_is_non_destructive(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8"
        )
        audit = (ROOT / "app/src/main/java/com/readroid/app/ImportCacheAudit.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("ImportCacheAudit.inspect(", activity)
        self.assertIn("ImportCacheAudit.track(file)", activity)
        self.assertIn("ImportCacheAudit.release(candidate.file)", activity)
        self.assertIn("LinkOption.NOFOLLOW_LINKS", audit)
        self.assertNotIn("Files.delete", audit)
        self.assertNotIn("SQLiteDatabase.deleteDatabase", audit)
        self.assertIn("REVIEW_AGE_MS", audit)

    def test_f118_recovery_requires_revalidation_after_consent(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8"
        )
        gate = (ROOT / "app/src/main/java/com/readroid/app/RecoveryResumeGate.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("RecoveryResumeGate.attest(source, reportHash)", activity)
        self.assertIn("RecoveryResumeGate.revalidate(proof, source, reportHash)", activity)
        self.assertIn("isRecoveryTargetCurrent(source, importedDocument,", activity)
        self.assertIn("restoreEditPlanForSession(", activity)
        self.assertIn("ApkZipIntegrity.verify(source)", gate)
        self.assertIn("ApkIntegrity.confirmExpected(source, reportedSha256)", gate)
        self.assertNotIn("Files.delete", gate)

    def test_f119_process_death_resume_and_grant_revocation_are_fail_closed(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8"
        )
        policy = (ROOT / "app/src/main/java/com/readroid/app/SavedProjectResume.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("SavedProjectResume.decide(", activity)
        self.assertIn('outState.putString("f119_process_epoch", PROCESS_EPOCH)', activity)
        self.assertIn('state.getString("f119_process_epoch")', activity)
        self.assertIn("sameProcessRecreation", policy)
        self.assertIn("SavedProjectResume.permitted(", activity)
        self.assertIn("P7ProjectHistory.hasPermission(this, uri)", activity)
        self.assertIn("selectedApkUri = null;", activity)
        self.assertIn("interrupted/unaccepted import", policy.lower())
        self.assertIn("return new Decision(null, null, accepted != null || interrupted != null, null)", policy)

    def test_f120_cold_resume_binds_saved_sha_to_actual_saf_bytes(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8"
        )
        policy = (ROOT / "app/src/main/java/com/readroid/app/SavedProjectResume.java").read_text(
            encoding="utf-8"
        )
        self.assertIn('outState.putString("f120_accepted_sha256", acceptedSha256)', activity)
        self.assertIn('state.getString("f120_accepted_sha256")', activity)
        self.assertIn("analyzeSelectedApk(resume.reimport, resume.expectedSha256)", activity)
        self.assertIn("SavedProjectResume.requireExpectedSha256(", activity)
        self.assertIn("expectedResumeSha256, copied.sha256", activity)
        self.assertIn("ApkIntegrity.confirmExpected(file, expectedResumeSha256)", activity)
        self.assertIn("validSha256(savedSha256) && permitted(accepted, checker)", policy)
        self.assertIn("return new Decision(accepted, accepted, false, savedSha256)", policy)

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
