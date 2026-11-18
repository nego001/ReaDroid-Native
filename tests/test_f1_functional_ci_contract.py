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
    "ApkImportStaging.java",
    "ImportWorkerLane.java",
    "ImportActivityScope.java",
    "ImportCrashJanitor.java",
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
    "ApkImportStagingInstrumentedTest",
    "ImportConcurrencyInstrumentedTest",
    "ImportWorkerLaneInstrumentedTest",
    "ImportActivityScopeInstrumentedTest",
    "ImportCrashJanitorInstrumentedTest",
    "ApkZipIntegrityInstrumentedTest",
    "ApkCacheAdmissionInstrumentedTest",
    "SavedProjectResumeInstrumentedTest",
    "F129RealProviderInstrumentedTest",
    "F130ProviderDeathInstrumentedTest",
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
        staging = (ROOT / "app/src/main/java/com/readroid/app/ApkImportStaging.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("ImportCacheAudit.track(staged)", staging)
        self.assertIn("ImportCacheAudit.release(staged)", staging)
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

    def test_f121_saf_failure_transaction_owns_and_cleans_unaccepted_cache(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8"
        )
        importer = (ROOT / "app/src/main/java/com/readroid/app/ApkImportStaging.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("ApkImportStaging.copy(", activity)
        self.assertIn("getContentResolver().openInputStream(uri)", activity)
        self.assertIn('File.createTempFile("readroid_", ".apk.pending", privateCache)', importer)
        self.assertIn("ImportCacheAudit.track(staged)", importer)
        self.assertIn("Files.deleteIfExists(staged.toPath())", importer)
        self.assertIn("ImportCacheAudit.release(staged)", importer)
        self.assertIn("if (!complete)", importer)
        self.assertIn("return new Result(candidate, copied)", importer)

    def test_f122_stale_import_aborts_inside_provider_zip_index_and_commit(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8"
        )
        staging = (ROOT / "app/src/main/java/com/readroid/app/ApkImportStaging.java").read_text(
            encoding="utf-8"
        )
        preflight = (ROOT / "app/src/main/java/com/readroid/app/ApkImportPreflight.java").read_text(
            encoding="utf-8"
        )
        admission = (ROOT / "app/src/main/java/com/readroid/app/ApkCacheAdmission.java").read_text(
            encoding="utf-8"
        )
        index = (ROOT / "app/src/main/java/com/readroid/app/ApkDiskIndex.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("importSessions.begin()", activity)
        self.assertIn("importSessions.invalidate()", activity)
        self.assertIn("analyze(uri, expectedResumeSha256, importToken)", activity)
        self.assertIn("!importToken.isActive()", activity)
        self.assertIn("ApkZipIntegrity.verify(file, importToken)", activity)
        self.assertIn("ApkDiskIndex.build(file, candidate, importToken)", activity)
        self.assertIn("ApkCacheAdmission.verify(file, copied.sizeBytes, copied.sha256, importToken)", activity)
        self.assertIn("ApkImportPreflight.copyAndHash(input, output, space, token)", staging)
        self.assertIn("ExportSessionGuard.check(token)", preflight)
        self.assertIn("ApkIntegrity.confirmExpected(cache, copiedSha256, token)", admission)
        self.assertIn("ExportSessionGuard.check(token)", index)

    def test_f123_saf_import_lane_is_bounded_and_separate_from_export_recovery(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8"
        )
        lane = (ROOT / "app/src/main/java/com/readroid/app/ImportWorkerLane.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("private final ImportWorkerLane importWorkers", activity)
        self.assertIn("importWorkers.submit(() ->", activity)
        self.assertIn("importWorkers.shutdownNow()", activity)
        self.assertIn("executor.shutdownNow()", activity)
        self.assertIn("importToken.requireActive()", activity)
        self.assertIn("importSessions.begin()", activity)
        self.assertIn("MAX_RUNNING = 2", lane)
        self.assertIn("MAX_PENDING = 1", lane)
        self.assertIn("new ArrayBlockingQueue<>(MAX_PENDING)", lane)
        self.assertIn("pool.getQueue().poll()", lane)
        self.assertIn("pool.getQueue().offer(latest)", lane)
        self.assertNotIn("newCachedThreadPool", lane)

    def test_f124_saturation_notice_only_for_live_latest_import(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8"
        )
        lane = (ROOT / "app/src/main/java/com/readroid/app/ImportWorkerLane.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("ImportWorkerLane.Submission admission = importWorkers.submit(", activity)
        self.assertIn("wasQueued.set(admission.waiting)", activity)
        self.assertIn("AGUARDANDO LEITURA SAF", activity)
        self.assertIn("Leitura SAF retomada", activity)
        self.assertIn("!importToken.isActive()", activity)
        self.assertIn("sequence != analysisSequence", activity)
        self.assertIn("workers.getQueue().contains(task)", lane)
        self.assertIn("synchronized (admissionLock)", lane)
        self.assertIn("new ArrayBlockingQueue<>(MAX_PENDING)", lane)
        self.assertNotIn("newCachedThreadPool", lane)

    def test_f125_activity_scope_only_cleans_its_own_uncommitted_imports(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8"
        )
        scope = (ROOT / "app/src/main/java/com/readroid/app/ImportActivityScope.java").read_text(
            encoding="utf-8"
        )
        staging = (ROOT / "app/src/main/java/com/readroid/app/ApkImportStaging.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("importScope = new ImportActivityScope(getCacheDir())", activity)
        self.assertIn("if (importScope != null) importScope.close()", activity)
        self.assertIn("importSessions.invalidate()", activity)
        self.assertIn("importScope.release(candidate.file)", activity)
        self.assertIn("importScope.release(file)", activity)
        self.assertIn("importToken, importScope", activity)
        self.assertIn("if (scope != null) scope.track(staged)", staging)
        self.assertIn("if (scope != null) scope.release(staged)", staging)
        self.assertIn("LinkOption.NOFOLLOW_LINKS", scope)
        self.assertIn("pending.add(path)", scope)
        self.assertIn("MAX_OWNED = 4", scope)
        self.assertNotIn("walkFileTree", scope)
        self.assertNotIn("deleteDatabase", scope)


    def test_f126_process_death_only_prunes_unfinished_private_copy(self):
        staging = (ROOT / "app/src/main/java/com/readroid/app/ApkImportStaging.java").read_text(
            encoding="utf-8")
        scope = (ROOT / "app/src/main/java/com/readroid/app/ImportActivityScope.java").read_text(
            encoding="utf-8")
        janitor = (ROOT / "app/src/main/java/com/readroid/app/ImportCrashJanitor.java").read_text(
            encoding="utf-8")
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(
            encoding="utf-8")
        self.assertIn('".apk.pending"', staging)
        self.assertIn("StandardCopyOption.ATOMIC_MOVE", staging)
        self.assertIn("scope.promote(staged, token)", staging)
        self.assertIn("StandardCopyOption.ATOMIC_MOVE", scope)
        self.assertIn("pending.add(destination)", scope)
        self.assertIn("COLD_IMPORT_SWEEP.compareAndSet(false, true)", activity)
        self.assertIn("ImportCrashJanitor.sweep(getCacheDir())", activity)
        self.assertIn('name.endsWith(".apk.pending")', janitor)
        self.assertIn("LinkOption.NOFOLLOW_LINKS", janitor)
        self.assertNotIn("walkFileTree", janitor)
        self.assertNotIn("SQLiteDatabase.deleteDatabase", janitor)
        self.assertNotIn("REPLACE_EXISTING", staging)
        self.assertNotIn("REPLACE_EXISTING", scope)


    def test_f127_real_process_death_probe_runs_on_both_emulators(self):
        probe = ROOT / "tests/f127_android_process_death.sh"
        script = probe.read_text(encoding="utf-8")
        self.assertIn("bash tests/f127_android_process_death.sh", self.workflow)
        self.assertIn("F127_REAL_FORCE_STOP_PASS", self.workflow)
        self.assertIn("adb shell am force-stop", script)
        self.assertIn("adb shell am start -W -n", script)
        self.assertIn("run-as $PKG", script)
        self.assertIn('adb install -r "$DEBUG_APK"', script)
        self.assertIn('adb shell pm path "$PKG"', script)
        self.assertIn("test ! -e cache/$PARTIAL", script)
        self.assertIn("test -f cache/$PARTIAL", script)
        self.assertIn("pid_before", script)
        self.assertIn("pid_after", script)
        self.assertIn("readroid_F127accepted123.apk", script)
        self.assertIn("readroid_F127partial123.apk.pending", script)
        self.assertNotIn("adb uninstall", script)
        self.assertNotIn("pm clear", script)
        self.assertNotIn("rm -rf", script)

    def test_f128_real_system_saf_grant_survives_process_then_revokes(self):
        script = (ROOT / "tests/f128_real_saf_grant.sh").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F128RealSafGrantInstrumentedTest.java").read_text(encoding="utf-8")
        gradle = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        self.assertIn("bash tests/f128_real_saf_grant.sh", self.workflow)
        self.assertIn("F128_REAL_SAF_PERMISSION_PASS", self.workflow)
        self.assertIn("F128RealSafGrantInstrumentedTest.java", self.workflow)
        self.assertIn("uiautomator:2.3.0", gradle)
        self.assertIn("Intent.ACTION_OPEN_DOCUMENT", tests)
        self.assertIn("getPersistedUriPermissions()", tests)
        self.assertIn("releasePersistableUriPermission", tests)
        self.assertIn("SavedProjectResume.decide(", tests)
        self.assertIn("P7ProjectHistory.hasPermission", tests)
        self.assertIn("adb shell am force-stop", script)
        self.assertIn("f128ObtainPersistedGrantFromSystemPicker", script)
        self.assertIn("f128AfterColdStartRevokeRealPersistedGrant", script)
        self.assertIn("f128NextProcessRejectsRevokedGrant", script)
        self.assertNotIn("pm clear", script)
        self.assertNotIn("adb uninstall", script)
        self.assertNotIn("rm -rf", script)

    def test_f129_faulty_provider_only_in_test_apk_and_real_resolver_guard(self):
        manifest = (ROOT / "app/src/androidTest/AndroidManifest.xml").read_text(encoding="utf-8")
        provider = (ROOT / "app/src/androidTest/java/com/readroid/app/F129FaultyContentProvider.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F129RealProviderInstrumentedTest.java").read_text(encoding="utf-8")
        production_manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(
            encoding="utf-8")
        self.assertIn("app/src/androidTest/AndroidManifest.xml", self.workflow)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F129FaultyContentProvider.java", self.workflow)
        self.assertIn("F129RealProviderInstrumentedTest", self.workflow)
        self.assertIn("F129FaultyContentProvider", manifest)
        self.assertIn("ParcelFileDescriptor.createPipe()", provider)
        self.assertIn("F129FaultyContentProvider", tests)
        self.assertIn("resolver().openInputStream", tests)
        self.assertIn("ApkImportStaging.copy(", tests)
        self.assertIn("scope.close()", tests)
        self.assertIn("ApkZipIntegrity.verify(promoted)", tests)
        self.assertNotIn("F129FaultyContentProvider", production_manifest)
        self.assertNotIn("android.permission.MANAGE_DOCUMENTS", production_manifest)

    def test_f130_crash_provider_is_remote_and_only_in_test_manifest(self):
        manifest = (ROOT / "app/src/androidTest/AndroidManifest.xml").read_text(encoding="utf-8")
        source = (ROOT / "app/src/androidTest/java/com/readroid/app/F130CrashContentProvider.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F130ProviderDeathInstrumentedTest.java").read_text(encoding="utf-8")
        production = (ROOT / "app/src/main/AndroidManifest.xml").read_text(
            encoding="utf-8")
        self.assertIn('android:process=":f130crash"', manifest)
        self.assertIn("F130CrashContentProvider", manifest)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F130CrashContentProvider.java", self.workflow)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F130ProviderDeathInstrumentedTest.java", self.workflow)
        self.assertIn("F130ProviderDeathInstrumentedTest", self.workflow)
        self.assertIn("ParcelFileDescriptor.createPipe()", source)
        self.assertIn("android.os.Process.killProcess", source)
        self.assertIn("getContentResolver().openInputStream", tests)
        self.assertIn("ApkImportStaging.copy(", tests)
        self.assertIn("ApkZipIntegrity.verify(", tests)
        self.assertIn("ImportActivityScope", tests)
        self.assertNotIn("F130CrashContentProvider", production)
        self.assertNotIn("android.permission.MANAGE_DOCUMENTS", production)

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
