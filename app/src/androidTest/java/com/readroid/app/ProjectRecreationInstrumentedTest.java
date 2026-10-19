package com.readroid.app;

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
                        assertEquals("Filtro: Editáveis  ▾",
                            ((android.widget.Button) field(explorer, "filterButton")).getText().toString());
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
}
