package com.readroid.app;

import android.content.Context;
import android.content.SharedPreferences;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** P7 layout and presets: actual preference writes, no APK or security mutation. */
@RunWith(AndroidJUnit4.class)
public final class P7VisualCatalogInstrumentedTest {
    @Test public void listLayoutIsPersistedAndChangesRealHomeAndSettingsViews() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences p = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        boolean hadLayout = p.contains("layout_variant");
        int previous = p.getInt("layout_variant", 0);
        boolean hadCompact = p.contains("compact");
        boolean wasCompact = p.getBoolean("compact", false);
        boolean hadRadius = p.contains("card_radius");
        int wasRadius = p.getInt("card_radius", 18);
        boolean hadPreset = p.contains("p7_active_preset");
        int wasPreset = p.getInt("p7_active_preset", -1);
        try {
            assertEquals(4, P7VisualCatalog.LAYOUT_NAMES.length);
            P7VisualCatalog.persistLayout(context, 3);
            assertEquals(3, P7VisualCatalog.currentLayout(context));
            assertFalse(p.getBoolean("compact", true));
            NegrescoTheme.apply(context);
            assertEquals(3, NegrescoTheme.LAYOUT_VARIANT);
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    LinearLayout grid = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-quick-actions-grid");
                    assertNotNull(grid);
                    assertEquals(6, grid.getChildCount());
                    for (int i = 0; i < grid.getChildCount(); i++) {
                        LinearLayout row = (LinearLayout) grid.getChildAt(i);
                        assertEquals(1, row.getChildCount());
                        assertTrue(row.getChildAt(0).isClickable());
                        assertEquals(-1, row.getChildAt(0).getLayoutParams().width);
                    }
                    LinearLayout options = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-personalization-options");
                    assertNotNull(options);
                    assertEquals(13, options.getChildCount());
                    for (int i = 0; i < options.getChildCount(); i++)
                        assertEquals(1,
                            ((LinearLayout) options.getChildAt(i)).getChildCount());
                });
                P7VisualCatalog.persistLayout(context, 0);
                scenario.recreate();
                scenario.onActivity(activity -> {
                    LinearLayout grid = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-quick-actions-grid");
                    assertEquals(2, grid.getChildCount());
                    for (int i = 0; i < grid.getChildCount(); i++)
                        assertEquals(3,
                            ((LinearLayout) grid.getChildAt(i)).getChildCount());
                });
            }
            try {
                P7VisualCatalog.persistLayout(context, 4);
                fail("Invalid layout was applied");
            } catch (IllegalArgumentException expected) {
                assertEquals(0, P7VisualCatalog.currentLayout(context));
            }
        } finally {
            SharedPreferences.Editor editor = p.edit();
            if (hadLayout) editor.putInt("layout_variant", previous);
            else editor.remove("layout_variant");
            if (hadCompact) editor.putBoolean("compact", wasCompact);
            else editor.remove("compact");
            if (hadRadius) editor.putInt("card_radius", wasRadius);
            else editor.remove("card_radius");
            if (hadPreset) editor.putInt("p7_active_preset", wasPreset);
            else editor.remove("p7_active_preset");
            assertTrue(editor.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void compactAndModernLayoutsPersistSafely() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                SharedPreferences p = activity.getSharedPreferences(
                    "v3_personalizacao", Context.MODE_PRIVATE);
                try {
                    P7VisualCatalog.applyLayout(activity, 1);
                    assertEquals(1, p.getInt("layout_variant", -1));
                    assertTrue(p.getBoolean("compact", false));
                    assertEquals(12, p.getInt("card_radius", -1));
                    P7VisualCatalog.applyLayout(activity, 2);
                    assertEquals(2, p.getInt("layout_variant", -1));
                    assertFalse(p.getBoolean("compact", true));
                    assertEquals(26, p.getInt("card_radius", -1));
                    try {
                        P7VisualCatalog.applyLayout(activity, -1);
                        fail("Unexpected layout accepted");
                    } catch (IllegalArgumentException expected) {
                        assertEquals(2, p.getInt("layout_variant", -1));
                    }
                } finally {
                    p.edit().remove("layout_variant").putBoolean("compact", false)
                        .putInt("card_radius", 18).commit();
                }
            });
        }
    }

    @Test public void presetWritesOnlyAppearanceAndRejectsOutOfRangeChoices() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                SharedPreferences p = activity.getSharedPreferences(
                    "v3_personalizacao", Context.MODE_PRIVATE);
                SharedPreferences security = activity.getSharedPreferences(
                    "security_state", Context.MODE_PRIVATE);
                try {
                    assertTrue(security.edit().putString("p7_test_secret", "retain").commit());
                    P7VisualCatalog.applyPreset(activity, 1);
                    assertEquals("purple", p.getString("accent", ""));
                    assertTrue(p.getBoolean("studio_glow", false));
                    assertEquals(1, p.getInt("p7_active_preset", -1));
                    assertEquals("retain", security.getString("p7_test_secret", ""));
                    try {
                        P7VisualCatalog.applyPreset(activity, 5);
                        fail("Invalid preset accepted");
                    } catch (IllegalArgumentException expected) {
                        assertEquals(1, p.getInt("p7_active_preset", -1));
                    }
                } finally {
                    security.edit().remove("p7_test_secret").commit();
                    p.edit().remove("p7_active_preset").putString("accent", "blue")
                        .putBoolean("studio_glow", true).commit();
                }
            });
        }
    }
}
