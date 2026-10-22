package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.attribute.FileTime;
import java.security.KeyStore;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

import static org.junit.Assert.*;

/**
 * Uses a unique test Keystore alias and directory per test, so running this
 * on a device never overwrites the user's production recovery checkpoint.
 */
@RunWith(AndroidJUnit4.class)
public final class RecoveryVaultInstrumentedTest {
    private static final class Fixture implements AutoCloseable {
        final File folder;
        final File original;
        final File other;
        final String alias;
        final RecoveryVault vault;

        Fixture() throws Exception {
            Context ctx = InstrumentationRegistry.getInstrumentation().getTargetContext();
            String id = UUID.randomUUID().toString();
            folder = new File(ctx.getFilesDir(), "v3_recovery_test_" + id);
            assertTrue(folder.mkdir());
            alias = "negrescodroid.instrumented.recovery." + id;
            vault = new RecoveryVault(folder, alias);
            original = new File(folder, "original.apk");
            other = new File(folder, "other.apk");
            Files.write(original.toPath(), "APK A for isolated recovery test"
                .getBytes(StandardCharsets.UTF_8));
            Files.write(other.toPath(), "APK B for isolated recovery test"
                .getBytes(StandardCharsets.UTF_8));
        }

        @Override public void close() throws Exception {
            vault.clear();
            Files.deleteIfExists(original.toPath());
            Files.deleteIfExists(other.toPath());
            Files.deleteIfExists(folder.toPath());
            KeyStore store = KeyStore.getInstance("AndroidKeyStore");
            store.load(null);
            if (store.containsAlias(alias)) store.deleteEntry(alias);
        }
    }

    private static Map<String, String> example() {
        Map<String, String> edits = new LinkedHashMap<>();
        edits.put("assets/settings.json", "{\"token\":\"private-local-test\"}");
        edits.put("assets/readme.txt", "Somente em memória");
        return edits;
    }

    @Test public void encryptedCheckpointCanBeRestoredAfterNewVaultInstance()
            throws Exception {
        try (Fixture f = new Fixture()) {
            byte[] original = Files.readAllBytes(f.original.toPath());
            Map<String, String> expected = example();
            f.vault.save(f.original, expected);
            assertTrue(f.vault.hasCheckpoint());
            byte[] encoded = Files.readAllBytes(
                new File(f.folder, "edit-plan-checkpoint.v1").toPath());
            assertFalse("Plaintext must not appear on disk",
                new String(encoded, StandardCharsets.ISO_8859_1)
                    .contains("private-local-test"));
            // A fresh object simulates a restarted process, not Activity recreation.
            RecoveryVault reopened = new RecoveryVault(f.folder, f.alias);
            assertEquals(expected, reopened.loadForSource(f.original));
            assertArrayEquals("Source file must be byte-for-byte unchanged",
                original, Files.readAllBytes(f.original.toPath()));
        }
    }

    @Test public void wrongApkIsRejectedWithoutChangingCheckpoint() throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            try {
                f.vault.loadForSource(f.other);
                fail("Cannot restore edits from another APK");
            } catch (SecurityException expected) {
                assertTrue(expected.getMessage().contains("outro APK"));
            }
            assertEquals(example(), f.vault.loadForSource(f.original));
        }
    }

    @Test public void modificationOfEncryptedBytesIsRejected() throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            File saved = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] ciphertext = Files.readAllBytes(saved.toPath());
            ciphertext[ciphertext.length - 1] ^= 1;
            Files.write(saved.toPath(), ciphertext);
            try {
                f.vault.loadForSource(f.original);
                fail("Tampered checkpoint passed AES-GCM authentication");
            } catch (javax.crypto.AEADBadTagException expected) {
                // Authenticated encryption must reject the payload before JSON parse.
            }
        }
    }

    @Test public void invalidAndOversizedPlansNeverOverwriteValidBackup()
            throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            Map<String, String> invalid = example();
            invalid.put("../escape.json", "bad");
            try {
                f.vault.save(f.original, invalid);
                fail("Unsafe path should not be checkpointed");
            } catch (IllegalArgumentException expected) {
                assertEquals(example(), f.vault.loadForSource(f.original));
            }
            Map<String, String> huge = new LinkedHashMap<>();
            for (int i = 0; i < 5; i++) {
                char[] text = new char[128000];
                Arrays.fill(text, 'x');
                huge.put("assets/oversize_" + i + ".txt", new String(text));
            }
            try {
                f.vault.save(f.original, huge);
                fail("Oversized plaintext must be refused");
            } catch (IllegalArgumentException expected) {
                assertEquals(example(), f.vault.loadForSource(f.original));
            }
        }
    }

    @Test public void malformedUnicodeDoesNotOverwriteEncryptedCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            Map<String, String> previous = example();
            f.vault.save(f.original, previous);
            File checkpoint = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] immutable = Files.readAllBytes(checkpoint.toPath());
            Map<String, String> invalid = example();
            invalid.put("assets/config.json", "abc" + (char) 0xD83D);
            try {
                f.vault.save(f.original, invalid);
                fail("Malformed UTF-16 must not replace valid ciphertext");
            } catch (IllegalArgumentException expected) {
                assertArrayEquals(immutable, Files.readAllBytes(checkpoint.toPath()));
                assertEquals(previous, f.vault.loadForSource(f.original));
            }
        }
    }

    @Test public void missingKeystoreKeyIsNotSilentlyRegeneratedOnLoad()
            throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            File checkpoint = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] saved = Files.readAllBytes(checkpoint.toPath());
            KeyStore store = KeyStore.getInstance("AndroidKeyStore");
            store.load(null);
            assertTrue(store.containsAlias(f.alias));
            store.deleteEntry(f.alias);
            assertFalse(store.containsAlias(f.alias));
            try {
                f.vault.loadForSource(f.original);
                fail("A lost key must not be silently replaced during restore");
            } catch (SecurityException expected) {
                assertTrue(expected.getMessage().contains("Keystore"));
            }
            store.load(null);
            assertFalse("Loading must not mint an unrecoverable replacement key",
                store.containsAlias(f.alias));
            assertArrayEquals(saved, Files.readAllBytes(checkpoint.toPath()));
        }
    }

    @Test public void storageFailureDoesNotChangePreviousEncryptedCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            File checkpoint = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] saved = Files.readAllBytes(checkpoint.toPath());
            File blockedStorage = new File(f.folder, "not_a_directory");
            Files.write(blockedStorage.toPath(), new byte[]{1, 2, 3});
            RecoveryVault blockedVault = new RecoveryVault(blockedStorage, f.alias);
            try {
                blockedVault.save(f.original, example());
                fail("A file cannot be used as a recovery directory");
            } catch (java.io.IOException expected) {
                assertTrue(blockedStorage.isFile());
                assertArrayEquals(saved, Files.readAllBytes(checkpoint.toPath()));
                assertEquals(example(), f.vault.loadForSource(f.original));
            } finally {
                Files.deleteIfExists(blockedStorage.toPath());
            }
        }
    }

    @Test public void lyingMapSizeCannotSaveAnUnrecoverableCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            File checkpoint = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] saved = Files.readAllBytes(checkpoint.toPath());
            Map<String, String> deceptive = new LinkedHashMap<String, String>() {
                @Override public int size() { return 1; }
            };
            for (int i = 0; i < 101; i++) {
                deceptive.put("assets/change_" + i + ".txt", "safe");
            }
            try {
                f.vault.save(f.original, deceptive);
                fail("A deceptive Map must not bypass the 100-change limit");
            } catch (IllegalArgumentException expected) {
                assertArrayEquals(saved, Files.readAllBytes(checkpoint.toPath()));
                assertEquals(example(), f.vault.loadForSource(f.original));
            }
        }
    }

    @Test public void boundedReaderAllowsExactFileBudgetButRejectsOneExtraByte()
            throws Exception {
        // The stream check also protects against a size change after stat().
        byte[] exact = new byte[512 * 1024 + 256];
        exact[0] = 10;
        exact[exact.length - 1] = 99;
        assertArrayEquals(exact, RecoveryVault.readBounded(
            new ByteArrayInputStream(exact)));
        byte[] oversized = Arrays.copyOf(exact, exact.length + 1);
        try {
            RecoveryVault.readBounded(new ByteArrayInputStream(oversized));
            fail("The reader must stop at MAX_FILE + 1 bytes");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("limite"));
        }
    }

    @Test public void badEnvelopeAndTruncatedCiphertextAreRejectedWithoutMutation()
            throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            File saved = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] valid = Files.readAllBytes(saved.toPath());
            byte[] wrongMagic = valid.clone();
            wrongMagic[0] ^= 1;
            Files.write(saved.toPath(), wrongMagic);
            try {
                f.vault.loadForSource(f.original);
                fail("Wrong magic must not be decrypted");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("Formato"));
            }
            byte[] wrongVersion = valid.clone();
            wrongVersion[4] ^= 1;
            Files.write(saved.toPath(), wrongVersion);
            try {
                f.vault.loadForSource(f.original);
                fail("Unknown format version must be rejected");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("Versão"));
            }
            Files.write(saved.toPath(), Arrays.copyOf(valid, valid.length - 1));
            try {
                f.vault.loadForSource(f.original);
                fail("Truncated ciphertext must fail authentication");
            } catch (javax.crypto.AEADBadTagException expected) {
                // No invalid plaintext or partial edits are returned.
            }
            Files.write(saved.toPath(), valid);
            assertEquals(example(), f.vault.loadForSource(f.original));
        }
    }

    @Test public void oversizedRecoveryFileIsRejectedWithoutCreatingKeystoreKey()
            throws Exception {
        try (Fixture f = new Fixture()) {
            File file = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] oversized = new byte[512 * 1024 + 257];
            Files.write(file.toPath(), oversized);
            KeyStore store = KeyStore.getInstance("AndroidKeyStore");
            store.load(null);
            assertFalse(store.containsAlias(f.alias));
            try {
                f.vault.loadForSource(f.original);
                fail("Oversized data must be rejected before Keystore use");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("inválida"));
            }
            store.load(null);
            assertFalse(store.containsAlias(f.alias));
            assertArrayEquals(oversized, Files.readAllBytes(file.toPath()));
        }
    }

    @Test public void savingWithLostKeyCannotOverwriteExistingRecovery()
            throws Exception {
        try (Fixture f = new Fixture()) {
            Map<String, String> existing = example();
            f.vault.save(f.original, existing);
            File checkpoint = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] encrypted = Files.readAllBytes(checkpoint.toPath());
            KeyStore store = KeyStore.getInstance("AndroidKeyStore");
            store.load(null);
            assertTrue(store.containsAlias(f.alias));
            store.deleteEntry(f.alias);
            Map<String, String> replacement = new LinkedHashMap<>();
            replacement.put("assets/new.txt", "second recovery");
            try {
                f.vault.save(f.original, replacement);
                fail("Saving cannot discard a checkpoint with a lost Keystore identity");
            } catch (SecurityException expected) {
                assertTrue(expected.getMessage().contains("Cópia existente"));
            }
            store.load(null);
            assertFalse(store.containsAlias(f.alias));
            assertArrayEquals("Old encrypted checkpoint must remain intact",
                encrypted, Files.readAllBytes(checkpoint.toPath()));
            // Explicit deletion is a separate user action and is the only way
            // to start over after losing the key. The old data is not recovered.
            f.vault.clear();
            f.vault.save(f.original, replacement);
            assertEquals(replacement, f.vault.loadForSource(f.original));
        }
    }

    @Test public void secondSaveWithOriginalKeystoreKeyReplacesCheckpointSafely()
            throws Exception {
        try (Fixture f = new Fixture()) {
            byte[] originalApk = Files.readAllBytes(f.original.toPath());
            Map<String, String> first = example();
            f.vault.save(f.original, first);
            File checkpoint = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] before = Files.readAllBytes(checkpoint.toPath());
            Map<String, String> second = new LinkedHashMap<>();
            second.put("assets/second.json", "segundo plano válido");
            f.vault.save(f.original, second);
            byte[] after = Files.readAllBytes(checkpoint.toPath());
            assertFalse("Re-encrypted checkpoint must use a fresh GCM IV",
                Arrays.equals(before, after));
            RecoveryVault reopened = new RecoveryVault(f.folder, f.alias);
            assertEquals(second, reopened.loadForSource(f.original));
            assertArrayEquals(originalApk, Files.readAllBytes(f.original.toPath()));
        }
    }

    private static void assertNoStagedCheckpoint(Fixture f) {
        File[] remains = f.folder.listFiles((dir, name) ->
            name.startsWith("checkpoint-") && name.endsWith(".tmp"));
        assertNotNull(remains);
        assertEquals("No encrypted temporary checkpoint may remain", 0, remains.length);
    }

    @Test public void failedCommitAfterSyncKeepsOldEncryptedCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            Map<String, String> previous = example();
            f.vault.save(f.original, previous);
            File checkpoint = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] encrypted = Files.readAllBytes(checkpoint.toPath());
            byte[] originalApk = Files.readAllBytes(f.original.toPath());
            RecoveryVault failing = new RecoveryVault(f.folder, f.alias, staged -> {
                assertTrue("Staged checkpoint must have been written", staged.length() > 0);
                throw new IOException("Falha simulada após sincronização");
            });
            Map<String, String> replacement = new LinkedHashMap<>();
            replacement.put("assets/novo.txt", "não substituir cópia existente");
            try {
                failing.save(f.original, replacement);
                fail("Simulated pre-commit failure must prevent replacement");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("simulada"));
            }
            assertArrayEquals(encrypted, Files.readAllBytes(checkpoint.toPath()));
            assertEquals(previous, f.vault.loadForSource(f.original));
            assertArrayEquals(originalApk, Files.readAllBytes(f.original.toPath()));
            assertNoStagedCheckpoint(f);
        }
    }

    @Test public void cancellationJustBeforeCommitKeepsOldCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            Map<String, String> previous = example();
            f.vault.save(f.original, previous);
            File checkpoint = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] encrypted = Files.readAllBytes(checkpoint.toPath());
            RecoveryVault interrupted = new RecoveryVault(f.folder, f.alias,
                staged -> Thread.currentThread().interrupt());
            Map<String, String> replacement = new LinkedHashMap<>();
            replacement.put("assets/novo.txt", "nunca sobrescrever");
            try {
                interrupted.save(f.original, replacement);
                fail("Cancelled write must not commit encrypted checkpoint");
            } catch (java.io.InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("interrompida"));
            } finally {
                Thread.interrupted(); // reset only this test thread's flag
            }
            assertArrayEquals(encrypted, Files.readAllBytes(checkpoint.toPath()));
            assertEquals(previous, f.vault.loadForSource(f.original));
            assertNoStagedCheckpoint(f);
        } finally {
            Thread.interrupted();
        }
    }

    @Test public void staleEncryptedStagesAreRemovedWithoutTouchingCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            Map<String, String> valid = example();
            f.vault.save(f.original, valid);
            File checkpoint = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] checkpointBytes = Files.readAllBytes(checkpoint.toPath());
            File stale = File.createTempFile("checkpoint-", ".tmp", f.folder);
            Files.write(stale.toPath(), new byte[]{3, 4, 5});
            File fresh = File.createTempFile("checkpoint-", ".tmp", f.folder);
            Files.write(fresh.toPath(), new byte[]{6, 7});
            File unrelated = new File(f.folder, "notes.tmp");
            Files.write(unrelated.toPath(), new byte[]{8});
            File matchedDirectory = new File(f.folder, "checkpoint-directory.tmp");
            assertTrue(matchedDirectory.mkdir());
            try {
                long now = System.currentTimeMillis();
                Files.setLastModifiedTime(stale.toPath(),
                    FileTime.fromMillis(now - 48L * 60 * 60 * 1000));
                assertEquals(1, RecoveryVault.pruneAbandonedStages(f.folder, now));
                assertFalse(stale.exists());
                assertTrue("Recent staging may be an active save", fresh.exists());
                assertTrue(unrelated.isFile());
                assertTrue("A directory must never be removed", matchedDirectory.isDirectory());
                assertArrayEquals(checkpointBytes, Files.readAllBytes(checkpoint.toPath()));
                assertEquals(valid, f.vault.loadForSource(f.original));
            } finally {
                Files.deleteIfExists(stale.toPath());
                Files.deleteIfExists(fresh.toPath());
                Files.deleteIfExists(unrelated.toPath());
                Files.deleteIfExists(matchedDirectory.toPath());
            }
        }
    }

    @Test public void savePrunesOldStageWithoutChangingValidRecoveryPlan()
            throws Exception {
        try (Fixture f = new Fixture()) {
            Map<String, String> valid = example();
            f.vault.save(f.original, valid);
            byte[] source = Files.readAllBytes(f.original.toPath());
            File stale = File.createTempFile("checkpoint-", ".tmp", f.folder);
            Files.write(stale.toPath(), new byte[]{1, 2, 3});
            Files.setLastModifiedTime(stale.toPath(),
                FileTime.fromMillis(System.currentTimeMillis() - 48L * 60 * 60 * 1000));
            try {
                f.vault.save(f.original, valid);
                assertFalse("Next successful save should clean abandoned stage",
                    stale.exists());
                assertEquals(valid, f.vault.loadForSource(f.original));
                assertArrayEquals(source, Files.readAllBytes(f.original.toPath()));
                assertNoStagedCheckpoint(f);
            } finally {
                Files.deleteIfExists(stale.toPath());
            }
        }
    }

    private static RecoveryVault pausedBeforeCommit(Fixture f,
            CountDownLatch written, CountDownLatch release) {
        return new RecoveryVault(f.folder, f.alias, staged -> {
            assertTrue(staged.length() > 0);
            written.countDown();
            try {
                if (!release.await(45, TimeUnit.SECONDS))
                    throw new IOException("Timeout waiting for test to release commit");
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                throw new java.io.InterruptedIOException("Gravação interrompida no teste");
            }
        });
    }

    @Test public void deleteWaitsForInFlightSaveThenRemovesCheckpoint()
            throws Exception {
        ExecutorService workers = Executors.newFixedThreadPool(2);
        CountDownLatch written = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            RecoveryVault paused = pausedBeforeCommit(f, written, release);
            Map<String, String> updated = new LinkedHashMap<>();
            updated.put("assets/novo.txt", "salvamento na fila");
            Future<Void> first = workers.submit(() -> {
                paused.save(f.original, updated);
                return null;
            });
            try {
                assertTrue("Saving must reach the pre-commit seam",
                    written.await(45, TimeUnit.SECONDS));
                CountDownLatch deleteStarted = new CountDownLatch(1);
                Future<Void> deletion = workers.submit(() -> {
                    deleteStarted.countDown();
                    f.vault.clear();
                    return null;
                });
                assertTrue(deleteStarted.await(15, TimeUnit.SECONDS));
                try {
                    deletion.get(250, TimeUnit.MILLISECONDS);
                    fail("Deletion cannot pass an in-flight checkpoint save");
                } catch (TimeoutException expected) {
                    // The second RecoveryVault instance shares the transaction lock.
                } finally {
                    release.countDown();
                }
                first.get(60, TimeUnit.SECONDS);
                deletion.get(60, TimeUnit.SECONDS);
                assertFalse("A user-requested deletion must remain the final action",
                    f.vault.hasCheckpoint());
                assertNoStagedCheckpoint(f);
            } finally {
                release.countDown();
                first.get(60, TimeUnit.SECONDS);
            }
        } finally {
            release.countDown();
            workers.shutdownNow();
            assertTrue(workers.awaitTermination(60, TimeUnit.SECONDS));
        }
    }

    @Test public void laterConcurrentSaveWinsWithoutLostUpdates()
            throws Exception {
        ExecutorService workers = Executors.newFixedThreadPool(2);
        CountDownLatch written = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        try (Fixture f = new Fixture()) {
            RecoveryVault paused = pausedBeforeCommit(f, written, release);
            Map<String, String> firstPlan = new LinkedHashMap<>();
            firstPlan.put("assets/first.txt", "primeiro");
            Map<String, String> secondPlan = new LinkedHashMap<>();
            secondPlan.put("assets/second.txt", "segundo");
            Future<Void> first = workers.submit(() -> {
                paused.save(f.original, firstPlan);
                return null;
            });
            try {
                assertTrue(written.await(45, TimeUnit.SECONDS));
                CountDownLatch secondStarted = new CountDownLatch(1);
                Future<Void> second = workers.submit(() -> {
                    secondStarted.countDown();
                    f.vault.save(f.original, secondPlan);
                    return null;
                });
                assertTrue(secondStarted.await(15, TimeUnit.SECONDS));
                try {
                    second.get(250, TimeUnit.MILLISECONDS);
                    fail("Later save must wait for the first commit");
                } catch (TimeoutException expected) {
                    // The later operation must not write during first staging.
                } finally {
                    release.countDown();
                }
                first.get(60, TimeUnit.SECONDS);
                second.get(60, TimeUnit.SECONDS);
                assertEquals(secondPlan, f.vault.loadForSource(f.original));
                assertNoStagedCheckpoint(f);
            } finally {
                release.countDown();
                first.get(60, TimeUnit.SECONDS);
            }
        } finally {
            release.countDown();
            workers.shutdownNow();
            assertTrue(workers.awaitTermination(60, TimeUnit.SECONDS));
        }
    }

    @Test public void deletionRemovesCheckpointButNotOriginal() throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            f.vault.clear();
            assertFalse(f.vault.hasCheckpoint());
            assertTrue(f.original.isFile());
            try {
                f.vault.loadForSource(f.original);
                fail("Deleted backup must not be loadable");
            } catch (java.io.IOException expected) {
                assertFalse(f.vault.hasCheckpoint());
            }
        }
    }
}
