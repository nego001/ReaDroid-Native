package com.readroid.app;

import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** P7 explorer UI contract. Uses only synthetic paths and no real APK content. */
@RunWith(AndroidJUnit4.class)
public final class P7ExplorerChromeInstrumentedTest {
    private static TextView find(View node, String exact) {
        if (node instanceof TextView
                && exact.equals(((TextView) node).getText().toString()))
            return (TextView) node;
        if (node instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) node;
            for (int i = 0; i < group.getChildCount(); i++) {
                TextView candidate = find(group.getChildAt(i), exact);
                if (candidate != null) return candidate;
            }
        }
        return null;
    }

    private static TextView findPrefix(View node, String prefix) {
        if (node instanceof TextView
                && ((TextView) node).getText().toString().startsWith(prefix))
            return (TextView) node;
        if (node instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) node;
            for (int i = 0; i < group.getChildCount(); i++) {
                TextView candidate = findPrefix(group.getChildAt(i), prefix);
                if (candidate != null) return candidate;
            }
        }
        return null;
    }

    @Test public void projectCardChipsAndBreadcrumbsRespectRealBrowserState() throws Exception {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    LinearLayout root = new LinearLayout(activity);
                    root.setOrientation(LinearLayout.VERTICAL);
                    activity.setContentView(root);
                    ExplorerView explorer = new ExplorerView(activity, root);
                    JSONArray entries = new JSONArray()
                        .put(new JSONObject().put("path", "assets/a.txt")
                            .put("sizeBytes", 9).put("category", "Assets"))
                        .put(new JSONObject().put("path", "lib/libdemo.so")
                            .put("sizeBytes", 10).put("category", "Bibliotecas"))
                        .put(new JSONObject().put("path", "res/icon.png")
                            .put("sizeBytes", 11).put("category", "Recursos"));
                    explorer.setFiles(entries, null);
                    explorer.setProjectSummary("com.example.synthetic", 4096);
                    assertNotNull(find(root, "Explorador de Arquivos"));
                    assertNotNull(find(root, "com.example.synthetic"));
                    assertNotNull(find(root, "0 alterações pendentes"));
                    assertNotNull(findPrefix(root, "▸  lib/"));
                    TextView chip = find(root, "Assets");
                    assertNotNull("Quick filter chip is missing", chip);
                    assertTrue(chip.performClick());
                    assertNull("Assets filter should hide libs",
                        findPrefix(root, "▸  lib/"));
                    TextView folder = findPrefix(root, "▸  assets/");
                    assertNotNull(folder);
                    assertTrue(folder.performClick());
                    assertNotNull(findPrefix(root, "a.txt"));
                    assertEquals("assets/", explorer.snapshotBrowseState().folder);
                    TextView rootCrumb = find(root, "APK");
                    assertNotNull(rootCrumb);
                    assertTrue(rootCrumb.performClick());
                    assertEquals("", explorer.snapshotBrowseState().folder);
                    assertNotNull(findPrefix(root, "▸  assets/"));
                    explorer.getEditPlan().addTextReplacement("assets/a.txt", "edited");
                    explorer.refresh();
                    assertNotNull(find(root, "1 alteração pendente"));
                    assertTrue(findPrefix(root, "▸  assets/").performClick());
                    assertNotNull(findPrefix(root, "●  a.txt"));
                } catch (Exception failure) {
                    throw new AssertionError(failure);
                }
            });
        }
    }
}
