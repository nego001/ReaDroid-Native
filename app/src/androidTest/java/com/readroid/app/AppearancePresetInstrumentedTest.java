package com.readroid.app;

import android.content.Context;
import android.content.SharedPreferences;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.json.JSONObject;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import static org.junit.Assert.*;

/** Device-level regression tests for appearance-only JSON import/export. */
@RunWith(AndroidJUnit4.class)
public final class AppearancePresetInstrumentedTest {
    private Context context;
    private SharedPreferences prefs;

    @Before public void resetAppearance() {
        context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        prefs = context.getSharedPreferences("v3_personalizacao", Context.MODE_PRIVATE);
        assertTrue(prefs.edit().clear().commit());
    }

    @Test public void roundTripKeepsAllCurrentAppearanceFields() throws Exception {
        assertTrue(prefs.edit()
            .putString("theme", "light")
            .putString("accent", "custom")
            .putString("custom_accent", "#67EFA1")
            .putBoolean("studio_glow", false)
            .putInt("card_radius", 26)
            .putInt("font_percent", 130)
            .putBoolean("compact", true)
            .putBoolean("nav_labels", false)
            .putInt("favorite_tab", 4)
            .putString("display_name", "Meu Negresco")
            .putString("display_subtitle", "Estúdio de APK")
            .commit());
        String exported = AppearancePreset.exportSettings(context);
        JSONObject json = new JSONObject(exported);
        assertEquals(1, json.getInt("schema"));
        assertFalse(exported.contains("password"));
        assertFalse(exported.contains("keystore"));
        assertTrue(prefs.edit().clear().commit());
        AppearancePreset.importSettings(context, exported);
        assertEquals("light", prefs.getString("theme", ""));
        assertEquals("custom", prefs.getString("accent", ""));
        assertEquals("#67EFA1", prefs.getString("custom_accent", ""));
        assertFalse(prefs.getBoolean("studio_glow", true));
        assertEquals(26, prefs.getInt("card_radius", 0));
        assertEquals(130, prefs.getInt("font_percent", 0));
        assertTrue(prefs.getBoolean("compact", false));
        assertFalse(prefs.getBoolean("nav_labels", true));
        assertEquals(4, prefs.getInt("favorite_tab", 0));
        assertEquals("Meu Negresco", prefs.getString("display_name", ""));
        assertEquals("Estúdio de APK", prefs.getString("display_subtitle", ""));
    }

    @Test public void legacyV3PresetsImportWithNewSafeDefaults() throws Exception {
        JSONObject old = validPreset();
        old.remove("custom_accent");
        old.remove("studio_glow");
        old.remove("card_radius");
        AppearancePreset.importSettings(context, old.toString());
        assertEquals("#1688FF", prefs.getString("custom_accent", null));
        assertTrue(prefs.getBoolean("studio_glow", false));
        assertEquals(18, prefs.getInt("card_radius", -1));
    }

    @Test public void wrongTypesAndRangesDoNotPartiallyImport() throws Exception {
        assertTrue(prefs.edit().putString("theme", "graphite").commit());
        for (String key : new String[]{"compact", "nav_labels", "font_percent", "favorite_tab",
                "studio_glow", "card_radius", "custom_accent"}) {
            JSONObject invalid = validPreset();
            switch (key) {
                case "font_percent":
                    invalid.put(key, "130"); break;
                case "favorite_tab":
                    invalid.put(key, 2.5); break;
                case "custom_accent":
                    invalid.put(key, "#FF0000ZZ"); break;
                case "card_radius":
                    invalid.put(key, 300); break;
                default:
                    invalid.put(key, "true"); break;
            }
            try {
                AppearancePreset.importSettings(context, invalid.toString());
                fail("Invalid JSON field was accepted: " + key);
            } catch (IllegalArgumentException expected) {
                assertEquals("graphite", prefs.getString("theme", ""));
            }
        }
    }

    @Test public void protectsOtherPreferencesAndRejectsUnsupportedSchemas() throws Exception {
        SharedPreferences security = context.getSharedPreferences("security_state", Context.MODE_PRIVATE);
        assertTrue(security.edit().putString("private_test_setting", "preserve").commit());
        AppearancePreset.importSettings(context, validPreset().toString());
        assertEquals("preserve", security.getString("private_test_setting", null));
        JSONObject unknownVersion = validPreset();
        unknownVersion.put("schema", 2);
        try {
            AppearancePreset.importSettings(context, unknownVersion.toString());
            fail("Unsupported preset schema was accepted");
        } catch (IllegalArgumentException expected) {
            assertEquals("oled", prefs.getString("theme", ""));
        } finally {
            security.edit().remove("private_test_setting").commit();
        }
    }

    @Test public void rejectsOversizedJsonAndIdentityControlCharacters() throws Exception {
        JSONObject invalid = validPreset();
        invalid.put("display_name", "Negresco\nDroid");
        try {
            AppearancePreset.importSettings(context, invalid.toString());
            fail("Control character was accepted");
        } catch (IllegalArgumentException expected) {
            assertFalse(prefs.contains("theme"));
        }
        try {
            AppearancePreset.importSettings(context, " ".repeat(8193));
            fail("Oversized preset was accepted");
        } catch (IllegalArgumentException expected) {
            assertFalse(prefs.contains("theme"));
        }
    }

    private static JSONObject validPreset() throws Exception {
        return new JSONObject()
            .put("schema", 1)
            .put("theme", "oled")
            .put("accent", "blue")
            .put("custom_accent", "#1688FF")
            .put("studio_glow", true)
            .put("card_radius", 18)
            .put("font_percent", 100)
            .put("compact", false)
            .put("nav_labels", true)
            .put("favorite_tab", 1)
            .put("display_name", "NEGRESCODROID")
            .put("display_subtitle", "APK ENGINEERING STUDIO");
    }
}
