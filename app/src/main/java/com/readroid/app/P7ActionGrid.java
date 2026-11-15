package com.readroid.app;

import android.app.Activity;
import android.view.View;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Button;
import android.widget.LinearLayout;

/** Reusable native six-action grid with viewport-safe rows and real callbacks. */
final class P7ActionGrid {
    private P7ActionGrid() {}

    static void populate(Activity activity, LinearLayout destination,
            String[] titles, int[] glyphs, View.OnClickListener[] handlers,
            int layout, int widthDp, float systemFontScale, float appFontScale) {
        if (activity == null || destination == null || titles == null
                || glyphs == null || handlers == null || titles.length != 6
                || glyphs.length != 6 || handlers.length != 6)
            throw new IllegalArgumentException("Ações da Home incompletas");
        int[] rows = P7VisualCatalog.quickActionRowsForViewport(
            layout, widthDp, systemFontScale, appFontScale);
        int next = 0;
        destination.removeAllViews();
        for (int columns : rows) {
            LinearLayout row = new LinearLayout(activity);
            row.setOrientation(LinearLayout.HORIZONTAL);
            destination.addView(row);
            for (int col = 0; col < columns; col++) {
                int index = next++;
                LinearLayout tile = StudioDashboard.referenceAction(activity,
                    titles[index], glyphs[index], handlers[index]);
                final boolean guidanceOnly = index >= 3;
                // TalkBack must not imply Smali decompilation, Smali editing,
                // or installable APK signing are operational yet. The exact
                // visible label and original explanatory click remain intact.
                tile.setAccessibilityDelegate(new View.AccessibilityDelegate() {
                    @Override public void onInitializeAccessibilityNodeInfo(
                            View host, AccessibilityNodeInfo info) {
                        super.onInitializeAccessibilityNodeInfo(host, info);
                        info.setClassName(Button.class.getName());
                        if (guidanceOnly)
                            info.setHintText("Recurso ainda não disponível. "
                                + "Toque para ver a explicação.");
                    }
                });
                LinearLayout.LayoutParams params = columns == 1
                    ? new LinearLayout.LayoutParams(-1, -2)
                    : new LinearLayout.LayoutParams(0, -2, 1f);
                params.setMargins(columns == 1 || col == 0
                        ? 0 : NegrescoTheme.dp(activity, 3), 0,
                    columns == 1 || col == columns - 1
                        ? 0 : NegrescoTheme.dp(activity, 3),
                    NegrescoTheme.dp(activity, columns == 1 ? 5 : 7));
                row.addView(tile, params);
            }
        }
        if (next != 6)
            throw new IllegalStateException("As seis ações precisam continuar visíveis");
    }
}
