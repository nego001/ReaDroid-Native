package com.readroid.app;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.By;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.UiObject2;
import androidx.test.uiautomator.Until;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.KeyStore;
import java.util.Collections;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/**
 * F1.49 — real Activity buttons and native confirmation dialogs.
 * Opt-in disposable emulator only; never overwrite a preexisting checkpoint
 * or key. No production hooks, fake consent, or mocked recovery vault.
 */
@RunWith(AndroidJUnit4.class)
public final class F149RecoveryDialogInstrumentedTest {
    private static final String PATH = "assets/f149-dialog.txt";
    private static final String KEY = "negrescodroid.v3.recovery.v1";
    private static final String SAVE = "Salvar cópia de recuperação criptografada";
    private static final String RESTORE = "Recuperar plano salvo neste aparelho";
    private static final String OFFER = "Recuperar 1 alterações?";
    private static final String POSITIVE = "Substituir plano";
    private static final String PENDING = "pending F149 B";
    private static final String STORED = "stored F149 A";

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

    private static final class Fixture implements AutoCloseable {
        final Context context;
        final RecoveryVault vault;
        final File source, folder, checkpoint;
        final String sha;
        final UiDevice device;

        Fixture() throws Exception {
            assertEquals("Explicit opt-in required for disposable recovery UI tests",
                "true", InstrumentationRegistry.getArguments().getString("f149DisposableVault"));
            device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
            assertEquals("F149 refuses to run on a physical device",
                "1", device.executeShellCommand("getprop ro.kernel.qemu").trim());
            context = InstrumentationRegistry.getInstrumentation().getTargetContext();
            folder = new File(context.getFilesDir(), "v3-private-recovery");
            assertFalse("Refuse an existing recovery directory", folder.exists());
            KeyStore keys = KeyStore.getInstance("AndroidKeyStore");
            keys.load(null);
            assertFalse("Refuse an existing recovery key", keys.containsAlias(KEY));
            vault = new RecoveryVault(context);
            checkpoint = new File(folder, "edit-plan-checkpoint.v1");
            source = File.createTempFile("f149_dialog_", ".apk", context.getCacheDir());
            try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(source.toPath()))) {
                zip.putNextEntry(new ZipEntry("AndroidManifest.xml"));
                zip.write("F149 disposable fixture".getBytes(StandardCharsets.UTF_8));
                zip.closeEntry();
                zip.putNextEntry(new ZipEntry(PATH));
                zip.write("original".getBytes(StandardCharsets.UTF_8));
                zip.closeEntry();
            }
            sha = ApkIntegrity.sha256(source);
        }

        void seed() throws Exception {
            vault.save(source, plan(STORED));
            assertEquals(plan(STORED), vault.loadForSource(source));
        }

        void bind(ActivityScenario<MainActivity> scenario) {
            scenario.onActivity(a -> {
                try {
                    set(a, "currentApk", source);
                    set(a, "selectedApkUri", null);
                    set(a, "report", new JSONObject().put("sha256", sha));
                    ExplorerView explorer = (ExplorerView) get(a, "explorerView");
                    explorer.setFiles(new JSONArray(), source);
                    explorer.getEditPlan().addTextReplacement(PATH, PENDING);
                    Method section = MainActivity.class.getDeclaredMethod("showSection", int.class);
                    section.setAccessible(true);
                    section.invoke(a, 3);
                } catch (Exception ex) { throw new AssertionError(ex); }
            });
        }

        void waitForText(String label) {
            assertNotNull("Native dialog text missing: " + label,
                device.wait(Until.findObject(By.textContains(label)), 10000));
        }

        void clickDialogButton(String label) {
            UiObject2 button = device.wait(Until.findObject(By.text(label)), 10000);
            if (button == null) {
                // Native Material dialogs may display the label in uppercase.
                button = device.findObject(By.text(label.toUpperCase(java.util.Locale.ROOT)));
            }
            assertNotNull("Native dialog button missing: " + label, button);
            button.click();
        }

        @Override public void close() throws Exception {
            // Only our opt-in test fixture may reach cleanup. The constructor
            // refused any preexisting directory and key before creating data.
            vault.clear();
            Files.deleteIfExists(folder.toPath());
            Files.deleteIfExists(source.toPath());
            KeyStore keys = KeyStore.getInstance("AndroidKeyStore");
            keys.load(null);
            if (keys.containsAlias(KEY)) keys.deleteEntry(KEY);
        }
    }

    private static Button findButton(View view, String label) {
        if (view instanceof Button && label.contentEquals(((Button) view).getText()))
            return (Button) view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                Button result = findButton(group.getChildAt(i), label);
                if (result != null) return result;
            }
        }
        return null;
    }

    private static void open(ActivityScenario<MainActivity> scenario, String label) {
        scenario.onActivity(a -> {
            Button button = findButton(a.getWindow().getDecorView(), label);
            assertNotNull("Actual Build action missing: " + label, button);
            assertTrue(button.isEnabled());
            assertTrue(button.performClick());
        });
    }

    private static void edit(ActivityScenario<MainActivity> scenario, String value) {
        scenario.onActivity(a -> {
            try {
                ((ExplorerView) get(a, "explorerView")).getEditPlan()
                    .addTextReplacement(PATH, value);
            } catch (Exception ex) { throw new AssertionError(ex); }
        });
    }

    private static void assertPending(ActivityScenario<MainActivity> scenario, String expected) {
        scenario.onActivity(a -> {
            try {
                assertEquals(plan(expected),
                    ((ExplorerView) get(a, "explorerView")).getEditPlan().snapshot());
            } catch (Exception ex) { throw new AssertionError(ex); }
        });
    }

    @Test public void f149ActualSaveDialogRejectsUndoBeforeConsent() throws Exception {
        try (Fixture f = new Fixture()) {
            f.seed();
            byte[] before = Files.readAllBytes(f.checkpoint.toPath());
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, SAVE);
                f.waitForText("Salvar plano neste aparelho?");
                edit(scenario, "temporary F149 C");
                edit(scenario, PENDING); // same map, different revision
                f.clickDialogButton("Criptografar e salvar");
                f.waitForText("Salvamento cancelado");
                assertPending(scenario, PENDING);
                assertArrayEquals(before, Files.readAllBytes(f.checkpoint.toPath()));
                assertEquals(plan(STORED), f.vault.loadForSource(f.source));
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f149ActualSaveDialogCommitsAuthorizedPlan() throws Exception {
        try (Fixture f = new Fixture()) {
            f.seed();
            byte[] before = Files.readAllBytes(f.checkpoint.toPath());
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, SAVE);
                f.waitForText("Salvar plano neste aparelho?");
                f.clickDialogButton("Criptografar e salvar");
                f.waitForText("Cópia protegida");
                assertPending(scenario, PENDING);
                assertFalse("Successful save must promote the new ciphertext",
                    java.util.Arrays.equals(before, Files.readAllBytes(f.checkpoint.toPath())));
                assertEquals(plan(PENDING), f.vault.loadForSource(f.source));
                assertEquals(f.sha, ApkIntegrity.sha256(f.source));
                File[] stages = f.folder.listFiles((dir, name) ->
                    name.startsWith("checkpoint-") && name.endsWith(".tmp"));
                assertNotNull(stages);
                assertEquals(0, stages.length);
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f149ActualRestoreDialogRejectsEditAfterConsent() throws Exception {
        try (Fixture f = new Fixture()) {
            f.seed();
            byte[] before = Files.readAllBytes(f.checkpoint.toPath());
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, RESTORE);
                f.waitForText(OFFER);
                CountDownLatch entered = new CountDownLatch(1);
                CountDownLatch release = new CountDownLatch(1);
                // Deterministically hold the actual single worker between
                // displaying the offer and its post-consent validation.
                scenario.onActivity(a -> {
                    try {
                        ((ExecutorService) get(a, "executor")).execute(() -> {
                            entered.countDown();
                            try {
                                if (!release.await(30, TimeUnit.SECONDS))
                                    throw new AssertionError("F149 worker barrier timed out");
                            } catch (InterruptedException ex) {
                                Thread.currentThread().interrupt();
                            }
                        });
                    } catch (Exception ex) { throw new AssertionError(ex); }
                });
                try {
                    assertTrue("Worker barrier was never entered", entered.await(5, TimeUnit.SECONDS));
                    f.clickDialogButton(POSITIVE);
                    // The native dialog has been accepted, but its real
                    // executor task cannot run until this edit is installed.
                    assertTrue("Restore offer did not dismiss",
                        f.device.wait(Until.gone(By.text(OFFER)), 5000));
                    edit(scenario, "newer unsaved F149 C");
                } finally {
                    release.countDown();
                }
                f.waitForText("Recuperação cancelada");
                assertPending(scenario, "newer unsaved F149 C");
                assertArrayEquals(before, Files.readAllBytes(f.checkpoint.toPath()));
                assertEquals(plan(STORED), f.vault.loadForSource(f.source));
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f149ActualRestoreDialogAppliesAuthenticatedPlan() throws Exception {
        try (Fixture f = new Fixture()) {
            f.seed();
            byte[] before = Files.readAllBytes(f.checkpoint.toPath());
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, RESTORE);
                f.waitForText(OFFER);
                f.clickDialogButton(POSITIVE);
                f.waitForText("Plano recuperado.");
                assertPending(scenario, STORED);
                assertArrayEquals(before, Files.readAllBytes(f.checkpoint.toPath()));
                assertEquals(f.sha, ApkIntegrity.sha256(f.source));
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f149ActualRestoreDialogRejectsDeletedCheckpoint() throws Exception {
        try (Fixture f = new Fixture()) {
            f.seed();
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, RESTORE);
                f.waitForText(OFFER);
                // Simulate a checkpoint that disappeared outside this
                // Activity, so the post-consent authentication must fail.
                f.vault.clear();
                assertFalse(f.vault.hasCheckpoint());
                f.clickDialogButton(POSITIVE);
                f.waitForText("Recuperação bloqueada");
                assertPending(scenario, PENDING);
                assertFalse(f.vault.hasCheckpoint());
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f150ActualDeleteDialogRejectsNewCheckpoint() throws Exception {
        try (Fixture f = new Fixture()) {
            f.seed();
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, "Excluir cópia de recuperação local");
                f.waitForText("Excluir a cópia protegida?");
                f.vault.save(f.source, plan("F150 replacement"));
                byte[] newer = Files.readAllBytes(f.checkpoint.toPath());
                f.clickDialogButton("Excluir cópia");
                f.waitForText("Não foi possível excluir");
                assertPending(scenario, PENDING);
                assertArrayEquals(newer, Files.readAllBytes(f.checkpoint.toPath()));
                assertEquals(plan("F150 replacement"), f.vault.loadForSource(f.source));
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f150ActualDeleteDialogRemovesAuthorizedCopyOnly() throws Exception {
        try (Fixture f = new Fixture()) {
            f.seed();
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, "Excluir cópia de recuperação local");
                f.waitForText("Excluir a cópia protegida?");
                f.clickDialogButton("Excluir cópia");
                f.waitForText("Cópia de recuperação removida.");
                assertFalse(f.vault.hasCheckpoint());
                assertPending(scenario, PENDING);
                assertEquals(f.sha, ApkIntegrity.sha256(f.source));
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f151ActualRestoreDialogRejectsResavedIdenticalPlan() throws Exception {
        try (Fixture f = new Fixture()) {
            f.seed();
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, RESTORE);
                f.waitForText(OFFER);
                f.vault.save(f.source, plan(STORED));
                byte[] newer = Files.readAllBytes(f.checkpoint.toPath());
                f.clickDialogButton(POSITIVE);
                f.waitForText("Recuperação bloqueada");
                assertPending(scenario, PENDING);
                assertArrayEquals(newer, Files.readAllBytes(f.checkpoint.toPath()));
                assertEquals(plan(STORED), f.vault.loadForSource(f.source));
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f153RestoreActionDoesNotWaitOnUiForBusyVault() throws Exception {
        try (Fixture f = new Fixture()) {
            f.seed();
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                CountDownLatch entered = new CountDownLatch(1);
                CountDownLatch release = new CountDownLatch(1);
                RecoveryVault writer = new RecoveryVault(f.folder, KEY, staged -> {
                    entered.countDown();
                    try {
                        if (!release.await(20, TimeUnit.SECONDS))
                            throw new java.io.IOException("F153 writer barrier timed out");
                    } catch (InterruptedException interrupted) {
                        Thread.currentThread().interrupt();
                        throw new java.io.InterruptedIOException("F153 writer interrupted");
                    }
                });
                ExecutorService worker = java.util.concurrent.Executors.newSingleThreadExecutor();
                java.util.concurrent.Future<?> save = worker.submit(() -> {
                    writer.save(f.source, plan("F153 concurrent checkpoint"));
                    return null;
                });
                try {
                    assertTrue("Writer did not acquire vault lock", entered.await(5, TimeUnit.SECONDS));
                    open(scenario, RESTORE);
                    // open() runs the real button listener on the UI thread.
                    // A synchronous vault query would wait until the writer
                    // timed out, failing the future below instead of returning.
                    assertFalse("UI action waited for the writer", save.isDone());
                    assertPending(scenario, PENDING);
                } finally {
                    release.countDown();
                    try { save.get(25, TimeUnit.SECONDS); }
                    finally { worker.shutdownNow(); }
                }
                f.waitForText(OFFER);
                f.clickDialogButton(POSITIVE);
                f.waitForText("Plano recuperado.");
                assertPending(scenario, "F153 concurrent checkpoint");
                assertEquals(f.sha, ApkIntegrity.sha256(f.source));
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f153AbsentCheckpointShowsNoticeWithoutChangingPendingPlan() throws Exception {
        try (Fixture f = new Fixture()) {
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, RESTORE);
                f.waitForText("Nenhuma cópia de recuperação foi encontrada.");
                assertPending(scenario, PENDING);
                assertFalse(f.vault.hasCheckpoint());
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f153StaleMissingCheckpointNoticeIsSuppressed() throws Exception {
        try (Fixture f = new Fixture()) {
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                CountDownLatch entered = new CountDownLatch(1);
                CountDownLatch release = new CountDownLatch(1);
                CountDownLatch drained = new CountDownLatch(1);
                scenario.onActivity(a -> {
                    try {
                        ((ExecutorService) get(a, "executor")).execute(() -> {
                            entered.countDown();
                            try {
                                if (!release.await(20, TimeUnit.SECONDS))
                                    throw new AssertionError("F153 queue barrier timed out");
                            } catch (InterruptedException ex) {
                                Thread.currentThread().interrupt();
                            }
                        });
                    } catch (Exception ex) { throw new AssertionError(ex); }
                });
                try {
                    assertTrue(entered.await(5, TimeUnit.SECONDS));
                    open(scenario, RESTORE);
                    edit(scenario, "newer pending F153");
                    scenario.onActivity(a -> {
                        try {
                            ((ExecutorService) get(a, "executor")).execute(drained::countDown);
                        } catch (Exception ex) { throw new AssertionError(ex); }
                    });
                } finally {
                    release.countDown();
                }
                assertTrue("Recovery request did not drain", drained.await(10, TimeUnit.SECONDS));
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                assertNull("Stale absence notice must not appear",
                    f.device.findObject(By.textContains("Nenhuma cópia de recuperação foi encontrada.")));
                assertPending(scenario, "newer pending F153");
                assertFalse(f.vault.hasCheckpoint());
            }
        }
    }

    @Test public void f155ActualSaveDialogRejectsNewCheckpoint() throws Exception {
        try (Fixture f = new Fixture()) {
            f.seed();
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, SAVE);
                f.waitForText("Salvar plano neste aparelho?");
                f.vault.save(f.source, plan("F155 newer checkpoint"));
                byte[] newer = Files.readAllBytes(f.checkpoint.toPath());
                f.clickDialogButton("Criptografar e salvar");
                f.waitForText("Falha ao salvar cópia");
                assertPending(scenario, PENDING);
                assertArrayEquals(newer, Files.readAllBytes(f.checkpoint.toPath()));
                assertEquals(plan("F155 newer checkpoint"), f.vault.loadForSource(f.source));
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f155ActualSaveDialogRejectsCheckpointCreatedAfterEmptyOffer() throws Exception {
        try (Fixture f = new Fixture()) {
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, SAVE);
                f.waitForText("Salvar plano neste aparelho?");
                f.seed();
                byte[] newer = Files.readAllBytes(f.checkpoint.toPath());
                f.clickDialogButton("Criptografar e salvar");
                f.waitForText("Falha ao salvar cópia");
                assertPending(scenario, PENDING);
                assertArrayEquals(newer, Files.readAllBytes(f.checkpoint.toPath()));
                assertEquals(plan(STORED), f.vault.loadForSource(f.source));
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f156ActualSaveDialogRejectsAbsentSaveClearCycle() throws Exception {
        try (Fixture f = new Fixture()) {
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, SAVE);
                f.waitForText("Salvar plano neste aparelho?");
                f.seed();
                f.vault.clear();
                f.clickDialogButton("Criptografar e salvar");
                f.waitForText("Falha ao salvar cópia");
                assertPending(scenario, PENDING);
                assertFalse(f.vault.hasCheckpoint());
                assertEquals(f.sha, ApkIntegrity.sha256(f.source));
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f156ActualDeleteDialogRejectsAbsentSaveClearCycle() throws Exception {
        try (Fixture f = new Fixture()) {
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, "Excluir cópia de recuperação local");
                f.waitForText("Excluir a cópia protegida?");
                f.seed();
                f.vault.clear();
                f.clickDialogButton("Excluir cópia");
                f.waitForText("Não foi possível excluir");
                assertPending(scenario, PENDING);
                assertFalse(f.vault.hasCheckpoint());
                assertEquals(f.sha, ApkIntegrity.sha256(f.source));
                f.clickDialogButton("OK");
                // A new consent to the currently empty slot remains legal.
                open(scenario, "Excluir cópia de recuperação local");
                f.waitForText("Excluir a cópia protegida?");
                f.clickDialogButton("Excluir cópia");
                f.waitForText("Cópia de recuperação removida.");
                assertPending(scenario, PENDING);
                assertFalse(f.vault.hasCheckpoint());
                f.clickDialogButton("OK");
            }
        }
    }

    @Test public void f157ActualShareDialogRejectsEditUndoBeforeConsent() throws Exception {
        try (Fixture f = new Fixture()) {
            android.app.Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
            android.app.Instrumentation.ActivityMonitor chooser = instrumentation.addMonitor(
                new android.content.IntentFilter(android.content.Intent.ACTION_CHOOSER),
                new android.app.Instrumentation.ActivityResult(android.app.Activity.RESULT_CANCELED, null),
                true);
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, "Compartilhar plano de alterações");
                f.waitForText("Compartilhar alterações sem criptografia?");
                edit(scenario, "F157 intermediate edit");
                edit(scenario, PENDING);
                f.clickDialogButton("Compartilhar");
                f.waitForText("Compartilhamento cancelado");
                assertEquals(0, chooser.getHits());
                assertPending(scenario, PENDING);
                assertEquals(f.sha, ApkIntegrity.sha256(f.source));
                f.clickDialogButton("OK");
            } finally { instrumentation.removeMonitor(chooser); }
        }
    }

    @Test public void f157ActualShareDialogRejectsReboundProject() throws Exception {
        try (Fixture f = new Fixture()) {
            android.app.Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
            android.app.Instrumentation.ActivityMonitor chooser = instrumentation.addMonitor(
                new android.content.IntentFilter(android.content.Intent.ACTION_CHOOSER),
                new android.app.Instrumentation.ActivityResult(android.app.Activity.RESULT_CANCELED, null),
                true);
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, "Compartilhar plano de alterações");
                f.waitForText("Compartilhar alterações sem criptografia?");
                scenario.onActivity(a -> {
                    try {
                        ExplorerView explorer = (ExplorerView) get(a, "explorerView");
                        explorer.setFiles(new JSONArray(), f.source);
                        explorer.getEditPlan().addTextReplacement(PATH, "F157 rebound edit");
                    } catch (Exception ex) { throw new AssertionError(ex); }
                });
                f.clickDialogButton("Compartilhar");
                f.waitForText("Compartilhamento cancelado");
                assertEquals(0, chooser.getHits());
                assertPending(scenario, "F157 rebound edit");
                f.clickDialogButton("OK");
            } finally { instrumentation.removeMonitor(chooser); }
        }
    }

    @Test public void f157ActualShareDialogLaunchesOnlyAuthorizedChooser() throws Exception {
        try (Fixture f = new Fixture()) {
            android.app.Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
            java.util.concurrent.atomic.AtomicReference<android.content.Intent> captured =
                new java.util.concurrent.atomic.AtomicReference<>();
            // Intercept the actual startActivity request, never deliver plaintext
            // to another app during an instrumented regression.
            android.app.Instrumentation.ActivityMonitor chooser =
                new android.app.Instrumentation.ActivityMonitor() {
                    @Override public android.app.Instrumentation.ActivityResult onStartActivity(
                            android.content.Intent intent) {
                        if (!android.content.Intent.ACTION_CHOOSER.equals(intent.getAction())) return null;
                        captured.set(intent);
                        return new android.app.Instrumentation.ActivityResult(
                            android.app.Activity.RESULT_CANCELED, null);
                    }
                };
            instrumentation.addMonitor(chooser);
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                f.bind(scenario);
                open(scenario, "Compartilhar plano de alterações");
                f.waitForText("Compartilhar alterações sem criptografia?");
                f.clickDialogButton("Compartilhar");
                instrumentation.waitForIdleSync();
                android.content.Intent request = captured.get();
                assertNotNull("Authorized chooser not launched", request);
                android.content.Intent payload = request.getParcelableExtra(android.content.Intent.EXTRA_INTENT);
                assertNotNull(payload);
                assertEquals(android.content.Intent.ACTION_SEND, payload.getAction());
                assertEquals("text/plain", payload.getType());
                JSONObject json = new JSONObject(payload.getStringExtra(android.content.Intent.EXTRA_TEXT));
                assertEquals("readroid-edit-plan-v1", json.getString("format"));
                assertFalse(json.getBoolean("applied"));
                JSONArray edits = json.getJSONArray("changes");
                assertEquals(1, edits.length());
                assertEquals(PATH, edits.getJSONObject(0).getString("path"));
                assertEquals(PENDING, edits.getJSONObject(0).getString("replacementText"));
                assertPending(scenario, PENDING);
                assertFalse(f.vault.hasCheckpoint());
                assertEquals(f.sha, ApkIntegrity.sha256(f.source));
            } finally { instrumentation.removeMonitor(chooser); }
        }
    }
}
