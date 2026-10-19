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
        o.put("custom_accent", p.getString("custom_accent", "#1688FF"));
        o.put("studio_glow", p.getBoolean("studio_glow", true));
        o.put("card_radius", p.getInt("card_radius", 18));
        o.put("font_percent", p.getInt("font_percent", 100));
        o.put("compact", p.getBoolean("compact", false));
        o.put("nav_labels", p.getBoolean("nav_labels", true));
        o.put("favorite_tab", p.getInt("favorite_tab", 1));
        o.put("display_name", p.getString("display_name", "NEGRESCODROID"));
        o.put("display_subtitle", p.getString("display_subtitle", "APK ENGINEERING STUDIO"));
        return o.toString(2);
    }

    /** Shared validator for preview and import; never mutates preferences. */
    private static JSONObject validatedData(String data) throws Exception {
        if (data == null || data.length() > 8192) throw new IllegalArgumentException("Arquivo de preferências muito grande");
        JSONObject o = new JSONObject(data);
        // JSON getters coerce "1" or 18.5 into integers on some Android versions.
        // Preserve strict schema/types and reject truncated fractional values.
        if (!isInteger(o.opt("schema")) || o.getInt("schema") != 1)
            throw new IllegalArgumentException("Formato de preferências incompatível");
        // Invalid imports must not touch any existing preference.
        for (String key : new String[]{"theme", "accent", "display_name", "display_subtitle"}) {
            if (!(o.opt(key) instanceof String))
                throw new IllegalArgumentException("Campo textual inválido: " + key);
        }
        for (String key : new String[]{"font_percent", "favorite_tab"}) {
            Object number = o.opt(key);
            if (!isInteger(number))
                throw new IllegalArgumentException("Campo numérico inválido: " + key);
        }
        for (String key : new String[]{"compact", "nav_labels"}) {
            if (!(o.opt(key) instanceof Boolean))
                throw new IllegalArgumentException("Campo lógico inválido: " + key);
        }
        if (o.has("custom_accent") && !(o.opt("custom_accent") instanceof String))
            throw new IllegalArgumentException("Cor HEX inválida");
        String theme = o.getString("theme");
        String accent = o.getString("accent");
        String customAccent = o.optString("custom_accent", "#1688FF");
        boolean glow = o.optBoolean("studio_glow", true);
        int radius = o.optInt("card_radius", 18);
        if (o.has("studio_glow") && !(o.opt("studio_glow") instanceof Boolean))
            throw new IllegalArgumentException("Tipo de efeito neon inválido");
        if (o.has("card_radius") && !isInteger(o.opt("card_radius")))
            throw new IllegalArgumentException("Tipo de raio inválido");
        int font = o.getInt("font_percent");
        int favorite = o.getInt("favorite_tab");
        boolean compact = o.getBoolean("compact");
        boolean labels = o.getBoolean("nav_labels");
        String name = o.getString("display_name");
        String subtitle = o.getString("display_subtitle");
        if (!allowed(theme, "oled", "graphite", "light")
            || !allowed(accent, "blue", "purple", "green", "orange", "custom")
            || !customAccent.matches("#[0-9a-fA-F]{6}")
            || !(radius == 12 || radius == 18 || radius == 26)
            || font < 85 || font > 135 || favorite < 1 || favorite > 4
            || name.trim().isEmpty() || name.length() > 30 || subtitle.length() > 48
            || containsControlCharacter(name) || containsControlCharacter(subtitle))
            throw new IllegalArgumentException("Preferências inválidas");
        return o;
    }

    /** Safe summary of a preset, shown before a user approves the import. */
    public static String describeSettings(String data) throws Exception {
        JSONObject o = validatedData(data);
        String theme = o.getString("theme");
        String accent = o.getString("accent");
        String themeLabel = "light".equals(theme) ? "Claro"
            : "graphite".equals(theme) ? "Grafite" : "OLED preto";
        String accentLabel = "purple".equals(accent) ? "Roxo"
            : "green".equals(accent) ? "Verde"
            : "orange".equals(accent) ? "Laranja"
            : "custom".equals(accent) ? o.getString("custom_accent") : "Azul";
        return "Tema: " + themeLabel
            + "\\nCor: " + accentLabel
            + "\\nTexto: " + o.getInt("font_percent") + "%"
            + "\\nEspaçamento: " + (o.getBoolean("compact") ? "Compacto" : "Confortável")
            + "\\nNeon: " + (o.optBoolean("studio_glow", true) ? "Ativo" : "Desativado")
            + "\\nCantos: " + o.optInt("card_radius", 18) + " dp"
            + "\\nAtalho favorito: " + o.getInt("favorite_tab")
            + "\\nNome: " + o.getString("display_name");
    }

    public static void importSettings(Context context, String data) throws Exception {
        JSONObject o = validatedData(data);
        String theme = o.getString("theme");
        String accent = o.getString("accent");
        String customAccent = o.optString("custom_accent", "#1688FF");
        boolean glow = o.optBoolean("studio_glow", true);
        int radius = o.optInt("card_radius", 18);
        int font = o.getInt("font_percent");
        int favorite = o.getInt("favorite_tab");
        boolean compact = o.getBoolean("compact");
        boolean labels = o.getBoolean("nav_labels");
        String name = o.getString("display_name");
        String subtitle = o.getString("display_subtitle");
        context.getSharedPreferences("v3_personalizacao", Context.MODE_PRIVATE).edit()
            .putString("theme", theme).putString("accent", accent)
            .putString("custom_accent", customAccent)
            .putBoolean("studio_glow", glow).putInt("card_radius", radius)
            .putInt("font_percent", font).putInt("favorite_tab", favorite)
            .putBoolean("compact", compact).putBoolean("nav_labels", labels)
            .putString("display_name", name).putString("display_subtitle", subtitle).apply();
    }

    private static boolean isInteger(Object value) {
        if (!(value instanceof Number)) return false;
        double number = ((Number) value).doubleValue();
        return !Double.isInfinite(number) && !Double.isNaN(number)
            && Math.rint(number) == number
            && number >= Integer.MIN_VALUE && number <= Integer.MAX_VALUE;
    }

    private static boolean containsControlCharacter(String value) {
        for (int index = 0; index < value.length(); index++) {
            if (Character.isISOControl(value.charAt(index))) return true;
        }
        return false;
    }

    private static boolean allowed(String value, String... choices) {
        for (String choice : choices) if (choice.equals(value)) return true;
        return false;
    }
}
