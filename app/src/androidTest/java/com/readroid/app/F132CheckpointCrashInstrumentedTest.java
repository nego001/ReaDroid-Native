package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.security.KeyStore;
import java.util.Collections;
import java.util.Map;
import static org.junit.Assert.*;

/**
 * F1.32: run from an independent AndroidJUnitRunner session AFTER each
 * real force-stop/restart. Verify AES/GCM decryption, SHA and ZIP integrity,
 * not just presence of a checkpoint path.
 */
@RunWith(AndroidJUnit4.class)
public final class F132CheckpointCrashInstrumentedTest {
    private static final String ALIAS = "negrescodroid.f132.ci.checkpoint.v1";
    private static final String KEY = "assets/f132-recovery.txt";
    private static final String REV_A = "F132 revision A - original accepted edits";
    private static final String REV_B = "F132 revision B - later accepted edits";

    private static Context context() {
        return InstrumentationRegistry.getInstrumentation().getTargetContext();
    }
    private static File root() {
        return new File(context().getFilesDir(), "f132_ci_checkpoint_lab");
    }
    private static File vaultFolder() { return new File(root(), "vault"); }
    private static File source() { return new File(root(), "accepted_source.apk"); }
    private static File checkpoint() {
        return new File(vaultFolder(), "edit-plan-checkpoint.v1");
    }
    private static RecoveryVault vault() {
        return new RecoveryVault(vaultFolder(), ALIAS);
    }
    private static String file(String name) throws IOException {
        return new String(Files.readAllBytes(new File(root(), name).toPath()),
            StandardCharsets.US_ASCII);
    }
    private static int pendingStages() throws IOException {
        int count = 0;
        try (DirectoryStream<java.nio.file.Path> entries =
                Files.newDirectoryStream(vaultFolder().toPath(), "checkpoint-*.tmp")) {
            for (java.nio.file.Path stage : entries) {
                assertTrue("Only regular local encrypted stages are allowed",
                    Files.isRegularFile(stage,
                        java.nio.file.LinkOption.NOFOLLOW_LINKS));
                byte[] bytes = Files.readAllBytes(stage);
                assertTrue("Synced stage unexpectedly empty", bytes.length >= 33);
                assertFalse("Uncommitted stage leaked plaintext",
                    new String(bytes, StandardCharsets.ISO_8859_1).contains(REV_B));
                count++;
            }
        }
        return count;
    }

    private static void check(String marker, String version, String contents,
            int expectedStages) throws Exception {
        assertTrue("F132 isolated source missing", source().isFile());
        assertTrue("F132 committed ciphertext missing", vault().hasCheckpoint());
        assertEquals("Checkpoint state mismatch", marker, file("status"));
        assertEquals("Committed revision unexpectedly replaced", version,
            file("accepted_version"));
        String stored = file("expected_checkpoint.sha256");
        assertTrue(SavedProjectResume.validSha256(stored));
        assertEquals("Previously committed ciphertext was modified",
            stored, ApkIntegrity.sha256(checkpoint()));
        assertEquals("Original ZIP bytes corrupted", 2,
            ApkZipIntegrity.verify(source()).verifiedFiles);
        String sha = ApkIntegrity.sha256(source());
        RecoveryResumeGate.Proof proof = RecoveryResumeGate.attest(source(), sha);
        RecoveryResumeGate.revalidate(proof, source(), sha);
        Map<String, String> recovered = vault().loadForSource(source());
        assertEquals("Keystore identity or recovered edits changed",
            Collections.singletonMap(KEY, contents), recovered);
        assertEquals("Read-only recovery changed checkpoint", stored,
            ApkIntegrity.sha256(checkpoint()));
        assertEquals("Unexpected encrypted precommit stage count",
            expectedStages, pendingStages());
    }

    @Test public void f132FirstCrashPreservesCommittedA() throws Exception {
        check("STAGED_B", "A", REV_A, 1);
    }

    @Test public void f132SuccessfulAtomicReplacementAcceptsB() throws Exception {
        check("COMMITTED_B", "B", REV_B, 1);
    }

    @Test public void f132SecondCrashPreservesCommittedB() throws Exception {
        check("STAGED_C", "B", REV_B, 2);
        // ONLY remove this fixed CI alias and isolated fixtures.
        vault().clear();
        assertFalse(vault().hasCheckpoint());
        assertEquals(0, pendingStages());
        Files.delete(new File(root(), "expected_checkpoint.sha256").toPath());
        Files.delete(new File(root(), "accepted_version").toPath());
        Files.delete(new File(root(), "status").toPath());
        Files.delete(source().toPath());
        Files.delete(vaultFolder().toPath());
        Files.delete(root().toPath());
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(ALIAS)) store.deleteEntry(ALIAS);
    }
}
