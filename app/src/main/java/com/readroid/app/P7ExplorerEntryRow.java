package com.readroid.app;

import android.app.Activity;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Live, accessible Explorer row matching the approved file-browser structure.
 * No fabricated dates, directory sizes, entry counts or thumbnails.
 */
public final class P7ExplorerEntryRow extends LinearLayout {
    private static int dp(Activity a, int value) {
        return NegrescoTheme.dp(a, value);
    }

    public P7ExplorerEntryRow(Activity activity, String name, String detail,
                              boolean folder, boolean edited,
                              OnClickListener open, OnClickListener options) {
        super(activity);
        setOrientation(HORIZONTAL);
        setGravity(Gravity.CENTER_VERTICAL);
        setPadding(dp(activity, 9), dp(activity, 7),
            dp(activity, 4), dp(activity, 7));
        setMinimumHeight(dp(activity, 58));
        GradientDrawable background = new GradientDrawable();
        background.setColor(NegrescoTheme.BACKGROUND);
        background.setStroke(dp(activity, 1), NegrescoTheme.BORDER);
        background.setCornerRadius(dp(activity, 4));
        setBackground(background);

        ImageView glyph = new ImageView(activity);
        glyph.setImageResource(folder ? R.drawable.ic_p7_folder
            : R.drawable.ic_p7_file);
        glyph.setScaleType(ImageView.ScaleType.FIT_CENTER);
        glyph.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
        addView(glyph, new LayoutParams(dp(activity, 33), dp(activity, 33)));

        LinearLayout description = new LinearLayout(activity);
        description.setOrientation(VERTICAL);
        LayoutParams descriptionParams = new LayoutParams(0, -2, 1f);
        descriptionParams.leftMargin = dp(activity, 11);
        addView(description, descriptionParams);

        TextView title = new TextView(activity);
        title.setText(edited ? "●  " + name : name);
        title.setSingleLine(true);
        title.setEllipsize(TextUtils.TruncateAt.MIDDLE);
        title.setTextColor(NegrescoTheme.TEXT);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        title.setTextSize(13 * NegrescoTheme.FONT_SCALE);
        title.setIncludeFontPadding(false);
        description.addView(title);

        TextView subtitle = new TextView(activity);
        subtitle.setText(detail);
        subtitle.setSingleLine(true);
        subtitle.setEllipsize(TextUtils.TruncateAt.END);
        subtitle.setTextColor(NegrescoTheme.MUTED);
        subtitle.setTextSize(10 * NegrescoTheme.FONT_SCALE);
        subtitle.setIncludeFontPadding(false);
        LayoutParams subtitleParams = new LayoutParams(-1, -2);
        subtitleParams.topMargin = dp(activity, 4);
        description.addView(subtitle, subtitleParams);

        TextView overflow = new TextView(activity);
        overflow.setText("⋮");
        overflow.setTextColor(NegrescoTheme.TEXT);
        overflow.setGravity(Gravity.CENTER);
        overflow.setTextSize(21 * NegrescoTheme.FONT_SCALE);
        overflow.setContentDescription("Opções de " + name);
        overflow.setClickable(true);
        overflow.setFocusable(true);
        LayoutParams menuParams = new LayoutParams(dp(activity, 44),
            dp(activity, 48));
        menuParams.leftMargin = dp(activity, 4);
        addView(overflow, menuParams);
        overflow.setOnClickListener(options);

        setContentDescription((folder ? "Abrir pasta " : "Abrir arquivo ")
            + name + (edited ? ", alterado" : ""));
        setClickable(true);
        setFocusable(true);
        setOnClickListener(open);

        LayoutParams rowParams = new LayoutParams(-1, -2);
        rowParams.bottomMargin = dp(activity, 2);
        setLayoutParams(rowParams);
    }
}
