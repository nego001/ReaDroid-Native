package com.readroid.app;

import android.app.Activity;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;

/**
 * P7 Home chrome: compact menu and settings affordances from the exact
 * reference screen. Both actions are supplied by MainActivity and operational.
 */
public final class P7HomeToolbar extends LinearLayout {
    private static int dp(Activity a, int n) { return NegrescoTheme.dp(a, n); }

    private static ImageView action(Activity a, int resource, String description) {
        ImageView image = new ImageView(a);
        image.setImageResource(resource);
        image.setPadding(dp(a, 9), dp(a, 9), dp(a, 9), dp(a, 9));
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setContentDescription(description);
        image.setFocusable(true);
        image.setClickable(true);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0xff070e17);
        bg.setStroke(dp(a, 1), 0xff18314a);
        bg.setCornerRadius(dp(a, 10));
        image.setBackground(bg);
        return image;
    }

    public P7HomeToolbar(Activity activity, OnClickListener menu,
                         OnClickListener settings) {
        super(activity);
        setOrientation(HORIZONTAL);
        setGravity(Gravity.CENTER_VERTICAL);
        setPadding(0, 0, 0, dp(activity, 4));
        ImageView hamburger = action(activity, R.drawable.ic_p7_menu,
            "Abrir menu de navegação");
        addView(hamburger, new LayoutParams(dp(activity, 38), dp(activity, 38)));
        hamburger.setOnClickListener(menu);
        View spacer = new View(activity);
        addView(spacer, new LayoutParams(0, 1, 1));
        ImageView gear = action(activity, R.drawable.ic_p7_settings,
            "Abrir personalização");
        addView(gear, new LayoutParams(dp(activity, 38), dp(activity, 38)));
        gear.setOnClickListener(settings);
    }
}
