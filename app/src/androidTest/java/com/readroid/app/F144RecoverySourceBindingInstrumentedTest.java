package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.KeyStore;
import java.util.Arrays;
import java.util.Collections;
import java.util.Map;
import java.util.UUID;
import static org.junit.Assert.*;

/**
 * F1.44: reject an APK source changed while an Activity-bound encrypted
 * checkpoint is staging, without disturbing the previous committed copy.
 */
@RunWith(AndroidJUnit4.class)
public final class F144RecoverySourceBindingInstrumentedTest {
    private static final String ENTRY = "assets/f144-source.txt";
    private static Map<String, String> changes(char revision) {
        return Collections.singletonMap(ENTRY, "F144-" + revision);
    }
    private static final class Fixture implements AutoCloseable {
        final File root, folder, source, checkpoint;
        final String alias;
        final RecoveryVault vault;
        final byte[] original;
        final String expectedSha;
        Fixture() throws Exception {
            Context ctx = InstrumentationRegistry.getInstrumentation()
                .getTargetContext();
            root = Files.createTempDirectory(ctx.getFilesDir().toPath(),
                "f144_source_binding_").toFile();
            folder = new File(root, "vault");
            source = new File(root, "accepted_source.apk");
            original = "F144 immutable accepted APK fixture"
                .getBytes(StandardCharsets.UTF_8);
            Files.write(source.toPath(), original);
            expectedSha = ApkIntegrity.sha256(source);
            alias = "negrescodroid.f144.test." + UUID.randomUUID();
            vault = new RecoveryVault(folder, alias);
            vault.save(source, changes('A'));
            checkpoint = new File(folder, "edit-plan-checkpoint.v1");
        }
        void assertOldEncryptedCheckpoint(byte[] prior) throws Exception {
            assertArrayEquals(prior, Files.readAllBytes(checkpoint.toPath()));
            assertArrayEquals(original, Files.readAllBytes(source.toPath()));
            assertEquals(changes('A'), vault.loadForSource(source));
            File[] temp = folder.listFiles((dir, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(temp);
            assertEquals(0, temp.length);
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
    @Test public void f144SourceChangeDuringStagePreservesPreviousA()
            throws Exception {
        try (Fixture f = new Fixture()) {
            byte[] prior = Files.readAllBytes(f.checkpoint.toPath());
            ExportSessionGuard.Token token = new ExportSessionGuard().begin();
            RecoveryVault altered = new RecoveryVault(f.folder, f.alias,
                stage -> {}, RecoveryStorageBudget.forDirectory(f.folder),
                (verified, total) -> {}, stage -> {
                    byte[] changed = f.original.clone();
                    changed[changed.length - 1] ^= 1; // same length, different SHA
                    Files.write(f.source.toPath(), changed);
                });
            try {
                altered.save(f.source, changes('B'), token, f.expectedSha);
                fail("Source mutated after initial digest must not replace A");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("APK original mudou"));
            } finally {
                // Restore only this isolated test fixture before authenticating A.
                Files.write(f.source.toPath(), f.original);
            }
            f.assertOldEncryptedCheckpoint(prior);
        }
    }
    @Test public void f144SourceMismatchBeforeStagingPreservesPreviousA()
            throws Exception {
        try (Fixture f = new Fixture()) {
            byte[] prior = Files.readAllBytes(f.checkpoint.toPath());
            ExportSessionGuard.Token token = new ExportSessionGuard().begin();
            String wrongSha = "0000000000000000000000000000000000000000000000000000000000000000";
            assertNotEquals(f.expectedSha, wrongSha);
            try {
                f.vault.save(f.source, changes('B'), token, wrongSha);
                fail("Mismatched accepted hash must be rejected immediately");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("APK original mudou"));
            }
            f.assertOldEncryptedCheckpoint(prior);
        }
    }
    @Test public void f144CurrentSourceAndTokenStillCommitB() throws Exception {
        try (Fixture f = new Fixture()) {
            ExportSessionGuard.Token token = new ExportSessionGuard().begin();
            byte[] prior = Files.readAllBytes(f.checkpoint.toPath());
            f.vault.save(f.source, changes('B'), token, f.expectedSha);
            assertTrue(token.isActive());
            assertFalse(Arrays.equals(prior, Files.readAllBytes(f.checkpoint.toPath())));
            assertArrayEquals(f.original, Files.readAllBytes(f.source.toPath()));
            assertEquals(changes('B'), f.vault.loadForSource(f.source));
            File[] temp = f.folder.listFiles((dir, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(temp);
            assertEquals(0, temp.length);
        }
    }
}
