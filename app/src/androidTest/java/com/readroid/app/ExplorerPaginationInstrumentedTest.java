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

/** Ensure the file browser really pages beyond its initial 120 visible entries. */
@RunWith(AndroidJUnit4.class)
public final class ExplorerPaginationInstrumentedTest {
    private static TextView find(View view, String prefix) {
        if (view instanceof TextView) {
            TextView label = (TextView) view;
            if (label.getText().toString().startsWith(prefix)) return label;
        }
        if (view instanceof ViewGroup) {
            ViewGroup parent = (ViewGroup) view;
            for (int index = 0; index < parent.getChildCount(); index++) {
                TextView found = find(parent.getChildAt(index), prefix);
                if (found != null) return found;
            }
        }
        return null;
    }

    @Test public void loadMoreShowsEntriesAfter120AndKeepsFolderNavigation() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                LinearLayout root = new LinearLayout(activity);
                root.setOrientation(LinearLayout.VERTICAL);
                activity.setContentView(root);
                ExplorerView explorer = new ExplorerView(activity, root);
                JSONArray items = new JSONArray();
                for (int i = 0; i < 145; i++) {
                    try {
                        JSONObject file = new JSONObject();
                        file.put("path", String.format(java.util.Locale.ROOT,
                            "assets/test_%03d.json", i));
                        file.put("sizeBytes", 35);
                        file.put("category", "Assets");
                        items.put(file);
                    } catch (Exception error) {
                        throw new AssertionError(error);
                    }
                }
                explorer.setFiles(items, null);
                TextView assetsFolder = find(root, "▸  assets/");
                assertNotNull("Assets directory was not shown", assetsFolder);
                assetsFolder.performClick();
                assertNotNull("Initial page did not offer remaining entries",
                    find(root, "Carregar mais"));
                assertNull("Last entry must not appear before requesting page two",
                    find(root, "test_144.json"));
                TextView loadMore = find(root, "Carregar mais");
                assertNotNull(loadMore);
                loadMore.performClick();
                assertNotNull("File number 145 must be visible after load more",
                    find(root, "test_144.json"));
                assertNull("All entries loaded: button must disappear",
                    find(root, "Carregar mais"));
            });
        }
    }
}
