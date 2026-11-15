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
    public static int LAYOUT_VARIANT = 0;
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
        LAYOUT_VARIANT = prefs.getInt("layout_variant",
            prefs.getBoolean("compact", false) ? 1 : 0);
        if (LAYOUT_VARIANT < 0 || LAYOUT_VARIANT >= P7VisualCatalog.LAYOUT_NAMES.length)
            LAYOUT_VARIANT = 0;
        COMPACT = LAYOUT_VARIANT == 1;
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

    /** Android system chrome follows the selected light/dark application palette. */
    public static void applySystemBars(android.app.Activity activity) {
        android.view.Window window = activity.getWindow();
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
        window.setStatusBarColor(BACKGROUND);
        window.setNavigationBarColor(BACKGROUND);
        boolean lightBackground = contrastRatio(BACKGROUND, Color.BLACK) > 7.0;
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            // Window.getInsetsController() can dereference an uninitialized
            // decor view on Android 15 during Activity creation.
            android.view.View decor = window.getDecorView();
            android.view.WindowInsetsController controller =
                decor == null ? null : decor.getWindowInsetsController();
            if (controller != null) {
                int appearance = android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                    | android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                controller.setSystemBarsAppearance(lightBackground ? appearance : 0, appearance);
            }
        } else {
            int lightIcons = android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                | android.view.View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            android.view.View decor = window.getDecorView();
            decor.setSystemUiVisibility((decor.getSystemUiVisibility() & ~lightIcons)
                | (lightBackground ? lightIcons : 0));
        }
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
        return navigationSurface(context, selected, false);
    }

    /** A solid ring distinguishes keyboard focus from the currently selected tab. */
    public static android.graphics.drawable.Drawable navigationSurface(
            Context context, boolean selected, boolean focused) {
        GradientDrawable shape = new GradientDrawable();
        shape.setCornerRadius(dp(context, 14));
        // The approved bottom bar is OLED black with a thin neon marker.
        // An active tab must not be wrapped in a large filled blue pill.
        shape.setColor(focused ? SURFACE : Color.TRANSPARENT);
        if (focused) {
            // Keyboard/DPAD users still get a visible 2dp focus outline.
            shape.setStroke(dp(context, 2), ACCENT);
        }
        return new android.graphics.drawable.RippleDrawable(
            android.content.res.ColorStateList.valueOf(mix(ACCENT, SURFACE, 0.60f)),
            shape, null);
    }
    /** WCAG contrast ratio for user-selected themes and custom accent previews. */
    public static double contrastRatio(int first, int second) {
        double a = relativeLuminance(first);
        double b = relativeLuminance(second);
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
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


    /** Shared native workshop chrome; honors the selected dark/light palette. */
    public static GradientDrawable studioDialogPanel(Context context) {
        GradientDrawable panel = new GradientDrawable();
        panel.setColor(SURFACE);
        panel.setCornerRadius(dp(context, CARD_RADIUS));
        panel.setStroke(dp(context, 1), mix(ACCENT, BORDER, 0.22f));
        return panel;
    }

    /** Native AlertDialog with the same palette as the underlying Design page. */
    public static void styleStudioDialog(android.app.AlertDialog dialog) {
        if (dialog == null || !dialog.isShowing()) {
            throw new IllegalArgumentException("Studio dialog must be showing");
        }
        android.view.Window window = dialog.getWindow();
        if (window != null) {
            window.setBackgroundDrawable(studioDialogPanel(dialog.getContext()));
        }
        Button close = dialog.getButton(android.app.AlertDialog.BUTTON_NEGATIVE);
        if (close != null) {
            close.setAllCaps(false);
            close.setTextColor(ACCENT);
        }
    }

    /** Actual export buttons; SVG is secondary, but remains a real action. */
    public static void styleWorkshopExport(Context context, Button button,
            boolean primary) {
        GradientDrawable background = new GradientDrawable();
        background.setCornerRadius(dp(context, 12));
        if (primary) {
            background.setOrientation(GradientDrawable.Orientation.TL_BR);
            background.setColors(new int[]{
                ACCENT, mix(ACCENT, BACKGROUND, 0.16f)});
        } else {
            background.setColor(mix(SURFACE, BACKGROUND, 0.16f));
            background.setStroke(dp(context, 1),
                mix(ACCENT, BORDER, 0.27f));
        }
        button.setBackground(background);
        button.setTextColor(primary ? ON_ACCENT : TEXT);
        button.setAllCaps(false);
        button.setPadding(dp(context, 12), 0, dp(context, 12), 0);
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
