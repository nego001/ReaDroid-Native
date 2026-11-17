package com.readroid.app;

import android.net.Uri;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** Real Activity recreation with a synthetic, untrusted and unsigned APK fixture. */
@RunWith(AndroidJUnit4.class)
public final class ProjectRecreationInstrumentedTest {
    private static final String PATH = "assets/v3_test.txt";
    private static final String CHANGE = "alteração pendente após rotação ✓";

    private static Object field(MainActivity activity, String name) throws Exception {
        return field((Object) activity, name);
    }

    private static Object field(Object object, String name) throws Exception {
        Field f = object.getClass().getDeclaredField(name);
        f.setAccessible(true);
        return f.get(object);
    }

    private static void setField(MainActivity activity, String name, Object value)
            throws Exception {
        Field f = MainActivity.class.getDeclaredField(name);
        f.setAccessible(true);
        f.set(activity, value);
    }

    private static View findTab(View root, String label) {
        CharSequence desc = root.getContentDescription();
        if (desc != null && desc.toString().startsWith("Seção " + label)
            && root.isClickable()) return root;
        if (root instanceof ViewGroup) {
            ViewGroup parent = (ViewGroup) root;
            for (int i = 0; i < parent.getChildCount(); i++) {
                View found = findTab(parent.getChildAt(i), label);
                if (found != null) return found;
            }
        }
        return null;
    }

    private static void injectTestWorkspace(MainActivity activity, File apk) throws Exception {
        // Test-only reflection exercises the real Activity lifecycle without
        // adding debug hooks to production, SAF grants or signing capabilities.
        setField(activity, "currentApk", apk);
        JSONObject file = new JSONObject().put("path", PATH)
            .put("sizeBytes", 8).put("category", "Assets");
        JSONObject report = new JSONObject()
            .put("entries", 2).put("sizeBytes", apk.length())
            .put("assets", 1)
            .put("manifestAnalysis", new JSONObject()
                .put("packageName", "com.negresco.rotation.fixture"))
            .put("explorer", new JSONObject().put("files", new JSONArray().put(file)));
        Method display = MainActivity.class.getDeclaredMethod("displayAnalyzedReport",
            JSONObject.class);
        display.setAccessible(true);
        display.invoke(activity, report);
        ExplorerView explorer = (ExplorerView) field(activity, "explorerView");
        explorer.getEditPlan().addTextReplacement(PATH, CHANGE);
        explorer.refresh();
        View files = findTab(activity.getWindow().getDecorView(), "Arquivos");
        assertNotNull("Missing Arquivos tab", files);
        assertTrue(files.performClick());
    }

    private static void assertWorkspace(MainActivity activity, File apk) throws Exception {
        File reopened = (File) field(activity, "currentApk");
        assertNotNull("APK was lost during Activity recreation", reopened);
        assertEquals("Different cached project after recreation",
            apk.getCanonicalPath(), reopened.getCanonicalPath());
        assertTrue("Cached test APK was unexpectedly deleted", reopened.isFile());
        JSONObject report = (JSONObject) field(activity, "report");
        assertNotNull("Analysis report was lost", report);
        assertEquals("com.negresco.rotation.fixture",
            report.getJSONObject("manifestAnalysis").getString("packageName"));
        ExplorerView explorer = (ExplorerView) field(activity, "explorerView");
        assertEquals(1, explorer.getEditPlan().size());
        assertEquals("Pending edit was lost", CHANGE,
            explorer.getEditPlan().get(PATH));
        View selected = findTab(activity.getWindow().getDecorView(), "Arquivos");
        assertNotNull(selected);
        assertTrue("Selected tab should survive recreation", selected.isSelected());
        assertTrue(selected.getContentDescription().toString().contains("selecionada"));
    }

    @Test public void explorerFolderSearchAndFilterSurviveRecreation() throws Exception {
        File apk = File.createTempFile("v3_browse_fixture_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                out.putNextEntry(new ZipEntry(PATH));
                out.write("original".getBytes(StandardCharsets.UTF_8));
                out.closeEntry();
            }
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    try {
                        injectTestWorkspace(activity, apk);
                        ExplorerView explorer = (ExplorerView) field(activity, "explorerView");
                        explorer.restoreBrowseState(new ExplorerView.BrowseState(
                            "assets/", "Editáveis", "v3_test", 240));
                        ExplorerView.BrowseState snapshot = explorer.snapshotBrowseState();
                        assertEquals("assets/", snapshot.folder);
                        assertEquals("Editáveis", snapshot.category);
                        assertEquals("v3_test", snapshot.query);
                        assertEquals(121, snapshot.pageLimit); // one-file fixture bounds pagination
                    } catch (Exception error) { throw new AssertionError(error); }
                });
                scenario.recreate();
                scenario.onActivity(activity -> {
                    try {
                        assertWorkspace(activity, apk);
                        ExplorerView explorer = (ExplorerView) field(activity, "explorerView");
                        ExplorerView.BrowseState snapshot = explorer.snapshotBrowseState();
                        assertEquals("assets/", snapshot.folder);
                        assertEquals("Editáveis", snapshot.category);
                        assertEquals("v3_test", snapshot.query);
                        // P7 uses a compact filter icon; the active category
                        // is announced on its selected accessible quick chip.
                        assertEquals("▦",
                            ((android.widget.Button) field(explorer, "filterButton"))
                                .getText().toString());
                        assertEquals("Editáveis", snapshot.category);
                    } catch (Exception error) { throw new AssertionError(error); }
                });
            }
        } finally {
            apk.delete();
        }
    }

    @Test public void projectAndPendingEditSurviveRecreationWithoutMutatingSource()
            throws Exception {
        File apk = File.createTempFile("v3_rotation_fixture_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                out.putNextEntry(new ZipEntry("AndroidManifest.xml"));
                out.write("test-only".getBytes(StandardCharsets.UTF_8));
                out.closeEntry();
                out.putNextEntry(new ZipEntry(PATH));
                out.write("original".getBytes(StandardCharsets.UTF_8));
                out.closeEntry();
            }
            byte[] original = Files.readAllBytes(apk.toPath());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    try { injectTestWorkspace(activity, apk); }
                    catch (Exception error) { throw new AssertionError(error); }
                });
                scenario.recreate();
                scenario.onActivity(activity -> {
                    try { assertWorkspace(activity, apk); }
                    catch (Exception error) { throw new AssertionError(error); }
                });
                assertArrayEquals("Rotation must never modify the original APK",
                    original, Files.readAllBytes(apk.toPath()));
            }
        } finally {
            apk.delete();
        }
    }

    @Test public void f119RevokedRecentPermissionLeavesCurrentProjectUnchanged()
            throws Exception {
        File apk = File.createTempFile("f119_previous_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                out.putNextEntry(new ZipEntry(PATH));
                out.write("original".getBytes(StandardCharsets.UTF_8));
                out.closeEntry();
            }
            byte[] before = Files.readAllBytes(apk.toPath());
            Uri selected = Uri.parse("content://com.readroid.app.f119/original.apk");
            Uri revoked = Uri.parse("content://com.readroid.app.revoked/other.apk");
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    try {
                        injectTestWorkspace(activity, apk);
                        setField(activity, "selectedApkUri", selected);
                        int generation = (Integer) field(activity, "analysisSequence");
                        P7ProjectHistory.Entry entry = new P7ProjectHistory.Entry(
                            revoked, "Revoked", "com.example.revoked", 0L);
                        Method reopen = MainActivity.class.getDeclaredMethod(
                            "openRecentProject", P7ProjectHistory.Entry.class);
                        reopen.setAccessible(true);
                        reopen.invoke(activity, entry);
                        assertWorkspace(activity, apk);
                        assertEquals(selected, field(activity, "selectedApkUri"));
                        assertNull(field(activity, "pendingApkUri"));
                        assertEquals(generation, field(activity, "analysisSequence"));
                        // ActivityScenario.close() calls onDestroy(), which
                        // legitimately deletes its privately owned APK cache.
                        // Assert source integrity BEFORE lifecycle teardown.
                        assertArrayEquals(before, Files.readAllBytes(apk.toPath()));
                    } catch (Exception error) {
                        throw new AssertionError(error);
                    }
                });
            }
        } finally { apk.delete(); }
    }

    @Test public void f120SavedStateRecordsAcceptedApkDigestWithoutSavingEdits()
            throws Exception {
        File apk = File.createTempFile("f120_state_fixture_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                out.putNextEntry(new ZipEntry("AndroidManifest.xml"));
                out.write("test".getBytes(StandardCharsets.UTF_8));
                out.closeEntry();
                out.putNextEntry(new ZipEntry(PATH));
                out.write("original".getBytes(StandardCharsets.UTF_8));
                out.closeEntry();
            }
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    try {
                        injectTestWorkspace(activity, apk);
                        Uri accepted = Uri.parse(
                            "content://com.readroid.app.f120/document/accepted.apk");
                        setField(activity, "selectedApkUri", accepted);
                        String digest = ApkIntegrity.sha256(apk);
                        ((JSONObject) field(activity, "report")).put("sha256", digest);
                        android.os.Bundle saved = new android.os.Bundle();
                        Method save = MainActivity.class.getDeclaredMethod(
                            "onSaveInstanceState", android.os.Bundle.class);
                        save.setAccessible(true);
                        save.invoke(activity, saved);
                        assertEquals(accepted, saved.getParcelable("selected_apk_uri"));
                        assertEquals(digest, saved.getString("f120_accepted_sha256"));
                        assertFalse("Edits must not appear in saved Activity state",
                            saved.toString().contains(CHANGE));
                        assertWorkspace(activity, apk);
                    } catch (Exception error) {
                        throw new AssertionError(error);
                    }
                });
            }
        } finally { apk.delete(); }
    }

    @Test public void f120PendingImportNeverReceivesAnAcceptedHashWithoutProject()
            throws Exception {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    setField(activity, "currentApk", null);
                    setField(activity, "report", null);
                    setField(activity, "selectedApkUri", null);
                    setField(activity, "pendingApkUri", Uri.parse(
                        "content://com.readroid.app.f120/document/pending.apk"));
                    android.os.Bundle saved = new android.os.Bundle();
                    Method save = MainActivity.class.getDeclaredMethod(
                        "onSaveInstanceState", android.os.Bundle.class);
                    save.setAccessible(true);
                    save.invoke(activity, saved);
                    assertNull(saved.getString("f120_accepted_sha256"));
                    assertNull(saved.getParcelable("selected_apk_uri"));
                    assertNotNull(saved.getParcelable("pending_apk_uri"));
                } catch (Exception error) {
                    throw new AssertionError(error);
                }
            });
        }
    }

    private static void awaitPendingImportSettled(ActivityScenario<MainActivity> scenario)
            throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(20);
        final boolean[] cleared = {false};
        while (System.nanoTime() < deadline) {
            scenario.onActivity(activity -> {
                try {
                    cleared[0] = field(activity, "pendingApkUri") == null;
                } catch (Exception error) {
                    throw new AssertionError(error);
                }
            });
            if (cleared[0]) return;
            Thread.sleep(30);
        }
        fail("The newest SAF import did not settle in 20 seconds");
    }

    @Test public void f122TwoFailedImportsCannotReplacePriorWorkspaceOrEdits()
            throws Exception {
        File apk = File.createTempFile("f122_previous_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                out.putNextEntry(new ZipEntry(PATH));
                out.write("original".getBytes(StandardCharsets.UTF_8));
                out.closeEntry();
            }
            byte[] previousBytes = Files.readAllBytes(apk.toPath());
            Uri oldUri = Uri.parse("content://com.readroid.app.f122/project/previous.apk");
            Uri first = Uri.parse("content://com.readroid.app.f122.invalid/first.apk");
            Uri second = Uri.parse("content://com.readroid.app.f122.invalid/second.apk");

            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    try {
                        injectTestWorkspace(activity, apk);
                        setField(activity, "selectedApkUri", oldUri);
                        int before = (Integer) field(activity, "analysisSequence");
                        Method open = MainActivity.class.getDeclaredMethod(
                            "analyzeSelectedApk", Uri.class);
                        open.setAccessible(true);
                        open.invoke(activity, first);
                        open.invoke(activity, second);
                        assertWorkspace(activity, apk);
                        assertEquals(before + 2, field(activity, "analysisSequence"));
                        assertEquals(second, field(activity, "pendingApkUri"));

                    } catch (Exception error) { throw new AssertionError(error); }
                });
                // Imports use a separate bounded lane. A barrier on the
                // shared export executor no longer waits for SAF work.
                awaitPendingImportSettled(scenario);
                scenario.onActivity(activity -> {
                    try {
                        assertWorkspace(activity, apk);
                        assertEquals(oldUri, field(activity, "selectedApkUri"));
                        assertNull("Last failed import must clear pending URI",
                            field(activity, "pendingApkUri"));
                        assertArrayEquals("Old project bytes changed after two failures",
                            previousBytes, Files.readAllBytes(apk.toPath()));
                    } catch (Exception error) { throw new AssertionError(error); }
                });
            }
        } finally { apk.delete(); }
    }

    @Test public void failedReplacementRetainsOldApkAndUnsavedEdits()
            throws Exception {
        File apk = File.createTempFile("p7_previous_project_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                out.putNextEntry(new ZipEntry(PATH));
                out.write("original".getBytes(StandardCharsets.UTF_8));
                out.closeEntry();
            }
            byte[] originalBytes = Files.readAllBytes(apk.toPath());
            Uri previousUri = Uri.parse("content://com.readroid.app.original/project.apk");
            Uri brokenUri = Uri.parse("content://com.readroid.app.invalid/new.apk");

            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    try {
                        injectTestWorkspace(activity, apk);
                        setField(activity, "selectedApkUri", previousUri);
                        // Exercise the actual async import implementation.
                        // The invalid content authority cannot produce an APK.
                        Method open = MainActivity.class.getDeclaredMethod(
                            "analyzeSelectedApk", Uri.class);
                        open.setAccessible(true);
                        open.invoke(activity, brokenUri);
                        assertWorkspace(activity, apk);

                    } catch (Exception error) { throw new AssertionError(error); }
                });
                awaitPendingImportSettled(scenario);
                scenario.onActivity(activity -> {
                    try {
                        assertWorkspace(activity, apk);
                        assertEquals("Failed import must not replace selected URI",
                            previousUri, field(activity, "selectedApkUri"));
                        assertNull("Failed import must clear its pending URI",
                            field(activity, "pendingApkUri"));
                        TextView summary = (TextView) field(activity, "apkSummary");
                        assertFalse("Previous project summary was replaced by failure",
                            summary.getText().toString().contains("FALHA"));
                    } catch (Exception error) { throw new AssertionError(error); }
                });
                assertArrayEquals("Failed import changed the existing APK bytes",
                    originalBytes, Files.readAllBytes(apk.toPath()));
            }
        } finally {
            apk.delete();
        }
    }
}
