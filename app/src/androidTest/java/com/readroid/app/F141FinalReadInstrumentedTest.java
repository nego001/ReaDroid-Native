package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.KeyStore;
import java.util.Arrays;
import java.util.Collections;
import java.util.Map;
import java.util.UUID;
import static org.junit.Assert.*;

/** F1.41: final post-fsync descriptor read, only isolated fixture/Keystore. */
@RunWith(AndroidJUnit4.class)
public final class F141FinalReadInstrumentedTest {
    private static final String ENTRY = "assets/f141-final.txt";
    private static String payload(char c) {
        char[] chars = new char[24000];
        Arrays.fill(chars, c);
        return "F141:" + c + ":" + new String(chars);
    }
    private static Map<String, String> edits(char c) {
        return Collections.singletonMap(ENTRY, payload(c));
    }
    private static final class Fixture implements AutoCloseable {
        final File root, dir, source, checkpoint;
        final String alias;
        final RecoveryVault vault;
        final byte[] original, cipherA;
        Fixture() throws Exception {
            Context context = InstrumentationRegistry.getInstrumentation()
                .getTargetContext();
            root = Files.createTempDirectory(context.getFilesDir().toPath(),
                "f141_final_read_").toFile();
            dir = new File(root, "vault");
            source = new File(root, "source.apk");
            original = "F141 isolated immutable source".getBytes(StandardCharsets.UTF_8);
            Files.write(source.toPath(), original);
            alias = "negrescodroid.f141.test." + UUID.randomUUID();
            vault = new RecoveryVault(dir, alias);
            vault.save(source, edits('A'));
            checkpoint = new File(dir, "edit-plan-checkpoint.v1");
            cipherA = Files.readAllBytes(checkpoint.toPath());
        }
        RecoveryVault observing(RecoveryVault.StageReadObserver observer) {
            return new RecoveryVault(dir, alias, stage -> {},
                RecoveryStorageBudget.forDirectory(dir),
                (verified, total) -> {}, stage -> {}, promoted -> {},
                promoted -> {}, observer);
        }
        void preservedSourceAndNoStages() throws Exception {
            assertArrayEquals(original, Files.readAllBytes(source.toPath()));
            File[] pending = dir.listFiles((d, n) ->
                n.startsWith("checkpoint-") && n.endsWith(".tmp"));
            assertNotNull(pending);
            assertEquals(0, pending.length);
        }
        @Override public void close() throws Exception {
            vault.clear();
            Files.deleteIfExists(source.toPath());
            Files.deleteIfExists(dir.toPath());
            Files.deleteIfExists(root.toPath());
            KeyStore store = KeyStore.getInstance("AndroidKeyStore");
            store.load(null);
            if (store.containsAlias(alias)) store.deleteEntry(alias);
        }
    }
    @Test public void f141InterruptedFinalReadKeepsPromotedBRecoverable()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] observed = {0};
            try {
                f.observing((verified, total) -> {
                    observed[0]++;
                    assertEquals(8192, verified);
                    assertTrue("Must interrupt before EOF", total > verified);
                    throw new InterruptedIOException("F141 deliberate final-read stop");
                }).save(f.source, edits('B'));
                fail("Final verification interruption must fail the save call");
            } catch (InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("F141 deliberate"));
            }
            assertEquals(1, observed[0]);
            assertFalse(Arrays.equals(f.cipherA,
                Files.readAllBytes(f.checkpoint.toPath())));
            assertEquals(edits('B'), f.vault.loadForSource(f.source));
            f.preservedSourceAndNoStages();
        }
    }
    @Test public void f141UnreadCiphertextTamperingIsDetected()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] observed = {0};
            try {
                f.observing((verified, total) -> {
                    if (observed[0]++ != 0) return;
                    assertEquals(8192, verified);
                    assertTrue(total > verified + 100);
                    byte[] bytes = Files.readAllBytes(f.checkpoint.toPath());
                    bytes[bytes.length - 50] ^= 0x21;
                    Files.write(f.checkpoint.toPath(), bytes);
                    Arrays.fill(bytes, (byte) 0);
                }).save(f.source, edits('B'));
                fail("Ciphertext modified in an unread chunk must be rejected");
            } catch (IOException expected) {
                assertTrue("Expected final ciphertext mismatch: " + expected,
                    expected.getMessage().contains("Conteúdo do estágio"));
            }
            assertTrue(observed[0] >= 1);
            assertFalse(Arrays.equals(f.cipherA,
                Files.readAllBytes(f.checkpoint.toPath())));
            try {
                assertNotEquals("Corrupted new checkpoint cannot yield B",
                    edits('B'), f.vault.loadForSource(f.source));
            } catch (IOException | java.security.GeneralSecurityException expected) {
                // Android Keystore rejects tampered ciphertext through GCM.
            }
            f.preservedSourceAndNoStages();
        }
    }
    @Test public void f141NormalFinalReadCompletesAllChunks()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] count = {0};
            final int[] last = {0};
            f.observing((verified, total) -> {
                if (count[0] == 0) {
                    assertEquals(8192, verified);
                    assertTrue(total > verified);
                }
                assertTrue(verified > last[0]);
                assertTrue(verified <= total);
                last[0] = verified;
                count[0]++;
            }).save(f.source, edits('B'));
            assertTrue("Expected multiple final-read chunks", count[0] >= 2);
            assertEquals(Files.size(f.checkpoint.toPath()), last[0]);
            assertEquals(edits('B'), f.vault.loadForSource(f.source));
            f.preservedSourceAndNoStages();
        }
    }
}
