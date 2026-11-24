package com.readroid.app;

import android.content.Context;
import android.net.Uri;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.KeyStore;
import java.util.Collections;
import java.util.Map;
import java.util.UUID;
import static org.junit.Assert.*;

/** F1.47: stale consent may not overwrite newer live edits or restore old data. */
@RunWith(AndroidJUnit4.class)
public final class F147RecoveryRestoreConsentInstrumentedTest {
    private static final String PATH = "assets/f147.txt";
    private static Map<String, String> plan(String text) {
        return Collections.singletonMap(PATH, text);
    }
    private static Object get(MainActivity a, String name) throws Exception {
        Field f = MainActivity.class.getDeclaredField(name);
        f.setAccessible(true);
        return f.get(a);
    }
    private static void set(MainActivity a, String name, Object value) throws Exception {
        Field f = MainActivity.class.getDeclaredField(name);
        f.setAccessible(true);
        f.set(a, value);
    }
    private static boolean isCurrent(MainActivity a, File source, int generation,
            String hash, ExplorerView.EditSession session, Map<String, String> baseline,
            long revision, ExportSessionGuard.Token token) throws Exception {
        Method m = MainActivity.class.getDeclaredMethod("isRecoveryRestoreRequestCurrent",
            File.class, Uri.class, int.class, String.class, ExplorerView.EditSession.class,
            Map.class, long.class, ExportSessionGuard.Token.class);
        m.setAccessible(true);
        return (Boolean) m.invoke(a, source, null, generation, hash, session,
            baseline, revision, token);
    }

    @Test public void f147LiveEditAfterPromptRejectsConsentEvenFromEmptyPlan()
            throws Exception {
        Context ctx = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File source = File.createTempFile("f147_live_", ".apk", ctx.getCacheDir());
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(a -> {
                try {
                    String hash = ApkIntegrity.sha256(source);
                    set(a, "currentApk", source);
                    set(a, "report", new JSONObject().put("sha256", hash));
                    set(a, "selectedApkUri", null);
                    ExplorerView e = (ExplorerView) get(a, "explorerView");
                    e.setFiles(new JSONArray(), source);
                    int generation = (Integer) get(a, "analysisSequence");
                    ExportSessionGuard guard = (ExportSessionGuard) get(a, "recoveryRestoreSessions");
                    ExportSessionGuard.Token token = guard.begin();
                    ExplorerView.EditSession session = e.captureEditSession();
                    Map<String, String> baseline = e.getEditPlan().snapshot();
                    long revision = e.getEditPlan().revision();
                    assertTrue(baseline.isEmpty());
                    assertTrue(isCurrent(a, source, generation, hash, session, baseline, revision, token));
                    e.getEditPlan().addTextReplacement(PATH, "new unsaved text");
                    assertFalse("Consent must not discard a later edit",
                        isCurrent(a, source, generation, hash, session, baseline, revision, token));
                    assertEquals(plan("new unsaved text"), e.getEditPlan().snapshot());
                    e.getEditPlan().remove(PATH);
                    assertEquals(baseline, e.getEditPlan().snapshot());
                    assertFalse("Empty→edited→empty must not resurrect old consent",
                        isCurrent(a, source, generation, hash, session, baseline, revision, token));
                    assertTrue(isCurrent(a, source, generation, hash, session, baseline,
                        e.getEditPlan().revision(), token));
                } catch (Exception ex) { throw new AssertionError(ex); }
            });
        } finally { source.delete(); }
    }

    @Test public void f147NewRequestAndRebindingInvalidateOldConsent()
            throws Exception {
        Context ctx = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File source = File.createTempFile("f147_rebind_", ".apk", ctx.getCacheDir());
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(a -> {
                try {
                    String hash = ApkIntegrity.sha256(source);
                    set(a, "currentApk", source);
                    set(a, "report", new JSONObject().put("sha256", hash));
                    set(a, "selectedApkUri", null);
                    ExplorerView e = (ExplorerView) get(a, "explorerView");
                    e.setFiles(new JSONArray(), source);
                    e.getEditPlan().addTextReplacement(PATH, "pending");
                    int generation = (Integer) get(a, "analysisSequence");
                    ExportSessionGuard guard = (ExportSessionGuard) get(a, "recoveryRestoreSessions");
                    ExplorerView.EditSession session = e.captureEditSession();
                    Map<String, String> baseline = e.getEditPlan().snapshot();
                    long revision = e.getEditPlan().revision();
                    ExportSessionGuard.Token old = guard.begin();
                    assertTrue(isCurrent(a, source, generation, hash, session, baseline, revision, old));
                    ExportSessionGuard.Token fresh = guard.begin();
                    assertFalse(isCurrent(a, source, generation, hash, session, baseline, revision, old));
                    assertTrue(isCurrent(a, source, generation, hash, session, baseline, revision, fresh));
                    e.setFiles(new JSONArray(), source);
                    assertFalse(isCurrent(a, source, generation, hash, session, baseline, revision, fresh));
                } catch (Exception ex) { throw new AssertionError(ex); }
            });
        } finally { source.delete(); }
    }

    private static final class Fixture implements AutoCloseable {
        final File root, folder, source, checkpoint;
        final String alias;
        final RecoveryVault vault;
        Fixture() throws Exception {
            Context ctx = InstrumentationRegistry.getInstrumentation().getTargetContext();
            root = Files.createTempDirectory(ctx.getFilesDir().toPath(), "f147_").toFile();
            folder = new File(root, "vault");
            source = new File(root, "source.apk");
            Files.write(source.toPath(), "F147 source".getBytes(StandardCharsets.UTF_8));
            alias = "negrescodroid.f147.test." + UUID.randomUUID();
            vault = new RecoveryVault(folder, alias);
            vault.save(source, plan("A"));
            checkpoint = new File(folder, "edit-plan-checkpoint.v1");
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

    @Test public void f147ReplacedCheckpointCannotRestoreOfferedA() throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof proof = f.vault.captureDeletionProof();
            Map<String, String> offered = f.vault.loadForSource(f.source, proof);
            f.vault.save(f.source, plan("B"));
            byte[] before = Files.readAllBytes(f.checkpoint.toPath());
            try {
                RecoveryRestoreConsent.reauthenticate(f.vault, f.source, offered, proof,
                    new ExportSessionGuard().begin());
                fail("Replaced checkpoint must require a new consent");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("mudou"));
            }
            assertArrayEquals(before, Files.readAllBytes(f.checkpoint.toPath()));
            assertEquals(plan("B"), f.vault.loadForSource(f.source));
        }
    }

    @Test public void f147DeletedCheckpointCannotRestoreOfferedA() throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof proof = f.vault.captureDeletionProof();
            Map<String, String> offered = f.vault.loadForSource(f.source, proof);
            f.vault.clear();
            try {
                RecoveryRestoreConsent.reauthenticate(f.vault, f.source, offered, proof,
                    new ExportSessionGuard().begin());
                fail("Deleted checkpoint must not restore an old in-memory plan");
            } catch (IOException expected) {
                assertFalse(f.vault.hasCheckpoint());
            }
        }
    }

    @Test public void f147RevokedTokenRejectsUnchangedCheckpoint() throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof proof = f.vault.captureDeletionProof();
            Map<String, String> offered = f.vault.loadForSource(f.source, proof);
            ExportSessionGuard guard = new ExportSessionGuard();
            ExportSessionGuard.Token token = guard.begin();
            guard.invalidate();
            try {
                RecoveryRestoreConsent.reauthenticate(f.vault, f.source, offered, proof, token);
                fail("Revoked consent must fail closed");
            } catch (InterruptedIOException expected) {
                assertEquals(plan("A"), f.vault.loadForSource(f.source));
            }
        }
    }

    @Test public void f147CurrentConsentReturnsAuthenticatedPlanWithoutWriting()
            throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof proof = f.vault.captureDeletionProof();
            Map<String, String> offered = f.vault.loadForSource(f.source, proof);
            byte[] before = Files.readAllBytes(f.checkpoint.toPath());
            Map<String, String> verified = RecoveryRestoreConsent.reauthenticate(
                f.vault, f.source, offered, proof, new ExportSessionGuard().begin()).changes();
            assertEquals(plan("A"), verified);
            assertNotSame(offered, verified);
            assertArrayEquals(before, Files.readAllBytes(f.checkpoint.toPath()));
            try {
                verified.put(PATH, "unexpected");
                fail("Verified snapshot must be immutable");
            } catch (UnsupportedOperationException expected) {
                assertEquals(plan("A"), verified);
            }
        }
    }

    @Test public void f151ResavedIdenticalPlanRequiresNewRestoreConsent() throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof old = f.vault.captureDeletionProof();
            Map<String, String> offered = f.vault.loadForSource(f.source, old);
            f.vault.save(f.source, offered);
            byte[] newer = Files.readAllBytes(f.checkpoint.toPath());
            try {
                RecoveryRestoreConsent.reauthenticate(f.vault, f.source, offered, old,
                    new ExportSessionGuard().begin());
                fail("Identical plaintext does not authorize a new ciphertext");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("mudou"));
            }
            RecoveryVault.DeletionProof fresh = f.vault.captureDeletionProof();
            assertEquals(offered, RecoveryRestoreConsent.reauthenticate(f.vault, f.source,
                offered, fresh, new ExportSessionGuard().begin()).changes());
            assertArrayEquals(newer, Files.readAllBytes(f.checkpoint.toPath()));
        }
    }

    @Test public void f151OldProofCannotAuthenticateReplacementAtInitialOffer() throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof old = f.vault.captureDeletionProof();
            f.vault.save(f.source, plan("B"));
            try {
                f.vault.loadForSource(f.source, old);
                fail("Initial offer must not combine an old proof with a new plan");
            } catch (IOException expected) {
                assertEquals(plan("B"), f.vault.loadForSource(f.source));
            }
        }
    }

    @Test public void f151ProofFromDifferentVaultRejectsSameSource() throws Exception {
        try (Fixture f = new Fixture(); Fixture other = new Fixture()) {
            RecoveryVault.DeletionProof foreign = other.vault.captureDeletionProof();
            try {
                f.vault.loadForSource(f.source, foreign);
                fail("Proof belongs to a different vault");
            } catch (IOException expected) {
                assertEquals(plan("A"), f.vault.loadForSource(f.source));
                assertEquals(plan("A"), other.vault.loadForSource(other.source));
            }
        }
    }

    @Test public void f152PostAuthenticationSaveInvalidatesApplication() throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof proof = f.vault.captureDeletionProof();
            Map<String, String> offered = f.vault.loadForSource(f.source, proof);
            ExportSessionGuard.Token token = new ExportSessionGuard().begin();
            RecoveryVault.RestoreApplication application =
                RecoveryRestoreConsent.reauthenticate(f.vault, f.source, offered, proof, token);
            f.vault.save(f.source, plan("B"));
            EditPlan live = new EditPlan();
            live.addTextReplacement(PATH, "pending");
            try {
                application.applyIfCurrent(token, () -> live.replaceAllValidated(application.changes()));
                fail("New save must invalidate the authenticated application");
            } catch (IOException expected) {
                assertEquals(plan("pending"), live.snapshot());
                assertEquals(plan("B"), f.vault.loadForSource(f.source));
            }
        }
    }

    @Test public void f152PostAuthenticationClearInvalidatesApplication() throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof proof = f.vault.captureDeletionProof();
            Map<String, String> offered = f.vault.loadForSource(f.source, proof);
            ExportSessionGuard.Token token = new ExportSessionGuard().begin();
            RecoveryVault.RestoreApplication application =
                RecoveryRestoreConsent.reauthenticate(f.vault, f.source, offered, proof, token);
            f.vault.clearIfCurrent(proof);
            try {
                application.applyIfCurrent(token, () -> fail("Deleted checkpoint applied"));
                fail("Expected invalidated application");
            } catch (IOException expected) {
                assertFalse(f.vault.hasCheckpoint());
            }
        }
    }

    @Test public void f152CurrentApplicationIsSingleUse() throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof proof = f.vault.captureDeletionProof();
            Map<String, String> offered = f.vault.loadForSource(f.source, proof);
            ExportSessionGuard.Token token = new ExportSessionGuard().begin();
            RecoveryVault.RestoreApplication application =
                RecoveryRestoreConsent.reauthenticate(f.vault, f.source, offered, proof, token);
            EditPlan live = new EditPlan();
            application.applyIfCurrent(token, () -> live.replaceAllValidated(application.changes()));
            assertEquals(offered, live.snapshot());
            try {
                application.applyIfCurrent(token, () -> fail("Consumed ticket applied again"));
                fail("Expected consumed application rejection");
            } catch (IOException expected) {
                assertEquals(offered, live.snapshot());
            }
        }
    }

    @Test public void f152BusyVaultRejectsApplicationWithoutWaitingForWriter()
            throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof proof = f.vault.captureDeletionProof();
            Map<String, String> offered = f.vault.loadForSource(f.source, proof);
            ExportSessionGuard.Token token = new ExportSessionGuard().begin();
            RecoveryVault.RestoreApplication application =
                RecoveryRestoreConsent.reauthenticate(f.vault, f.source, offered, proof, token);
            java.util.concurrent.CountDownLatch entered = new java.util.concurrent.CountDownLatch(1);
            java.util.concurrent.CountDownLatch release = new java.util.concurrent.CountDownLatch(1);
            RecoveryVault writer = new RecoveryVault(f.folder, f.alias, staged -> {
                entered.countDown();
                try {
                    if (!release.await(15, java.util.concurrent.TimeUnit.SECONDS))
                        throw new IOException("F152 writer barrier timed out");
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new InterruptedIOException("F152 writer interrupted");
                }
            });
            java.util.concurrent.ExecutorService worker =
                java.util.concurrent.Executors.newSingleThreadExecutor();
            java.util.concurrent.Future<?> save = worker.submit(() -> {
                writer.save(f.source, plan("B"));
                return null;
            });
            try {
                assertTrue("Real writer never acquired the vault lock",
                    entered.await(5, java.util.concurrent.TimeUnit.SECONDS));
                // Real main-thread invocation while another thread owns the
                // lock; no disk access or blocking lock acquisition permitted.
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    try {
                        application.applyIfCurrent(token, () -> fail("Busy vault applied plan"));
                        fail("Busy vault must reject immediately");
                    } catch (IOException expected) {
                        assertTrue(expected.getMessage().contains("em uso"));
                        assertEquals(1L, release.getCount());
                        assertFalse(save.isDone());
                    }
                });
            } finally {
                release.countDown();
                try { save.get(20, java.util.concurrent.TimeUnit.SECONDS); }
                finally { worker.shutdownNow(); }
            }
            assertEquals(plan("B"), f.vault.loadForSource(f.source));
        }
    }

    @Test public void f152RevokedApplicationTokenCannotMutatePlan() throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof proof = f.vault.captureDeletionProof();
            Map<String, String> offered = f.vault.loadForSource(f.source, proof);
            ExportSessionGuard guard = new ExportSessionGuard();
            ExportSessionGuard.Token token = guard.begin();
            RecoveryVault.RestoreApplication application =
                RecoveryRestoreConsent.reauthenticate(f.vault, f.source, offered, proof, token);
            guard.invalidate();
            try {
                application.applyIfCurrent(token, () -> fail("Revoked application mutated plan"));
                fail("Expected revoked token rejection");
            } catch (InterruptedIOException expected) {
                assertEquals(offered, f.vault.loadForSource(f.source));
            }
        }
    }

    @Test public void f154InterruptedVaultWaitDoesNotMutateCheckpoint() throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof proof = f.vault.captureDeletionProof();
            byte[] original = Files.readAllBytes(f.checkpoint.toPath());
            java.util.concurrent.CountDownLatch entered = new java.util.concurrent.CountDownLatch(1);
            java.util.concurrent.CountDownLatch release = new java.util.concurrent.CountDownLatch(1);
            RecoveryVault writer = new RecoveryVault(f.folder, f.alias, staged -> {
                entered.countDown();
                try {
                    if (!release.await(20, java.util.concurrent.TimeUnit.SECONDS))
                        throw new IOException("F154 writer barrier timed out");
                } catch (InterruptedException ex) {
                    Thread.currentThread().interrupt();
                    throw new InterruptedIOException("F154 writer interrupted");
                }
                // Deliberately abort the staged write, retaining original.
                throw new IOException("F154 controlled writer abort");
            });
            java.util.concurrent.ExecutorService worker =
                java.util.concurrent.Executors.newSingleThreadExecutor();
            java.util.concurrent.Future<?> writerResult = worker.submit(() -> {
                try {
                    writer.save(f.source, plan("B"));
                    fail("Controlled writer must abort before promotion");
                } catch (IOException expected) {
                    assertEquals("F154 controlled writer abort", expected.getMessage());
                }
                return null;
            });
            try {
                assertTrue(entered.await(5, java.util.concurrent.TimeUnit.SECONDS));
                java.util.List<java.util.concurrent.Callable<?>> operations =
                    java.util.Arrays.asList(
                        () -> f.vault.hasCheckpointInterruptibly(),
                        () -> f.vault.captureDeletionProof(),
                        () -> f.vault.loadForSource(f.source, proof),
                        () -> { f.vault.clearIfCurrent(proof); return null; },
                        () -> { f.vault.save(f.source, plan("C")); return null; });
                for (java.util.concurrent.Callable<?> operation : operations) {
                    java.util.concurrent.CountDownLatch started = new java.util.concurrent.CountDownLatch(1);
                    java.util.concurrent.CountDownLatch finished = new java.util.concurrent.CountDownLatch(1);
                    java.util.concurrent.atomic.AtomicReference<Throwable> failure =
                        new java.util.concurrent.atomic.AtomicReference<>();
                    Thread waiter = new Thread(() -> {
                        started.countDown();
                        try {
                            operation.call();
                            failure.set(new AssertionError("Interrupted operation succeeded"));
                        } catch (InterruptedIOException expected) {
                            if (!Thread.currentThread().isInterrupted())
                                failure.set(new AssertionError("Interrupt status was lost"));
                        } catch (Throwable ex) {
                            failure.set(ex);
                        } finally {
                            finished.countDown();
                        }
                    }, "f154-vault-waiter");
                    waiter.start();
                    try {
                        assertTrue(started.await(5, java.util.concurrent.TimeUnit.SECONDS));
                        waiter.interrupt();
                        assertTrue("Interrupted waiter did not return while writer held the lock",
                            finished.await(3, java.util.concurrent.TimeUnit.SECONDS));
                        assertNull(failure.get());
                        assertFalse(writerResult.isDone());
                        assertArrayEquals(original, Files.readAllBytes(f.checkpoint.toPath()));
                    } finally {
                        waiter.interrupt();
                    }
                }
            } finally {
                release.countDown();
                try { writerResult.get(25, java.util.concurrent.TimeUnit.SECONDS); }
                finally { worker.shutdownNow(); }
            }
            assertArrayEquals(original, Files.readAllBytes(f.checkpoint.toPath()));
            assertEquals(plan("A"), f.vault.loadForSource(f.source));
        }
    }

    @Test public void f155StaleSaveProofCannotOverwriteSamePlanResave() throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof stale = f.vault.captureDeletionProof();
            f.vault.save(f.source, plan("A"));
            byte[] newer = Files.readAllBytes(f.checkpoint.toPath());
            String hash = ApkIntegrity.sha256(f.source);
            try {
                f.vault.save(f.source, plan("B"), new ExportSessionGuard().begin(), hash, stale);
                fail("Stale save consent must not overwrite the new ciphertext");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("mudou"));
                assertArrayEquals(newer, Files.readAllBytes(f.checkpoint.toPath()));
            }
            f.vault.save(f.source, plan("B"), new ExportSessionGuard().begin(),
                hash, f.vault.captureDeletionProof());
            assertEquals(plan("B"), f.vault.loadForSource(f.source));
        }
    }

    @Test public void f155SlotChangeDuringStagingRejectsPromotion() throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault.DeletionProof offered = f.vault.captureDeletionProof();
            byte[] original = Files.readAllBytes(f.checkpoint.toPath());
            byte[] changed = original.clone();
            changed[changed.length - 1] ^= 1;
            RecoveryVault writer = new RecoveryVault(f.folder, f.alias,
                staged -> Files.write(f.checkpoint.toPath(), changed));
            try {
                writer.save(f.source, plan("B"), new ExportSessionGuard().begin(),
                    ApkIntegrity.sha256(f.source), offered);
                fail("Changed slot during staging must not be overwritten");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("mudou"));
                assertArrayEquals(changed, Files.readAllBytes(f.checkpoint.toPath()));
            }
        }
    }

    @Test public void f156AbsentSaveProofCannotSurviveSaveClearCycle() throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.clear();
            RecoveryVault.DeletionProof absent = f.vault.captureDeletionProof();
            f.vault.save(f.source, plan("B"));
            f.vault.clear();
            assertFalse(f.vault.hasCheckpoint());
            try {
                f.vault.save(f.source, plan("C"), new ExportSessionGuard().begin(),
                    ApkIntegrity.sha256(f.source), absent);
                fail("Absent slot proof must not survive save and clear");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("mudou"));
                assertFalse(f.vault.hasCheckpoint());
            }
            f.vault.save(f.source, plan("C"), new ExportSessionGuard().begin(),
                ApkIntegrity.sha256(f.source), f.vault.captureDeletionProof());
            assertEquals(plan("C"), f.vault.loadForSource(f.source));
        }
    }

    @Test public void f156AbsentDeleteProofCannotSurviveSaveClearCycle() throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.clear();
            RecoveryVault.DeletionProof absent = f.vault.captureDeletionProof();
            f.vault.save(f.source, plan("B"));
            f.vault.clear();
            try {
                f.vault.clearIfCurrent(absent);
                fail("Old absent deletion consent must remain stale");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("mudou"));
                assertFalse(f.vault.hasCheckpoint());
            }
            f.vault.clearIfCurrent(f.vault.captureDeletionProof());
            assertFalse(f.vault.hasCheckpoint());
        }
    }
}
