package com.readroid.app;

import android.content.Context;
import android.content.SharedPreferences;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Real persistence and Activity recreation for catalog themes. */
@RunWith(AndroidJUnit4.class)
public final class P7ThemeCatalogInstrumentedTest {
    @Test public void themeChoicePersistsAndLeavesProjectIndependentPreferencesUnchanged() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                SharedPreferences prefs = activity.getSharedPreferences(
                    "v3_personalizacao", Context.MODE_PRIVATE);
                String originalTheme = prefs.getString("theme", "oled");
                String originalAccent = prefs.getString("accent", "blue");
                try {
                    prefs.edit().putString("theme","oled").putString("accent","blue")
                        .putString("test_workspace_sentinel","untouched").commit();
                    P7ThemeCatalog.apply(activity, 2);
                    assertEquals("oled", prefs.getString("theme", ""));
                    assertEquals("green", prefs.getString("accent", ""));
                    assertEquals("untouched", prefs.getString("test_workspace_sentinel",""));
                    try {
                        P7ThemeCatalog.apply(activity, 100);
                        fail("Invalid themes must be rejected");
                    } catch (IllegalArgumentException expected) {
                        assertEquals("green", prefs.getString("accent",""));
                    }
                } finally {
                    prefs.edit().putString("theme",originalTheme)
                        .putString("accent",originalAccent)
                        .remove("test_workspace_sentinel").commit();
                }
            });
        }
    }
}
