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
    "RecoveryDirectoryGuard.java",
    "RecoveryStorageBudget.java",
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
    "F133RecoverySpaceConcurrencyInstrumentedTest",
    "F134RecoveryStageIntegrityInstrumentedTest",
    "F135StageVerificationInstrumentedTest",
    "F136PreMoveRaceInstrumentedTest",
    "F137DescriptorPinnedStageInstrumentedTest",
    "F138DirectoryCommitInstrumentedTest",
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

    def test_f130_crash_provider_is_an_independent_ci_only_app(self):
        fixture_manifest = (ROOT / "f130fixture/src/main/AndroidManifest.xml").read_text(
            encoding="utf-8")
        fixture_provider = (ROOT / "f130fixture/src/main/java/com/readroid/f130fixture/CrashProvider.java").read_text(
            encoding="utf-8")
        fixture_gradle = (ROOT / "f130fixture/build.gradle.kts").read_text(
            encoding="utf-8")
        debug_manifest = (ROOT / "app/src/debug/AndroidManifest.xml").read_text(
            encoding="utf-8")
        harness = (ROOT / "app/src/debug/java/com/readroid/app/F130CrashHarnessActivity.java").read_text(encoding="utf-8")
        script = (ROOT / "tests/f130_external_provider_death.sh").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F130ProviderDeathInstrumentedTest.java").read_text(encoding="utf-8")
        production = (ROOT / "app/src/main/AndroidManifest.xml").read_text(
            encoding="utf-8")
        settings = (ROOT / "settings.gradle.kts").read_text(encoding="utf-8")
        self.assertIn('include(":app", ":f130fixture")', settings)
        self.assertIn('android:process=":provider"', fixture_manifest)
        self.assertIn('com.readroid.f130fixture.provider', fixture_manifest)
        self.assertIn('applicationId = "com.readroid.f130fixture"', fixture_gradle)
        self.assertIn('ParcelFileDescriptor.createPipe()', fixture_provider)
        self.assertIn('app/src/debug/AndroidManifest.xml', self.workflow)
        self.assertIn('F130CrashHarnessActivity', debug_manifest)
        self.assertIn('com.readroid.f130fixture.provider', debug_manifest)
        self.assertIn('ApkImportStaging.copy(', harness)
        self.assertIn('getContentResolver().openInputStream(SOURCE)', harness)
        self.assertIn('ApkZipIntegrity.verify(', harness)
        self.assertIn('ImportActivityScope', harness)
        self.assertIn('f130ValidLocalEntriesButMissingZipEndAreRejected', tests)
        self.assertNotIn('f130RemoteProviderProcessDeathRejectsPartialApk', tests)
        self.assertIn(':f130fixture:assembleDebug', self.workflow)
        self.assertIn('adb install -r f130fixture/build/outputs/apk/debug/f130fixture-debug.apk', self.workflow)
        self.assertIn('bash tests/f130_external_provider_death.sh', self.workflow)
        self.assertIn('F130_EXTERNAL_PROVIDER_DEATH_PASS', self.workflow)
        self.assertIn('adb shell am force-stop "$FIXTURE"', script)
        self.assertIn('run_as "wc -c $ROOT/readroid_*.apk.pending"', script)
        self.assertIn('PASS_CASCADE_COLD_START', script)
        self.assertIn('adb shell am start -W -n "$APP/.MainActivity"', script)
        self.assertIn('getCacheDir()', harness)
        self.assertIn('ImportCrashJanitor', (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8"))
        self.assertIn('run_as "test -f $ROOT/readroid_F130accepted123.apk"', script)
        self.assertNotIn('pm clear', script)
        self.assertNotIn('rm -rf', script)
        for path in (
            "f130fixture/build.gradle.kts",
            "f130fixture/src/main/AndroidManifest.xml",
            "f130fixture/src/main/java/com/readroid/f130fixture/CrashProvider.java",
            "settings.gradle.kts", "app/src/debug/java/com/readroid/app/F130CrashHarnessActivity.java", "tests/f130_external_provider_death.sh",
        ):
            self.assertIn(path, self.workflow)
        self.assertNotIn('F130CrashHarnessActivity', production)
        self.assertNotIn('com.readroid.f130fixture.provider', production)
        self.assertNotIn("assembleQa", self.workflow)
        self.assertNotIn("upload-artifact@", self.workflow)

    def test_f131_repeated_real_cold_starts_preserve_history_and_vault(self):
        test_path = ROOT / "app/src/androidTest/java/com/readroid/app/F131RepeatedColdRestartInstrumentedTest.java"
        test = test_path.read_text(encoding="utf-8")
        script = (ROOT / "tests/f128_real_saf_grant.sh").read_text(encoding="utf-8")
        self.assertIn("app/src/androidTest/java/com/readroid/app/F131RepeatedColdRestartInstrumentedTest.java", self.workflow)
        self.assertIn("F131RepeatedColdRestartInstrumentedTest", test)
        self.assertIn("P7ProjectHistory.record(", test)
        self.assertIn("P7ProjectHistory.list(", test)
        self.assertIn("RecoveryVault protectedVault", test)
        self.assertIn("RecoveryResumeGate.attest(", test)
        self.assertIn("SavedProjectResume.decide(", test)
        self.assertIn("assertPendingPrunedByRealMainActivity()", test)
        self.assertIn("KeyStore.getInstance(\"AndroidKeyStore\")", test)
        self.assertIn("F131_HISTORY_CHECKPOINT_RESTART_PASS", script)
        for method in (
            "f131SeedAcceptedHistoryAndEncryptedCheckpoint",
            "f131ColdStartRoundOne", "f131ColdStartRoundTwo",
            "f131ColdStartRoundThree",
            "f131RevokedGrantStillPreservesEncryptedRecovery",
            "f131SecondRevokedRestartCleansAndPreservesRecovery",
        ):
            self.assertIn(method, script)
            self.assertIn(method, test)
        self.assertIn("adb shell am force-stop", script)
        self.assertIn("ro.kernel.qemu", script)
        self.assertNotIn("pm clear", script)
        self.assertNotIn("rm -rf", script)


    def test_f132_real_checkpoint_precommit_death_and_atomic_replacement(self):
        debug = (ROOT / "app/src/debug/AndroidManifest.xml").read_text(
            encoding="utf-8")
        harness = (ROOT / "app/src/debug/java/com/readroid/app/F132CheckpointHarnessActivity.java").read_text(encoding="utf-8")
        test = (ROOT / "app/src/androidTest/java/com/readroid/app/F132CheckpointCrashInstrumentedTest.java").read_text(encoding="utf-8")
        script = (ROOT / "tests/f132_checkpoint_process_death.sh").read_text(encoding="utf-8")
        production = (ROOT / "app/src/main/AndroidManifest.xml").read_text(
            encoding="utf-8")
        self.assertIn("F132CheckpointHarnessActivity", debug)
        self.assertNotIn("F132CheckpointHarnessActivity", production)
        self.assertIn("new RecoveryVault(vaultFolder(dir), ALIAS,", harness)
        self.assertIn("mark(dir, marker)", harness)
        self.assertIn("Thread.sleep(60000)", harness)
        self.assertIn("RecoveryVault vault = new RecoveryVault(", harness)
        self.assertIn("RecoveryResumeGate.attest(", test)
        self.assertIn("RecoveryResumeGate.revalidate(", test)
        self.assertIn("vault().loadForSource(source())", test)
        self.assertIn("AndroidKeyStore", test)
        self.assertIn("F132_CHECKPOINT_ATOMIC_CRASH_PASS", script)
        self.assertIn("adb shell am force-stop", script)
        self.assertIn("f132FirstCrashPreservesCommittedA", script)
        self.assertIn("f132SuccessfulAtomicReplacementAcceptsB", script)
        self.assertIn("f132SecondCrashPreservesCommittedB", script)
        self.assertIn("ro.kernel.qemu", script)
        self.assertNotIn("pm clear", script)
        self.assertNotIn("rm -rf", script)
        self.assertIn("bash tests/f132_checkpoint_process_death.sh", self.workflow)
        for path in ("app/src/debug/java/com/readroid/app/F132CheckpointHarnessActivity.java", "app/src/androidTest/java/com/readroid/app/F132CheckpointCrashInstrumentedTest.java", "tests/f132_checkpoint_process_death.sh"):
            self.assertIn(path, self.workflow)
        self.assertNotIn("upload-artifact@", self.workflow)
        self.assertNotIn("assembleQa", self.workflow)

    def test_f133_encrypted_checkpoint_space_and_transaction_lock(self):
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        budget = (ROOT / "app/src/main/java/com/readroid/app/RecoveryStorageBudget.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F133RecoverySpaceConcurrencyInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("RecoveryStorageBudget.requireStagingRoom(freeSpace, encoded.length)", vault)
        self.assertEqual(2, vault.count(
            "RecoveryStorageBudget.requireStagingRoom(freeSpace, encoded.length)"))
        self.assertIn("new StatFs(directory.getAbsolutePath()).getAvailableBytes()", budget)
        self.assertIn("SAFETY_RESERVE", budget)
        self.assertIn("AtomicLong free", tests)
        self.assertIn("f133InsufficientRoomBeforeStagingCannotChangeOldCheckpoint", tests)
        self.assertIn("f133StorageDropsAfterFsyncBeforeMoveOldVersionSurvives", tests)
        self.assertIn("f133ConcurrentReadWaitsForFailedSaveAndGetsLastGoodPlan", tests)
        self.assertIn("f133ConcurrentClearWaitsForFailedSaveThenRemovesOnlyVault", tests)
        self.assertIn("f133RejectsUnknownSpaceAndImpossibleStageBudgets", tests)
        self.assertIn("workers.shutdownNow()", tests)
        self.assertIn("vault().clear()", (ROOT / "app/src/androidTest/java/com/readroid/app/F132CheckpointCrashInstrumentedTest.java").read_text(encoding="utf-8"))
        self.assertIn("app/src/main/java/com/readroid/app/RecoveryStorageBudget.java", self.workflow)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F133RecoverySpaceConcurrencyInstrumentedTest.java", self.workflow)
        self.assertNotIn("pm clear", tests)
        self.assertNotIn("rm -rf", tests)

    def test_f134_stage_integrity_check_rejects_corrupted_or_symlinked_stages(self):
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F134RecoveryStageIntegrityInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("verifyStagedCiphertext(temporary, encoded, stageReadObserver);", vault)
        self.assertIn("OsConstants.O_NOFOLLOW", vault)
        self.assertIn("Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)", vault)
        self.assertIn("mismatch |= chunk[i] ^ expected[offset + i]", vault)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F134RecoveryStageIntegrityInstrumentedTest.java", self.workflow)
        self.assertIn("com.readroid.app.F134RecoveryStageIntegrityInstrumentedTest",
                      self.workflow)
        for method in (
            "f134TruncatedFsyncedStageCannotReplaceValidCiphertext",
            "f134SameLengthBitFlipCannotReplaceValidCiphertext",
            "f134DeletedTemporaryCannotEraseOldRecovery",
            "f134SymlinkToMatchingBytesMustNeverBePromoted",
            "f134ReaderCannotSeeCorruptedStageDuringConcurrentSave",
        ):
            self.assertIn(method, tests)
        self.assertIn("Files.createSymbolicLink(stage.toPath(), replacement.toPath())", tests)
        self.assertIn("threads.shutdownNow()", tests)
        self.assertIn("vault.loadForSource(original)", tests)
        self.assertNotIn("pm clear", tests)
        self.assertNotIn("rm -rf", tests)

    def test_f135_verification_interruption_and_multiple_real_process_deaths(self):
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        debug = (ROOT / "app/src/debug/AndroidManifest.xml").read_text(
            encoding="utf-8")
        harness = (ROOT / "app/src/debug/java/com/readroid/app/F135VerifierCrashHarnessActivity.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F135StageVerificationInstrumentedTest.java").read_text(encoding="utf-8")
        external = (ROOT / "app/src/androidTest/java/com/readroid/app/F135VerifierCrashInstrumentedTest.java").read_text(encoding="utf-8")
        script = (ROOT / "tests/f135_verifier_process_death.sh").read_text(encoding="utf-8")
        production = (ROOT / "app/src/main/AndroidManifest.xml").read_text(
            encoding="utf-8")
        self.assertIn("StageReadObserver", vault)
        self.assertIn("observer.onChunk(offset, expected.length)", vault)
        self.assertIn("verifyStagedCiphertext(temporary, encoded, stageReadObserver)", vault)
        self.assertIn("F135VerifierCrashHarnessActivity", debug)
        self.assertNotIn("F135VerifierCrashHarnessActivity", production)
        self.assertIn("new RecoveryVault(folder(), KEY,", harness)
        self.assertIn("verified < 8192 || verified >= total", harness)
        self.assertIn("Thread.sleep(60000)", harness)
        self.assertIn("f135InterruptMidVerificationCannotCommitCheckpoint", tests)
        self.assertIn("f135ConcurrentReaderWaitsForAbortedVerifier", tests)
        self.assertIn("f135FirstMidVerificationCrashPreservesA", external)
        self.assertIn("f135SecondMidVerificationCrashPreservesA", external)
        self.assertIn("f135CommittedBStillDecryptsAfterTwoCrashes", external)
        self.assertIn("F135_VERIFIER_PROCESS_DEATH_PASS", script)
        self.assertIn("adb shell am force-stop", script)
        self.assertIn("ro.kernel.qemu", script)
        self.assertIn("bash tests/f135_verifier_process_death.sh", self.workflow)
        self.assertIn("app/src/debug/java/com/readroid/app/F135VerifierCrashHarnessActivity.java", self.workflow)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F135StageVerificationInstrumentedTest.java", self.workflow)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F135VerifierCrashInstrumentedTest.java", self.workflow)
        self.assertIn("tests/f135_verifier_process_death.sh", self.workflow)
        self.assertNotIn("pm clear", script)
        self.assertNotIn("rm -rf", script)

    def test_f136_premove_race_guard_rechecks_bytes_and_inode(self):
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F136PreMoveRaceInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("interface BeforeMove", vault)
        self.assertIn("beforeMove.run(temporary);", vault)
        self.assertIn("verifyStagedCiphertext(temporary, encoded, (verified, total) -> {});", vault)
        self.assertIn("final StageIdentity verifiedIdentity = stageIdentity(temporary)", vault)
        self.assertIn("verifiedIdentity.sameFile(stageIdentity(temporary))", vault)
        self.assertIn("Os.lstat(staged.getAbsolutePath())", vault)
        self.assertIn("Files.move(temporary.toPath()", vault)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F136PreMoveRaceInstrumentedTest.java", self.workflow)
        self.assertIn("com.readroid.app.F136PreMoveRaceInstrumentedTest", self.workflow)
        for method in (
            "f136BitFlipBetweenVerifyAndMoveCannotCommit",
            "f136TruncationBetweenVerifyAndMoveCannotCommit",
            "f136DeletionBetweenVerifyAndMoveCannotCommit",
            "f136SameBytesNewInodeBetweenVerifyAndMoveRejected",
            "f136SymlinkSwapWithMatchingBytesBetweenVerifyAndMoveRejected",
            "f136InterruptedBeforeMovePreservesLastGoodCheckpoint",
            "f136UnmodifiedStageStillAtomicallyReplacesCheckpoint",
        ):
            self.assertIn(method, tests)
        self.assertIn("KeyStore.getInstance(\"AndroidKeyStore\")", tests)
        self.assertNotIn("rm -rf", tests)
        self.assertNotIn("pm clear", tests)

    def test_emulator_crash_harnesses_report_install_and_pid_failures(self):
        for path in (
            "tests/f130_external_provider_death.sh", "tests/f132_checkpoint_process_death.sh", "tests/f135_verifier_process_death.sh",
        ):
            script = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn("install_ci_apk()", script)
            self.assertIn("install attempt $attempt failed", script)
            self.assertIn("unexpected command failure line $LINENO", script)
            self.assertIn("getprop ro.kernel.qemu", script)
            self.assertNotIn("pm clear", script)
            self.assertNotIn("rm -rf", script)
            self.assertNotIn("adb uninstall", script)
            self.assertIn(path, self.workflow)

    def test_f137_pins_stage_descriptor_and_rejects_hardlinks(self):
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F137DescriptorPinnedStageInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("OsConstants.O_NOFOLLOW", vault)
        self.assertIn("OsConstants.O_CLOEXEC", vault)
        self.assertIn("stageIdentity(in.getFD())", vault)
        self.assertIn("Os.fstat(openDescriptor)", vault)
        self.assertIn("Os.lstat(staged.getAbsolutePath())", vault)
        self.assertIn("requireSingleStageLinkCount(stat.st_nlink)", vault)
        self.assertIn("!opened.sameFile(stageIdentity(stage))", vault)
        self.assertIn("!opened.sameFile(stageIdentity(in.getFD()))", vault)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F137DescriptorPinnedStageInstrumentedTest.java", self.workflow)
        self.assertIn("com.readroid.app.F137DescriptorPinnedStageInstrumentedTest",
                      self.workflow)
        for method in (
            "f137SameBytesDifferentInodeDuringReadRejected",
            "f137SymlinkReplacementDuringReadRejected",
            "f137HardlinkCreatedDuringReadRejected",
            "f137HardlinkAfterFirstVerificationRejected",
            "f137HardlinkBeforeFirstVerificationRejected",
            "f137UnaliasedStageStillCommitsAndDecrypts",
            "f137LinkCountPolicyRejectsAliasesWithoutKernelSupport",
        ):
            self.assertIn(method, tests)
        self.assertIn("Files.createLink(", tests)
        self.assertIn("Files.createSymbolicLink(", tests)
        self.assertIn("Assume.assumeTrue(", tests)
        self.assertIn("assumeHardlinksSupported(f)", tests)
        self.assertIn("RecoveryVault.requireSingleStageLinkCount", tests)
        self.assertIn("requireSingleStageLinkCount(stat.st_nlink)", vault)
        self.assertIn("KeyStore.getInstance(\"AndroidKeyStore\")", tests)
        self.assertNotIn("pm clear", tests)
        self.assertNotIn("rm -rf", tests)

    def test_f138_pinned_private_directory_and_durable_atomic_commit(self):
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        guard = (ROOT / "app/src/main/java/com/readroid/app/RecoveryDirectoryGuard.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F138DirectoryCommitInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("RecoveryDirectoryGuard.open(storage)", vault)
        self.assertIn("pinnedDirectory.requireSameDirectory()", vault)
        self.assertIn("pinnedDirectory.syncAfterRename()", vault)
        self.assertIn("StageIdentity promoted = stageIdentity(new File(storage, FILE_NAME))", vault)
        self.assertIn("committed = true;", vault)
        self.assertIn("OsConstants.O_DIRECTORY", guard)
        self.assertIn("OsConstants.O_NOFOLLOW", guard)
        self.assertIn("Os.fstat(descriptor)", guard)
        self.assertIn("Os.lstat(root.getAbsolutePath())", guard)
        self.assertIn("Os.fsync(descriptor)", guard)
        self.assertIn("Os.close(descriptor)", guard)
        for method in (
            "f138RejectsSymlinkedVaultDirectoryBeforeStaging",
            "f138DirectoryRebindingBeforeRenameIsRejected",
            "f138PinnedDirectoryDetectsRebindingIndependently",
            "f138ValidAtomicMoveKeepsStageInodeAndDecrypts",
            "f138DirectoryFdSyncSucceedsOnPrivateEmulatorStorage",
        ):
            self.assertIn(method, tests)
        self.assertIn("app/src/main/java/com/readroid/app/RecoveryDirectoryGuard.java", self.workflow)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F138DirectoryCommitInstrumentedTest.java", self.workflow)
        self.assertIn("com.readroid.app.F138DirectoryCommitInstrumentedTest", self.workflow)
        self.assertNotIn("pm clear", tests)
        self.assertNotIn("rm -rf", tests)

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
