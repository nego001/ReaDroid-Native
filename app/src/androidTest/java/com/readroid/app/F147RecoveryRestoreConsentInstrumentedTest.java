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
            ExportSessionGuard.Token token) throws Exception {
        Method m = MainActivity.class.getDeclaredMethod("isRecoveryRestoreRequestCurrent",
            File.class, Uri.class, int.class, String.class, ExplorerView.EditSession.class,
            Map.class, ExportSessionGuard.Token.class);
        m.setAccessible(true);
        return (Boolean) m.invoke(a, source, null, generation, hash, session,
            baseline, token);
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
                    assertTrue(baseline.isEmpty());
                    assertTrue(isCurrent(a, source, generation, hash, session, baseline, token));
                    e.getEditPlan().addTextReplacement(PATH, "new unsaved text");
                    assertFalse("Consent must not discard a later edit",
                        isCurrent(a, source, generation, hash, session, baseline, token));
                    assertEquals(plan("new unsaved text"), e.getEditPlan().snapshot());
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
                    ExportSessionGuard.Token old = guard.begin();
                    assertTrue(isCurrent(a, source, generation, hash, session, baseline, old));
                    ExportSessionGuard.Token fresh = guard.begin();
                    assertFalse(isCurrent(a, source, generation, hash, session, baseline, old));
                    assertTrue(isCurrent(a, source, generation, hash, session, baseline, fresh));
                    e.setFiles(new JSONArray(), source);
                    assertFalse(isCurrent(a, source, generation, hash, session, baseline, fresh));
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
            Map<String, String> offered = f.vault.loadForSource(f.source);
            f.vault.save(f.source, plan("B"));
            byte[] before = Files.readAllBytes(f.checkpoint.toPath());
            try {
                RecoveryRestoreConsent.reauthenticate(f.vault, f.source, offered,
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
            Map<String, String> offered = f.vault.loadForSource(f.source);
            f.vault.clear();
            try {
                RecoveryRestoreConsent.reauthenticate(f.vault, f.source, offered,
                    new ExportSessionGuard().begin());
                fail("Deleted checkpoint must not restore an old in-memory plan");
            } catch (IOException expected) {
                assertFalse(f.vault.hasCheckpoint());
            }
        }
    }

    @Test public void f147RevokedTokenRejectsUnchangedCheckpoint() throws Exception {
        try (Fixture f = new Fixture()) {
            Map<String, String> offered = f.vault.loadForSource(f.source);
            ExportSessionGuard guard = new ExportSessionGuard();
            ExportSessionGuard.Token token = guard.begin();
            guard.invalidate();
            try {
                RecoveryRestoreConsent.reauthenticate(f.vault, f.source, offered, token);
                fail("Revoked consent must fail closed");
            } catch (InterruptedIOException expected) {
                assertEquals(plan("A"), f.vault.loadForSource(f.source));
            }
        }
    }

    @Test public void f147CurrentConsentReturnsAuthenticatedPlanWithoutWriting()
            throws Exception {
        try (Fixture f = new Fixture()) {
            Map<String, String> offered = f.vault.loadForSource(f.source);
            byte[] before = Files.readAllBytes(f.checkpoint.toPath());
            Map<String, String> verified = RecoveryRestoreConsent.reauthenticate(
                f.vault, f.source, offered, new ExportSessionGuard().begin());
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
}
