package com.readroid.app;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;

/**
 * Twelve genuine combinations of the V3 engine's three surface modes and
 * four supported accent colors, backed by real persisted preferences.
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
        "Arctic Blue", "Arctic Violet", "Arctic Mint", "Arctic Amber"
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

    public static int count() { return NAMES.length; }
    private static void check(int index) {
        if (index < 0 || index >= count())
            throw new IllegalArgumentException("Tema não reconhecido");
    }
    public static String[] names() { return NAMES.clone(); }
    public static String nameAt(int index) { check(index); return NAMES[index]; }
    public static String subtitleAt(int index) { check(index); return SUBTITLES[index]; }
    public static int previewAccentAt(int index) {
        check(index); return PREVIEW_ACCENTS[index];
    }
    /** 0 = OLED, 1 = graphite, 2 = light. */
    public static int surfaceAt(int index) {
        check(index);
        return "graphite".equals(SURFACES[index]) ? 1 :
            "light".equals(SURFACES[index]) ? 2 : 0;
    }
    /** A custom hex accent must not pretend to be a catalog selection. */
    public static int currentTheme(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String surface = prefs.getString("theme", "oled");
        String accent = prefs.getString("accent", "blue");
        for (int i = 0; i < count(); i++)
            if (SURFACES[i].equals(surface) && ACCENTS[i].equals(accent))
                return i;
        return -1;
    }

    /** Package-private persistence for instrumented round-trip tests. */
    static void persist(Context context, int selected) {
        check(selected);
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        boolean saved = prefs.edit()
            .putString("theme", SURFACES[selected])
            .putString("accent", ACCENTS[selected])
            .remove("p7_active_preset")
            .commit();
        if (!saved) throw new IllegalStateException("Não foi possível salvar o tema");
    }

    public static void apply(Activity activity, int selected) {
        persist(activity, selected);
        activity.recreate();
    }
}
