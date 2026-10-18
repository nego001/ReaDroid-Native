package com.readroid.app;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.view.View;

/** Five crisp, scalable navigation glyphs drawn with native Canvas. */
public final class NavGlyph extends View {
    private final int kind;
    private boolean selected;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);

    public NavGlyph(Context context, int kind) {
        super(context);
        this.kind = kind;
        setLayerType(View.LAYER_TYPE_SOFTWARE, null);
    }

    public void setSelectedState(boolean value) {
        selected = value;
        invalidate();
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float size = Math.min(getWidth(), getHeight());
        if (size <= 0) return;
        canvas.save();
        canvas.translate((getWidth() - size) / 2f, (getHeight() - size) / 2f);
        canvas.scale(size / 32f, size / 32f);
        paint.setColor(selected ? NegrescoTheme.ACCENT : NegrescoTheme.MUTED);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(2.2f);
        paint.setStrokeCap(Paint.Cap.ROUND);
        paint.setStrokeJoin(Paint.Join.ROUND);
        Path path = new Path();
        switch (kind) {
            case 0:
                path.moveTo(5, 15); path.lineTo(16, 6); path.lineTo(27, 15);
                path.moveTo(9, 13); path.lineTo(9, 26); path.lineTo(23, 26); path.lineTo(23, 13);
                path.moveTo(14, 26); path.lineTo(14, 19); path.lineTo(18, 19); path.lineTo(18, 26);
                break;
            case 1:
                path.moveTo(4, 10); path.lineTo(13, 10); path.lineTo(16, 13);
                path.lineTo(28, 13); path.lineTo(25, 26); path.lineTo(5, 26); path.close();
                path.moveTo(5, 10); path.lineTo(5, 7); path.lineTo(15, 7);
                break;
            case 2:
                path.moveTo(16, 4); path.lineTo(27, 10); path.lineTo(27, 22);
                path.lineTo(16, 28); path.lineTo(5, 22); path.lineTo(5, 10); path.close();
                path.moveTo(5, 10); path.lineTo(16, 16); path.lineTo(27, 10);
                path.moveTo(16, 16); path.lineTo(16, 28);
                break;
            case 3:
                path.moveTo(16, 3); path.lineTo(27, 8); path.lineTo(26, 19);
                path.quadTo(23, 26, 16, 29); path.quadTo(9, 26, 6, 19);
                path.lineTo(5, 8); path.close();
                path.moveTo(11, 16); path.lineTo(15, 20); path.lineTo(22, 12);
                break;
            default:
                path.moveTo(16, 3); path.lineTo(19, 13); path.lineTo(29, 16);
                path.lineTo(19, 19); path.lineTo(16, 29); path.lineTo(13, 19);
                path.lineTo(3, 16); path.lineTo(13, 13); path.close();
                break;
        }
        canvas.drawPath(path, paint);
        canvas.restore();
    }
}
