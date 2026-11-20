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

/** Inspect F1.35 cold restarts without ever touching the production vault. */
@RunWith(AndroidJUnit4.class)
public final class F135VerifierCrashInstrumentedTest {
    private static final String KEY = "negrescodroid.f135.ci.verification.v1";
    private static final String PATH = "assets/f135-verified.txt";
    private static final String A = "F135 accepted revision A";
    private static final String B = "F135 accepted revision B";
    private static File root() {
        Context ctx = InstrumentationRegistry.getInstrumentation().getTargetContext();
        return new File(ctx.getFilesDir(), "f135_ci_verify_lab");
    }
    private static File folder() { return new File(root(), "vault"); }
    private static File source() { return new File(root(), "source.apk"); }
    private static File checkpoint() {
        return new File(folder(), "edit-plan-checkpoint.v1");
    }
    private static String file(String name) throws IOException {
        return new String(Files.readAllBytes(new File(root(), name).toPath()),
            StandardCharsets.US_ASCII);
    }
    private static int stages() throws Exception {
        int count = 0;
        try (DirectoryStream<java.nio.file.Path> stream =
                Files.newDirectoryStream(folder().toPath(), "checkpoint-*.tmp")) {
            for (java.nio.file.Path p : stream) {
                assertTrue(Files.isRegularFile(p, java.nio.file.LinkOption.NOFOLLOW_LINKS));
                assertTrue(Files.size(p) > 8192);
                count++;
            }
        }
        return count;
    }
    private static void assertVersion(String marker, String version,
            String expectedPlan, int count) throws Exception {
        assertEquals(marker, file("status"));
        assertEquals(version, file("accepted.version"));
        assertEquals(file("accepted.sha256"), ApkIntegrity.sha256(checkpoint()));
        assertEquals(Collections.singletonMap(PATH, expectedPlan),
            new RecoveryVault(folder(), KEY).loadForSource(source()));
        assertEquals("F135 accepted source file", new String(
            Files.readAllBytes(source().toPath()), StandardCharsets.UTF_8));
        assertEquals(count, stages());
    }
    @Test public void f135FirstMidVerificationCrashPreservesA() throws Exception {
        assertVersion("READING_1", "SEEDED", A, 1);
    }
    @Test public void f135SecondMidVerificationCrashPreservesA() throws Exception {
        assertVersion("READING_2", "SEEDED", A, 2);
    }
    @Test public void f135CommittedBStillDecryptsAfterTwoCrashes() throws Exception {
        assertVersion("COMMITTED_B", "B", B, 2);
        new RecoveryVault(folder(), KEY).clear();
        assertEquals(0, stages());
        assertFalse(checkpoint().exists());
        Files.deleteIfExists(new File(root(), "status").toPath());
        Files.deleteIfExists(new File(root(), "accepted.sha256").toPath());
        Files.deleteIfExists(new File(root(), "accepted.version").toPath());
        Files.deleteIfExists(source().toPath());
        Files.deleteIfExists(folder().toPath());
        Files.deleteIfExists(root().toPath());
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        if (ks.containsAlias(KEY)) ks.deleteEntry(KEY);
    }
}
