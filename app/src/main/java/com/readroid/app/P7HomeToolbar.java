package com.readroid.app;

import android.app.Activity;
import android.content.res.ColorStateList;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Button;
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
        // Reference shows quiet line icons, not large outlined squares.
        // The icon itself is 22dp within a still-clickable 48dp target.
        image.setPadding(dp(a, 13), dp(a, 13), dp(a, 13), dp(a, 13));
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setContentDescription(description);
        image.setMinimumWidth(dp(a, 48));
        image.setMinimumHeight(dp(a, 48));
        image.setFocusable(true);
        image.setClickable(true);
        GradientDrawable touchMask = new GradientDrawable();
        touchMask.setColor(0xffffffff);
        touchMask.setCornerRadius(dp(a, 10));
        image.setBackground(new RippleDrawable(
            ColorStateList.valueOf(0x44219eff), null, touchMask));
        image.setTooltipText(description);
        image.setAccessibilityDelegate(new View.AccessibilityDelegate() {
            @Override public void onInitializeAccessibilityNodeInfo(
                    View host, AccessibilityNodeInfo node) {
                super.onInitializeAccessibilityNodeInfo(host, node);
                node.setClassName(Button.class.getName());
            }
        });
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
        addView(hamburger, new LayoutParams(dp(activity, 48), dp(activity, 48)));
        hamburger.setOnClickListener(menu);
        View spacer = new View(activity);
        addView(spacer, new LayoutParams(0, 1, 1));
        ImageView gear = action(activity, R.drawable.ic_p7_settings,
            "Abrir personalização");
        addView(gear, new LayoutParams(dp(activity, 48), dp(activity, 48)));
        gear.setOnClickListener(settings);
    }
}
