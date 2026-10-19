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

/**
 * Page-two regression across Activity recreation.
 * The only input is a private, unsigned fixture constructed inside test cache.
 */
@RunWith(AndroidJUnit4.class)
public final class ExplorerStatePaginationInstrumentedTest {
    private static View findTab(View root, String name) {
        CharSequence desc = root.getContentDescription();
        if (desc != null && desc.toString().startsWith("Seção " + name)
            && root.isClickable()) return root;
        if (root instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) root;
            for (int i = 0; i < group.getChildCount(); i++) {
                View result = findTab(group.getChildAt(i), name);
                if (result != null) return result;
            }
        }
        return null;
    }

    private static TextView findText(View root, String prefix) {
        if (root instanceof TextView) {
            TextView text = (TextView) root;
            if (text.getText().toString().startsWith(prefix)) return text;
        }
        if (root instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) root;
            for (int i = 0; i < group.getChildCount(); i++) {
                TextView result = findText(group.getChildAt(i), prefix);
                if (result != null) return result;
            }
        }
        return null;
    }

    private static void setApk(MainActivity activity, File apk) throws Exception {
        Field field = MainActivity.class.getDeclaredField("currentApk");
        field.setAccessible(true);
        field.set(activity, apk);
    }

    private static ExplorerView explorer(MainActivity activity) throws Exception {
        Field field = MainActivity.class.getDeclaredField("explorerView");
        field.setAccessible(true);
        return (ExplorerView) field.get(activity);
    }

    private static JSONObject report(File apk) throws Exception {
        JSONArray files = new JSONArray();
        for (int i = 0; i < 145; i++) {
            files.put(new JSONObject()
                .put("path", String.format(java.util.Locale.ROOT,
                    "assets/file_%03d.txt", i))
                .put("sizeBytes", 8).put("category", "Assets"));
        }
        return new JSONObject()
            .put("entries", 145).put("sizeBytes", apk.length()).put("assets", 145)
            .put("manifestAnalysis", new JSONObject()
                .put("packageName", "com.negresco.pagination.fixture"))
            .put("explorer", new JSONObject().put("files", files));
    }

    @Test public void folderAndPageTwoSurviveRecreationAndOriginalIsUnchanged()
            throws Exception {
        File apk = File.createTempFile("v3_page_two_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                for (int i = 0; i < 145; i++) {
                    out.putNextEntry(new ZipEntry(String.format(java.util.Locale.ROOT,
                        "assets/file_%03d.txt", i)));
                    out.write("original".getBytes(StandardCharsets.UTF_8));
                    out.closeEntry();
                }
            }
            byte[] bytes = Files.readAllBytes(apk.toPath());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    try {
                        setApk(activity, apk);
                        Method display = MainActivity.class.getDeclaredMethod(
                            "displayAnalyzedReport", JSONObject.class);
                        display.setAccessible(true);
                        display.invoke(activity, report(apk));
                        View root = activity.getWindow().getDecorView();
                        View tab = findTab(root, "Arquivos");
                        assertNotNull(tab);
                        assertTrue(tab.performClick());
                        TextView folder = findText(root, "▸  assets/");
                        assertNotNull("Assets folder missing", folder);
                        assertTrue(folder.performClick());
                        assertNull("The 145th entry must start on page two",
                            findText(root, "file_144.txt"));
                        TextView more = findText(root, "Carregar mais");
                        assertNotNull("Paging control missing", more);
                        assertTrue(more.performClick());
                        assertNotNull("Page two did not load", findText(root, "file_144.txt"));
                        ExplorerView.BrowseState state = explorer(activity).snapshotBrowseState();
                        assertEquals("assets/", state.folder);
                        assertEquals(240, state.pageLimit);
                    } catch (Exception error) { throw new AssertionError(error); }
                });
                scenario.recreate();
                scenario.onActivity(activity -> {
                    try {
                        View root = activity.getWindow().getDecorView();
                        ExplorerView.BrowseState state = explorer(activity).snapshotBrowseState();
                        assertEquals("assets/", state.folder);
                        assertEquals("Todos", state.category);
                        assertEquals("", state.query);
                        assertEquals(240, state.pageLimit);
                        assertTrue(findTab(root, "Arquivos").isSelected());
                        assertNotNull("Last visible item disappeared after recreation",
                            findText(root, "file_144.txt"));
                        assertNull("Paging should remain complete",
                            findText(root, "Carregar mais"));
                    } catch (Exception error) { throw new AssertionError(error); }
                });
                assertArrayEquals("Activity recreation cannot mutate source ZIP",
                    bytes, Files.readAllBytes(apk.toPath()));
            }
        } finally {
            apk.delete();
        }
    }
}
