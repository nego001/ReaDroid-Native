package com.readroid.app;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;
import android.view.View;

/**
 * Three independent reference-like vector thumbnails.
 * 0 = theme preview with phone and content, 1 = layout wireframe,
 * 2 = compact appearance preset swatch. No network or bitmap placeholders.
 */
public final class P7ThemePreviewView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final int accent;
    private final int mode;
    private final int themeSurface;
    private final boolean themeGlow;

    public P7ThemePreviewView(Context context, int accent) {
        this(context, accent, 0, 0, false);
    }

    public P7ThemePreviewView(Context context, int accent, int mode) {
        this(context, accent, mode, 0, false);
    }

    /** 0 OLED, 1 graphite, 2 light: real engine surfaces for theme cards. */
    public P7ThemePreviewView(Context context, int accent, int mode, int surface) {
        this(context, accent, mode, surface, false);
    }

    /** A highlight uses the same native studio-glow setting as the application. */
    public P7ThemePreviewView(Context context, int accent, int mode,
                              int surface, boolean glow) {
        super(context);
        this.accent = accent;
        this.mode = mode;
        this.themeSurface = surface;
        this.themeGlow = glow;
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
    }

    private void block(Canvas c, int color, float left, float top,
                       float right, float bottom, float radius) {
        paint.setShader(null);
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(color);
        c.drawRoundRect(new RectF(left, top, right, bottom), radius, radius, paint);
    }

    private void outline(Canvas c, int color, float left, float top,
                         float right, float bottom, float radius) {
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(1.6f);
        paint.setShader(null);
        paint.setColor(color);
        c.drawRoundRect(new RectF(left, top, right, bottom), radius, radius, paint);
        paint.setStyle(Paint.Style.FILL);
    }

    private void drawTheme(Canvas c) {
        // Mirror the actual V3 background/surface colors, not a dark-only
        // thumbnail that falsely previews light and graphite variants.
        final int background = themeSurface == 2 ? 0xfff2f5fa :
            themeSurface == 1 ? 0xff111217 : 0xff000000;
        final int surface = themeSurface == 2 ? 0xffffffff :
            themeSurface == 1 ? 0xff1c1e26 : 0xff101925;
        final int border = themeSurface == 2 ? 0xffd9e2ee :
            themeSurface == 1 ? 0xff343843 : 0xff25364b;
        final int line = themeSurface == 2 ? 0xff53657c :
            themeSurface == 1 ? 0xffa1a6b7 : 0xff93a6be;
        block(c, background, 10, 0, 90, 100, 10);
        outline(c, border, 10, 0, 90, 100, 10);
        block(c, accent, 18, 10, 48, 15, 2);
        block(c, line, 18, 22, 82, 26, 2);
        // Two columns of cards and three file rows reproduce the Home preview.
        block(c, surface, 16, 32, 47, 52, 4);
        block(c, surface, 53, 32, 84, 52, 4);
        block(c, accent, 21, 39, 31, 42, 1);
        block(c, accent, 58, 39, 68, 42, 1);
        block(c, surface, 17, 60, 83, 67, 3);
        block(c, surface, 17, 72, 83, 79, 3);
        block(c, accent, 21, 62, 26, 65, 1);
        block(c, accent, 21, 74, 26, 77, 1);
        block(c, surface, 16, 85, 84, 96, 3);
        block(c, accent, 24, 89, 37, 91, 1);
        if (themeGlow) {
            // Real V3 studioSurface applies accent-tinted gradients/borders
            // when studio_glow=true. These restrained strokes communicate the
            // mode; clean previews keep only their ordinary surface borders.
            outline(c, accent, 16, 32, 47, 52, 4);
            outline(c, accent, 53, 32, 84, 52, 4);
            outline(c, accent, 17, 60, 83, 67, 3);
        }
    }

    private void drawLayout(Canvas c) {
        if (themeSurface == 4) {
            block(c, 0xff07101d, 8, 7, 92, 93, 9);
            outline(c, 0xff4c6a87, 8, 7, 92, 93, 9);
            block(c, accent, 19, 18, 67, 24, 2);
            // Three rows, two actual action cards in each.
            for (int row = 0; row < 3; row++) {
                int top = 34 + row * 18;
                block(c, 0xff20364d, 18, top, 47, top + 13, 3);
                block(c, 0xff20364d, 53, top, 82, top + 13, 3);
                block(c, accent, 22, top + 4, 28, top + 6, 1);
                block(c, accent, 57, top + 4, 63, top + 6, 1);
            }
            return;
        }
        if (themeSurface == 3) {
            block(c, 0xff07101d, 8, 7, 92, 93, 9);
            outline(c, 0xff4c6a87, 8, 7, 92, 93, 9);
            block(c, accent, 19, 18, 67, 24, 2);
            for (int i = 0; i < 6; i++)
                block(c, 0xff20364d, 18, 34 + i * 8, 82, 39 + i * 8, 2);
            return;
        }
        block(c, 0xff07101d, 8, 7, 92, 93, 9);
        outline(c, 0xff4c6a87, 8, 7, 92, 93, 9);
        block(c, 0xff7f94a9, 19, 20, 81, 26, 2);
        block(c, 0xff20364d, 18, 35, 42, 46, 3);
        block(c, 0xff20364d, 47, 35, 81, 46, 3);
        block(c, 0xff20364d, 18, 52, 81, 62, 3);
        block(c, 0xff20364d, 18, 68, 81, 78, 3);
        block(c, accent, 23, 56, 31, 59, 1);
        block(c, 0xff4e7395, 19, 84, 81, 86, 1);
    }

    private void drawPreset(Canvas c) {
        block(c, 0xff07101c, 4, 5, 96, 95, 12);
        paint.setStyle(Paint.Style.FILL);
        paint.setShader(new LinearGradient(
            14, 15, 90, 93,
            new int[]{0xff081326, accent, 0xff13162b},
            new float[]{0f, 0.72f, 1f}, Shader.TileMode.CLAMP));
        c.drawRoundRect(new RectF(13, 12, 87, 88), 12, 12, paint);
        paint.setShader(null);
        block(c, 0xb5091322, 23, 23, 71, 32, 5);
        block(c, 0xa6081322, 23, 42, 80, 53, 5);
        block(c, 0xb5091322, 23, 63, 67, 73, 5);
        outline(c, 0xff69829d, 4, 5, 96, 95, 12);
    }

    @Override protected void onDraw(Canvas c) {
        super.onDraw(c);
        if (getWidth() <= 0 || getHeight() <= 0) return;
        c.save();
        c.scale(getWidth() / 100f, getHeight() / 100f);
        if (mode == 1) drawLayout(c);
        else if (mode == 2) drawPreset(c);
        else drawTheme(c);
        c.restore();
    }
}
