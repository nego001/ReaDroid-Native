package com.readroid.app;

import android.app.Activity;
import android.graphics.Typeface;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * P7.3 native visual chrome. APK inspection, SQLite and edits stay in ExplorerView.
 * All values shown are derived from the open session, never the promotional mockup.
 */
public final class P7ExplorerChrome extends LinearLayout {
    public interface FolderNavigator { void navigate(String folder); }

    private final Activity activity;
    private final FolderNavigator navigator;
    private final LinearLayout breadcrumbItems;
    private final TextView projectName;
    private final TextView projectDescription;
    private final TextView editCounter;

    private int dp(int v) { return NegrescoTheme.dp(activity, v); }

    private TextView text(String value, int size, int color, boolean strong) {
        TextView item = new TextView(activity);
        item.setText(value);
        item.setTextSize(size * NegrescoTheme.FONT_SCALE);
        item.setTextColor(color);
        if (strong) item.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return item;
    }

    public P7ExplorerChrome(Activity activity, LinearLayout parent,
            FolderNavigator navigator) {
        super(activity);
        this.activity = activity;
        this.navigator = navigator;
        setOrientation(VERTICAL);
        parent.addView(this, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout titleRow = new LinearLayout(activity);
        titleRow.setOrientation(HORIZONTAL);
        titleRow.setGravity(Gravity.CENTER_VERTICAL);
        addView(titleRow);
        NavGlyph icon = new NavGlyph(activity, 1);
        icon.setSelectedState(true);
        titleRow.addView(icon, new LinearLayout.LayoutParams(dp(30), dp(30)));
        LinearLayout heading = new LinearLayout(activity);
        heading.setOrientation(VERTICAL);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(0, -2, 1);
        titleParams.leftMargin = dp(10);
        titleRow.addView(heading, titleParams);
        heading.addView(text("Explorador de Arquivos", 19, NegrescoTheme.TEXT, true));
        heading.addView(text("Navegue e edite o conteúdo do APK", 11,
            NegrescoTheme.MUTED, false));

        LinearLayout projectCard = new LinearLayout(activity);
        projectCard.setOrientation(VERTICAL);
        projectCard.setPadding(dp(14), dp(12), dp(14), dp(12));
        projectCard.setBackground(NegrescoTheme.studioCard(activity, true));
        LinearLayout.LayoutParams projectParams = new LinearLayout.LayoutParams(-1, -2);
        projectParams.topMargin = dp(12);
        addView(projectCard, projectParams);
        projectName = text("Nenhum APK selecionado", 15, NegrescoTheme.TEXT, true);
        projectName.setMaxLines(2);
        projectName.setEllipsize(TextUtils.TruncateAt.END);
        projectCard.addView(projectName);
        projectDescription = text("Abra um APK para explorar os arquivos.", 11,
            NegrescoTheme.MUTED, false);
        projectCard.addView(projectDescription);
        editCounter = text("0 alterações pendentes", 11, NegrescoTheme.ACCENT, true);
        LinearLayout.LayoutParams edits = new LinearLayout.LayoutParams(-2, -2);
        edits.topMargin = dp(8);
        projectCard.addView(editCounter, edits);

        HorizontalScrollView breadcrumbs = new HorizontalScrollView(activity);
        breadcrumbs.setHorizontalScrollBarEnabled(false);
        breadcrumbs.setFillViewport(false);
        LinearLayout.LayoutParams crumbParams = new LinearLayout.LayoutParams(-1, -2);
        crumbParams.topMargin = dp(12);
        crumbParams.bottomMargin = dp(7);
        addView(breadcrumbs, crumbParams);
        breadcrumbItems = new LinearLayout(activity);
        breadcrumbItems.setOrientation(HORIZONTAL);
        breadcrumbItems.setGravity(Gravity.CENTER_VERTICAL);
        breadcrumbs.addView(breadcrumbItems);
        updateBreadcrumb("", false);
    }

    public void setProject(String title, long sizeBytes) {
        boolean present = title != null && !title.trim().isEmpty();
        projectName.setText(present ? title : "Nenhum APK selecionado");
        projectDescription.setText(!present ? "Abra um APK para explorar os arquivos."
            : (sizeBytes < 0 ? "APK da sessão atual"
                : "APK da sessão atual  •  " + humanSize(sizeBytes)));
    }

    public void setEditCount(int count) {
        int safeCount = Math.max(0, count);
        editCounter.setText(safeCount == 1 ? "1 alteração pendente"
            : safeCount + " alterações pendentes");
    }

    public void updateBreadcrumb(String folder, boolean searching) {
        breadcrumbItems.removeAllViews();
        crumb("APK", "", !searching && (folder == null || folder.isEmpty()));
        if (searching) {
            TextView result = text("  ›  Resultados da busca", 12,
                NegrescoTheme.MUTED, false);
            breadcrumbItems.addView(result);
            return;
        }
        if (folder == null || folder.isEmpty()) return;
        String[] segments = folder.split("/");
        if (segments.length > 4) {
            TextView skipped = text("  ›  …", 12, NegrescoTheme.MUTED, false);
            breadcrumbItems.addView(skipped);
        }
        StringBuilder prefix = new StringBuilder();
        for (int i = 0; i < segments.length; i++) {
            if (segments[i].isEmpty()) continue;
            prefix.append(segments[i]).append('/');
            if (i < segments.length - 4) continue;
            crumb(segments[i], prefix.toString(), i == segments.length - 1);
        }
    }

    private void crumb(String label, String destination, boolean active) {
        if (!destination.isEmpty()) breadcrumbItems.addView(
            text("  ›  ", 12, NegrescoTheme.MUTED, false));
        TextView chip = text(label, 12,
            active ? NegrescoTheme.ACCENT : NegrescoTheme.TEXT, active);
        chip.setSingleLine(true);
        chip.setMaxWidth(dp(140));
        chip.setEllipsize(TextUtils.TruncateAt.END);
        chip.setMinHeight(dp(43));
        chip.setGravity(Gravity.CENTER_VERTICAL);
        chip.setPadding(dp(6), 0, dp(6), 0);
        chip.setContentDescription(destination.isEmpty()
            ? "Ir à raiz do APK" : "Abrir pasta " + destination);
        chip.setClickable(true);
        chip.setFocusable(true);
        chip.setOnClickListener(v -> navigator.navigate(destination));
        breadcrumbItems.addView(chip);
    }

    private static String humanSize(long bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1048576) return String.format(java.util.Locale.ROOT,
            "%.1f KB", bytes / 1024.0);
        if (bytes < 1073741824L) return String.format(java.util.Locale.ROOT,
            "%.1f MB", bytes / 1048576.0);
        return String.format(java.util.Locale.ROOT,
            "%.2f GB", bytes / 1073741824.0);
    }
}
