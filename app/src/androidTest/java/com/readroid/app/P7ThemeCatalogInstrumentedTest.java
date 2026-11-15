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
    @Test public void catalogHasTwentyFourUniqueRealPreferenceCombinations() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences p = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        String originalTheme = p.getString("theme", "oled");
        String originalAccent = p.getString("accent", "blue");
        boolean hasTheme = p.contains("theme");
        boolean hasAccent = p.contains("accent");
        boolean originalGlow = p.getBoolean("studio_glow", true);
        boolean hasGlow = p.contains("studio_glow");
        int originalPreset = p.getInt("p7_active_preset", -1);
        boolean hasPreset = p.contains("p7_active_preset");
        Set<String> identities = new HashSet<>();
        try {
            assertEquals(24, P7ThemeCatalog.count());
            assertEquals("Negreco Blue", P7ThemeCatalog.nameAt(0));
            assertEquals("Sunset", P7ThemeCatalog.nameAt(3));
            for (int i = 0; i < P7ThemeCatalog.count(); i++) {
                P7ThemeCatalog.persist(context, i);
                assertEquals(i, P7ThemeCatalog.currentTheme(context));
                String signature = p.getString("theme", "") + "/" +
                    p.getString("accent", "") + "/" +
                    p.getBoolean("studio_glow", true);
                assertEquals(P7ThemeCatalog.glowAt(i),
                    p.getBoolean("studio_glow", !P7ThemeCatalog.glowAt(i)));
                assertTrue("Duplicate theme state: " + signature,
                    identities.add(signature));
                assertEquals(-1, p.getInt("p7_active_preset", -1));
            }
            assertEquals(24, identities.size());
        } finally {
            SharedPreferences.Editor restore = p.edit();
            if (hasTheme) restore.putString("theme", originalTheme);
            else restore.remove("theme");
            if (hasAccent) restore.putString("accent", originalAccent);
            else restore.remove("accent");
            if (hasGlow) restore.putBoolean("studio_glow", originalGlow);
            else restore.remove("studio_glow");
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
        boolean hadGlow = p.contains("studio_glow");
        boolean priorGlow = p.getBoolean("studio_glow", true);
        try {
            assertTrue(p.edit().putString("theme", "oled")
                .putString("accent", "custom").putBoolean("studio_glow", true)
                .commit());
            assertEquals(-1, P7ThemeCatalog.currentTheme(context));
            assertTrue(p.edit().putString("theme", "light")
                .putString("accent", "orange").commit());
            assertEquals(11, P7ThemeCatalog.currentTheme(context));
            try {
                P7ThemeCatalog.persist(context, 24);
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
            if (hadGlow) restore.putBoolean("studio_glow", priorGlow);
            else restore.remove("studio_glow");
            assertTrue(restore.commit());
        }
    }

    @Test public void cleanVariantTogglesRealGlowWithoutChangingLegacyPalette() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences p = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        String previousTheme = p.getString("theme", "oled");
        String previousAccent = p.getString("accent", "blue");
        boolean oldGlow = p.getBoolean("studio_glow", true);
        boolean hadTheme = p.contains("theme"), hadAccent = p.contains("accent");
        boolean hadGlow = p.contains("studio_glow");
        int oldPreset = p.getInt("p7_active_preset", -1);
        boolean hadPreset = p.contains("p7_active_preset");
        try {
            P7ThemeCatalog.persist(context, 0);
            assertEquals(0, P7ThemeCatalog.currentTheme(context));
            assertEquals("oled", p.getString("theme", ""));
            assertEquals("blue", p.getString("accent", ""));
            assertTrue(NegrescoTheme.STUDIO_GLOW || p.getBoolean("studio_glow", false));
            P7ThemeCatalog.persist(context, 12);
            assertEquals(12, P7ThemeCatalog.currentTheme(context));
            assertEquals("oled", p.getString("theme", ""));
            assertEquals("blue", p.getString("accent", ""));
            assertFalse(p.getBoolean("studio_glow", true));
            NegrescoTheme.apply(context);
            assertFalse("The engine must disable native studio glow",
                NegrescoTheme.STUDIO_GLOW);
            P7ThemeCatalog.persist(context, 0);
            NegrescoTheme.apply(context);
            assertTrue("The engine must enable native studio glow",
                NegrescoTheme.STUDIO_GLOW);
        } finally {
            SharedPreferences.Editor editor = p.edit();
            if (hadTheme) editor.putString("theme", previousTheme);
            else editor.remove("theme");
            if (hadAccent) editor.putString("accent", previousAccent);
            else editor.remove("accent");
            if (hadGlow) editor.putBoolean("studio_glow", oldGlow);
            else editor.remove("studio_glow");
            if (hadPreset) editor.putInt("p7_active_preset", oldPreset);
            else editor.remove("p7_active_preset");
            assertTrue(editor.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void miniatureThemeChromeUsesActualSurfacePalette() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        final int[] expectedToolbar = {
            0xff93a6be, 0xffa1a6b7, 0xff53657c
        };
        Bitmap[] images = new Bitmap[3];
        try {
            for (int surface = 0; surface < 3; surface++) {
                images[surface] = Bitmap.createBitmap(
                    100, 100, Bitmap.Config.ARGB_8888);
                P7ThemePreviewView view = new P7ThemePreviewView(
                    context, 0xff1688ff, 0, surface, false);
                view.layout(0, 0, 100, 100);
                view.draw(new Canvas(images[surface]));
                // The same preview really uses the current OLED/graphite/light
                // palette for its mini toolbar. Never show a fake project count.
                assertEquals("Mini action chrome must match current palette",
                    expectedToolbar[surface], images[surface].getPixel(76, 11));
                assertEquals("Accent highlights remain real for each theme",
                    0xff1688ff, images[surface].getPixel(29, 12));
            }
            assertFalse("OLED and graphite miniatures cannot be identical",
                images[0].sameAs(images[1]));
            assertFalse("OLED and light miniatures cannot be identical",
                images[0].sameAs(images[2]));
        } finally {
            for (Bitmap bitmap : images)
                if (bitmap != null) bitmap.recycle();
        }
    }

    @Test public void neonAndCleanPreviewsHaveDifferentPixels() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        Bitmap glow = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
        Bitmap clean = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
        try {
            P7ThemePreviewView highlighted = new P7ThemePreviewView(
                context, 0xff1688ff, 0, 0, true);
            P7ThemePreviewView minimal = new P7ThemePreviewView(
                context, 0xff1688ff, 0, 0, false);
            highlighted.layout(0, 0, 100, 100);
            minimal.layout(0, 0, 100, 100);
            highlighted.draw(new Canvas(glow));
            minimal.draw(new Canvas(clean));
            assertFalse("Glow and clean previews must not be identical",
                glow.sameAs(clean));
            assertEquals(glow.getPixel(50, 18), clean.getPixel(50, 18));
        } finally {
            glow.recycle();
            clean.recycle();
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
                boolean beforeGlow = prefs.getBoolean("studio_glow", true);
                boolean hadGlow = prefs.contains("studio_glow");
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
                    SharedPreferences.Editor revert = prefs.edit()
                        .putString("theme",originalTheme)
                        .putString("accent",originalAccent)
                        .remove("test_workspace_sentinel");
                    if (hadGlow) revert.putBoolean("studio_glow", beforeGlow);
                    else revert.remove("studio_glow");
                    assertTrue(revert.commit());
                }
            });
        }
    }
}
