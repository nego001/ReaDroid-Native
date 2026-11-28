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

/** Assertions after real force-stop when full attestation finished but save() had not returned. */
@RunWith(AndroidJUnit4.class)
public final class F142PostAttestationCrashInstrumentedTest {
    private static final String KEY = "negrescodroid.f142.ci.postattestation.v1";
    private static final String ENTRY = "assets/f142-final.txt";
    private static File root() {
        Context c = InstrumentationRegistry.getInstrumentation().getTargetContext();
        return new File(c.getFilesDir(), "f142_ci_post_attestation_lab");
    }
    private static File source() { return new File(root(), "accepted_source.apk"); }
    private static File dir() { return new File(root(), "vault"); }
    private static File checkpoint() { return new File(dir(), "edit-plan-checkpoint.v1"); }
    private static String meta(String name) throws Exception {
        return new String(Files.readAllBytes(new File(root(), name).toPath()),
            StandardCharsets.US_ASCII);
    }
    private static Map<String, String> edits(char c) {
        // Independently reconstruct expected text; do not load a debug
        // Activity class from the instrumentation APK's class loader.
        char[] chars = new char[24000];
        java.util.Arrays.fill(chars, c);
        return Collections.singletonMap(ENTRY,
            "F142:" + c + ":" + new String(chars));
    }
    private static int stages() throws Exception {
        int count = 0;
        try (DirectoryStream<java.nio.file.Path> stream =
                Files.newDirectoryStream(dir().toPath(), "checkpoint-*.tmp")) {
            for (java.nio.file.Path ignored : stream) count++;
        }
        return count;
    }
    private static void check(String marker, char previous, char next)
            throws Exception {
        assertEquals(marker, meta("status"));
        assertEquals(String.valueOf(previous), meta("accepted.version"));
        assertEquals(2, ApkZipIntegrity.verify(source()).verifiedFiles);
        String fingerprint = ApkIntegrity.sha256(source());
        RecoveryResumeGate.Proof proof = RecoveryResumeGate.attest(source(), fingerprint);
        RecoveryResumeGate.revalidate(proof, source(), fingerprint);
        String oldHash = meta("accepted.sha256");
        String newHash = meta("promoted.sha256");
        assertTrue(SavedProjectResume.validSha256(oldHash));
        assertTrue(SavedProjectResume.validSha256(newHash));
        assertNotEquals(oldHash, newHash);
        assertEquals(newHash, ApkIntegrity.sha256(checkpoint()));
        assertEquals("New revision must decrypt after force-stop",
            edits(next), new RecoveryVault(dir(), KEY).loadForSource(source()));
        assertEquals(newHash, ApkIntegrity.sha256(checkpoint()));
        assertEquals(0, stages());
        // Host has verified a NEW process PID before running this method.
        Files.write(new File(root(), "accepted.sha256").toPath(),
            newHash.getBytes(StandardCharsets.US_ASCII));
        Files.write(new File(root(), "accepted.version").toPath(),
            String.valueOf(next).getBytes(StandardCharsets.US_ASCII));
        Files.delete(new File(root(), "promoted.sha256").toPath());
    }
    @Test public void f142FirstPostAttestationKillRecoversPromotedB() throws Exception {
        check("ATTESTED_B", 'A', 'B');
    }
    @Test public void f142SecondPostAttestationKillRecoversPromotedC() throws Exception {
        check("ATTESTED_C", 'B', 'C');
    }
    @Test public void f142NormalSaveAfterTwoCrashesRecoversD() throws Exception {
        assertEquals("COMMITTED_D", meta("status"));
        assertEquals("D", meta("accepted.version"));
        assertFalse(new File(root(), "promoted.sha256").exists());
        assertEquals(meta("accepted.sha256"), ApkIntegrity.sha256(checkpoint()));
        assertEquals(edits('D'), new RecoveryVault(dir(), KEY).loadForSource(source()));
        assertEquals(0, stages());
        new RecoveryVault(dir(), KEY).clear();
        Files.delete(new File(root(), "accepted.sha256").toPath());
        Files.delete(new File(root(), "accepted.version").toPath());
        Files.delete(new File(root(), "status").toPath());
        Files.delete(source().toPath());
        Files.delete(dir().toPath());
        Files.delete(root().toPath());
        KeyStore keys = KeyStore.getInstance("AndroidKeyStore");
        keys.load(null);
        if (keys.containsAlias(KEY)) keys.deleteEntry(KEY);
    }
}
