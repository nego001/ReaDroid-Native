package com.readroid.app;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;

/**
 * Twenty-four actual combinations: three native surface modes, four supported
 * accents and the V3 engine's real studio-glow on/off rendering choice.
 * Existing indices 0-3 are never renumbered for compatibility.
 */
public final class P7ThemeCatalog {
    private P7ThemeCatalog() {}
    private static final String PREFS = "v3_personalizacao";
    private static final String[] SURFACES = {
        "oled", "graphite", "oled", "oled",
        "oled", "graphite", "graphite", "graphite",
        "light", "light", "light", "light"
    };
    private static final String[] ACCENTS = {
        "blue", "blue", "green", "orange",
        "purple", "purple", "green", "orange",
        "blue", "purple", "green", "orange"
    };
    private static final String[] NAMES = {
        "Negreco Blue", "Carbon Dark", "Matrix Green", "Sunset",
        "Neon Violet", "Carbon Violet", "Carbon Jade", "Carbon Amber",
        "Arctic Blue", "Arctic Violet", "Arctic Mint", "Arctic Amber",
        "Negreco Clean", "Carbon Clean", "Matrix Clean", "Sunset Clean",
        "Violet Clean", "Carbon Violet Clean", "Carbon Jade Clean",
        "Carbon Amber Clean", "Arctic Blue Clean", "Arctic Violet Clean",
        "Arctic Mint Clean", "Arctic Amber Clean"
    };
    private static final String[] SUBTITLES = {
        "Profissional", "Minimalista", "Hacker Style", "Vibrante",
        "OLED violeta", "Grafite violeta", "Grafite verde", "Grafite âmbar",
        "Claro azul", "Claro violeta", "Claro verde", "Claro âmbar"
    };
    private static final int[] PREVIEW_ACCENTS = {
        0xff1688ff, 0xff1688ff, 0xff27c99a, 0xffffa24a,
        0xff9b6dff, 0xff9b6dff, 0xff27c99a, 0xffffa24a,
        0xff1688ff, 0xff9b6dff, 0xff27c99a, 0xffffa24a
    };

    // The legacy twelve retain their indices and use the V3 glow; the twelve
    // clean versions expose a rendering mode that is already implemented.
    public static int count() { return NAMES.length; }
    private static int baseIndex(int index) {
        check(index);
        return index % SURFACES.length;
    }
    public static boolean glowAt(int index) {
        check(index);
        return index < SURFACES.length;
    }
    private static void check(int index) {
        if (index < 0 || index >= count())
            throw new IllegalArgumentException("Tema não reconhecido");
    }
    public static String[] names() { return NAMES.clone(); }
    public static String nameAt(int index) { check(index); return NAMES[index]; }
    public static String subtitleAt(int index) {
        return (glowAt(index) ? "Neon · " : "Sem brilho · ") +
            SUBTITLES[baseIndex(index)];
    }
    public static int previewAccentAt(int index) {
        return PREVIEW_ACCENTS[baseIndex(index)];
    }
    /** 0 = OLED, 1 = graphite, 2 = light. */
    public static int surfaceAt(int index) {
        check(index);
        int base = baseIndex(index);
        return "graphite".equals(SURFACES[base]) ? 1 :
            "light".equals(SURFACES[base]) ? 2 : 0;
    }
    /** A custom hex accent must not pretend to be a catalog selection. */
    public static int currentTheme(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String surface = prefs.getString("theme", "oled");
        String accent = prefs.getString("accent", "blue");
        boolean glow = prefs.getBoolean("studio_glow", true);
        for (int i = 0; i < count(); i++) {
            int base = baseIndex(i);
            if (SURFACES[base].equals(surface) && ACCENTS[base].equals(accent)
                    && glowAt(i) == glow)
                return i;
        }
        return -1;
    }

    /** Package-private persistence for instrumented round-trip tests. */
    static void persist(Context context, int selected) {
        check(selected);
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        int base = baseIndex(selected);
        boolean saved = prefs.edit()
            .putString("theme", SURFACES[base])
            .putString("accent", ACCENTS[base])
            .putBoolean("studio_glow", glowAt(selected))
            .remove("p7_active_preset")
            .commit();
        if (!saved) throw new IllegalStateException("Não foi possível salvar o tema");
    }

    public static void apply(Activity activity, int selected) {
        persist(activity, selected);
        activity.recreate();
    }
}
