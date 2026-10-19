package com.readroid.app;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.view.View;

/**
 * Small neon cube illustration inspired by the V3 visual reference.
 * All graphics are drawn locally using Canvas (no bitmaps, blur or animations).
 */
public final class NeonCubeView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);

    public NeonCubeView(Context context) {
        super(context);
        setContentDescription("Ilustração decorativa de um APK");
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
    }

    private Path line(float... points) {
        Path path = new Path();
        path.moveTo(points[0], points[1]);
        for (int i = 2; i < points.length; i += 2) path.lineTo(points[i], points[i + 1]);
        return path;
    }

    private void stroke(Canvas c, Path shape, int color, float width, int alpha) {
        paint.setShader(null);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeJoin(Paint.Join.ROUND);
        paint.setStrokeCap(Paint.Cap.ROUND);
        paint.setStrokeWidth(width);
        paint.setColor(color);
        paint.setAlpha(alpha);
        c.drawPath(shape, paint);
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float scale = Math.min(getWidth(), getHeight()) / 120f;
        if (scale <= 0) return;
        canvas.save();
        canvas.translate((getWidth() - scale * 120f) / 2f,
            (getHeight() - scale * 120f) / 2f);
        canvas.scale(scale, scale);
        int accent = NegrescoTheme.ACCENT;

        paint.setStyle(Paint.Style.FILL);
        paint.setShader(new RadialGradient(60, 94, 61,
            new int[]{Color.argb(105, Color.red(accent), Color.green(accent), Color.blue(accent)),
                Color.TRANSPARENT}, null, Shader.TileMode.CLAMP));
        canvas.drawCircle(60, 83, 56, paint);
        paint.setShader(null);
        paint.setAlpha(255);

        Path top = line(60, 15, 98, 36, 60, 58, 22, 36, 60, 15);
        Path left = line(22, 36, 60, 58, 60, 101, 22, 79, 22, 36);
        Path right = line(60, 58, 98, 36, 98, 79, 60, 101, 60, 58);
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(accent);
        paint.setAlpha(25);
        canvas.drawPath(left, paint);
        paint.setAlpha(50);
        canvas.drawPath(right, paint);
        paint.setAlpha(38);
        canvas.drawPath(top, paint);
        for (Path path : new Path[]{top, left, right}) {
            stroke(canvas, path, accent, 7, 30);
            stroke(canvas, path, accent, 3.2f, 95);
            stroke(canvas, path, NegrescoTheme.TEXT, 1.2f, 170);
        }
        paint.setStyle(Paint.Style.STROKE);
        paint.setColor(accent);
        paint.setStrokeWidth(1.3f);
        paint.setAlpha(115);
        canvas.drawOval(8, 93, 112, 112, paint);
        canvas.drawOval(18, 97, 102, 108, paint);
        paint.setAlpha(255);
        paint.setStyle(Paint.Style.FILL);
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTextSize(15);
        paint.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        paint.setColor(NegrescoTheme.TEXT);
        canvas.drawText("APK", 60, 80, paint);
        paint.reset();
        paint.setAntiAlias(true);
        canvas.restore();
    }
}
