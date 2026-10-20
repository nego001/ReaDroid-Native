package com.readroid.app;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;

/** Real, appearance-only P7 layout variants and preset combinations.
 * Never edits the active APK, signing keys or EditPlan.
 */
public final class P7VisualCatalog {
    private P7VisualCatalog() {}
    private static final String PREFS = "v3_personalizacao";
    public static final String[] LAYOUT_NAMES = {"Padrão", "Compacto", "Moderno"};
    public static final String[] PRESET_NAMES =
        {"Dark OLED", "Cyber Neon", "Minimal", "Glass", "Retro"};

    public static int currentLayout(Context c) {
        int value = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getInt("layout_variant", 0);
        return value >= 0 && value < LAYOUT_NAMES.length ? value : 0;
    }

    public static int currentPreset(Context c) {
        int value = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getInt("p7_active_preset", -1);
        return value >= 0 && value < PRESET_NAMES.length ? value : -1;
    }

    public static void applyLayout(Activity a, int value) {
        if (value < 0 || value >= LAYOUT_NAMES.length)
            throw new IllegalArgumentException("Layout não reconhecido");
        SharedPreferences prefs = a.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        boolean ok = prefs.edit()
            .putInt("layout_variant", value)
            .putBoolean("compact", value == 1)
            .putInt("card_radius", value == 1 ? 12 : value == 2 ? 26 : 18)
            .remove("p7_active_preset")
            .commit();
        if (!ok) throw new IllegalStateException("Não foi possível salvar o layout");
        a.recreate();
    }

    /** All values are from the existing, validated V3 palette. */
    public static void applyPreset(Activity a, int selected) {
        if (selected < 0 || selected >= PRESET_NAMES.length)
            throw new IllegalArgumentException("Preset não reconhecido");
        final String[] themes = {"oled", "oled", "light", "graphite", "oled"};
        final String[] accents = {"blue", "purple", "blue", "blue", "orange"};
        final boolean[] glows = {false, true, false, true, false};
        final int[] radii = {18, 26, 12, 26, 12};
        final int[] layouts = {0, 2, 1, 2, 1};
        boolean ok = a.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString("theme", themes[selected])
            .putString("accent", accents[selected])
            .putBoolean("studio_glow", glows[selected])
            .putInt("card_radius", radii[selected])
            .putInt("layout_variant", layouts[selected])
            .putBoolean("compact", layouts[selected] == 1)
            .putInt("p7_active_preset", selected)
            .commit();
        if (!ok) throw new IllegalStateException("Não foi possível salvar o preset");
        a.recreate();
    }
}
