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
import static org.junit.Assert.*;

/**
 * F1.35: non-destructive emulator tests for verifier cancellation and readers.
 * The real OS process death is handled by a separate ADB-driven debug harness.
 */
@RunWith(AndroidJUnit4.class)
public final class F135StageVerificationInstrumentedTest {
    static final String PATH = "assets/f135.txt";
    private static String large(String prefix) {
        StringBuilder text = new StringBuilder(prefix);
        while (text.length() < 64000) text.append("Block verification payload 0123456789 ");
        return text.toString();
    }
    private static Map<String, String> revision(String value) {
        return Collections.singletonMap(PATH, value);
    }
    private static final class Fixture implements AutoCloseable {
        final File root, folder, source, checkpoint;
        final String alias;
        final RecoveryVault vault;
        final byte[] accepted, original;
        Fixture() throws Exception {
            Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
            root = Files.createTempDirectory(context.getFilesDir().toPath(),
                "f135_verifier_").toFile();
            folder = new File(root, "vault");
            source = new File(root, "source.apk");
            original = "F135 read-only original".getBytes(StandardCharsets.UTF_8);
            Files.write(source.toPath(), original);
            checkpoint = new File(folder, "edit-plan-checkpoint.v1");
            alias = "negrescodroid.f135.instrumentation." + UUID.randomUUID();
            vault = new RecoveryVault(folder, alias);
            vault.save(source, revision("accepted A"));
            accepted = Files.readAllBytes(checkpoint.toPath());
        }
        void unchanged() throws Exception {
            assertArrayEquals(accepted, Files.readAllBytes(checkpoint.toPath()));
            assertEquals(revision("accepted A"), vault.loadForSource(source));
            assertArrayEquals(original, Files.readAllBytes(source.toPath()));
            File[] temps = folder.listFiles((dir, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(temps);
            assertEquals("Rejected verifier must remove its partial stage", 0, temps.length);
        }
        @Override public void close() throws Exception {
            vault.clear();
            Files.deleteIfExists(source.toPath());
            Files.deleteIfExists(folder.toPath());
            Files.deleteIfExists(root.toPath());
            KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
            ks.load(null);
            if (ks.containsAlias(alias)) ks.deleteEntry(alias);
        }
    }
    private static RecoveryVault interrupted(Fixture fixture,
            RecoveryVault.StageReadObserver observer) {
        return new RecoveryVault(fixture.folder, fixture.alias, stage -> {},
            RecoveryStorageBudget.forDirectory(fixture.folder), observer);
    }

    @Test public void f135InterruptMidVerificationCannotCommitCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            int[] progress = {0};
            RecoveryVault failing = interrupted(f, (verified, total) -> {
                assertTrue("Need several chunks to prove mid-verification", total > 8192);
                assertTrue(verified < total);
                progress[0]++;
                Thread.currentThread().interrupt();
            });
            try {
                failing.save(f.source, revision(large("B")));
                fail("Interrupted verifier cannot promote checkpoint");
            } catch (InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("interrompida"));
            } finally {
                Thread.interrupted(); // clear only this test thread
            }
            assertEquals("Observer must fire on first verified chunk", 1, progress[0]);
            f.unchanged();
        }
    }

    @Test public void f135ConcurrentReaderWaitsForAbortedVerifier()
            throws Exception {
        ExecutorService workers = Executors.newFixedThreadPool(2);
        CountDownLatch reached = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        try (Fixture f = new Fixture()) {
            RecoveryVault paused = interrupted(f, (verified, total) -> {
                assertTrue("Verification pause must leave unread ciphertext",
                    verified < total);
                reached.countDown();
                try {
                    if (!release.await(20, TimeUnit.SECONDS))
                        throw new IOException("F135 timed out inside verifier");
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new InterruptedIOException("F135 verifier interrupted");
                }
                throw new InterruptedIOException("F135 deliberately cancelled");
            });
            Future<Boolean> writer = workers.submit(() -> {
                try {
                    paused.save(f.source, revision(large("B")));
                    return false;
                } catch (InterruptedIOException expected) {
                    return true;
                }
            });
            try {
                assertTrue("Verifier never reached first chunk",
                    reached.await(20, TimeUnit.SECONDS));
                CountDownLatch waiting = new CountDownLatch(1);
                Future<Map<String, String>> reader = workers.submit(() -> {
                    waiting.countDown();
                    return f.vault.loadForSource(f.source);
                });
                assertTrue(waiting.await(10, TimeUnit.SECONDS));
                try {
                    reader.get(200, TimeUnit.MILLISECONDS);
                    fail("Reader must wait until interrupted verifier unwinds");
                } catch (TimeoutException expected) {
                    // Prior accepted data cannot be read mid-transaction.
                } finally { release.countDown(); }
                assertTrue(writer.get(40, TimeUnit.SECONDS));
                assertEquals(revision("accepted A"),
                    reader.get(40, TimeUnit.SECONDS));
                f.unchanged();
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
}
