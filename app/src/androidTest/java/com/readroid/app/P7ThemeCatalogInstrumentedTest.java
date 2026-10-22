package com.readroid.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import java.util.HashSet;
import java.util.Set;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Real persistence and Activity recreation for catalog themes. */
@RunWith(AndroidJUnit4.class)
public final class P7ThemeCatalogInstrumentedTest {
    @Test public void catalogHasTwelveUniqueRealPreferenceCombinations() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences p = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        String originalTheme = p.getString("theme", "oled");
        String originalAccent = p.getString("accent", "blue");
        boolean hasTheme = p.contains("theme");
        boolean hasAccent = p.contains("accent");
        int originalPreset = p.getInt("p7_active_preset", -1);
        boolean hasPreset = p.contains("p7_active_preset");
        Set<String> identities = new HashSet<>();
        try {
            assertEquals(12, P7ThemeCatalog.count());
            assertEquals("Negreco Blue", P7ThemeCatalog.nameAt(0));
            assertEquals("Sunset", P7ThemeCatalog.nameAt(3));
            for (int i = 0; i < P7ThemeCatalog.count(); i++) {
                P7ThemeCatalog.persist(context, i);
                assertEquals(i, P7ThemeCatalog.currentTheme(context));
                String signature = p.getString("theme", "") + "/" +
                    p.getString("accent", "");
                assertTrue("Duplicate theme state: " + signature,
                    identities.add(signature));
                assertEquals(-1, p.getInt("p7_active_preset", -1));
            }
            assertEquals(12, identities.size());
        } finally {
            SharedPreferences.Editor restore = p.edit();
            if (hasTheme) restore.putString("theme", originalTheme);
            else restore.remove("theme");
            if (hasAccent) restore.putString("accent", originalAccent);
            else restore.remove("accent");
            if (hasPreset) restore.putInt("p7_active_preset", originalPreset);
            else restore.remove("p7_active_preset");
            assertTrue(restore.commit());
        }
    }

    @Test public void customAppearanceIsNeverMislabelledAsCatalogTheme() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences p = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        String oldSurface = p.getString("theme", "oled");
        String oldAccent = p.getString("accent", "blue");
        boolean hasSurface = p.contains("theme");
        boolean hasAccent = p.contains("accent");
        try {
            assertTrue(p.edit().putString("theme", "oled")
                .putString("accent", "custom").commit());
            assertEquals(-1, P7ThemeCatalog.currentTheme(context));
            assertTrue(p.edit().putString("theme", "light")
                .putString("accent", "orange").commit());
            assertEquals(11, P7ThemeCatalog.currentTheme(context));
            try {
                P7ThemeCatalog.persist(context, 12);
                fail("Catalog must not silently apply a missing theme");
            } catch (IllegalArgumentException expected) {
                assertEquals(11, P7ThemeCatalog.currentTheme(context));
            }
        } finally {
            SharedPreferences.Editor restore = p.edit();
            if (hasSurface) restore.putString("theme", oldSurface);
            else restore.remove("theme");
            if (hasAccent) restore.putString("accent", oldAccent);
            else restore.remove("accent");
            assertTrue(restore.commit());
        }
    }

    @Test public void previewsShowTrueOledGraphiteAndLightSurfaces() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        int[] pixels = new int[3];
        for (int surface = 0; surface < 3; surface++) {
            P7ThemePreviewView view = new P7ThemePreviewView(
                context, 0xff1688ff, 0, surface);
            Bitmap bitmap = Bitmap.createBitmap(
                100, 100, Bitmap.Config.ARGB_8888);
            try {
                view.layout(0, 0, 100, 100);
                view.draw(new Canvas(bitmap));
                pixels[surface] = bitmap.getPixel(50, 18);
            } finally {
                bitmap.recycle();
            }
        }
        assertEquals(0xff000000, pixels[0]);
        assertEquals(0xff111217, pixels[1]);
        assertEquals(0xfff2f5fa, pixels[2]);
    }

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
