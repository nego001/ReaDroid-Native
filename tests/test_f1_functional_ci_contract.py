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
    "F139PostMoveBoundaryInstrumentedTest",
    "F140PostSyncIntegrityInstrumentedTest",
    "F141FinalReadInstrumentedTest",
    "F142PostAttestationInstrumentedTest",
    "F143RecoverySaveBindingInstrumentedTest",
    "F144RecoverySourceBindingInstrumentedTest",
    "F145PostCommitSourceInstrumentedTest",
    "F146RecoveryAcknowledgementInstrumentedTest",
    "F147RecoveryRestoreConsentInstrumentedTest",
    "F149RecoveryDialogInstrumentedTest",
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
        # F1.41 API29: activity startup may precede pidof observation.
        self.assertIn("for attempt in $(seq 1 15); do", script)
        self.assertIn('[[ -n "$new_owner_pid" && "$new_owner_pid" != "$owner_pid" ]]', script)
        self.assertIn('if [[ -z "$new_owner_pid" || "$new_owner_pid" == "$owner_pid" ]]', script)
        self.assertIn('fail "consumer process did not restart after cascading provider death"', script)
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
        self.assertIn("File promotedCheckpoint = new File(storage, FILE_NAME);", vault)
        self.assertIn("StageIdentity promoted = stageIdentity(promotedCheckpoint)", vault)
        self.assertIn("committed = true;", vault)
        self.assertIn("OsConstants.O_RDONLY", guard)
        self.assertIn("OsConstants.S_ISDIR(stat.st_mode)", guard)
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

    def test_f139_real_process_termination_after_atomic_move_before_fsync(self):
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        manifest = (ROOT / "app/src/debug/AndroidManifest.xml").read_text(
            encoding="utf-8")
        production = (ROOT / "app/src/main/AndroidManifest.xml").read_text(
            encoding="utf-8")
        harness = (ROOT / "app/src/debug/java/com/readroid/app/F139PostRenameCrashHarnessActivity.java").read_text(encoding="utf-8")
        unit = (ROOT / "app/src/androidTest/java/com/readroid/app/F139PostMoveBoundaryInstrumentedTest.java").read_text(encoding="utf-8")
        recovery = (ROOT / "app/src/androidTest/java/com/readroid/app/F139PostRenameCrashInstrumentedTest.java").read_text(encoding="utf-8")
        script = (ROOT / "tests/f139_postrename_process_death.sh").read_text(encoding="utf-8")
        self.assertIn("interface AfterAtomicMove", vault)
        self.assertIn("afterAtomicMove.run(new File(storage, FILE_NAME));", vault)
        move = vault.index("Files.move(temporary.toPath(), new File(storage, FILE_NAME).toPath()")
        committed = vault.index("committed = true;", move)
        hook = vault.index("afterAtomicMove.run(new File(storage, FILE_NAME));", committed)
        sync = vault.index("pinnedDirectory.syncAfterRename();", hook)
        self.assertLess(move, committed)
        self.assertLess(committed, hook)
        self.assertLess(hook, sync)
        self.assertIn("F139PostRenameCrashHarnessActivity", manifest)
        self.assertNotIn("F139PostRenameCrashHarnessActivity", production)
        self.assertIn("new RecoveryVault(folder(), ALIAS,", harness)
        self.assertIn("Thread.sleep(60000)", harness)
        self.assertIn("PROMOTED_B_PRE_SYNC", harness)
        self.assertIn("PROMOTED_C_PRE_SYNC", harness)
        self.assertIn("f139PostMoveFailureCannotRollbackAlreadyPromotedB", unit)
        self.assertIn("f139NormalPostMoveBoundaryStillSyncsAndRecovers", unit)
        self.assertIn("f139FirstPostRenameKillRecoversPromotedB", recovery)
        self.assertIn("f139SecondPostRenameKillRecoversPromotedC", recovery)
        self.assertIn("f139CleanCommitAfterTwoCrashesRecoversD", recovery)
        self.assertIn("ro.kernel.qemu", script)
        self.assertIn("adb shell am force-stop", script)
        self.assertIn("F139_POSTRENAME_PROCESS_DEATH_PASS", script)
        self.assertIn("bash tests/f139_postrename_process_death.sh", self.workflow)
        for path in ("app/src/debug/java/com/readroid/app/F139PostRenameCrashHarnessActivity.java", "app/src/androidTest/java/com/readroid/app/F139PostMoveBoundaryInstrumentedTest.java", "app/src/androidTest/java/com/readroid/app/F139PostRenameCrashInstrumentedTest.java", "tests/f139_postrename_process_death.sh"):
            self.assertIn(path, self.workflow)
        self.assertIn("com.readroid.app.F139PostMoveBoundaryInstrumentedTest",
                      self.workflow)
        self.assertNotIn("pm clear", script)
        self.assertNotIn("rm -rf", script)
        self.assertNotIn("upload-artifact@", self.workflow)

    def test_f140_post_fsync_crashes_and_final_ciphertext_attestation(self):
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        debug_manifest = (ROOT / "app/src/debug/AndroidManifest.xml").read_text(
            encoding="utf-8")
        production_manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(
            encoding="utf-8")
        debug = (ROOT / "app/src/debug/java/com/readroid/app/F140PostSyncCrashHarnessActivity.java").read_text(encoding="utf-8")
        unit = (ROOT / "app/src/androidTest/java/com/readroid/app/F140PostSyncIntegrityInstrumentedTest.java").read_text(encoding="utf-8")
        recovery = (ROOT / "app/src/androidTest/java/com/readroid/app/F140PostSyncCrashInstrumentedTest.java").read_text(encoding="utf-8")
        script = (ROOT / "tests/f140_postsync_process_death.sh").read_text(encoding="utf-8")
        self.assertIn("interface AfterDirectorySync", vault)
        self.assertIn("afterDirectorySync.run(promotedCheckpoint)", vault)
        sync = vault.index("pinnedDirectory.syncAfterRename();")
        hook = vault.index("afterDirectorySync.run(promotedCheckpoint)", sync)
        stat = vault.index("StageIdentity promoted = stageIdentity(promotedCheckpoint)", hook)
        verify = vault.index("verifyStagedCiphertext(promotedCheckpoint, encoded,", stat)
        self.assertLess(sync, hook)
        self.assertLess(hook, stat)
        self.assertLess(stat, verify)
        self.assertIn("F140PostSyncCrashHarnessActivity", debug_manifest)
        self.assertNotIn("F140PostSyncCrashHarnessActivity", production_manifest)
        self.assertIn("Thread.sleep(60000)", debug)
        self.assertIn("checkpoint -> {}, promoted -> {", debug)
        self.assertIn("PROMOTED_B_POST_SYNC", debug)
        self.assertIn("PROMOTED_C_POST_SYNC", debug)
        for method in (
            "f140PostSyncExceptionLeavesNewCheckpointRecoverable",
            "f140PostSyncSameLengthBitFlipIsDetected",
            "f140PostSyncDifferentInodeWithSameBytesIsRejected",
            "f140NormalSyncedPromotionIsFullyAttested",
        ):
            self.assertIn(method, unit)
        for method in (
            "f140FirstPostSyncKillRecoversPromotedB",
            "f140SecondPostSyncKillRecoversPromotedC",
            "f140CleanCommitAfterTwoCrashesRecoversD",
        ):
            self.assertIn(method, recovery)
        self.assertIn("ro.kernel.qemu", script)
        self.assertIn("adb shell am force-stop", script)
        self.assertIn("F140_POSTSYNC_PROCESS_DEATH_PASS", script)
        self.assertIn("bash tests/f140_postsync_process_death.sh", self.workflow)
        self.assertIn("com.readroid.app.F140PostSyncIntegrityInstrumentedTest",
                      self.workflow)
        for path in ("app/src/debug/java/com/readroid/app/F140PostSyncCrashHarnessActivity.java", "app/src/androidTest/java/com/readroid/app/F140PostSyncIntegrityInstrumentedTest.java", "app/src/androidTest/java/com/readroid/app/F140PostSyncCrashInstrumentedTest.java", "tests/f140_postsync_process_death.sh"):
            self.assertIn(path, self.workflow)
        self.assertNotIn("pm clear", script)
        self.assertNotIn("rm -rf", script)
        self.assertNotIn("upload-artifact@", self.workflow)

    def test_f141_mid_final_read_crash_and_recovery_are_emulator_only(self):
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        manifest = (ROOT / "app/src/debug/AndroidManifest.xml").read_text(encoding="utf-8")
        prod = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        harness = (ROOT / "app/src/debug/java/com/readroid/app/F141FinalReadCrashHarnessActivity.java").read_text(encoding="utf-8")
        unit = (ROOT / "app/src/androidTest/java/com/readroid/app/F141FinalReadInstrumentedTest.java").read_text(encoding="utf-8")
        recovery = (ROOT / "app/src/androidTest/java/com/readroid/app/F141FinalReadCrashInstrumentedTest.java").read_text(encoding="utf-8")
        script = (ROOT / "tests/f141_final_read_process_death.sh").read_text(encoding="utf-8")
        self.assertIn("private final StageReadObserver finalReadObserver;", vault)
        self.assertIn("finalReadObserver);", vault)
        self.assertIn("F141FinalReadCrashHarnessActivity", manifest)
        self.assertNotIn("F141FinalReadCrashHarnessActivity", prod)
        self.assertIn("verified == 8192", harness)
        self.assertIn("total > verified", harness)
        self.assertIn("Thread.sleep(60000)", harness)
        for name in (
            "f141InterruptedFinalReadKeepsPromotedBRecoverable",
            "f141UnreadCiphertextTamperingIsDetected",
            "f141NormalFinalReadCompletesAllChunks",
        ):
            self.assertIn(name, unit)
        for name in (
            "f141FirstFinalReadKillRecoversPromotedB",
            "f141SecondFinalReadKillRecoversPromotedC",
            "f141NormalSaveAfterTwoCrashesRecoversD",
        ):
            self.assertIn(name, recovery)
        for check in ("ro.kernel.qemu", "adb shell am force-stop",
                      "F141_FINAL_READ_PROCESS_DEATH_PASS", "old_pid=", "new_pid="):
            self.assertIn(check, script)
        for path in (
            "app/src/debug/java/com/readroid/app/F141FinalReadCrashHarnessActivity.java",
            "app/src/androidTest/java/com/readroid/app/F141FinalReadInstrumentedTest.java",
            "app/src/androidTest/java/com/readroid/app/F141FinalReadCrashInstrumentedTest.java",
            "tests/f141_final_read_process_death.sh",
        ):
            self.assertIn(path, self.workflow)
        self.assertIn("bash tests/f141_final_read_process_death.sh", self.workflow)
        self.assertNotIn("pm clear", script)
        self.assertNotIn("rm -rf", script)
        self.assertNotIn("upload-artifact@", self.workflow)

    def test_f142_completed_ciphertext_attestation_before_acknowledgement(self):
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        manifest = (ROOT / "app/src/debug/AndroidManifest.xml").read_text(encoding="utf-8")
        production = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        harness = (ROOT / "app/src/debug/java/com/readroid/app/F142PostAttestationCrashHarnessActivity.java").read_text(encoding="utf-8")
        unit = (ROOT / "app/src/androidTest/java/com/readroid/app/F142PostAttestationInstrumentedTest.java").read_text(encoding="utf-8")
        recovered = (ROOT / "app/src/androidTest/java/com/readroid/app/F142PostAttestationCrashInstrumentedTest.java").read_text(encoding="utf-8")
        script = (ROOT / "tests/f142_post_attestation_process_death.sh").read_text(encoding="utf-8")
        verify = vault.index("verifyStagedCiphertext(promotedCheckpoint, encoded,\\n                finalReadObserver);".replace("\\n", "\n"))
        callback = vault.index("afterFinalAttestation.run(promotedCheckpoint);", verify)
        cleanup = vault.index("} finally {", callback)
        self.assertLess(verify, callback)
        self.assertLess(callback, cleanup)
        self.assertIn("interface AfterFinalAttestation", vault)
        self.assertIn("private final AfterFinalAttestation afterFinalAttestation;", vault)
        self.assertIn("finalReadObserver, checkpoint -> {});", vault)
        self.assertIn("F142PostAttestationCrashHarnessActivity", manifest)
        self.assertNotIn("F142PostAttestationCrashHarnessActivity", production)
        self.assertIn("last[0] != totalSeen[0]", harness)
        self.assertIn("Thread.sleep(60000)", harness)
        self.assertIn('status("ATTESTED_" + next)', harness)
        for case in (
            "f142PostAttestationExceptionKeepsPromotedBRecoverable",
            "f142SuccessfulAttestationPrecedesSaveReturn",
            "f142FinalReadFailurePreventsAttestationCallback",
        ):
            self.assertIn(case, unit)
        for case in (
            "f142FirstPostAttestationKillRecoversPromotedB",
            "f142SecondPostAttestationKillRecoversPromotedC",
            "f142NormalSaveAfterTwoCrashesRecoversD",
        ):
            self.assertIn(case, recovered)
        for check in (
            "ro.kernel.qemu", "adb shell am force-stop",
            "F142_POST_ATTESTATION_PROCESS_DEATH_PASS", "old_pid=", "new_pid=",
            "kill_after_attestation A", "kill_after_attestation B",
        ):
            self.assertIn(check, script)
        for path in (
            "app/src/debug/java/com/readroid/app/F142PostAttestationCrashHarnessActivity.java",
            "app/src/androidTest/java/com/readroid/app/F142PostAttestationInstrumentedTest.java",
            "app/src/androidTest/java/com/readroid/app/F142PostAttestationCrashInstrumentedTest.java",
            "tests/f142_post_attestation_process_death.sh",
        ):
            self.assertIn(path, self.workflow)
        self.assertIn("bash tests/f142_post_attestation_process_death.sh", self.workflow)
        self.assertNotIn("pm clear", script)
        self.assertNotIn("rm -rf", script)
        self.assertNotIn("upload-artifact@", self.workflow)

    def test_f143_recovery_save_consent_and_checkpoint_commit_are_bound(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8")
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        suite = (ROOT / "app/src/androidTest/java/com/readroid/app/F143RecoverySaveBindingInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("private final ExportSessionGuard recoverySaveSessions", activity)
        self.assertIn("final File sourceAtPrompt = currentApk;", activity)
        self.assertIn("final Map<String, String> editsAtPrompt =", activity)
        self.assertIn("isRecoverySaveRequestCurrent(sourceAtPrompt, documentAtPrompt,", activity)
        self.assertIn("RecoveryResumeGate.attest(sourceAtPrompt, hashAtPrompt);", activity)
        self.assertIn("new RecoveryVault(this).save(sourceAtPrompt, editsAtPrompt,", activity)
        self.assertIn("token, hashAtPrompt, checkpointAtOffer);", activity)
        self.assertIn("recoverySaveSessions.invalidate();", activity)
        self.assertIn("snapshotAtPrompt.equals(explorerView.getEditPlan().snapshot())", activity)
        self.assertIn("ExportSessionGuard.check(token);", vault)
        final_check = vault.index("ExportSessionGuard.check(token);\\n            try {".replace("\\n", "\n"))
        rename = vault.index("Files.move(temporary.toPath()", final_check)
        self.assertLess(final_check, rename)
        for method in (
            "f143StalePromptRejectsNewProject",
            "f143SameSourceRebindingRejectsPrompt",
            "f143EditedPlanRejectsPrompt",
            "f143InvalidatedBeforeAtomicMovePreservesA",
            "f143CurrentTokenStillSavesB",
        ):
            self.assertIn(method, suite)
        self.assertIn("com.readroid.app.F143RecoverySaveBindingInstrumentedTest",
                      self.workflow)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F143RecoverySaveBindingInstrumentedTest.java",
                      self.workflow)
        self.assertNotIn("upload-artifact@", self.workflow)

    def test_f144_recovery_source_hash_is_checked_before_atomic_replacement(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8")
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F144RecoverySourceBindingInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("token, hashAtPrompt, checkpointAtOffer);", activity)
        self.assertIn("String expectedSourceSha256", vault)
        self.assertIn("expectedSourceSha256.equals(fingerprint)", vault)
        self.assertIn("expectedSourceSha256.equals(sha256(sourceApk))", vault)
        self.assertLess(
            vault.index("expectedSourceSha256.equals(sha256(sourceApk))"),
            vault.index("Files.move(temporary.toPath()"))
        for test_case in (
            "f144SourceChangeDuringStagePreservesPreviousA",
            "f144SourceMismatchBeforeStagingPreservesPreviousA",
            "f144CurrentSourceAndTokenStillCommitB",
        ):
            self.assertIn(test_case, tests)
        self.assertIn("com.readroid.app.F144RecoverySourceBindingInstrumentedTest",
                      self.workflow)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F144RecoverySourceBindingInstrumentedTest.java",
                      self.workflow)
        self.assertNotIn("upload-artifact@", self.workflow)

    def test_f145_post_commit_source_mismatch_never_claims_rollback(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8")
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F145PostCommitSourceInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("static final class PostCommitSourceException", vault)
        self.assertIn("error instanceof RecoveryVault.PostCommitSourceException", activity)
        self.assertIn("Cópia gravada; origem não confirmada", activity)
        callback = vault.index("afterFinalAttestation.run(promotedCheckpoint);")
        after = vault.index("afterCommitSha256 = sha256(sourceApk);", callback)
        cleanup = vault.index("} finally {", after)
        self.assertLess(callback, after)
        self.assertLess(after, cleanup)
        for case in (
            "f145ChangedSourceAfterPromotionReportsCommittedCheckpoint",
            "f145MissingSourceAfterPromotionReportsCommittedCheckpoint",
            "f145StableSourceReturnsNormalSuccess",
            "f145LegacySaveWithoutExpectedHashRemainsCompatible",
        ):
            self.assertIn(case, tests)
        self.assertIn("com.readroid.app.F145PostCommitSourceInstrumentedTest", self.workflow)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F145PostCommitSourceInstrumentedTest.java", self.workflow)
        self.assertNotIn("upload-artifact@", self.workflow)

    def test_f146_worker_reattests_source_after_checkpoint_save_returns(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8")
        gate = (ROOT / "app/src/main/java/com/readroid/app/RecoverySaveAcknowledgementGate.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F146RecoveryAcknowledgementInstrumentedTest.java").read_text(encoding="utf-8")
        proof = activity.index("final RecoveryResumeGate.Proof preSaveProof =")
        save = activity.index("new RecoveryVault(this).save(sourceAtPrompt, editsAtPrompt,", proof)
        verify = activity.index("RecoverySaveAcknowledgementGate.revalidate(", save)
        notification = activity.index('setTitle("Cópia protegida")', verify)
        self.assertLess(proof, save)
        self.assertLess(save, verify)
        self.assertLess(verify, notification)
        self.assertIn("RecoveryResumeGate.revalidate(preSaveProof, originalSource,", gate)
        self.assertIn("new RecoveryVault.PostCommitSourceException(", gate)
        self.assertIn("error instanceof RecoveryVault.PostCommitSourceException", activity)
        for test_case in (
            "f146SourceChangedAfterSaveBeforeNoticeRejectsAck",
            "f146SourceRemovedAfterSaveBeforeNoticeRejectsAck",
            "f146ReboundProofAfterSaveRejectsAck",
            "f146StableSourceConfirmsCommittedCheckpoint",
        ):
            self.assertIn(test_case, tests)
        self.assertIn("com.readroid.app.F146RecoveryAcknowledgementInstrumentedTest",
                      self.workflow)
        for path in (
            "app/src/main/java/com/readroid/app/RecoverySaveAcknowledgementGate.java",
            "app/src/androidTest/java/com/readroid/app/F146RecoveryAcknowledgementInstrumentedTest.java",
        ):
            self.assertIn(path, self.workflow)
        self.assertNotIn("upload-artifact@", self.workflow)

    def test_f147_restore_consent_reauthenticates_and_preserves_pending_plan(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8")
        gate = (ROOT / "app/src/main/java/com/readroid/app/RecoveryRestoreConsent.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F147RecoveryRestoreConsentInstrumentedTest.java").read_text(encoding="utf-8")
        start = activity.index("restoreRecovery.setOnClickListener")
        offer = activity.index("final Map<String, String> pendingAtRequest", start)
        consent = activity.index('setPositiveButton("Substituir plano"', offer)
        check = activity.index("RecoveryRestoreConsent.reauthenticate(", consent)
        apply = activity.index("explorerView.restoreEditPlanForSession(", check)
        self.assertLess(offer, consent)
        self.assertLess(consent, check)
        self.assertLess(check, apply)
        self.assertIn("pendingAtRequest.equals(explorerView.getEditPlan().snapshot())", activity)
        self.assertIn("recoveryRestoreSessions.begin()", activity)
        self.assertGreaterEqual(activity.count("recoveryRestoreSessions.invalidate();"), 5)
        self.assertIn("vault.prepareRestoreApplication(source, checkpointAtOffer, token)", gate)
        self.assertIn("offered.equals(current)", gate)
        self.assertGreaterEqual(gate.count("token.requireActive();"), 2)
        for case in (
            "f147LiveEditAfterPromptRejectsConsentEvenFromEmptyPlan",
            "f147NewRequestAndRebindingInvalidateOldConsent",
            "f147ReplacedCheckpointCannotRestoreOfferedA",
            "f147DeletedCheckpointCannotRestoreOfferedA",
            "f147RevokedTokenRejectsUnchangedCheckpoint",
            "f147CurrentConsentReturnsAuthenticatedPlanWithoutWriting",
        ):
            self.assertIn(case, tests)
        self.assertIn("com.readroid.app.F147RecoveryRestoreConsentInstrumentedTest", self.workflow)
        self.assertIn("app/src/main/java/com/readroid/app/RecoveryRestoreConsent.java", self.workflow)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F147RecoveryRestoreConsentInstrumentedTest.java", self.workflow)

    def test_f148_recovery_consent_tracks_edit_revision_even_after_undo(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8")
        plan = (ROOT / "app/src/main/java/com/readroid/app/EditPlan.java").read_text(encoding="utf-8")
        save = (ROOT / "app/src/androidTest/java/com/readroid/app/F143RecoverySaveBindingInstrumentedTest.java").read_text(encoding="utf-8")
        restore = (ROOT / "app/src/androidTest/java/com/readroid/app/F147RecoveryRestoreConsentInstrumentedTest.java").read_text(encoding="utf-8")
        state = (ROOT / "app/src/androidTest/java/com/readroid/app/EditPlanStateInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("private long revision;", plan)
        self.assertEqual(plan.count("revision++;"), 4)
        self.assertIn("revisionAtPrompt == explorerView.getEditPlan().revision()", activity)
        self.assertIn("revisionAtRequest == explorerView.getEditPlan().revision()", activity)
        self.assertEqual(activity.count("pendingAtRequest, revisionAtRequest, restoreToken))"), 4)
        self.assertIn("Old prompt must stay invalid after undo", save)
        self.assertIn("must not resurrect old consent", restore)
        self.assertIn("f148RevisionAdvancesOnlyForActualContentChanges", state)
        self.assertIn("f148ValidatedReplacementAndClearTrackRevision", state)

    def test_f149_real_recovery_dialogs_preserve_pending_edits(self):
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F149RecoveryDialogInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("f149DisposableVault=true", self.workflow)
        self.assertIn('getString("f149DisposableVault")', tests)
        self.assertIn('executeShellCommand("getprop ro.kernel.qemu")', tests)
        self.assertIn("F149 refuses to run on a physical device", tests)
        self.assertIn("Refuse an existing recovery directory", tests)
        self.assertIn("Refuse an existing recovery key", tests)
        self.assertIn("button.performClick()", tests)
        self.assertIn("button.click()", tests)
        self.assertIn("UiDevice.getInstance", tests)
        self.assertIn("CountDownLatch", tests)
        self.assertIn("f149ActualSaveDialogRejectsUndoBeforeConsent", tests)
        self.assertIn("f149ActualSaveDialogCommitsAuthorizedPlan", tests)
        self.assertIn("f149ActualRestoreDialogRejectsEditAfterConsent", tests)
        self.assertIn("f149ActualRestoreDialogAppliesAuthenticatedPlan", tests)
        self.assertIn("f149ActualRestoreDialogRejectsDeletedCheckpoint", tests)
        self.assertIn("com.readroid.app.F149RecoveryDialogInstrumentedTest", self.workflow)
        self.assertIn("app/src/androidTest/java/com/readroid/app/F149RecoveryDialogInstrumentedTest.java", self.workflow)

    def test_f150_delete_consent_is_bound_to_exact_ciphertext(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8")
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        unit = (ROOT / "app/src/androidTest/java/com/readroid/app/RecoveryVaultInstrumentedTest.java").read_text(encoding="utf-8")
        ui = (ROOT / "app/src/androidTest/java/com/readroid/app/F149RecoveryDialogInstrumentedTest.java").read_text(encoding="utf-8")
        start = activity.index("removeRecovery.setOnClickListener")
        capture = activity.index("captureDeletionProof()", start)
        consent = activity.index('setPositiveButton("Excluir cópia"', capture)
        deletion = activity.index("clearIfCurrent(offered)", consent)
        self.assertLess(capture, consent)
        self.assertLess(consent, deletion)
        self.assertIn("MessageDigest.isEqual(digest, current.digest)", vault)
        self.assertIn("void clearIfCurrent(DeletionProof offered)", vault)
        self.assertIn("offered.matches(captureDeletionProofLocked())", vault)
        for name in (
            "f150OldDeletionProofCannotDeleteResavedSamePlan",
            "f150AbsentDeletionProofCannotDeleteLaterSave",
            "f150ChangedCiphertextRejectsOldDeletionProof",
        ):
            self.assertIn(name, unit)
        self.assertIn("f150ActualDeleteDialogRejectsNewCheckpoint", ui)
        self.assertIn("f150ActualDeleteDialogRemovesAuthorizedCopyOnly", ui)

    def test_f151_restore_consent_is_bound_to_exact_ciphertext(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8")
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        gate = (ROOT / "app/src/main/java/com/readroid/app/RecoveryRestoreConsent.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F147RecoveryRestoreConsentInstrumentedTest.java").read_text(encoding="utf-8")
        ui = (ROOT / "app/src/androidTest/java/com/readroid/app/F149RecoveryDialogInstrumentedTest.java").read_text(encoding="utf-8")
        start = activity.index("restoreRecovery.setOnClickListener")
        capture = activity.index("recoveryVault.captureDeletionProof()", start)
        read = activity.index("recoveryVault.loadForSource(source, checkpointAtOffer)", capture)
        consent = activity.index('setPositiveButton("Substituir plano"', read)
        self.assertLess(capture, read)
        self.assertLess(read, consent)
        self.assertIn("changes, checkpointAtOffer, restoreToken", activity)
        self.assertIn("vault.prepareRestoreApplication(source, checkpointAtOffer, token)", gate)
        self.assertIn("loadSerialized(sourceApk, offered)", vault)
        self.assertIn("MessageDigest.isEqual(offered.digest,", vault)
        self.assertIn("digest(encoded)", vault)
        self.assertIn("f151ResavedIdenticalPlanRequiresNewRestoreConsent", tests)
        self.assertIn("f151OldProofCannotAuthenticateReplacementAtInitialOffer", tests)
        self.assertIn("f151ProofFromDifferentVaultRejectsSameSource", tests)
        self.assertIn("f151ActualRestoreDialogRejectsResavedIdenticalPlan", ui)

    def test_f152_application_ticket_rejects_intervening_vault_writes(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8")
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        gate = (ROOT / "app/src/main/java/com/readroid/app/RecoveryRestoreConsent.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F147RecoveryRestoreConsentInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("IN_PROCESS_LOCK.tryLock()", vault)
        self.assertIn("consumed || checkpointRevision != revision", vault)
        self.assertEqual(vault.count("checkpointRevision++;"), 3)
        self.assertIn("new RestoreApplication(checkpointRevision, changes)", vault)
        self.assertIn("vault.prepareRestoreApplication(source, checkpointAtOffer, token)", gate)
        self.assertIn("verified.applyIfCurrent(restoreToken,", activity)
        self.assertIn("recoverySession, verified.changes(), false", activity)
        self.assertIn("f152PostAuthenticationSaveInvalidatesApplication", tests)
        self.assertIn("f152PostAuthenticationClearInvalidatesApplication", tests)
        self.assertIn("f152CurrentApplicationIsSingleUse", tests)
        self.assertIn("f152BusyVaultRejectsApplicationWithoutWaitingForWriter", tests)
        self.assertIn("f152RevokedApplicationTokenCannotMutatePlan", tests)

    def test_f153_restore_preflight_is_worker_only(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8")
        ui = (ROOT / "app/src/androidTest/java/com/readroid/app/F149RecoveryDialogInstrumentedTest.java").read_text(encoding="utf-8")
        start = activity.index("restoreRecovery.setOnClickListener")
        end = activity.index("Button removeRecovery", start)
        listener = activity[start:end]
        worker = listener.index("executor.execute(() ->")
        check = listener.index("recoveryVault.hasCheckpointInterruptibly()")
        self.assertLess(worker, check)
        self.assertNotIn("hasCheckpoint", listener[:worker])
        self.assertNotIn("currentApk.isFile()", listener[:worker])
        self.assertIn("Nenhuma cópia de recuperação foi encontrada.", listener)
        self.assertIn("f153RestoreActionDoesNotWaitOnUiForBusyVault", ui)
        self.assertIn("f153AbsentCheckpointShowsNoticeWithoutChangingPendingPlan", ui)
        self.assertIn("f153StaleMissingCheckpointNoticeIsSuppressed", ui)

    def test_f154_recovery_vault_worker_lock_is_interruptible(self):
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F147RecoveryRestoreConsentInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("IN_PROCESS_LOCK.lockInterruptibly()", vault)
        self.assertIn("Thread.currentThread().interrupt()", vault)
        self.assertEqual(vault.count("IN_PROCESS_LOCK.lock();"), 1)
        self.assertIn("boolean hasCheckpointInterruptibly()", vault)
        self.assertIn("f154InterruptedVaultWaitDoesNotMutateCheckpoint", tests)

    def test_f155_save_consent_is_bound_to_previous_slot(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8")
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F147RecoveryRestoreConsentInstrumentedTest.java").read_text(encoding="utf-8")
        ui = (ROOT / "app/src/androidTest/java/com/readroid/app/F149RecoveryDialogInstrumentedTest.java").read_text(encoding="utf-8")
        start = activity.index("saveRecovery.setOnClickListener")
        capture = activity.index("captureDeletionProof()", start)
        consent = activity.index('setPositiveButton("Criptografar e salvar"', capture)
        save = activity.index("new RecoveryVault(this).save(sourceAtPrompt, editsAtPrompt,", consent)
        self.assertLess(capture, consent)
        self.assertLess(consent, save)
        self.assertIn("token, hashAtPrompt, checkpointAtOffer", activity)
        self.assertIn("requireSaveSlot(offered);", vault)
        self.assertLess(vault.index("if (offered != null) requireSaveSlot(offered);"),
                        vault.index("Files.move(temporary.toPath()"))
        self.assertIn("f155ActualSaveDialogRejectsNewCheckpoint", ui)
        self.assertIn("f155ActualSaveDialogRejectsCheckpointCreatedAfterEmptyOffer", ui)
        self.assertIn("f155StaleSaveProofCannotOverwriteSamePlanResave", tests)
        self.assertIn("f155SlotChangeDuringStagingRejectsPromotion", tests)

    def test_f156_slot_proofs_do_not_survive_mutation_cycles(self):
        vault = (ROOT / "app/src/main/java/com/readroid/app/RecoveryVault.java").read_text(encoding="utf-8")
        tests = (ROOT / "app/src/androidTest/java/com/readroid/app/F147RecoveryRestoreConsentInstrumentedTest.java").read_text(encoding="utf-8")
        ui = (ROOT / "app/src/androidTest/java/com/readroid/app/F149RecoveryDialogInstrumentedTest.java").read_text(encoding="utf-8")
        self.assertIn("revision == current.revision && matchesCiphertext(current)", vault)
        self.assertIn("new DeletionProof(backup, null, null, checkpointRevision)", vault)
        self.assertIn("new DeletionProof(backup, after, digest, checkpointRevision)", vault)
        self.assertIn("offered.matchesCiphertext(captureDeletionProofLocked())", vault)
        self.assertIn("f156AbsentSaveProofCannotSurviveSaveClearCycle", tests)
        self.assertIn("f156AbsentDeleteProofCannotSurviveSaveClearCycle", tests)
        self.assertIn("f156ActualSaveDialogRejectsAbsentSaveClearCycle", ui)
        self.assertIn("f156ActualDeleteDialogRejectsAbsentSaveClearCycle", ui)

    def test_f157_plaintext_share_is_bound_to_current_plan(self):
        activity = (ROOT / "app/src/main/java/com/readroid/app/MainActivity.java").read_text(encoding="utf-8")
        ui = (ROOT / "app/src/androidTest/java/com/readroid/app/F149RecoveryDialogInstrumentedTest.java").read_text(encoding="utf-8")
        start = activity.index("editExport.setOnClickListener")
        snapshot = activity.index("final Map<String, String> shareSnapshot", start)
        consent = activity.index('setPositiveButton("Compartilhar"', snapshot)
        gate = activity.index("isRecoverySaveRequestCurrent(shareSource, shareDocument,", consent)
        serialize = activity.index("explorerView.getEditPlan().toJson()", gate)
        launch = activity.index("startActivity(Intent.createChooser(send", serialize)
        self.assertLess(snapshot, consent)
        self.assertLess(consent, gate)
        self.assertLess(gate, serialize)
        self.assertLess(serialize, launch)
        self.assertIn("shareSnapshot, shareRevision", activity)
        self.assertIn("sharePlanOffers.begin()", activity)
        self.assertIn("f157ActualShareDialogRejectsEditUndoBeforeConsent", ui)
        self.assertIn("f157ActualShareDialogRejectsReboundProject", ui)
        self.assertIn("f157ActualShareDialogLaunchesOnlyAuthorizedChooser", ui)

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
