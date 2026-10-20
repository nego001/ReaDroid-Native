package com.readroid.app;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.View;

/** Native, resolution-independent thumbnail of the actual reference card layout. */
public final class P7ThemePreviewView extends View {
    private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final int accent;
    public P7ThemePreviewView(Context context, int accent) {
        super(context);
        this.accent = accent;
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
    }
    private void block(Canvas c, int color, float left, float top,
                       float right, float bottom, float radius) {
        p.setColor(color);
        p.setStyle(Paint.Style.FILL);
        c.drawRoundRect(new RectF(left,top,right,bottom),radius,radius,p);
    }
    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (getWidth() <= 0 || getHeight() <= 0) return;
        canvas.save();
        canvas.scale(getWidth()/100f,getHeight()/100f);
        block(canvas,0xff02070e,9,2,91,98,10);
        p.setColor(0xff526679);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(1.5f);
        canvas.drawRoundRect(new RectF(9,2,91,98),10,10,p);
        p.setStyle(Paint.Style.FILL);
        block(canvas,accent,18,13,43,18,2);
        block(canvas,0xff293849,18,23,81,27,2);
        block(canvas,0xff132333,18,33,46,54,4);
        block(canvas,0xff132333,52,33,81,54,4);
        block(canvas,accent,22,38,35,40,1);
        block(canvas,accent,55,38,66,40,1);
        block(canvas,0xff132333,18,60,81,69,3);
        block(canvas,0xff132333,18,73,81,82,3);
        block(canvas,accent,21,62,26,67,2);
        block(canvas,accent,21,75,26,80,2);
        block(canvas,0xff1d4a71,18,90,81,92,1);
        canvas.restore();
    }
}
