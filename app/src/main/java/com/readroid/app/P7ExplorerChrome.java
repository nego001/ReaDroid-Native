package com.readroid.app;

import android.app.Activity;
import android.graphics.Typeface;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.ImageView;

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
    private Runnable onExit;
    private Runnable onOpenApk;
    private Runnable onReviewPlan;
    private String currentFolder = "";

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
        TextView back = text("‹", 30, NegrescoTheme.TEXT, false);
        back.setGravity(Gravity.CENTER);
        back.setMinWidth(dp(48));
        back.setMinHeight(dp(48));
        back.setContentDescription("Voltar no Explorador");
        back.setClickable(true);
        back.setFocusable(true);
        back.setOnClickListener(v -> {
            if (!currentFolder.isEmpty()) {
                String parentFolder = currentFolder.substring(0, currentFolder.length() - 1);
                int previous = parentFolder.lastIndexOf('/');
                navigator.navigate(previous < 0 ? "" : parentFolder.substring(0, previous + 1));
            } else if (onExit != null) onExit.run();
            else navigator.navigate("");
        });
        titleRow.addView(back, new LinearLayout.LayoutParams(dp(48), dp(48)));
        LinearLayout heading = new LinearLayout(activity);
        heading.setOrientation(VERTICAL);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(0, -2, 1);
        titleParams.leftMargin = dp(10);
        titleRow.addView(heading, titleParams);
        heading.addView(text("Explorador de Arquivos", 19, NegrescoTheme.TEXT, true));
        heading.addView(text("Navegue e edite o conteúdo do APK", 11,
            NegrescoTheme.MUTED, false));
        TextView overflow = text("⋮", 24, NegrescoTheme.TEXT, true);
        overflow.setGravity(Gravity.CENTER);
        overflow.setMinWidth(dp(48));
        overflow.setMinHeight(dp(48));
        overflow.setContentDescription("Mais opções do Explorador");
        overflow.setClickable(true);
        overflow.setFocusable(true);
        overflow.setOnClickListener(v -> new android.app.AlertDialog.Builder(activity)
            .setTitle("Explorador de Arquivos")
            .setItems(new String[]{"Abrir outro APK", "Voltar ao início"}, (dialog, which) -> {
                if (which == 0 && onOpenApk != null) onOpenApk.run();
                else if (which == 1 && onExit != null) onExit.run();
            })
            .setNegativeButton("Fechar", null).show());
        titleRow.addView(overflow,
            new LinearLayout.LayoutParams(dp(48), dp(48)));

        LinearLayout projectCard = new LinearLayout(activity);
        projectCard.setOrientation(HORIZONTAL);
        projectCard.setGravity(Gravity.CENTER_VERTICAL);
        projectCard.setPadding(dp(10), dp(9), dp(10), dp(9));
        projectCard.setBackground(NegrescoTheme.studioCard(activity, false));
        LinearLayout.LayoutParams projectParams = new LinearLayout.LayoutParams(-1, -2);
        projectParams.topMargin = dp(9);
        addView(projectCard, projectParams);

        ImageView apkIcon = new ImageView(activity);
        apkIcon.setImageResource(R.drawable.ic_p7_file);
        apkIcon.setContentDescription("Ícone do APK selecionado");
        projectCard.addView(apkIcon,
            new LinearLayout.LayoutParams(dp(35), dp(35)));
        LinearLayout detail = new LinearLayout(activity);
        detail.setOrientation(VERTICAL);
        LinearLayout.LayoutParams detailParams = new LinearLayout.LayoutParams(
            0, -2, 1);
        detailParams.leftMargin = dp(9);
        detailParams.rightMargin = dp(6);
        projectCard.addView(detail, detailParams);
        projectName = text("Nenhum APK selecionado", 13, NegrescoTheme.TEXT, true);
        projectName.setMaxLines(1);
        projectName.setEllipsize(TextUtils.TruncateAt.END);
        detail.addView(projectName);
        projectDescription = text("Abra um APK para explorar os arquivos.", 10,
            NegrescoTheme.MUTED, false);
        projectDescription.setMaxLines(1);
        projectDescription.setEllipsize(TextUtils.TruncateAt.END);
        detail.addView(projectDescription);

        editCounter = text("0 alterações pendentes", 10, NegrescoTheme.ACCENT, true);
        editCounter.setGravity(Gravity.CENTER);
        editCounter.setBackground(NegrescoTheme.studioCard(activity, true));
        editCounter.setMaxLines(2);
        editCounter.setContentDescription("Abrir plano de edição");
        editCounter.setClickable(true);
        editCounter.setFocusable(true);
        editCounter.setMinHeight(dp(48));
        editCounter.setOnClickListener(v -> {
            if (onReviewPlan != null) onReviewPlan.run();
        });
        editCounter.setPadding(dp(7), dp(7), dp(7), dp(7));
        projectCard.addView(editCounter,
            new LinearLayout.LayoutParams(dp(113), -2));

        HorizontalScrollView breadcrumbs = new HorizontalScrollView(activity);
        breadcrumbs.setHorizontalScrollBarEnabled(false);
        breadcrumbs.setFillViewport(false);
        LinearLayout.LayoutParams crumbParams = new LinearLayout.LayoutParams(-1, -2);
        crumbParams.topMargin = dp(5);
        crumbParams.bottomMargin = dp(4);
        addView(breadcrumbs, crumbParams);
        breadcrumbItems = new LinearLayout(activity);
        breadcrumbItems.setOrientation(HORIZONTAL);
        breadcrumbItems.setGravity(Gravity.CENTER_VERTICAL);
        breadcrumbs.addView(breadcrumbItems);
        updateBreadcrumb("", false);
    }

    public void setActions(Runnable exit, Runnable openApk, Runnable reviewPlan) {
        onExit = exit;
        onOpenApk = openApk;
        onReviewPlan = reviewPlan;
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
        currentFolder = folder == null ? "" : folder;
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
        chip.setMinHeight(dp(48));
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
