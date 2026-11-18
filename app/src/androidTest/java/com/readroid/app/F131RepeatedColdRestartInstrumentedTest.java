package com.readroid.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Process;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.security.KeyStore;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.*;

/**
 * F1.31: Android 10/15 real SAF grant + P7 history + encrypted recovery
 * persistence through three separate process deaths and two revoked-grant
 * restarts. These opt-in methods run ONLY via f128_real_saf_grant.sh on a
 * disposable CI emulator. The user's real checkpoint alias is NEVER used.
 */
@RunWith(AndroidJUnit4.class)
public final class F131RepeatedColdRestartInstrumentedTest {
    private static final String PREF = "f131_ci_history_checkpoint";
    private static final String F128_PREF = "f128_ci_saf_grant";
    private static final String F128_URI = "document_uri";
    private static final String F128_SHA = "accepted_sha256";
    private static final String SOURCE = "f131_accepted_reference.apk";
    private static final String VAULT_DIR = "f131_ci_encrypted_recovery";
    private static final String KEY = "negrescodroid.f131.ci.recovery.v1";
    private static final String CHECKPOINT = "edit-plan-checkpoint.v1";
    private static final String PENDING = "readroid_F131abandoned123.apk.pending";
    private static final String EDIT_PATH = "assets/f131-notes.txt";
    private static final String EDIT_TEXT = "F131 encrypted checkpoint across restarts";

    private static Context context() {
        return InstrumentationRegistry.getInstrumentation().getTargetContext();
    }

    private static SharedPreferences state() {
        return context().getSharedPreferences(PREF, Context.MODE_PRIVATE);
    }

    private static Uri accepted() {
        String text = state().getString("accepted_uri", null);
        if (text == null)
            text = context().getSharedPreferences(F128_PREF, Context.MODE_PRIVATE)
                .getString(F128_URI, null);
        assertNotNull("F1.28 real picker URI is required", text);
        Uri uri = Uri.parse(text);
        assertEquals("content", uri.getScheme());
        return uri;
    }

    private static String expectedSha() {
        String hash = state().getString("accepted_sha256", null);
        if (hash == null)
            hash = context().getSharedPreferences(F128_PREF, Context.MODE_PRIVATE)
                .getString(F128_SHA, null);
        assertTrue("F1.28 must accept a verified original APK",
            SavedProjectResume.validSha256(hash));
        return hash;
    }

    private static File privateSource() {
        return new File(context().getFilesDir(), SOURCE);
    }

    private static File vaultFolder() {
        return new File(context().getFilesDir(), VAULT_DIR);
    }

    private static RecoveryVault vault() {
        return new RecoveryVault(vaultFolder(), KEY);
    }

    private static File checkpoint() {
        return new File(vaultFolder(), CHECKPOINT);
    }

    private static File unfinished() {
        return new File(context().getCacheDir(), PENDING);
    }

    private static void stageUnfinishedImport() throws Exception {
        assertTrue(ImportCrashJanitor.pendingName(PENDING));
        Files.write(unfinished().toPath(), "abandoned incomplete SAF copy"
            .getBytes(StandardCharsets.UTF_8),
            StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
    }

    private static void assertPendingPrunedByRealMainActivity() {
        assertTrue("An abandoned import must exist before cold startup",
            unfinished().isFile());
        try (ActivityScenario<MainActivity> ignored =
                ActivityScenario.launch(MainActivity.class)) {
            assertFalse("MainActivity cold start must discard ONLY pending SAF copy",
                unfinished().exists());
        }
    }

    private static void checkCheckpointUnchanged() throws Exception {
        String expected = state().getString("checkpoint_sha256", null);
        assertTrue(SavedProjectResume.validSha256(expected));
        assertTrue("Encrypted recovery disappeared", vault().hasCheckpoint());
        assertEquals("Repeated process restarts must not rewrite ciphertext",
            expected, ApkIntegrity.sha256(checkpoint()));
        assertEquals("Accepted source bytes changed after restart",
            expectedSha(), ApkIntegrity.sha256(privateSource()));
        Map<String, String> loaded = vault().loadForSource(privateSource());
        assertEquals(Collections.singletonMap(EDIT_PATH, EDIT_TEXT), loaded);
        RecoveryResumeGate.Proof proof = RecoveryResumeGate.attest(
            privateSource(), expectedSha());
        RecoveryResumeGate.revalidate(proof, privateSource(), expectedSha());
        assertEquals(expected, ApkIntegrity.sha256(checkpoint()));
    }

    private static void checkHistoryStable() {
        Uri uri = accepted();
        assertTrue("Persisted OS grant must still exist",
            P7ProjectHistory.hasPermission(context(), uri));
        List<P7ProjectHistory.Entry> history = P7ProjectHistory.list(context());
        assertFalse("Previously accepted document missing from recent history",
            history.isEmpty());
        P7ProjectHistory.Entry entry = history.get(0);
        assertEquals(uri, entry.uri);
        assertEquals(state().getString("name", null), entry.name);
        assertEquals("ci.f131.recovery", entry.packageName);
        assertEquals(state().getLong("opened_at", -1), entry.openedAt);
    }

    private static void checkNoAutomaticResurrection() {
        Uri old = accepted();
        Uri interrupted = Uri.parse("content://ci.f131.unaccepted/pending.apk");
        SavedProjectResume.Decision denied = SavedProjectResume.decide(
            old, interrupted, false, false, expectedSha(),
            uri -> P7ProjectHistory.hasPermission(context(), uri));
        assertNull("Revoked accepted URI must NOT auto-reimport", denied.reimport);
        assertNull(denied.acceptedReference);
        assertNull(denied.expectedSha256);
        assertTrue("Revoked grant must require user reselection",
            denied.requiresReselection);
        assertFalse(P7ProjectHistory.hasPermission(context(), old));
        for (P7ProjectHistory.Entry entry : P7ProjectHistory.list(context()))
            assertNotEquals("Revoked URI must be hidden from history", old, entry.uri);
    }

    private static void advanceProcessEpoch(int previousEpoch, int nextEpoch) {
        assertEquals("Process sequence skipped or repeated", previousEpoch,
            state().getInt("epoch", -1));
        assertNotEquals("A real OS process restart is required",
            state().getInt("pid", -1), Process.myPid());
        assertTrue("Cannot persist process epoch", state().edit()
            .putInt("pid", Process.myPid()).putInt("epoch", nextEpoch).commit());
    }

    @Test public void f131SeedAcceptedHistoryAndEncryptedCheckpoint()
            throws Exception {
        assertFalse("F131 sandbox already exists", privateSource().exists());
        assertFalse("F131 recovery directory already exists", vaultFolder().exists());
        assertFalse("Cannot overwrite old F131 state", state().contains("epoch"));
        Uri uri = accepted();
        assertTrue(P7ProjectHistory.hasPermission(context(), uri));
        try (InputStream source = context().getContentResolver().openInputStream(uri);
             OutputStream destination = Files.newOutputStream(privateSource().toPath(),
                 StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            assertNotNull("The real SAF document has disappeared", source);
            byte[] buffer = new byte[65536];
            for (int bytes; (bytes = source.read(buffer)) != -1;)
                destination.write(buffer, 0, bytes);
        }
        assertEquals(expectedSha(), ApkIntegrity.sha256(privateSource()));
        assertEquals(1, ApkZipIntegrity.verify(privateSource()).verifiedFiles > 0 ? 1 : 0);
        assertTrue("History may only record a document with persisted grant",
            P7ProjectHistory.record(context(), uri, "ci.f131.recovery"));
        P7ProjectHistory.Entry recorded = P7ProjectHistory.list(context()).get(0);
        assertEquals(uri, recorded.uri);

        RecoveryVault protectedVault = vault();
        protectedVault.save(privateSource(), Collections.singletonMap(EDIT_PATH, EDIT_TEXT));
        byte[] ciphertext = Files.readAllBytes(checkpoint().toPath());
        assertFalse("Recovery must NOT persist plaintext edits",
            new String(ciphertext, StandardCharsets.ISO_8859_1).contains(EDIT_TEXT));
        assertTrue("Initial acceptance state could not be committed",
            state().edit().putInt("pid", Process.myPid()).putInt("epoch", 0)
                .putString("accepted_uri", uri.toString())
                .putString("accepted_sha256", expectedSha())
                .putString("name", recorded.name).putLong("opened_at", recorded.openedAt)
                .putString("checkpoint_sha256", ApkIntegrity.sha256(checkpoint()))
                .commit());
        checkCheckpointUnchanged();
        checkHistoryStable();
        stageUnfinishedImport();
    }

    private static void checkAuthorizedRound(int oldEpoch, int newEpoch)
            throws Exception {
        advanceProcessEpoch(oldEpoch, newEpoch);
        assertPendingPrunedByRealMainActivity();
        checkCheckpointUnchanged();
        checkHistoryStable();
        Uri accepted = accepted();
        Uri ignoredPending = Uri.parse("content://ci.f131.unaccepted/failed.apk");
        SavedProjectResume.Decision resumed = SavedProjectResume.decide(
            accepted, ignoredPending, false, false, expectedSha(),
            uri -> P7ProjectHistory.hasPermission(context(), uri));
        assertEquals("Accepted source must win over an unaccepted pending URI",
            accepted, resumed.reimport);
        assertNotEquals(ignoredPending, resumed.reimport);
        assertEquals(expectedSha(), resumed.expectedSha256);
        // Prepare another residue for the NEXT real force-stop, not this Activity.
        if (newEpoch < 3) stageUnfinishedImport();
    }

    @Test public void f131ColdStartRoundOne() throws Exception {
        checkAuthorizedRound(0, 1);
    }

    @Test public void f131ColdStartRoundTwo() throws Exception {
        checkAuthorizedRound(1, 2);
    }

    @Test public void f131ColdStartRoundThree() throws Exception {
        checkAuthorizedRound(2, 3);
    }

    @Test public void f131RevokedGrantStillPreservesEncryptedRecovery()
            throws Exception {
        advanceProcessEpoch(3, 4);
        checkNoAutomaticResurrection();
        checkCheckpointUnchanged();
        stageUnfinishedImport();
    }

    @Test public void f131SecondRevokedRestartCleansAndPreservesRecovery()
            throws Exception {
        advanceProcessEpoch(4, 5);
        assertPendingPrunedByRealMainActivity();
        checkNoAutomaticResurrection();
        checkCheckpointUnchanged();

        // CI-only cleanup of isolated fixtures and Keystore alias. No user
        // document is deleted or modified; the OS grant was revoked by F1.28.
        assertTrue("Could not clear test-only encrypted checkpoint",
            !vault().hasCheckpoint() || deleteTestCheckpoint());
        assertTrue(Files.deleteIfExists(privateSource().toPath()));
        Files.deleteIfExists(vaultFolder().toPath());
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(KEY)) store.deleteEntry(KEY);
        assertTrue("Test-only history cleanup failed", P7ProjectHistory.clear(context()));
        assertTrue("F131 state cleanup failed", state().edit().clear().commit());
    }

    private static boolean deleteTestCheckpoint() throws Exception {
        vault().clear();
        return !vault().hasCheckpoint();
    }
}
