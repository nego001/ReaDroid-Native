package com.readroid.app;

import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.io.FileOutputStream;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class IndexedExplorerViewInstrumentedTest {
    private static TextView find(View v, String start) {
        if (v instanceof TextView
                && ((TextView) v).getText().toString().startsWith(start))
            return (TextView) v;
        if (v instanceof ViewGroup) {
            ViewGroup g = (ViewGroup) v;
            for (int i = 0; i < g.getChildCount(); i++) {
                TextView result = find(g.getChildAt(i), start);
                if (result != null) return result;
            }
        }
        return null;
    }

    private static View entry(View v, String description) {
        if (description.equals(v.getContentDescription())) return v;
        if (v instanceof ViewGroup) {
            ViewGroup p = (ViewGroup) v;
            for (int i = 0; i < p.getChildCount(); i++) {
                View result = entry(p.getChildAt(i), description);
                if (result != null) return result;
            }
        }
        return null;
    }

    private static EditText input(View v) {
        if (v instanceof EditText) return (EditText) v;
        if (v instanceof ViewGroup) {
            ViewGroup g = (ViewGroup) v;
            for (int i = 0; i < g.getChildCount(); i++) {
                EditText child = input(g.getChildAt(i));
                if (child != null) return child;
            }
        }
        return null;
    }

    @Test public void restoresDeepIndexedFolderMissingFromJsonFallback() throws Exception {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                File apk = null, index = null;
                try {
                    apk = File.createTempFile("deep_restore_", ".apk", activity.getCacheDir());
                    index = new File(apk.getAbsolutePath() + ".idx.db");
                    JSONArray partialFallback = new JSONArray();
                    try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                        for (int i = 0; i < 145; i++) {
                            String path = String.format(Locale.ROOT, "assets/a%03d.txt", i);
                            out.putNextEntry(new ZipEntry(path));
                            out.write("a".getBytes(java.nio.charset.StandardCharsets.UTF_8));
                            out.closeEntry();
                            if (i < 120) partialFallback.put(new JSONObject()
                                .put("path", path).put("category", "Assets")
                                .put("sizeBytes", 1));
                        }
                        out.putNextEntry(new ZipEntry("verydeep/inner/readme.txt"));
                        out.write("hello".getBytes(java.nio.charset.StandardCharsets.UTF_8));
                        out.closeEntry();
                        out.putNextEntry(new ZipEntry("emptyfolder/"));
                        out.closeEntry();
                    }
                    ApkDiskIndex.build(apk, index);
                    assertTrue(ApkDiskIndex.containsDirectory(apk, index, "verydeep/inner/"));
                    assertTrue(ApkDiskIndex.containsDirectory(apk, index, "emptyfolder/"));
                    assertFalse(ApkDiskIndex.containsDirectory(apk, index, "missing/"));

                    LinearLayout firstRoot = new LinearLayout(activity);
                    firstRoot.setOrientation(LinearLayout.VERTICAL);
                    ExplorerView first = new ExplorerView(activity, firstRoot);
                    first.setIndexedFiles(partialFallback, apk, index);
                    assertTrue(entry(firstRoot, "Abrir pasta verydeep/").performClick());
                    assertTrue(entry(firstRoot, "Abrir pasta inner/").performClick());
                    ExplorerView.BrowseState deepState = first.snapshotBrowseState();
                    assertEquals("verydeep/inner/", deepState.folder);

                    // Simulate Activity recreation with a new ExplorerView.
                    LinearLayout secondRoot = new LinearLayout(activity);
                    secondRoot.setOrientation(LinearLayout.VERTICAL);
                    ExplorerView restored = new ExplorerView(activity, secondRoot);
                    restored.setIndexedFiles(partialFallback, apk, index);
                    restored.restoreBrowseState(deepState);
                    assertEquals("Deep folder should survive rotation",
                        "verydeep/inner/", restored.snapshotBrowseState().folder);
                    assertNotNull(entry(secondRoot, "Abrir arquivo readme.txt"));

                    // Explicitly empty folders also exist in SQLite.
                    restored.restoreBrowseState(new ExplorerView.BrowseState(
                        "emptyfolder/", "Todos", "", 120));
                    assertEquals("emptyfolder/", restored.snapshotBrowseState().folder);

                    // Rejected paths must not escape to another archive or the host FS.
                    for (String bad : new String[]{"verydeep/../", "/absolute/",
                            "nonexistent/", "verydeep/inner"}) {
                        restored.restoreBrowseState(new ExplorerView.BrowseState(
                            bad, "Todos", "", 120));
                        assertEquals("Unsafe or missing directory accepted",
                            "", restored.snapshotBrowseState().folder);
                    }
                } catch (Exception err) {
                    throw new AssertionError(err);
                } finally {
                    if (index != null)
                        android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
                    if (apk != null) apk.delete();
                }
            });
        }
    }

    @Test public void editsBeyondFallbackRemainVisibleInChangedAndEditableFilters()
            throws Exception {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                File apk = null, index = null;
                try {
                    apk = File.createTempFile("edits_index_", ".apk", activity.getCacheDir());
                    index = new File(apk.getAbsolutePath() + ".idx.db");
                    JSONArray truncatedJson = new JSONArray();
                    try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                        for (int i = 0; i < 145; i++) {
                            String path = String.format(Locale.ROOT, "assets/a%03d.txt", i);
                            out.putNextEntry(new ZipEntry(path));
                            out.write("text".getBytes(java.nio.charset.StandardCharsets.UTF_8));
                            out.closeEntry();
                            if (i < 120) truncatedJson.put(new JSONObject()
                                .put("path", path).put("category", "Assets")
                                .put("sizeBytes", 4));
                        }
                        out.putNextEntry(new ZipEntry("assets/raw.bin"));
                        out.write(new byte[]{1, 2, 3});
                        out.closeEntry();
                    }
                    ApkDiskIndex.build(apk, index);
                    LinearLayout root = new LinearLayout(activity);
                    root.setOrientation(LinearLayout.VERTICAL);
                    ExplorerView explorer = new ExplorerView(activity, root);
                    explorer.setIndexedFiles(truncatedJson, apk, index);
                    explorer.getEditPlan().addTextReplacement(
                        "assets/a144.txt", "temporary edit");
                    // A stale plan entry is never shown as a real APK file.
                    explorer.getEditPlan().addTextReplacement(
                        "ghost/missing.txt", "not really in the APK");
                    explorer.restoreBrowseState(
                        new ExplorerView.BrowseState("", "Alterados", "", 120));
                    assertNotNull("Real edited folder should be browsable",
                        entry(root, "Abrir pasta assets/"));
                    assertNull("Ghost folder must not be fabricated",
                        entry(root, "Abrir pasta ghost/"));
                    assertTrue(entry(root, "Abrir pasta assets/").performClick());
                    assertNotNull("Edited entry must come from the full index",
                        entry(root, "Abrir arquivo a144.txt, alterado"));
                    assertNull(entry(root, "Abrir arquivo a000.txt"));
                    EditText search = input(root);
                    search.setText("a144");
                    assertNotNull("Edited file should be searchable globally",
                        entry(root, "Abrir arquivo assets/a144.txt, alterado"));
                    assertEquals(2, explorer.getEditPlan().size());
                    explorer.restoreBrowseState(
                        new ExplorerView.BrowseState("assets/", "Editáveis", "", 120));
                    assertEquals("assets/", explorer.snapshotBrowseState().folder);
                    assertNotNull(entry(root, "Abrir arquivo a000.txt"));
                    assertNotNull(find(root, "Próxima página"));
                    find(root, "Próxima página").performClick();
                    assertNotNull("Editable item beyond fallback must be pageable",
                        entry(root, "Abrir arquivo a144.txt, alterado"));
                    assertNull("Binary entries cannot count as editable",
                        entry(root, "Abrir arquivo raw.bin"));
                } catch (Exception err) {
                    throw new AssertionError(err);
                } finally {
                    if (index != null)
                        android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
                    if (apk != null) apk.delete();
                }
            });
        }
    }

    @Test public void staleIndexShowsPartialWarningWithoutLosingEdits()
            throws Exception {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                File apk = null, index = null;
                try {
                    apk = File.createTempFile("stale_index_", ".apk",
                        activity.getCacheDir());
                    index = new File(apk.getAbsolutePath() + ".idx.db");
                    JSONArray partial = new JSONArray();
                    try (ZipOutputStream zip = new ZipOutputStream(
                            new FileOutputStream(apk))) {
                        for (int i = 0; i < 145; i++) {
                            String path = String.format(Locale.ROOT,
                                "assets/a%03d.txt", i);
                            zip.putNextEntry(new ZipEntry(path));
                            zip.write("test".getBytes(
                                java.nio.charset.StandardCharsets.UTF_8));
                            zip.closeEntry();
                            if (i < 120) partial.put(new JSONObject()
                                .put("path", path)
                                .put("category", "Assets")
                                .put("sizeBytes", 4));
                        }
                    }
                    ApkDiskIndex.build(apk, index);
                    LinearLayout root = new LinearLayout(activity);
                    root.setOrientation(LinearLayout.VERTICAL);
                    activity.setContentView(root);
                    ExplorerView explorer = new ExplorerView(activity, root);
                    explorer.setIndexedFiles(partial, apk, index);
                    explorer.getEditPlan().addTextReplacement(
                        "assets/a000.txt", "changed");
                    explorer.refresh();
                    TextView warning = find(root, "Índice indisponível.");
                    assertNotNull("Warning node must be built", warning);
                    assertEquals("Healthy index must hide warning",
                        View.GONE, warning.getVisibility());

                    // Mutate only the synthetic source to invalidate size+mtime
                    // identity, without editing a real user's APK.
                    try (FileOutputStream output = new FileOutputStream(apk, true)) {
                        output.write(new byte[]{1, 2, 3, 4});
                    }
                    explorer.refresh();
                    assertEquals("Stale index must not silently show partial data",
                        View.VISIBLE, warning.getVisibility());
                    assertNotNull("Fallback counts must admit incompleteness",
                        find(root, "Prévia possivelmente incompleta"));
                    assertEquals("In-memory edit plan must survive fallback",
                        1, explorer.getEditPlan().size());
                    assertNotNull(entry(root, "Abrir pasta assets/"));
                    assertNull("Partial listing cannot invent omitted entries",
                        entry(root, "Abrir arquivo a144.txt"));

                    // Fresh non-indexed sessions must not inherit stale banners.
                    explorer.setFiles(partial, null);
                    assertEquals(View.GONE, warning.getVisibility());
                } catch (Exception error) {
                    throw new AssertionError(error);
                } finally {
                    if (index != null)
                        android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
                    if (apk != null) apk.delete();
                }
            });
        }
    }

    @Test public void indexedPagesSearchAndEditPlanSurviveNavigation() throws Exception {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                File apk = null, index = null;
                try {
                    apk = File.createTempFile("indexed_view_", ".apk", activity.getCacheDir());
                    index = new File(apk.getAbsolutePath() + ".idx.db");
                    JSONArray entries = new JSONArray();
                    try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                        for (int i = 0; i < 301; i++) {
                            String path = String.format(Locale.ROOT, "assets/a%03d.txt", i);
                            out.putNextEntry(new ZipEntry(path));
                            out.write("sample".getBytes(java.nio.charset.StandardCharsets.UTF_8));
                            out.closeEntry();
                            entries.put(new JSONObject().put("path", path)
                                .put("sizeBytes", 6).put("category", "Assets"));
                        }
                    }
                    ApkDiskIndex.build(apk, index);
                    LinearLayout root = new LinearLayout(activity);
                    root.setOrientation(LinearLayout.VERTICAL);
                    activity.setContentView(root);
                    ExplorerView explorer = new ExplorerView(activity, root);
                    explorer.setIndexedFiles(entries, apk, index);
                    View assets = entry(root, "Abrir pasta assets/");
                    assertNotNull(assets);
                    assets.performClick();
                    assertNotNull(entry(root, "Abrir arquivo a000.txt"));
                    assertNull(entry(root, "Abrir arquivo a300.txt"));
                    assertNotNull(find(root, "Próxima página"));
                    find(root, "Próxima página").performClick();
                    assertNotNull(find(root, "Página anterior"));
                    assertNotNull(entry(root, "Abrir arquivo a120.txt"));
                    find(root, "Próxima página").performClick();
                    assertNotNull(entry(root, "Abrir arquivo a300.txt"));
                    explorer.getEditPlan().addTextReplacement("assets/a300.txt", "modified");
                    explorer.refresh();
                    assertNotNull(entry(root, "Abrir arquivo a300.txt, alterado"));
                    EditText search = input(root);
                    assertNotNull(search);
                    search.setText("a005");
                    assertNotNull(entry(root, "Abrir arquivo assets/a005.txt"));
                    ExplorerView.BrowseState saved = explorer.snapshotBrowseState();
                    assertEquals(0, saved.indexPageOffset);
                    char[] oversized = new char[300];
                    java.util.Arrays.fill(oversized, 'q');
                    search.setText(new String(oversized));
                    assertEquals("Overlong paste must be bounded to SQLite limit",
                        256, search.getText().length());
                    TextView indexWarning = find(root, "Índice indisponível.");
                    assertNotNull(indexWarning);
                    assertEquals("Long paste must not disable healthy index",
                        View.GONE, indexWarning.getVisibility());
                    search.setText("a300");
                    assertNotNull("Search must still see page-3 indexed files",
                        entry(root, "Abrir arquivo assets/a300.txt, alterado"));
                    explorer.restoreBrowseState(new ExplorerView.BrowseState(
                        "assets/", "Todos", new String(oversized), 120));
                    assertEquals("Retained search must obey the index limit",
                        256, search.getText().length());
                    assertEquals(View.GONE, indexWarning.getVisibility());
                    search.setText("");
                    assertNotNull(find(root, "a000.txt"));
                    assertEquals(1, explorer.getEditPlan().size());
                } catch (Exception err) {
                    throw new AssertionError(err);
                } finally {
                    if (index != null)
                        android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
                    if (apk != null) apk.delete();
                }
            });
        }
    }
}
