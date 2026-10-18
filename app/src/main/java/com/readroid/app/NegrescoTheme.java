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
        ON_ACCENT = "green".equals(accent) || "orange".equals(accent) ? 0xff101820 : 0xffffffff;
    }

    public static int dp(Context context, int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
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
        button.setTextSize(14 * FONT_SCALE);
        GradientDrawable d = new GradientDrawable();
        d.setColor(primary ? ACCENT : SURFACE);
        d.setCornerRadius(dp(context, COMPACT ? 8 : 13));
        if (!primary) d.setStroke(dp(context, 1), BORDER);
        button.setBackground(d);
        button.setPadding(dp(context, 16), dp(context, 9), dp(context, 16), dp(context, 9));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, dp(context, COMPACT ? 46 : 56));
        lp.bottomMargin = dp(context, COMPACT ? 6 : 10);
        button.setLayoutParams(lp);
        return button;
    }
}
