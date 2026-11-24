package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.KeyStore;
import java.util.Arrays;
import java.util.Collections;
import java.util.Map;
import java.util.UUID;
import static org.junit.Assert.*;

/**
 * F1.45: source mutation after atomic promotion must never report ordinary
 * success or falsely claim rollback. Everything uses disposable test storage.
 */
@RunWith(AndroidJUnit4.class)
public final class F145PostCommitSourceInstrumentedTest {
    private static final String ENTRY = "assets/f145-source.txt";
    private static Map<String, String> edits(char c) {
        return Collections.singletonMap(ENTRY, "F145:" + c);
    }
    private static final class Fixture implements AutoCloseable {
        final File root, folder, source, checkpoint;
        final String alias, expectedSha;
        final byte[] original, initialCipher;
        final RecoveryVault vault;

        Fixture() throws Exception {
            Context context = InstrumentationRegistry.getInstrumentation()
                .getTargetContext();
            root = Files.createTempDirectory(context.getFilesDir().toPath(),
                "f145_post_commit_").toFile();
            folder = new File(root, "vault");
            source = new File(root, "accepted_source.apk");
            original = "F145 immutable source for recovery".getBytes(StandardCharsets.UTF_8);
            Files.write(source.toPath(), original);
            expectedSha = ApkIntegrity.sha256(source);
            alias = "negrescodroid.f145.test." + UUID.randomUUID();
            vault = new RecoveryVault(folder, alias);
            vault.save(source, edits('A'));
            checkpoint = new File(folder, "edit-plan-checkpoint.v1");
            initialCipher = Files.readAllBytes(checkpoint.toPath());
        }

        RecoveryVault afterAttestation(RecoveryVault.AfterFinalAttestation after) {
            return new RecoveryVault(folder, alias, stage -> {},
                RecoveryStorageBudget.forDirectory(folder),
                (read, total) -> {}, stage -> {}, moved -> {},
                synced -> {}, (read, total) -> {}, after);
        }

        void assertCommittedBAndNoStages() throws Exception {
            assertTrue(checkpoint.isFile());
            assertFalse("Post-commit errors must not restore A",
                Arrays.equals(initialCipher, Files.readAllBytes(checkpoint.toPath())));
            assertArrayEquals(original, Files.readAllBytes(source.toPath()));
            assertEquals(edits('B'), vault.loadForSource(source));
            File[] remains = folder.listFiles((d, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(remains);
            assertEquals(0, remains.length);
        }

        @Override public void close() throws Exception {
            vault.clear();
            Files.deleteIfExists(source.toPath());
            Files.deleteIfExists(folder.toPath());
            Files.deleteIfExists(root.toPath());
            KeyStore keys = KeyStore.getInstance("AndroidKeyStore");
            keys.load(null);
            if (keys.containsAlias(alias)) keys.deleteEntry(alias);
        }
    }

    @Test public void f145ChangedSourceAfterPromotionReportsCommittedCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] callbackCount = {0};
            try {
                f.afterAttestation(promoted -> {
                    callbackCount[0]++;
                    assertEquals(f.checkpoint, promoted);
                    assertFalse(Arrays.equals(f.initialCipher,
                        Files.readAllBytes(promoted.toPath())));
                    byte[] changed = f.original.clone();
                    changed[changed.length - 1] ^= 0x10;
                    Files.write(f.source.toPath(), changed);
                }).save(f.source, edits('B'), new ExportSessionGuard().begin(),
                    f.expectedSha);
                fail("A post-commit changed source cannot report clean success");
            } catch (RecoveryVault.PostCommitSourceException expected) {
                assertTrue(expected.getMessage().contains("já gravada"));
                assertTrue(expected.getMessage().contains("mudou"));
            } finally {
                Files.write(f.source.toPath(), f.original);
            }
            assertEquals(1, callbackCount[0]);
            f.assertCommittedBAndNoStages();
        }
    }

    @Test public void f145MissingSourceAfterPromotionReportsCommittedCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            try {
                f.afterAttestation(promoted -> {
                    assertEquals(f.checkpoint, promoted);
                    Files.delete(f.source.toPath());
                }).save(f.source, edits('B'), new ExportSessionGuard().begin(),
                    f.expectedSha);
                fail("A vanished source must not be reported as fully verified");
            } catch (RecoveryVault.PostCommitSourceException expected) {
                assertTrue(expected.getMessage().contains("já gravada"));
                assertTrue(expected.getMessage().contains("não foi possível"));
            } finally {
                Files.write(f.source.toPath(), f.original);
            }
            f.assertCommittedBAndNoStages();
        }
    }

    @Test public void f145StableSourceReturnsNormalSuccess()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] callbackCount = {0};
            f.afterAttestation(promoted -> {
                callbackCount[0]++;
                assertEquals(f.checkpoint, promoted);
            }).save(f.source, edits('B'), new ExportSessionGuard().begin(),
                f.expectedSha);
            assertEquals(1, callbackCount[0]);
            f.assertCommittedBAndNoStages();
        }
    }

    @Test public void f145LegacySaveWithoutExpectedHashRemainsCompatible()
            throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.source, edits('B'));
            f.assertCommittedBAndNoStages();
        }
    }
}
