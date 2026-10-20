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
                    TextView assets = find(root, "▸  assets/");
                    assertNotNull(assets);
                    assets.performClick();
                    assertNotNull(find(root, "a000.txt"));
                    assertNull(find(root, "a300.txt"));
                    assertNotNull(find(root, "Próxima página"));
                    find(root, "Próxima página").performClick();
                    assertNotNull(find(root, "Página anterior"));
                    assertNotNull(find(root, "a120.txt"));
                    find(root, "Próxima página").performClick();
                    assertNotNull(find(root, "a300.txt"));
                    explorer.getEditPlan().addTextReplacement("assets/a300.txt", "modified");
                    explorer.refresh();
                    assertNotNull(find(root, "●  a300.txt"));
                    EditText search = input(root);
                    assertNotNull(search);
                    search.setText("a005");
                    assertNotNull(find(root, "assets/a005.txt"));
                    ExplorerView.BrowseState saved = explorer.snapshotBrowseState();
                    assertEquals(0, saved.indexPageOffset);
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
