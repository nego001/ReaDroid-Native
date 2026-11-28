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

/** F1.42: post-attestation, pre-return interruption in private test storage. */
@RunWith(AndroidJUnit4.class)
public final class F142PostAttestationInstrumentedTest {
    private static final String ENTRY = "assets/f142-attested.txt";
    private static Map<String, String> edits(char c) {
        char[] chars = new char[24000];
        Arrays.fill(chars, c);
        return Collections.singletonMap(ENTRY,
            "F142:" + c + ":" + new String(chars));
    }
    private static final class Fixture implements AutoCloseable {
        final File root, storage, source, checkpoint;
        final String alias;
        final RecoveryVault vault;
        final byte[] sourceBytes, originalCipher;
        Fixture() throws Exception {
            Context context = InstrumentationRegistry.getInstrumentation()
                .getTargetContext();
            root = Files.createTempDirectory(context.getFilesDir().toPath(),
                "f142_post_attestation_").toFile();
            storage = new File(root, "vault");
            source = new File(root, "source.apk");
            sourceBytes = "F142 isolated immutable source".getBytes(StandardCharsets.UTF_8);
            Files.write(source.toPath(), sourceBytes);
            alias = "negrescodroid.f142.test." + UUID.randomUUID();
            vault = new RecoveryVault(storage, alias);
            vault.save(source, edits('A'));
            checkpoint = new File(storage, "edit-plan-checkpoint.v1");
            originalCipher = Files.readAllBytes(checkpoint.toPath());
        }
        RecoveryVault observing(RecoveryVault.StageReadObserver progress,
                RecoveryVault.AfterFinalAttestation after) {
            return new RecoveryVault(storage, alias, stage -> {},
                RecoveryStorageBudget.forDirectory(storage),
                (verified, total) -> {}, stage -> {}, checkpoint -> {},
                checkpoint -> {}, progress, after);
        }
        void assertUnchangedSourceNoTemporary() throws Exception {
            assertArrayEquals(sourceBytes, Files.readAllBytes(source.toPath()));
            File[] stages = storage.listFiles((d, n) ->
                n.startsWith("checkpoint-") && n.endsWith(".tmp"));
            assertNotNull(stages);
            assertEquals(0, stages.length);
        }
        @Override public void close() throws Exception {
            vault.clear();
            Files.deleteIfExists(source.toPath());
            Files.deleteIfExists(storage.toPath());
            Files.deleteIfExists(root.toPath());
            KeyStore keys = KeyStore.getInstance("AndroidKeyStore");
            keys.load(null);
            if (keys.containsAlias(alias)) keys.deleteEntry(alias);
        }
    }
    @Test public void f142PostAttestationExceptionKeepsPromotedBRecoverable()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] progress = {0, 0};
            final int[] called = {0};
            try {
                f.observing((bytes, total) -> {
                    assertTrue(bytes > progress[0]);
                    progress[0] = bytes;
                    progress[1] = total;
                }, promoted -> {
                    called[0]++;
                    assertEquals(progress[1], progress[0]);
                    assertTrue(progress[1] > 8192);
                    assertEquals(f.checkpoint, promoted);
                    throw new InterruptedIOException("F142 stop after completed attestation");
                }).save(f.source, edits('B'));
                fail("An unacknowledged post-commit exception must reach caller");
            } catch (InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("F142 stop"));
            }
            assertEquals(1, called[0]);
            assertFalse(Arrays.equals(f.originalCipher,
                Files.readAllBytes(f.checkpoint.toPath())));
            assertEquals(edits('B'), f.vault.loadForSource(f.source));
            f.assertUnchangedSourceNoTemporary();
        }
    }
    @Test public void f142SuccessfulAttestationPrecedesSaveReturn()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] last = {0, 0};
            final int[] attestations = {0};
            f.observing((verified, total) -> {
                assertTrue(verified > last[0]);
                last[0] = verified;
                last[1] = total;
            }, promoted -> {
                attestations[0]++;
                assertEquals("Last chunk must have finished", last[1], last[0]);
                assertTrue(last[1] > 8192);
                assertEquals(f.checkpoint, promoted);
            }).save(f.source, edits('B'));
            assertEquals(1, attestations[0]);
            assertEquals(edits('B'), f.vault.loadForSource(f.source));
            f.assertUnchangedSourceNoTemporary();
        }
    }
    @Test public void f142FinalReadFailurePreventsAttestationCallback()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] invoked = {0};
            try {
                f.observing((verified, total) -> {
                    assertEquals(8192, verified);
                    assertTrue(total > verified);
                    throw new InterruptedIOException("F142 read stopped before attestation");
                }, promoted -> invoked[0]++).save(f.source, edits('B'));
                fail("Interrupted final read must not notify full attestation");
            } catch (InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("F142 read stopped"));
            }
            assertEquals(0, invoked[0]);
            // Atomic promotion already happened; do not incorrectly restore A.
            assertEquals(edits('B'), f.vault.loadForSource(f.source));
            f.assertUnchangedSourceNoTemporary();
        }
    }
}
