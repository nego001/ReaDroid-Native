package com.readroid.app;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;

/** Verified subset of the visual catalog backed by existing V3 preferences. */
public final class P7ThemeCatalog {
    private P7ThemeCatalog() {}
    private static final String[] THEMES = {"oled", "graphite", "oled", "oled"};
    private static final String[] ACCENTS = {"blue", "blue", "green", "orange"};

    public static void apply(Activity activity, int selected) {
        if (selected < 0 || selected >= THEMES.length)
            throw new IllegalArgumentException("Tema não reconhecido");
        SharedPreferences preferences = activity.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        boolean saved = preferences.edit()
            .putString("theme", THEMES[selected])
            .putString("accent", ACCENTS[selected])
            .commit();
        if (!saved) throw new IllegalStateException("Não foi possível salvar o tema");
        activity.recreate();
    }
}
