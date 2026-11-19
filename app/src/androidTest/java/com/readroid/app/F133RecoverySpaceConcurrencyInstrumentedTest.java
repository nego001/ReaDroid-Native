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
import java.util.Collections;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.Assert.*;

/**
 * F1.33: deterministic available-space changes + real Android Keystore
 * encryption with concurrent vault readers/deleters on actual threads.
 * Does NOT fill device storage or claim to simulate a kernel ENOSPC syscall.
 */
@RunWith(AndroidJUnit4.class)
public final class F133RecoverySpaceConcurrencyInstrumentedTest {
    private static final long ENOUGH = 64L * 1024 * 1024;
    private static final String TEXT_PATH = "assets/f133-recovery.txt";

    private static final class Fixture implements AutoCloseable {
        final File root;
        final File folder;
        final File apk;
        final String alias;
        final RecoveryVault vault;
        final byte[] original;

        Fixture() throws Exception {
            Context context =
                InstrumentationRegistry.getInstrumentation().getTargetContext();
            root = Files.createTempDirectory(context.getFilesDir().toPath(),
                "f133_private_").toFile();
            folder = new File(root, "encrypted");
            apk = new File(root, "accepted.apk");
            original = "F133 accepted APK source bytes".getBytes(StandardCharsets.UTF_8);
            Files.write(apk.toPath(), original);
            alias = "negrescodroid.f133.instrumented." + UUID.randomUUID();
            vault = new RecoveryVault(folder, alias);
        }

        File committed() { return new File(folder, "edit-plan-checkpoint.v1"); }

        void noPartialStages() {
            File[] stages = folder.listFiles((dir, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull("Recovery folder unexpectedly missing", stages);
            assertEquals("Failed write left encrypted temp file behind", 0,
                stages.length);
        }

        void unchanged(byte[] accepted, Map<String, String> expected)
                throws Exception {
            assertArrayEquals("Committed ciphertext must not be replaced",
                accepted, Files.readAllBytes(committed().toPath()));
            assertEquals("Recovery plan must decrypt with original Keystore alias",
                expected, vault.loadForSource(apk));
            assertArrayEquals("Accepted source APK modified",
                original, Files.readAllBytes(apk.toPath()));
            noPartialStages();
        }

        @Override public void close() throws Exception {
            vault.clear();
            Files.deleteIfExists(apk.toPath());
            Files.deleteIfExists(folder.toPath());
            Files.deleteIfExists(root.toPath());
            KeyStore keys = KeyStore.getInstance("AndroidKeyStore");
            keys.load(null);
            if (keys.containsAlias(alias)) keys.deleteEntry(alias);
        }
    }

    private static Map<String, String> revision(String revision) {
        return Collections.singletonMap(TEXT_PATH, revision);
    }

    private static void lowSpace(IOException error) {
        assertTrue("Failure must explicitly report insufficient space: " + error,
            error.getMessage() != null
                && error.getMessage().contains("Espaço insuficiente"));
    }

    @Test public void f133InsufficientRoomBeforeStagingCannotChangeOldCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            Map<String, String> old = revision("accepted A");
            f.vault.save(f.apk, old);
            byte[] accepted = Files.readAllBytes(f.committed().toPath());
            RecoveryVault noRoom = new RecoveryVault(f.folder, f.alias,
                staged -> fail("Low space must fail BEFORE opening staged file"),
                () -> 0L);
            try {
                noRoom.save(f.apk, revision("rejected B"));
                fail("A low-space checkpoint cannot commit");
            } catch (IOException expected) { lowSpace(expected); }
            f.unchanged(accepted, old);
        }
    }

    @Test public void f133StorageDropsAfterFsyncBeforeMoveOldVersionSurvives()
            throws Exception {
        try (Fixture f = new Fixture()) {
            Map<String, String> old = revision("accepted A");
            Map<String, String> newer = revision("accepted C");
            f.vault.save(f.apk, old);
            byte[] accepted = Files.readAllBytes(f.committed().toPath());
            AtomicLong free = new AtomicLong(ENOUGH);
            RecoveryVault lowAfterSync = new RecoveryVault(f.folder, f.alias,
                staged -> {
                    assertTrue("Stage must exist after fsync", staged.length() >= 33);
                    assertArrayEquals("Old ciphertext must remain during stage",
                        accepted, Files.readAllBytes(f.committed().toPath()));
                    free.set(0);
                }, free::get);
            try {
                lowAfterSync.save(f.apk, revision("rejected B"));
                fail("Falling free-space budget must reject final commit");
            } catch (IOException expected) { lowSpace(expected); }
            f.unchanged(accepted, old);
            // A later save CAN replace the checkpoint after space returns.
            free.set(ENOUGH);
            f.vault.save(f.apk, newer);
            assertEquals(newer, f.vault.loadForSource(f.apk));
            assertFalse("New AES-GCM encryption must use a fresh IV",
                java.util.Arrays.equals(accepted,
                    Files.readAllBytes(f.committed().toPath())));
            f.noPartialStages();
        }
    }

    private static RecoveryVault blockedLowSpace(Fixture f, AtomicLong free,
            CountDownLatch staged, CountDownLatch release) {
        return new RecoveryVault(f.folder, f.alias, file -> {
            assertTrue("Synchronized encrypted stage missing", file.length() >= 33);
            staged.countDown();
            try {
                if (!release.await(20, TimeUnit.SECONDS))
                    throw new IOException("F133 test timed out waiting to release stage");
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                throw new InterruptedIOException("F133 worker interrupted");
            }
            free.set(0);
        }, free::get);
    }

    private static boolean attemptsRejectedSave(RecoveryVault vault, Fixture f)
            throws Exception {
        try {
            vault.save(f.apk, revision("never committed B"));
            return false;
        } catch (IOException low) {
            lowSpace(low);
            return true;
        }
    }

    @Test public void f133ConcurrentReadWaitsForFailedSaveAndGetsLastGoodPlan()
            throws Exception {
        ExecutorService workers = Executors.newFixedThreadPool(2);
        CountDownLatch staged = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        try (Fixture f = new Fixture()) {
            Map<String, String> old = revision("accepted A");
            f.vault.save(f.apk, old);
            byte[] accepted = Files.readAllBytes(f.committed().toPath());
            AtomicLong free = new AtomicLong(ENOUGH);
            RecoveryVault blocked = blockedLowSpace(f, free, staged, release);
            Future<Boolean> writer = workers.submit(
                () -> attemptsRejectedSave(blocked, f));
            try {
                assertTrue("Writer never reached durable precommit boundary",
                    staged.await(20, TimeUnit.SECONDS));
                CountDownLatch readStarted = new CountDownLatch(1);
                Future<Map<String, String>> reader = workers.submit(() -> {
                    readStarted.countDown();
                    return f.vault.loadForSource(f.apk);
                });
                assertTrue(readStarted.await(10, TimeUnit.SECONDS));
                try {
                    reader.get(200, TimeUnit.MILLISECONDS);
                    fail("Reader must NOT observe uncommitted staged ciphertext");
                } catch (TimeoutException expected) {
                    // Full save/read transaction shares the production lock.
                } finally { release.countDown(); }
                assertTrue("Low-space writer must fail closed",
                    writer.get(40, TimeUnit.SECONDS));
                assertEquals("Reader must see previous valid checkpoint only",
                    old, reader.get(40, TimeUnit.SECONDS));
                f.unchanged(accepted, old);
            } finally {
                release.countDown();
                writer.get(40, TimeUnit.SECONDS);
            }
        } finally {
            release.countDown();
            workers.shutdownNow();
            assertTrue(workers.awaitTermination(40, TimeUnit.SECONDS));
        }
    }

    @Test public void f133ConcurrentClearWaitsForFailedSaveThenRemovesOnlyVault()
            throws Exception {
        ExecutorService workers = Executors.newFixedThreadPool(2);
        CountDownLatch staged = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        try (Fixture f = new Fixture()) {
            f.vault.save(f.apk, revision("accepted A"));
            byte[] sourceBytes = Files.readAllBytes(f.apk.toPath());
            AtomicLong free = new AtomicLong(ENOUGH);
            RecoveryVault blocked = blockedLowSpace(f, free, staged, release);
            Future<Boolean> writer = workers.submit(
                () -> attemptsRejectedSave(blocked, f));
            try {
                assertTrue("Writer never reached synced precommit boundary",
                    staged.await(20, TimeUnit.SECONDS));
                CountDownLatch clearStarted = new CountDownLatch(1);
                Future<?> deleter = workers.submit(() -> {
                    clearStarted.countDown();
                    f.vault.clear();
                    return null;
                });
                assertTrue(clearStarted.await(10, TimeUnit.SECONDS));
                try {
                    deleter.get(200, TimeUnit.MILLISECONDS);
                    fail("Explicit deletion must wait for in-flight transaction");
                } catch (TimeoutException expected) {
                    // clear() cannot race an active encrypted stage.
                } finally { release.countDown(); }
                assertTrue(writer.get(40, TimeUnit.SECONDS));
                deleter.get(40, TimeUnit.SECONDS);
                assertFalse("Explicit clear must remove accepted checkpoint",
                    f.vault.hasCheckpoint());
                f.noPartialStages();
                assertArrayEquals("Clear must never remove original APK",
                    sourceBytes, Files.readAllBytes(f.apk.toPath()));
            } finally {
                release.countDown();
                writer.get(40, TimeUnit.SECONDS);
            }
        } finally {
            release.countDown();
            workers.shutdownNow();
            assertTrue(workers.awaitTermination(40, TimeUnit.SECONDS));
        }
    }

    @Test public void f133RejectsUnknownSpaceAndImpossibleStageBudgets()
            throws Exception {
        try {
            RecoveryStorageBudget.requireStagingRoom(() -> -1L, 128);
            fail("Unknown available bytes must fail closed");
        } catch (IOException expected) { lowSpace(expected); }
        try {
            RecoveryStorageBudget.requireStagingRoom(() -> Long.MAX_VALUE,
                RecoveryStorageBudget.MAX_ENCRYPTED_STAGE + 1);
            fail("Unbounded encrypted staging must be rejected");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("Orçamento"));
        }
        RecoveryStorageBudget.requireStagingRoom(
            () -> RecoveryStorageBudget.SAFETY_RESERVE + 1, 1);
    }
}
