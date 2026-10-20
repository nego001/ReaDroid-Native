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
