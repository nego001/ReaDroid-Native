package com.readroid.app;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/** NegrescoDroid visual tokens and reusable native widgets. */
public final class NegrescoTheme {
    public static int BACKGROUND = 0xff05080e;
    public static int SURFACE = 0xff101925;
    public static int BORDER = 0xff25364b;
    public static int ACCENT = 0xff1688ff;
    public static int TEXT = 0xfff1f6ff;
    public static int MUTED = 0xff93a6be;
    public static int ON_ACCENT = 0xffffffff;
    public static float FONT_SCALE = 1f;
    public static boolean COMPACT = false;
    public static boolean STUDIO_GLOW = true;
    public static int CARD_RADIUS = 18;
    private NegrescoTheme() {}

    public static void apply(Context context) {
        android.content.SharedPreferences prefs = context.getSharedPreferences("v3_personalizacao", Context.MODE_PRIVATE);
        String theme = prefs.getString("theme", "oled");
        if ("light".equals(theme)) {
            BACKGROUND = 0xfff2f5fa; SURFACE = 0xffffffff; BORDER = 0xffd9e2ee;
            TEXT = 0xff152238; MUTED = 0xff53657c;
        } else if ("graphite".equals(theme)) {
            BACKGROUND = 0xff111217; SURFACE = 0xff1c1e26; BORDER = 0xff343843;
            TEXT = 0xfff4f5fa; MUTED = 0xffa1a6b7;
        } else {
            BACKGROUND = 0xff000000; SURFACE = 0xff101925; BORDER = 0xff25364b;
            TEXT = 0xfff1f6ff; MUTED = 0xff93a6be;
        }
        String accent = prefs.getString("accent", "blue");
        FONT_SCALE = Math.max(0.85f, Math.min(1.35f, prefs.getInt("font_percent", 100) / 100f));
        COMPACT = prefs.getBoolean("compact", false);
        ACCENT = "purple".equals(accent) ? 0xff9b6dff
            : "green".equals(accent) ? 0xff27c99a
            : "orange".equals(accent) ? 0xffffa24a : 0xff1688ff;
        if ("custom".equals(accent)) {
            String custom = prefs.getString("custom_accent", "#1688FF");
            if (custom != null && custom.matches("#[0-9a-fA-F]{6}"))
                ACCENT = Color.parseColor(custom);
        }
        // WCAG relative luminance. Prefer the foreground with greater contrast.
        ON_ACCENT = relativeLuminance(ACCENT) > 0.179 ? Color.BLACK : Color.WHITE;
        STUDIO_GLOW = prefs.getBoolean("studio_glow", true);
        int radius = prefs.getInt("card_radius", 18);
        CARD_RADIUS = radius == 12 || radius == 18 || radius == 26 ? radius : 18;
    }

    public static int dp(Context context, int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    private static double linearChannel(int value) {
        double channel = value / 255.0;
        return channel <= 0.04045 ? channel / 12.92
            : Math.pow((channel + 0.055) / 1.055, 2.4);
    }

    private static double relativeLuminance(int color) {
        return 0.2126 * linearChannel(Color.red(color))
            + 0.7152 * linearChannel(Color.green(color))
            + 0.0722 * linearChannel(Color.blue(color));
    }

    /** Neutral, accessible touch surface for the selected bottom tab. */
    public static android.graphics.drawable.Drawable navigationSurface(Context context, boolean selected) {
        GradientDrawable shape = new GradientDrawable();
        shape.setCornerRadius(dp(context, 14));
        if (selected) {
            shape.setColor(mix(SURFACE, ACCENT, STUDIO_GLOW ? 0.24f : 0.12f));
            shape.setStroke(dp(context, 1), mix(ACCENT, BORDER, 0.52f));
        } else {
            shape.setColor(Color.TRANSPARENT);
        }
        return new android.graphics.drawable.RippleDrawable(
            android.content.res.ColorStateList.valueOf(mix(ACCENT, SURFACE, 0.60f)),
            shape, null);
    }

    private static int mix(int first, int second, float weight) {
        float inv = 1f - weight;
        return Color.rgb(
            Math.round(Color.red(first) * inv + Color.red(second) * weight),
            Math.round(Color.green(first) * inv + Color.green(second) * weight),
            Math.round(Color.blue(first) * inv + Color.blue(second) * weight));
    }

    /**
     * Theme-aware studio surface with a subtle diagonal tint and thin luminous
     * accent stroke. Does not use bitmap assets or runtime blur, so it remains
     * inexpensive on older Android devices.
     */
    public static GradientDrawable studioCard(Context context, boolean highlighted) {
        int start = mix(SURFACE, ACCENT, STUDIO_GLOW ? (highlighted ? 0.13f : 0.055f) : 0.025f);
        int end = mix(SURFACE, BACKGROUND, 0.23f);
        GradientDrawable gradient = new GradientDrawable(
            GradientDrawable.Orientation.TL_BR, new int[]{start, end});
        gradient.setCornerRadius(dp(context, CARD_RADIUS));
        gradient.setStroke(dp(context, 1),
            highlighted && STUDIO_GLOW ? mix(ACCENT, BORDER, 0.32f) : BORDER);
        return gradient;
    }

    public static GradientDrawable panel(Context context) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(SURFACE);
        d.setCornerRadius(dp(context, 16));
        d.setStroke(dp(context, 1), BORDER);
        return d;
    }

    public static TextView heading(Context context, String title, String subtitle) {
        TextView view = new TextView(context);
        view.setText(title + "\n" + subtitle);
        view.setTextSize(23 * FONT_SCALE);
        view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        view.setTextColor(TEXT);
        view.setLineSpacing(dp(context, 5), 1f);
        view.setPadding(0, dp(context, 8), 0, dp(context, 18));
        return view;
    }

    public static Button action(Context context, String label, boolean primary) {
        Button button = new Button(context);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextColor(primary ? ON_ACCENT : TEXT);
        button.setMinHeight(dp(context, 48));
        button.setContentDescription(label);
        button.setTextSize(14 * FONT_SCALE);
        GradientDrawable d = new GradientDrawable();
        if (primary) {
            d.setOrientation(GradientDrawable.Orientation.TL_BR);
            d.setColors(new int[]{ACCENT, mix(ACCENT, BACKGROUND, 0.23f)});
        } else {
            d.setColor(SURFACE);
            d.setStroke(dp(context, 1), BORDER);
        }
        d.setCornerRadius(dp(context, COMPACT ? 10 : 14));
        button.setBackground(d);
        button.setPadding(dp(context, 16), dp(context, 9), dp(context, 16), dp(context, 9));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, dp(context, COMPACT ? 48 : 56));
        lp.bottomMargin = dp(context, COMPACT ? 6 : 10);
        button.setLayoutParams(lp);
        return button;
    }
}
