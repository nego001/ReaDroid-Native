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
        // These Canvas glyphs are decorative. Their parent announces the
        // button name once to TalkBack rather than repeating icon and label.
        setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
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
                // Build: an actual wrench glyph, not the previous cube.
                path.moveTo(25, 5); path.cubicTo(22, 3, 18, 4, 16, 7);
                path.lineTo(18, 11); path.lineTo(12, 17);
                path.lineTo(8, 15); path.lineTo(5, 19);
                path.cubicTo(3, 22, 4, 27, 8, 28);
                path.cubicTo(11, 29, 14, 27, 15, 24);
                path.lineTo(14, 20); path.lineTo(20, 14);
                path.lineTo(24, 16);
                path.cubicTo(27, 13, 29, 8, 25, 5); path.close();
                break;
            case 3:
                path.moveTo(16, 3); path.lineTo(27, 8); path.lineTo(26, 19);
                path.quadTo(23, 26, 16, 29); path.quadTo(9, 26, 6, 19);
                path.lineTo(5, 8); path.close();
                path.moveTo(11, 16); path.lineTo(15, 20); path.lineTo(22, 12);
                break;
            case 4:
                // Design: artist palette and four paint wells, as in the reference.
                path.addOval(new android.graphics.RectF(4, 5, 28, 27),
                    Path.Direction.CW);
                path.moveTo(27, 18);
                path.cubicTo(24, 14, 19, 16, 20, 20);
                path.cubicTo(21, 24, 25, 25, 27, 18);
                canvas.drawPath(path, paint);
                paint.setStyle(Paint.Style.FILL);
                canvas.drawCircle(11, 11, 2, paint);
                canvas.drawCircle(17, 10, 2, paint);
                canvas.drawCircle(22, 13, 2, paint);
                canvas.drawCircle(10, 18, 2, paint);
                canvas.restore();
                return;
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
