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
 * F1.39: independent instrumentation AFTER the host terminates the app
 * in the post-rename/pre-directory-fsync window. A valid new checkpoint
 * is expected, not the OLD checkpoint (unlike F1.32).
 */
@RunWith(AndroidJUnit4.class)
public final class F139PostRenameCrashInstrumentedTest {
    private static final String KEY = "negrescodroid.f139.ci.postrename.v1";
    private static final String ENTRY = "assets/f139-postrename.txt";
    private static final String A = "F139 accepted A";
    private static final String B = "F139 promoted B after crash";
    private static final String C = "F139 promoted C after crash";
    private static final String D = "F139 completed D";

    private static File root() {
        Context context =
            InstrumentationRegistry.getInstrumentation().getTargetContext();
        return new File(context.getFilesDir(), "f139_ci_postrename_lab");
    }
    private static File source() { return new File(root(), "accepted_source.apk"); }
    private static File dir() { return new File(root(), "vault"); }
    private static File checkpoint() {
        return new File(dir(), "edit-plan-checkpoint.v1");
    }
    private static String metadata(String filename) throws IOException {
        return new String(Files.readAllBytes(
            new File(root(), filename).toPath()), StandardCharsets.US_ASCII);
    }
    private static Map<String, String> edits(String revision) {
        return Collections.singletonMap(ENTRY, revision);
    }
    private static int staged() throws Exception {
        int count = 0;
        try (DirectoryStream<java.nio.file.Path> entries =
                Files.newDirectoryStream(dir().toPath(), "checkpoint-*.tmp")) {
            for (java.nio.file.Path ignored : entries) count++;
        }
        return count;
    }
    private static void check(String marker, String previous,
            String newRevision) throws Exception {
        assertTrue("F139 source missing", source().isFile());
        assertEquals(2, ApkZipIntegrity.verify(source()).verifiedFiles);
        String originalSHA = ApkIntegrity.sha256(source());
        RecoveryResumeGate.Proof proof =
            RecoveryResumeGate.attest(source(), originalSHA);
        RecoveryResumeGate.revalidate(proof, source(), originalSHA);
        assertEquals(marker, metadata("status"));
        assertEquals("External metadata was incorrectly advanced before sync",
            previous, metadata("accepted.version"));
        String lastAccepted = metadata("accepted.sha256");
        assertTrue(SavedProjectResume.validSha256(lastAccepted));
        String promoted = metadata("promoted.sha256");
        assertTrue(SavedProjectResume.validSha256(promoted));
        assertNotEquals("Pre-rename checkpoint should have been overwritten",
            lastAccepted, promoted);
        assertEquals("New ciphertext must be the renamed file",
            promoted, ApkIntegrity.sha256(checkpoint()));
        assertEquals("Last promoted checkpoint must decrypt after cold start",
            edits(newRevision),
            new RecoveryVault(dir(), KEY).loadForSource(source()));
        assertEquals("Read-only recovery changed committed bytes",
            promoted, ApkIntegrity.sha256(checkpoint()));
        assertEquals("ATOMIC_MOVE should leave no pending temporary", 0,
            staged());
    }
    private static void acknowledge(String version) throws Exception {
        Files.write(new File(root(), "accepted.sha256").toPath(),
            metadata("promoted.sha256").getBytes(StandardCharsets.US_ASCII));
        Files.write(new File(root(), "accepted.version").toPath(),
            version.getBytes(StandardCharsets.US_ASCII));
        Files.delete(new File(root(), "promoted.sha256").toPath());
    }

    @Test public void f139FirstPostRenameKillRecoversPromotedB()
            throws Exception {
        check("PROMOTED_B_PRE_SYNC", "A", B);
        acknowledge("B");
    }

    @Test public void f139SecondPostRenameKillRecoversPromotedC()
            throws Exception {
        check("PROMOTED_C_PRE_SYNC", "B", C);
        acknowledge("C");
    }

    @Test public void f139CleanCommitAfterTwoCrashesRecoversD()
            throws Exception {
        assertEquals("COMMITTED_D", metadata("status"));
        assertEquals("D", metadata("accepted.version"));
        assertFalse(new File(root(), "promoted.sha256").exists());
        assertEquals(metadata("accepted.sha256"),
            ApkIntegrity.sha256(checkpoint()));
        assertEquals(edits(D), new RecoveryVault(dir(), KEY)
            .loadForSource(source()));
        assertEquals(0, staged());
        // Delete only this exact fixed CI lab + keystore alias.
        new RecoveryVault(dir(), KEY).clear();
        Files.delete(new File(root(), "accepted.sha256").toPath());
        Files.delete(new File(root(), "accepted.version").toPath());
        Files.delete(new File(root(), "status").toPath());
        Files.delete(source().toPath());
        Files.delete(dir().toPath());
        Files.delete(root().toPath());
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(KEY)) store.deleteEntry(KEY);
    }
}
