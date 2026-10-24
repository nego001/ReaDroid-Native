package com.readroid.app;

import android.app.Activity;
import android.graphics.Typeface;
import android.graphics.Bitmap;
import android.widget.ImageView;
import android.widget.Button;
import android.net.Uri;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.text.DateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import org.json.JSONObject;

/**
 * Four real project counters and up to three recent SAF-backed APK entries.
 * No APK bytes, guessed threats, fake projects or auto-saved edit plans.
 */
public final class P7HomeOverview extends LinearLayout {
    public interface ProjectOpener {
        void open(P7ProjectHistory.Entry entry);
    }

    private final Activity activity;
    private final View.OnClickListener openFiles;
    private ProjectOpener projectOpener;
    private View.OnClickListener showAll;
    /** MainActivity serializes history removal with pending import writes. */
    private java.util.function.Consumer<Uri> historyRemover;
    private static final String[] STAT_LABELS = {
        "Projetos", "Arquivos", "APKs Builds", "Ameaças"
    };
    private final TextView[] values = new TextView[4];
    private final LinearLayout[] statCards = new LinearLayout[4];
    private final LinearLayout recentCard;
    private final TextView seeAll;
    private final List<P7ProjectHistory.Entry> recent = new ArrayList<>();
    private JSONObject currentReport;
    private Uri currentUri;

    private int dp(int n) { return NegrescoTheme.dp(activity, n); }

    private TextView text(String value, int sp, int color, boolean bold) {
        TextView t = new TextView(activity);
        t.setText(value);
        t.setTextSize(sp * NegrescoTheme.FONT_SCALE);
        t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return t;
    }

    private LinearLayout vertical() {
        LinearLayout v = new LinearLayout(activity);
        v.setOrientation(VERTICAL);
        return v;
    }

    /** Make TextView actions announce their actual button role to TalkBack. */
    private static void exposeAsButton(View control) {
        control.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
        control.setAccessibilityDelegate(new View.AccessibilityDelegate() {
            @Override public void onInitializeAccessibilityNodeInfo(
                    View host, AccessibilityNodeInfo info) {
                super.onInitializeAccessibilityNodeInfo(host, info);
                info.setClassName(Button.class.getName());
            }
        });
    }

    /**
     * Speak each real statistic once as a label/value pair. Unknown is not
     * zero: build and threat counts have no verified source yet.
     */
    private void updateAccessibleStats() {
        for (int i = 0; i < values.length; i++) {
            String value = values[i].getText().toString();
            statCards[i].setContentDescription(STAT_LABELS[i] + ": "
                + ("—".equals(value) ? "não disponível" : value));
        }
    }

    public P7HomeOverview(Activity activity, View.OnClickListener openFiles) {
        super(activity);
        this.activity = activity;
        this.openFiles = openFiles;
        setOrientation(VERTICAL);

        for (int row = 0; row < 2; row++) {
            LinearLayout line = new LinearLayout(activity);
            line.setOrientation(HORIZONTAL);
            addView(line);
            for (int column = 0; column < 2; column++) {
                int i = row * 2 + column;
                // Approved stat tiles: bright blue glyph on the LEFT,
                // number + caption vertically stacked to its RIGHT.
                LinearLayout cell = new LinearLayout(activity);
                cell.setOrientation(HORIZONTAL);
                cell.setGravity(Gravity.CENTER_VERTICAL);
                cell.setMinimumHeight(dp(62));
                cell.setPadding(dp(10), dp(7), dp(8), dp(7));
                cell.setBackground(NegrescoTheme.studioCard(activity, false));
                cell.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_YES);
                cell.setFocusable(true);
                statCards[i] = cell;
                LayoutParams lp = new LayoutParams(0, -2, 1);
                lp.setMargins(column == 0 ? 0 : dp(5), 0,
                    column == 0 ? dp(5) : 0, dp(7));
                line.addView(cell, lp);

                View icon;
                if (i == 0 || i == 1) {
                    ImageView resource = new ImageView(activity);
                    resource.setImageResource(i == 0
                        ? R.drawable.ic_p7_cube : R.drawable.ic_p7_file);
                    resource.setScaleType(ImageView.ScaleType.FIT_CENTER);
                    icon = resource;
                } else {
                    NavGlyph vector = new NavGlyph(activity, i == 2 ? 2 : 3);
                    vector.setSelectedState(true);
                    icon = vector;
                }
                icon.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
                cell.addView(icon, new LayoutParams(dp(29), dp(29)));
                LinearLayout metrics = vertical();
                LayoutParams metricsLp = new LayoutParams(0, -2, 1f);
                metricsLp.leftMargin = dp(11);
                cell.addView(metrics, metricsLp);
                values[i] = text("—", 18, NegrescoTheme.TEXT, true);
                values[i].setIncludeFontPadding(false);
                values[i].setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
                metrics.addView(values[i]);
                TextView caption = text(STAT_LABELS[i], 10, NegrescoTheme.MUTED, false);
                caption.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
                caption.setMaxLines(1);
                caption.setEllipsize(TextUtils.TruncateAt.END);
                metrics.addView(caption);
            }
        }

        LinearLayout heading = new LinearLayout(activity);
        heading.setGravity(Gravity.CENTER_VERTICAL);
        heading.setOrientation(HORIZONTAL);
        heading.setPadding(0, dp(7), 0, dp(5));
        addView(heading);
        TextView title = text("Projetos recentes", 15, NegrescoTheme.TEXT, true);
        heading.addView(title, new LayoutParams(0, -2, 1));
        seeAll = text("Ver todos  ›", 11, NegrescoTheme.ACCENT, false);
        seeAll.setGravity(Gravity.CENTER);
        seeAll.setMinHeight(dp(48));
        seeAll.setMinimumHeight(dp(48));
        seeAll.setPadding(dp(8), 0, 0, 0);
        seeAll.setContentDescription("Ver todos os projetos recentes");
        seeAll.setFocusable(true);
        exposeAsButton(seeAll);
        seeAll.setOnClickListener(v -> {
            if (showAll != null) showAll.onClick(v);
        });
        heading.addView(seeAll);
        recentCard = vertical();
        addView(recentCard);
        update(null, 0);
    }

    public void setHistoryCallbacks(ProjectOpener open, View.OnClickListener all) {
        projectOpener = open;
        showAll = all;
        renderHistory();
    }

    public void setHistoryRemover(java.util.function.Consumer<Uri> remove) {
        historyRemover = remove;
    }

    public void setRecentProjects(List<P7ProjectHistory.Entry> entries, Uri activeUri) {
        recent.clear();
        if (entries != null) recent.addAll(entries);
        currentUri = activeUri;
        renderHistory();
    }

    /** Must be invoked on the UI thread; session report is never persisted here. */
    public void update(JSONObject report, int editCount) {
        currentReport = report;
        JSONObject explorer = report == null ? null : report.optJSONObject("explorer");
        int count = report == null ? -1 : report.optInt("entries", -1);
        if (count < 0 && explorer != null) count = explorer.optInt("fileCount", -1);
        if (count < 0 && explorer != null && explorer.optJSONArray("files") != null)
            count = explorer.optJSONArray("files").length();
        values[1].setText(count >= 0 ? String.valueOf(count) : "—");
        // There is no measured build history or completed threat verdict yet.
        values[2].setText("—");
        values[3].setText("—");
        renderHistory();
    }

    private String currentPackage() {
        JSONObject manifest = currentReport == null ? null
            : currentReport.optJSONObject("manifestAnalysis");
        String name = manifest == null ? "" : manifest.optString("packageName", "");
        return name == null || name.trim().isEmpty() ? "APK atual" : name;
    }

    private void addRow(String name, String info, String date, Uri document,
                        boolean recorded, Runnable action) {
        LinearLayout line = new LinearLayout(activity);
        line.setGravity(Gravity.CENTER_VERTICAL);
        line.setPadding(dp(10), dp(8), dp(8), dp(8));
        line.setBackground(NegrescoTheme.studioCard(activity, false));
        LayoutParams lp = new LayoutParams(-1, -2);
        lp.bottomMargin = dp(5);
        recentCard.addView(line, lp);

        // Real launcher artwork is read from the inspected APK resource table.
        // For unsigned/obfuscated APKs without a drawable, use our own icon.
        ImageView symbol = new ImageView(activity);
        Bitmap artwork = document == null ? null :
            P7RecentAppIcons.load(activity, document);
        if (artwork != null) symbol.setImageBitmap(artwork);
        else symbol.setImageResource(R.drawable.ic_p7_file);
        symbol.setScaleType(ImageView.ScaleType.FIT_CENTER);
        symbol.setContentDescription("Ícone do arquivo " + name);
        line.addView(symbol, new LayoutParams(dp(34), dp(34)));

        LinearLayout labels = vertical();
        LayoutParams main = new LayoutParams(0, -2, 1f);
        main.leftMargin = dp(5);
        line.addView(labels, main);
        TextView title = text(name, 12, NegrescoTheme.TEXT, true);
        title.setSingleLine(true);
        title.setEllipsize(TextUtils.TruncateAt.END);
        labels.addView(title);
        TextView subtitle = text(info, 10, NegrescoTheme.MUTED, false);
        subtitle.setSingleLine(true);
        subtitle.setEllipsize(TextUtils.TruncateAt.END);
        labels.addView(subtitle);

        if (date != null && !date.isEmpty()) {
            TextView when = text(date, 9, NegrescoTheme.MUTED, false);
            LayoutParams dateParams = new LayoutParams(-2, -2);
            dateParams.leftMargin = dp(4);
            line.addView(when, dateParams);
        }
        if (recorded && document != null) {
            TextView overflow = text("⋮", 21, NegrescoTheme.MUTED, true);
            overflow.setGravity(Gravity.CENTER);
            overflow.setMinWidth(dp(48));
            overflow.setMinimumWidth(dp(48));
            overflow.setMinHeight(dp(48));
            overflow.setMinimumHeight(dp(48));
            overflow.setContentDescription("Mais opções de " + name);
            overflow.setFocusable(true);
            exposeAsButton(overflow);
            overflow.setClickable(true);
            overflow.setOnClickListener(v -> showRecentOptions(name, document, action));
            line.addView(overflow, new LayoutParams(dp(48), dp(48)));
        }
        line.setContentDescription("Abrir projeto " + name + ", " + info);
        line.setClickable(true);
        line.setFocusable(true);
        line.setOnClickListener(v -> action.run());
    }

    private void showRecentOptions(String name, Uri uri, Runnable open) {
        new android.app.AlertDialog.Builder(activity)
            .setTitle(name)
            .setItems(new String[]{"Abrir projeto", "Remover do histórico"},
                (dialog, item) -> {
                    if (item == 0) {
                        open.run();
                    } else {
                        new android.app.AlertDialog.Builder(activity)
                            .setTitle("Remover do histórico?")
                            .setMessage("Apenas esta referência será removida. " +
                                "O APK original não será apagado.")
                            .setNegativeButton("Cancelar", null)
                            .setPositiveButton("Remover", (confirm, which) -> {
                                if (historyRemover != null) {
                                    historyRemover.accept(uri);
                                    return;
                                }
                                if (P7ProjectHistory.forget(activity, uri)) {
                                    List<P7ProjectHistory.Entry> updated =
                                        P7ProjectHistory.list(activity);
                                    P7RecentAppIcons.prune(activity, updated);
                                    setRecentProjects(updated, currentUri);
                                } else {
                                    new android.app.AlertDialog.Builder(activity)
                                        .setMessage("Não foi possível remover este item.")
                                        .setPositiveButton("OK", null).show();
                                }
                            }).show();
                    }
                })
            .setNegativeButton("Fechar", null).show();
    }

    private void renderHistory() {
        if (recentCard == null) return;
        recentCard.removeAllViews();
        boolean active = currentReport != null;
        boolean includedCurrent = false;
        int shown = 0;
        int total = recent.size();

        if (active && currentUri != null) {
            for (P7ProjectHistory.Entry entry : recent)
                if (entry.uri.equals(currentUri)) includedCurrent = true;
        }
        if (active && !includedCurrent) {
            addRow(currentPackage(), "Projeto aberto nesta sessão", "",
                currentUri, false, () ->
                openFiles.onClick(this));
            shown++;
            total++;
        }
        for (P7ProjectHistory.Entry entry : recent) {
            if (shown >= 3) break;
            String date = entry.openedAt <= 0 ? "" :
                DateFormat.getDateInstance(DateFormat.SHORT).format(new Date(entry.openedAt));
            addRow(entry.name, entry.packageName, date, entry.uri, true, () -> {
                if (currentReport != null && currentUri != null
                        && currentUri.equals(entry.uri)) {
                    openFiles.onClick(this);
                } else if (projectOpener != null) {
                    projectOpener.open(entry);
                }
            });
            shown++;
        }

        if (shown == 0) {
            LinearLayout empty = vertical();
            empty.setPadding(dp(12), dp(10), dp(12), dp(10));
            empty.setBackground(NegrescoTheme.studioCard(activity, false));
            recentCard.addView(empty);
            empty.addView(text("Nenhum projeto aberto", 14, NegrescoTheme.TEXT, true));
            empty.addView(text("Abra um APK para começar seu histórico local.",
                11, NegrescoTheme.MUTED, false));
        }
        values[0].setText(String.valueOf(total));
        updateAccessibleStats();
        boolean canViewAll = !recent.isEmpty();
        seeAll.setVisibility(canViewAll ? View.VISIBLE : View.GONE);
        seeAll.setClickable(canViewAll);
    }
}
