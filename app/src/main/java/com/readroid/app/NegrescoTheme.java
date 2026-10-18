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
    public static final int BACKGROUND = 0xff05080e;
    public static final int SURFACE = 0xff101925;
    public static final int BORDER = 0xff25364b;
    public static final int ACCENT = 0xff1688ff;
    public static final int TEXT = 0xfff1f6ff;
    public static final int MUTED = 0xff93a6be;
    private NegrescoTheme() {}

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
        view.setTextSize(23);
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
        button.setTextColor(TEXT);
        button.setTextSize(14);
        GradientDrawable d = new GradientDrawable();
        d.setColor(primary ? ACCENT : SURFACE);
        d.setCornerRadius(dp(context, 13));
        if (!primary) d.setStroke(dp(context, 1), BORDER);
        button.setBackground(d);
        button.setPadding(dp(context, 16), dp(context, 9), dp(context, 16), dp(context, 9));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, dp(context, 56));
        lp.bottomMargin = dp(context, 10);
        button.setLayoutParams(lp);
        return button;
    }
}
