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
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

import static org.junit.Assert.*;

/**
 * F1.34: Android Keystore-backed checks for corrupt/truncated/replaced
 * encrypted stage AFTER fsync but BEFORE atomic promotion.
 * Every destructive mutation is restricted to a new test-only directory.
 */
@RunWith(AndroidJUnit4.class)
public final class F134RecoveryStageIntegrityInstrumentedTest {
    private static final String ENTRY = "assets/f134-confirmed.txt";
    private static final String REV_A = "Last accepted revision A";
    private static final String REV_B = "Never accept a corrupted revision B";

    private static Map<String, String> revision(String text) {
        return Collections.singletonMap(ENTRY, text);
    }

    private static final class Fixture implements AutoCloseable {
        final File root;
        final File vaultDir;
        final File original;
        final File accepted;
        final String keyAlias;
        final RecoveryVault vault;
        final byte[] encryptedA;
        final byte[] originalBytes;

        Fixture() throws Exception {
            Context ctx = InstrumentationRegistry.getInstrumentation().getTargetContext();
            root = Files.createTempDirectory(ctx.getFilesDir().toPath(),
                "f134_stage_integrity_").toFile();
            vaultDir = new File(root, "vault");
            original = new File(root, "original.apk");
            originalBytes = "F134 immutable local test APK bytes".getBytes(
                StandardCharsets.UTF_8);
            Files.write(original.toPath(), originalBytes);
            accepted = new File(vaultDir, "edit-plan-checkpoint.v1");
            keyAlias = "negrescodroid.f134.instrumented." + UUID.randomUUID();
            vault = new RecoveryVault(vaultDir, keyAlias);
            vault.save(original, revision(REV_A));
            encryptedA = Files.readAllBytes(accepted.toPath());
        }

        RecoveryVault withStageMutation(RecoveryVault.BeforeCommit mutation) {
            return new RecoveryVault(vaultDir, keyAlias, mutation);
        }

        void checkOriginalUnchanged() throws Exception {
            assertTrue("Last accepted ciphertext must still exist", accepted.isFile());
            assertArrayEquals("Corrupt staged write replaced accepted ciphertext",
                encryptedA, Files.readAllBytes(accepted.toPath()));
            assertEquals("Old checkpoint must decrypt using SAME Android key",
                revision(REV_A), vault.loadForSource(original));
            assertArrayEquals("Original source was unexpectedly edited",
                originalBytes, Files.readAllBytes(original.toPath()));
            File[] stages = vaultDir.listFiles((parent, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(stages);
            assertEquals("Failed save must clean up stage", 0, stages.length);
        }

        @Override public void close() throws Exception {
            vault.clear();
            Files.deleteIfExists(original.toPath());
            Files.deleteIfExists(vaultDir.toPath());
            Files.deleteIfExists(root.toPath());
            KeyStore store = KeyStore.getInstance("AndroidKeyStore");
            store.load(null);
            if (store.containsAlias(keyAlias)) store.deleteEntry(keyAlias);
        }
    }

    private static void rejectTamperedSave(Fixture f,
            RecoveryVault.BeforeCommit mutation) throws Exception {
        RecoveryVault attacker = f.withStageMutation(mutation);
        try {
            attacker.save(f.original, revision(REV_B));
            fail("Tampered encrypted temporary must never become checkpoint");
        } catch (IOException expected) {
            assertNotNull("Integrity failure must provide diagnostics",
                expected.getMessage());
        }
        f.checkOriginalUnchanged();
    }

    @Test public void f134TruncatedFsyncedStageCannotReplaceValidCiphertext()
            throws Exception {
        try (Fixture f = new Fixture()) {
            rejectTamperedSave(f, stage -> {
                byte[] bytes = Files.readAllBytes(stage.toPath());
                assertTrue(bytes.length > 33);
                Files.write(stage.toPath(), Arrays.copyOf(bytes, bytes.length - 1));
            });
        }
    }

    @Test public void f134SameLengthBitFlipCannotReplaceValidCiphertext()
            throws Exception {
        try (Fixture f = new Fixture()) {
            rejectTamperedSave(f, stage -> {
                byte[] bytes = Files.readAllBytes(stage.toPath());
                bytes[bytes.length / 2] ^= (byte) 0x5a;
                Files.write(stage.toPath(), bytes);
            });
        }
    }

    @Test public void f134DeletedTemporaryCannotEraseOldRecovery()
            throws Exception {
        try (Fixture f = new Fixture()) {
            rejectTamperedSave(f, stage ->
                assertTrue("Test stage should exist before deletion",
                    Files.deleteIfExists(stage.toPath())));
        }
    }

    @Test public void f134SymlinkToMatchingBytesMustNeverBePromoted()
            throws Exception {
        try (Fixture f = new Fixture()) {
            File replacement = new File(f.root, "shadow_encrypted_stage.bin");
            try {
                rejectTamperedSave(f, stage -> {
                    byte[] bytes = Files.readAllBytes(stage.toPath());
                    // Same bytes and same length, but outside the trusted
                    // staging directory: rejecting the symlink is essential.
                    Files.write(replacement.toPath(), bytes);
                    Files.delete(stage.toPath());
                    Files.createSymbolicLink(stage.toPath(), replacement.toPath());
                });
                assertTrue("Test-owned target must not be modified",
                    replacement.isFile());
            } finally {
                Files.deleteIfExists(replacement.toPath());
            }
        }
    }

    @Test public void f134ReaderCannotSeeCorruptedStageDuringConcurrentSave()
            throws Exception {
        ExecutorService threads = Executors.newFixedThreadPool(2);
        CountDownLatch staged = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        try (Fixture f = new Fixture()) {
            RecoveryVault corrupted = f.withStageMutation(stage -> {
                staged.countDown();
                try {
                    if (!release.await(20, TimeUnit.SECONDS))
                        throw new IOException("F134 timed out waiting for reader");
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new java.io.InterruptedIOException(
                        "F134 stage worker interrupted");
                }
                // Destroy bytes while a concurrent reader is waiting on
                // RecoveryVault's one-process transaction lock.
                byte[] bytes = Files.readAllBytes(stage.toPath());
                bytes[0] ^= (byte) 0x01;
                Files.write(stage.toPath(), bytes);
            });
            Future<Boolean> writer = threads.submit(() -> {
                try {
                    corrupted.save(f.original, revision(REV_B));
                    return false;
                } catch (IOException expected) {
                    return expected.getMessage() != null;
                }
            });
            try {
                assertTrue("Writer never reached precommit boundary",
                    staged.await(20, TimeUnit.SECONDS));
                CountDownLatch readerStarted = new CountDownLatch(1);
                Future<Map<String, String>> reader = threads.submit(() -> {
                    readerStarted.countDown();
                    return f.vault.loadForSource(f.original);
                });
                assertTrue(readerStarted.await(10, TimeUnit.SECONDS));
                try {
                    reader.get(200, TimeUnit.MILLISECONDS);
                    fail("Reader may not observe an uncommitted stage");
                } catch (TimeoutException expected) {
                    // Reader remains blocked until the transaction finishes.
                } finally {
                    release.countDown();
                }
                assertTrue("Corrupted writer must fail", writer.get(40, TimeUnit.SECONDS));
                assertEquals(revision(REV_A), reader.get(40, TimeUnit.SECONDS));
                f.checkOriginalUnchanged();
            } finally {
                release.countDown();
                writer.get(40, TimeUnit.SECONDS);
            }
        } finally {
            release.countDown();
            threads.shutdownNow();
            assertTrue(threads.awaitTermination(40, TimeUnit.SECONDS));
        }
    }
}
