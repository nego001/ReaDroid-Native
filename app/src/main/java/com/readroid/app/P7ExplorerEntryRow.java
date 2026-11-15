package com.readroid.app;

import android.app.Activity;
import android.graphics.Typeface;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.LayerDrawable;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.Locale;

/**
 * Live, accessible Explorer row matching the approved file-browser structure.
 * No fabricated dates, directory sizes, entry counts or thumbnails.
 */
public final class P7ExplorerEntryRow extends LinearLayout {
    private static int dp(Activity a, int value) {
        return NegrescoTheme.dp(a, value);
    }

    /**
     * All glyphs are bundled with the app; filenames supply only a visual
     * category. No resource, URL or executable content is loaded from the APK.
     */
    static int iconResource(String name, boolean folder) {
        if (folder) return R.drawable.ic_p7_folder;
        String lower = name == null ? "" : name.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".png") || lower.endsWith(".webp")
                || lower.endsWith(".jpg") || lower.endsWith(".jpeg")
                || lower.endsWith(".gif") || lower.endsWith(".bmp"))
            return R.drawable.ic_p7_image;
        if (lower.endsWith(".xml") || lower.endsWith(".smali")
                || lower.endsWith(".kt") || lower.endsWith(".java"))
            return R.drawable.ic_p7_code;
        if (lower.endsWith(".dex") || lower.endsWith(".so")
                || lower.endsWith(".arsc"))
            return R.drawable.ic_p7_cube;
        return R.drawable.ic_p7_file;
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
        // The approved Explorer uses a continuous file list with fine separators,
        // not individually outlined file cards. Draw the rule at the bottom only.
        LayerDrawable background = new LayerDrawable(new Drawable[] {
            new ColorDrawable(NegrescoTheme.BACKGROUND),
            new ColorDrawable(NegrescoTheme.BORDER)
        });
        background.setLayerGravity(1, Gravity.BOTTOM | Gravity.FILL_HORIZONTAL);
        background.setLayerHeight(1, dp(activity, 1));
        setBackground(background);

        ImageView glyph = new ImageView(activity);
        glyph.setImageResource(iconResource(name, folder));
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
        // The trailing three-dot control is a separate action from opening
        // the entry. TalkBack must identify it as a Button, not plain text.
        overflow.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_YES);
        overflow.setAccessibilityDelegate(new View.AccessibilityDelegate() {
            @Override public void onInitializeAccessibilityNodeInfo(
                    View host, AccessibilityNodeInfo info) {
                super.onInitializeAccessibilityNodeInfo(host, info);
                info.setClassName(Button.class.getName());
            }
        });
        overflow.setClickable(true);
        overflow.setFocusable(true);
        LayoutParams menuParams = new LayoutParams(dp(activity, 48),
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
        rowParams.bottomMargin = 0;
        setLayoutParams(rowParams);
    }
}
