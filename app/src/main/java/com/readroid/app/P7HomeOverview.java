package com.readroid.app;

import android.app.Activity;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import org.json.JSONObject;

/**
 * P7 Home: truthful session counters and a recent-project-shaped panel.
 * Does not claim to store project history, risk counts or completed builds.
 */
public final class P7HomeOverview extends LinearLayout {
    private final Activity activity;
    private final TextView[] values = new TextView[4];
    private final TextView recentName;
    private final TextView recentDetails;
    private final LinearLayout recentCard;

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

    public P7HomeOverview(Activity a, View.OnClickListener openFiles) {
        super(a);
        activity = a;
        setOrientation(VERTICAL);
        TextView title = text("VISÃO GERAL", 13, NegrescoTheme.TEXT, true);
        title.setLetterSpacing(0.06f);
        addView(title);
        View space = new View(a);
        addView(space, new LayoutParams(1, dp(8)));
        String[] names = {"Projetos abertos", "Itens do APK",
            "Edições no plano", "Segurança"};
        String[] symbols = {"◇", "▤", "✎", "⬡"};
        for (int row = 0; row < 2; row++) {
            LinearLayout line = new LinearLayout(a);
            line.setOrientation(HORIZONTAL);
            addView(line);
            for (int column = 0; column < 2; column++) {
                int i = row * 2 + column;
                LinearLayout cell = vertical();
                cell.setMinimumHeight(dp(76));
                cell.setPadding(dp(12), dp(10), dp(10), dp(10));
                cell.setBackground(NegrescoTheme.studioCard(a, false));
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, -2, 1);
                lp.setMargins(column == 0 ? 0 : dp(5), 0,
                    column == 0 ? dp(5) : 0, dp(9));
                line.addView(cell, lp);
                TextView icon = text(symbols[i], 17, NegrescoTheme.ACCENT, true);
                cell.addView(icon);
                values[i] = text("—", 19, NegrescoTheme.TEXT, true);
                cell.addView(values[i]);
                TextView name = text(names[i], 11, NegrescoTheme.MUTED, false);
                cell.addView(name);
            }
        }
        TextView heading = text("Projetos recentes", 15, NegrescoTheme.TEXT, true);
        heading.setPadding(0, dp(7), 0, dp(9));
        addView(heading);
        recentCard = vertical();
        recentCard.setPadding(dp(14), dp(12), dp(14), dp(12));
        recentCard.setBackground(NegrescoTheme.studioCard(a, false));
        addView(recentCard);
        recentName = text("Nenhum projeto aberto", 14, NegrescoTheme.TEXT, true);
        recentDetails = text("O histórico persistente ainda está em desenvolvimento.", 11,
            NegrescoTheme.MUTED, false);
        recentCard.addView(recentName);
        recentCard.addView(recentDetails);
        recentCard.setOnClickListener(openFiles);
        update(null, 0);
    }

    /** Called on the UI thread only. Counts derive from the real active report. */
    public void update(JSONObject report, int editCount) {
        final boolean active = report != null;
        values[0].setText(active ? "1" : "0");
        JSONObject explorer = active ? report.optJSONObject("explorer") : null;
        // Reports vary by parser version: prefer the actual entry count.
        int count = active ? report.optInt("entries", -1) : -1;
        if (count < 0 && explorer != null)
            count = explorer.optInt("fileCount", -1);
        if (count < 0 && explorer != null && explorer.optJSONArray("files") != null)
            count = explorer.optJSONArray("files").length();
        values[1].setText(count >= 0 ? String.valueOf(count) : "—");
        values[2].setText(active ? String.valueOf(Math.max(0, editCount)) : "—");
        values[3].setText(active ? "Consultar" : "Pendente");
        values[3].setTextSize(14 * NegrescoTheme.FONT_SCALE);
        if (!active) {
            recentName.setText("Nenhum projeto aberto");
            recentDetails.setText("O histórico persistente ainda está em desenvolvimento.");
            recentCard.setContentDescription("Nenhum projeto aberto nesta sessão");
            recentCard.setClickable(false);
            recentCard.setFocusable(false);
            return;
        }
        JSONObject manifest = report.optJSONObject("manifestAnalysis");
        String packageName = manifest == null ? "" : manifest.optString("packageName", "");
        if (packageName == null || packageName.trim().isEmpty()) packageName = "APK atual";
        recentName.setText(packageName);
        recentDetails.setText("Projeto desta sessão · tocar para ver os arquivos");
        recentCard.setContentDescription("Abrir arquivos do projeto desta sessão: " + packageName);
        recentCard.setClickable(true);
        recentCard.setFocusable(true);
    }
}
