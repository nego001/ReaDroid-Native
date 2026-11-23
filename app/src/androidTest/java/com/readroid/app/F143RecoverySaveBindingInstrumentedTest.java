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

/** F1.43: real Activity session gates + isolated vault cancellation. */
@RunWith(AndroidJUnit4.class)
public final class F143RecoverySaveBindingInstrumentedTest {
    private static final String ENTRY = "assets/f143-edit.txt";
    private static final String CHANGE = "F143 changed text";

    private static void set(MainActivity activity, String field, Object value)
            throws Exception {
        Field f = MainActivity.class.getDeclaredField(field);
        f.setAccessible(true);
        f.set(activity, value);
    }
    private static Object get(MainActivity activity, String field)
            throws Exception {
        Field f = MainActivity.class.getDeclaredField(field);
        f.setAccessible(true);
        return f.get(activity);
    }
    private static boolean current(MainActivity activity, File source, Uri document,
            int generation, String hash, ExplorerView.EditSession session,
            Map<String, String> changes) throws Exception {
        Method m = MainActivity.class.getDeclaredMethod("isRecoverySaveRequestCurrent",
            File.class, Uri.class, int.class, String.class,
            ExplorerView.EditSession.class, Map.class);
        m.setAccessible(true);
        return (Boolean) m.invoke(activity, source, document,
            generation, hash, session, changes);
    }
    private static JSONObject report(String hash) throws Exception {
        return new JSONObject().put("sha256", hash);
    }
    @Test public void f143StalePromptRejectsNewProject() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File a = File.createTempFile("f143_prompt_a_", ".apk", context.getCacheDir());
        File b = File.createTempFile("f143_prompt_b_", ".apk", context.getCacheDir());
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    ExplorerView explorer = (ExplorerView) get(activity, "explorerView");
                    set(activity, "currentApk", a);
                    set(activity, "report", report(repeat('a')));
                    explorer.setFiles(new JSONArray(), a);
                    explorer.getEditPlan().addTextReplacement(ENTRY, CHANGE);
                    int generation = (Integer) get(activity, "analysisSequence");
                    ExplorerView.EditSession old = explorer.captureEditSession();
                    Map<String, String> changes = explorer.getEditPlan().snapshot();
                    assertTrue(current(activity, a, null, generation, repeat('a'),
                        old, changes));
                    set(activity, "currentApk", b);
                    set(activity, "report", report(repeat('b')));
                    explorer.getEditPlan().clear();
                    explorer.setFiles(new JSONArray(), b);
                    assertFalse("Old dialog must not save current project B",
                        current(activity, a, null, generation, repeat('a'), old, changes));
                    assertEquals(0, explorer.getEditPlan().size());
                } catch (Exception e) { throw new AssertionError(e); }
            });
        } finally { a.delete(); b.delete(); }
    }
    @Test public void f143SameSourceRebindingRejectsPrompt() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File source = File.createTempFile("f143_rebound_", ".apk", context.getCacheDir());
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    ExplorerView explorer = (ExplorerView) get(activity, "explorerView");
                    set(activity, "currentApk", source);
                    set(activity, "report", report(repeat('a')));
                    explorer.setFiles(new JSONArray(), source);
                    explorer.getEditPlan().addTextReplacement(ENTRY, CHANGE);
                    int generation = (Integer) get(activity, "analysisSequence");
                    ExplorerView.EditSession old = explorer.captureEditSession();
                    Map<String, String> changes = explorer.getEditPlan().snapshot();
                    assertTrue(current(activity, source, null, generation,
                        repeat('a'), old, changes));
                    explorer.setFiles(new JSONArray(), source);
                    assertFalse(current(activity, source, null, generation,
                        repeat('a'), old, changes));
                } catch (Exception e) { throw new AssertionError(e); }
            });
        } finally { source.delete(); }
    }
    @Test public void f143EditedPlanRejectsPrompt() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File source = File.createTempFile("f143_edited_", ".apk", context.getCacheDir());
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    ExplorerView explorer = (ExplorerView) get(activity, "explorerView");
                    set(activity, "currentApk", source);
                    set(activity, "report", report(repeat('a')));
                    explorer.setFiles(new JSONArray(), source);
                    explorer.getEditPlan().addTextReplacement(ENTRY, CHANGE);
                    int generation = (Integer) get(activity, "analysisSequence");
                    ExplorerView.EditSession session = explorer.captureEditSession();
                    Map<String, String> snapshot = explorer.getEditPlan().snapshot();
                    assertTrue(current(activity, source, null, generation,
                        repeat('a'), session, snapshot));
                    explorer.getEditPlan().addTextReplacement(ENTRY, "new edit after prompt");
                    assertFalse("Edits changed before consent must invalidate old plan",
                        current(activity, source, null, generation,
                            repeat('a'), session, snapshot));
                } catch (Exception e) { throw new AssertionError(e); }
            });
        } finally { source.delete(); }
    }
    private static String repeat(char c) {
        char[] bytes = new char[64];
        java.util.Arrays.fill(bytes, c);
        return new String(bytes);
    }
    private static final class Fixture implements AutoCloseable {
        final File root, folder, source, checkpoint;
        final String alias;
        final RecoveryVault vault;
        Fixture() throws Exception {
            Context ctx = InstrumentationRegistry.getInstrumentation()
                .getTargetContext();
            root = Files.createTempDirectory(ctx.getFilesDir().toPath(),
                "f143_binding_").toFile();
            folder = new File(root, "vault");
            source = new File(root, "source.apk");
            Files.write(source.toPath(),
                "F143 immutable source".getBytes(StandardCharsets.UTF_8));
            alias = "negrescodroid.f143.test." + UUID.randomUUID();
            vault = new RecoveryVault(folder, alias);
            vault.save(source, Collections.singletonMap(ENTRY, "A"));
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
    @Test public void f143InvalidatedBeforeAtomicMovePreservesA()
            throws Exception {
        try (Fixture f = new Fixture()) {
            byte[] before = Files.readAllBytes(f.checkpoint.toPath());
            ExportSessionGuard sessions = new ExportSessionGuard();
            ExportSessionGuard.Token token = sessions.begin();
            RecoveryVault paused = new RecoveryVault(f.folder, f.alias,
                stage -> {}, RecoveryStorageBudget.forDirectory(f.folder),
                (read, total) -> {}, stage -> sessions.invalidate());
            try {
                paused.save(f.source,
                    Collections.singletonMap(ENTRY, "B"), token);
                fail("Cancelled project must never replace A");
            } catch (InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("cancelada"));
            }
            assertArrayEquals(before, Files.readAllBytes(f.checkpoint.toPath()));
            assertEquals(Collections.singletonMap(ENTRY, "A"),
                f.vault.loadForSource(f.source));
            File[] stages = f.folder.listFiles((dir, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(stages);
            assertEquals(0, stages.length);
        }
    }
    @Test public void f143CurrentTokenStillSavesB() throws Exception {
        try (Fixture f = new Fixture()) {
            ExportSessionGuard sessions = new ExportSessionGuard();
            ExportSessionGuard.Token token = sessions.begin();
            f.vault.save(f.source, Collections.singletonMap(ENTRY, "B"), token);
            assertTrue(token.isActive());
            assertEquals(Collections.singletonMap(ENTRY, "B"),
                f.vault.loadForSource(f.source));
        }
    }
}
