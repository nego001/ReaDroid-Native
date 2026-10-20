package com.readroid.app;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.view.View;

/** P7 native low-cost hooded tech mascot. Decorative, never blocks touch input. */
public final class P7MascotView extends View {
    private final Paint pen = new Paint(Paint.ANTI_ALIAS_FLAG);

    public P7MascotView(Context context) {
        super(context);
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
        setClickable(false);
    }

    @Override protected void onDraw(Canvas c) {
        super.onDraw(c);
        if (getWidth() == 0 || getHeight() == 0) return;
        c.save();
        c.translate((getWidth() - Math.min(getWidth(), getHeight()) * 0.80f) / 2f, 0f);
        c.scale(Math.min(getWidth(), getHeight()) / 100f,
            Math.min(getWidth(), getHeight()) / 100f);
        // Dark hood silhouette uses paths instead of heavyweight gradients/bitmap blur.
        Path hood = new Path();
        hood.moveTo(14, 96); hood.lineTo(17, 46);
        hood.cubicTo(20, 22, 34, 11, 50, 7);
        hood.cubicTo(70, 13, 83, 27, 86, 51);
        hood.lineTo(91, 96); hood.close();
        pen.setStyle(Paint.Style.FILL);
        pen.setColor(0xff08182b); c.drawPath(hood, pen);
        pen.setStyle(Paint.Style.STROKE); pen.setStrokeWidth(2);
        pen.setColor(0xff176cb3); c.drawPath(hood, pen);
        Path face = new Path();
        face.moveTo(28, 49); face.quadTo(50, 36, 73, 49);
        face.lineTo(69, 76); face.quadTo(50, 88, 32, 75); face.close();
        pen.setStyle(Paint.Style.FILL); pen.setColor(0xff01050b);
        c.drawPath(face, pen);
        Path leftEye = new Path();
        leftEye.moveTo(32, 55); leftEye.quadTo(39, 58, 45, 56);
        leftEye.lineTo(42, 61); leftEye.quadTo(36, 61, 32, 55);
        Path rightEye = new Path();
        rightEye.moveTo(68, 55); rightEye.quadTo(61, 58, 55, 56);
        rightEye.lineTo(58, 61); rightEye.quadTo(64, 61, 68, 55);
        pen.setStyle(Paint.Style.FILL); pen.setColor(0xff25caff);
        c.drawPath(leftEye, pen); c.drawPath(rightEye, pen);
        pen.setStyle(Paint.Style.STROKE); pen.setColor(0xff2cb6ff);
        pen.setStrokeWidth(1.6f);
        c.drawLine(30, 94, 44, 83, pen);
        c.drawLine(70, 94, 57, 83, pen);
        pen.setColor(0xff35709e); c.drawLine(50, 13, 50, 27, pen);
        c.restore();
    }
}
