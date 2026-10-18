package com.readroid.app;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONObject;

/** Versioned, appearance-only preferences. No secrets or project data. */
public final class AppearancePreset {
    private AppearancePreset() {}

    public static String exportSettings(Context context) throws Exception {
        SharedPreferences p = context.getSharedPreferences("v3_personalizacao", Context.MODE_PRIVATE);
        JSONObject o = new JSONObject();
        o.put("schema", 1);
        o.put("theme", p.getString("theme", "oled"));
        o.put("accent", p.getString("accent", "blue"));
        o.put("font_percent", p.getInt("font_percent", 100));
        o.put("compact", p.getBoolean("compact", false));
        o.put("nav_labels", p.getBoolean("nav_labels", true));
        o.put("favorite_tab", p.getInt("favorite_tab", 1));
        o.put("display_name", p.getString("display_name", "NEGRESCODROID"));
        o.put("display_subtitle", p.getString("display_subtitle", "APK ENGINEERING STUDIO"));
        return o.toString(2);
    }

    public static void importSettings(Context context, String data) throws Exception {
        if (data == null || data.length() > 8192) throw new IllegalArgumentException("Arquivo de preferências muito grande");
        JSONObject o = new JSONObject(data);
        if (o.getInt("schema") != 1) throw new IllegalArgumentException("Formato de preferências incompatível");
        String theme = o.getString("theme");
        String accent = o.getString("accent");
        int font = o.getInt("font_percent");
        int favorite = o.getInt("favorite_tab");
        boolean compact = o.getBoolean("compact");
        boolean labels = o.getBoolean("nav_labels");
        String name = o.getString("display_name");
        String subtitle = o.getString("display_subtitle");
        if (!allowed(theme, "oled", "graphite", "light")
            || !allowed(accent, "blue", "purple", "green", "orange")
            || font < 85 || font > 135 || favorite < 1 || favorite > 4
            || name.trim().isEmpty() || name.length() > 30 || subtitle.length() > 48)
            throw new IllegalArgumentException("Preferências inválidas");
        context.getSharedPreferences("v3_personalizacao", Context.MODE_PRIVATE).edit()
            .putString("theme", theme).putString("accent", accent)
            .putInt("font_percent", font).putInt("favorite_tab", favorite)
            .putBoolean("compact", compact).putBoolean("nav_labels", labels)
            .putString("display_name", name).putString("display_subtitle", subtitle).apply();
    }

    private static boolean allowed(String value, String... choices) {
        for (String choice : choices) if (choice.equals(value)) return true;
        return false;
    }
}
