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
    public static final String[] LAYOUT_NAMES = {
        "Padrão", "Compacto", "Moderno", "Lista", "Duas colunas", "Destaques",
        "Fluxo", "Exploração", "Central", "Panorama", "Escalonado",
        "Escalonado inverso"
    };
    public static final String[] PRESET_NAMES =
        {"Dark OLED", "Cyber Neon", "Minimal", "Glass", "Retro"};

    /** Native Home structure: original 3x2, list 1x6, or two-column 2x3. */
    static int quickActionColumns(int layout) {
        if (layout == 3) return 1;
        if (layout == 4) return 2;
        return 3;
    }

    /**
     * Actual six-action Home geometry. Featured mode keeps the two primary
     * workflows full width, then displays the remaining four in pairs.
     */
    static int[] quickActionRowSizes(int layout) {
        if (layout == 5) return new int[]{1, 1, 2, 2};
        // Reading order: open APK first, analysis/build next, then three
        // secondary operations. Actions remain in their original indexes.
        if (layout == 6) return new int[]{1, 2, 3};
        // Five distinct row geometries, all preserving original action order,
        // callbacks, and all six accessibility targets.
        if (layout == 7) return new int[]{1, 3, 2};
        if (layout == 8) return new int[]{2, 1, 3};
        if (layout == 9) return new int[]{2, 3, 1};
        if (layout == 10) return new int[]{3, 1, 2};
        if (layout == 11) return new int[]{3, 2, 1};
        int columns = quickActionColumns(layout);
        int[] rows = new int[6 / columns];
        for (int i = 0; i < rows.length; i++) rows[i] = columns;
        return rows;
    }

    /**
     * Reflow the six Home actions only when the available viewport or
     * effective text scale cannot safely support the selected row width.
     * Never change the saved layout preference, labels, handler order or
     * count. Use 2 columns for narrow/large-text, 1 for very constrained.
     */
    static int[] quickActionRowsForViewport(int layout, int widthDp,
            float systemFontScale, float appFontScale) {
        int[] preferred = quickActionRowSizes(layout);
        if (widthDp <= 0) return preferred;
        float fontScale = Math.max(0.75f, systemFontScale)
            * Math.max(0.85f, appFontScale);
        int safeColumns = widthDp < 320 || fontScale >= 1.55f ? 1
            : widthDp < 360 || fontScale >= 1.20f ? 2 : 3;
        boolean needsReflow = false;
        for (int size : preferred)
            if (size > safeColumns) needsReflow = true;
        if (!needsReflow) return preferred;
        // Uniform rows avoid ragged 2+1 splits of formerly 3-column rows.
        int[] rows = new int[6 / safeColumns];
        for (int i = 0; i < rows.length; i++) rows[i] = safeColumns;
        return rows;
    }

    public static int currentLayout(Context c) {
        int value = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getInt("layout_variant", 0);
        return value >= 0 && value < LAYOUT_NAMES.length ? value : 0;
    }

    public static int currentPreset(Context c) {
        SharedPreferences prefs = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        int value = prefs.getInt("p7_active_preset", -1);
        if (value < 0 || value >= PRESET_NAMES.length) return -1;
        String[] themes = {"oled", "oled", "light", "graphite", "oled"};
        String[] accents = {"blue", "purple", "blue", "blue", "orange"};
        if (!themes[value].equals(prefs.getString("theme", "oled"))
                || !accents[value].equals(prefs.getString("accent", "blue")))
            return -1;
        return value;
    }

    static void persistLayout(Context context, int value) {
        if (value < 0 || value >= LAYOUT_NAMES.length)
            throw new IllegalArgumentException("Layout não reconhecido");
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        boolean ok = prefs.edit()
            .putInt("layout_variant", value)
            .putBoolean("compact", value == 1)
            .putInt("card_radius", value == 1 ? 12 : value == 2 ? 26 : 18)
            .remove("p7_active_preset")
            .commit();
        if (!ok) throw new IllegalStateException("Não foi possível salvar o layout");
    }

    public static void applyLayout(Activity a, int value) {
        persistLayout(a, value);
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
