package com.readroid.app;

import android.app.Activity;
import android.content.res.Configuration;
import android.graphics.Typeface;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.text.style.RelativeSizeSpan;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Native, accessible V3 studio dashboard. The views supplied here are the same
 * functional controls created by MainActivity: actions and OTA policy stay intact.
 * No external images, network requests or permissions are used by this layout.
 */
public final class StudioDashboard {
    private StudioDashboard() {}

    private static int dp(Activity activity, int value) {
        return NegrescoTheme.dp(activity, value);
    }

    private static TextView label(Activity a, String value, int sp, int color, boolean bold) {
        TextView text = new TextView(a);
        text.setText(value);
        text.setTextColor(color);
        text.setTextSize(sp * NegrescoTheme.FONT_SCALE);
        if (bold) text.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return text;
    }

    private static LinearLayout column(Activity a) {
        LinearLayout col = new LinearLayout(a);
        col.setOrientation(LinearLayout.VERTICAL);
        return col;
    }

    private static void detach(View item) {
        ViewGroup parent = (ViewGroup) item.getParent();
        if (parent != null) parent.removeView(item);
    }

    private static void gap(Activity a, LinearLayout parent, int height) {
        View space = new View(a);
        parent.addView(space, new LinearLayout.LayoutParams(1, dp(a, height)));
    }

    private static LinearLayout card(Activity a, boolean highlight) {
        LinearLayout content = column(a);
        content.setPadding(dp(a, 16), dp(a, 16), dp(a, 16), dp(a, 16));
        content.setBackground(NegrescoTheme.studioCard(a, highlight));
        content.setElevation(dp(a, highlight ? 3 : 1));
        content.setClipChildren(false);
        return content;
    }

    public static LinearLayout quickTile(Activity activity, String name, String description,
                                          int iconKind, boolean favorite, View.OnClickListener listener) {
        LinearLayout tile = card(activity, favorite);
        tile.setPadding(dp(activity, 14), dp(activity, 12), dp(activity, 12), dp(activity, 12));
        LinearLayout iconRow = new LinearLayout(activity);
        iconRow.setGravity(Gravity.CENTER_VERTICAL);
        NavGlyph icon = new NavGlyph(activity, iconKind);
        icon.setSelectedState(true);
        iconRow.addView(icon, new LinearLayout.LayoutParams(dp(activity, 30), dp(activity, 30)));
        if (favorite) {
            TextView badge = label(activity, "  ★", 12, NegrescoTheme.ACCENT, true);
            iconRow.addView(badge);
        }
        tile.addView(iconRow);
        gap(activity, tile, 8);
        TextView title = label(activity, name, 15, NegrescoTheme.TEXT, true);
        title.setMaxLines(2);
        tile.addView(title);
        TextView body = label(activity, description, 11, NegrescoTheme.MUTED, false);
        body.setMaxLines(3);
        tile.addView(body);
        tile.setContentDescription("Abrir " + name + (favorite ? ", atalho favorito" : ""));
        tile.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
        iconRow.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        title.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        body.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        tile.setClickable(true);
        tile.setFocusable(true);
        tile.setOnClickListener(listener);
        return tile;
    }

    /** Compact three-column action card matching the approved Home composition. */
    public static LinearLayout referenceAction(Activity a, String title, int glyph,
            View.OnClickListener action) {
        LinearLayout tile = new LinearLayout(a);
        tile.setOrientation(LinearLayout.HORIZONTAL);
        tile.setGravity(Gravity.CENTER_VERTICAL);
        tile.setPadding(dp(a, 6), dp(a, 6), dp(a, 5), dp(a, 6));
        tile.setMinimumHeight(dp(a, 47));
        tile.setBackground(NegrescoTheme.studioCard(a, false));
        NavGlyph symbol = new NavGlyph(a, glyph);
        symbol.setSelectedState(true);
        tile.addView(symbol, new LinearLayout.LayoutParams(dp(a, 20), dp(a, 20)));
        TextView label = label(a, title, 10, NegrescoTheme.TEXT, false);
        label.setMaxLines(2);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, -2, 1f);
        lp.leftMargin = dp(a, 5);
        tile.addView(label, lp);
        tile.setContentDescription(title);
        symbol.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        label.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        tile.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
        tile.setClickable(true);
        tile.setFocusable(true);
        tile.setOnClickListener(action);
        return tile;
    }

    private static LinearLayout option(Activity a, Button action, String glyph, String detail) {
        LinearLayout wrapper = card(a, false);
        wrapper.setPadding(dp(a, 10), dp(a, 12), dp(a, 10), dp(a, 12));
        LinearLayout header = new LinearLayout(a);
        header.setGravity(Gravity.CENTER_VERTICAL);
        TextView icon = label(a, glyph, 23, NegrescoTheme.ACCENT, true);
        header.addView(icon);
        TextView arrow = label(a, "  ›", 21, NegrescoTheme.MUTED, false);
        header.addView(arrow);
        wrapper.addView(header);
        gap(a, wrapper, 7);
        TextView name = label(a, action.getText().toString(), 12, NegrescoTheme.TEXT, true);
        name.setMaxLines(2);
        wrapper.addView(name);
        TextView description = label(a, detail, 10, NegrescoTheme.MUTED, false);
        description.setMaxLines(2);
        wrapper.addView(description);
        wrapper.setClickable(true);
        wrapper.setFocusable(true);
        wrapper.setContentDescription(action.getText().toString() + ". " + detail);
        wrapper.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
        header.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        name.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        description.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        wrapper.setOnClickListener(v -> action.performClick());
        return wrapper;
    }

    private static void buildOptions(Activity a, LinearLayout destination, Button[] actions) {
        String[] glyphs = {"◉", "◆", "Aa", "▦", "▤", "☆", "⌂", "◈", "↥", "↧", "✧", "▢", "↺"};
        String[] details = {
            "OLED, grafite ou claro", "Cores prontas ou HEX",
            "Escala de fonte", "Compacto ou confortável",
            "Ícones e rótulos", "Acesso rápido favorito",
            "Nome e subtítulo", "Prévia antes de aplicar",
            "Salvar arquivo JSON", "Restaurar um arquivo JSON",
            "Neon ou minimalista", "Bordas do seu jeito", "Voltar ao padrão"
        };
        destination.removeAllViews();
        for (int index = 0; index < actions.length; index += 2) {
            LinearLayout row = new LinearLayout(a);
            row.setOrientation(LinearLayout.HORIZONTAL);
            destination.addView(row);
            for (int col = 0; col < 2; col++) {
                int i = index + col;
                if (i >= actions.length) break;
                Button action = actions[i];
                detach(action);
                LinearLayout tile = option(a, action, glyphs[i], details[i]);
                boolean lastAlone = (i == actions.length - 1 && col == 0);
                tile.setMinimumHeight(dp(a, NegrescoTheme.COMPACT ? 106 : 120));
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    lastAlone ? -1 : 0, -2, lastAlone ? 0f : 1f);
                lp.setMargins(col == 0 ? 0 : dp(a, 4), 0,
                    col == 0 ? (lastAlone ? 0 : dp(a, 4)) : 0, dp(a, 8));
                row.addView(tile, lp);
            }
        }
    }

    /** Add an informative, consistent header to the five main application tabs. */
    public static void featureHeader(Activity a, LinearLayout section, int glyph,
                                     String title, String description) {
        LinearLayout header = card(a, true);
        LinearLayout top = new LinearLayout(a);
        top.setGravity(Gravity.CENTER_VERTICAL);
        NavGlyph mark = new NavGlyph(a, glyph);
        mark.setSelectedState(true);
        top.addView(mark, new LinearLayout.LayoutParams(dp(a, 34), dp(a, 34)));
        TextView heading = label(a, title, 21, NegrescoTheme.TEXT, true);
        LinearLayout.LayoutParams headingParams = new LinearLayout.LayoutParams(-2, -2);
        headingParams.leftMargin = dp(a, 12);
        top.addView(heading, headingParams);
        header.addView(top);
        gap(a, header, 8);
        TextView hint = label(a, description, 13, NegrescoTheme.MUTED, false);
        header.addView(hint);
        section.addView(header, 0);
        View spacer = new View(a);
        section.addView(spacer, 1, new LinearLayout.LayoutParams(1, dp(a, 10)));
    }

    public static void styleFeatureButton(Activity a, Button button, String symbol,
                                           String description, boolean important) {
        String title = button.getText().toString();
        String full = symbol + "   " + title + "\n" + description;
        SpannableString rich = new SpannableString(full);
        int line = full.indexOf('\n');
        rich.setSpan(new RelativeSizeSpan(0.8f), line + 1, full.length(),
            Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        // Feature cards have dark surfaces even when the original action was primary.
        // Never reuse ON_ACCENT here: it can be black for bright custom accents.
        rich.setSpan(new ForegroundColorSpan(NegrescoTheme.MUTED),
            line + 1, full.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        button.setText(rich);
        button.setTextColor(NegrescoTheme.TEXT);
        button.setGravity(Gravity.CENTER_VERTICAL | Gravity.START);
        button.setTextSize(13 * NegrescoTheme.FONT_SCALE);
        button.setMinHeight(dp(a, NegrescoTheme.COMPACT ? 72 : 88));
        button.setSingleLine(false);
        button.setMaxLines(Integer.MAX_VALUE);
        button.setPadding(dp(a, 17), dp(a, 11), dp(a, 12), dp(a, 11));
        button.setBackground(NegrescoTheme.studioCard(a, important));
        // Allow Android's larger-font settings to grow the card instead of
        // clipping security instructions or long action descriptions.
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.bottomMargin = dp(a, 10);
        button.setLayoutParams(lp);
        button.setContentDescription(title + ". " + description);
    }

    public static void compose(Activity a, LinearLayout home, LinearLayout designSettingsDestination,
                               TextView apkSummary, TextView projectMetrics, Button choose,
                               P7HomeOverview overview,
                               TextView shortcutsTitle, TextView shortcutHint, LinearLayout quickGrid,
                               TextView customizationTitle, TextView customizationHint,
                               Button togglePersonalization, LinearLayout personalizationGroup,
                               Button[] controls, TextView otaTitle, TextView otaStatus,
                               Button otaChannel, Button otaCheck,
                               TextView detailsTitle, TextView output, Button project) {
        home.removeAllViews();
        home.setClipChildren(false);
        home.setClipToPadding(false);

        // P7.2: high-contrast welcome hero and low-cost Canvas mascot.
        LinearLayout welcome = card(a, false);
        welcome.setPadding(dp(a, 12), dp(a, 7), dp(a, 12), dp(a, 7));
        LinearLayout welcomeLine = new LinearLayout(a);
        welcomeLine.setGravity(Gravity.CENTER_VERTICAL);
        welcome.addView(welcomeLine);
        LinearLayout welcomeText = column(a);
        welcomeLine.addView(welcomeText, new LinearLayout.LayoutParams(0, -2, 1f));
        welcomeText.addView(label(a, "Olá, Desenvolvedor", 15,
            NegrescoTheme.TEXT, true));
        gap(a, welcomeText, 5);
        welcomeText.addView(label(a,
            "Analise, edite e reconstrua seus apps de forma simples e poderosa.",
            11, NegrescoTheme.MUTED, false));
        // The approved mascot is a tall illustration, not a tiny glyph.
        // Match its portrait silhouette without stretching the source artwork.
        int artWidth = a.getResources().getConfiguration().screenWidthDp < 360 ? 104 : 126;
        int artHeight = a.getResources().getConfiguration().screenWidthDp < 360 ? 126 : 151;
        P7MascotView mascot = new P7MascotView(a);
        LinearLayout.LayoutParams art = new LinearLayout.LayoutParams(
            dp(a, artWidth), dp(a, artHeight));
        art.leftMargin = dp(a, 5);
        welcomeLine.addView(mascot, art);
        home.addView(welcome);
        gap(a, home, 7);

        // Main project area with the live report-bound text views and real picker.
        LinearLayout hero = card(a, false);
        TextView heroLabel = label(a, "◈  PROJETO ATUAL", 12, NegrescoTheme.ACCENT, true);
        heroLabel.setLetterSpacing(0.05f);
        hero.addView(heroLabel);
        gap(a, hero, 8);
        apkSummary.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        apkSummary.setTextSize(16 * NegrescoTheme.FONT_SCALE);
        apkSummary.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        apkSummary.setPadding(0, dp(a, 4), 0, dp(a, 8));
        LinearLayout projectRow = new LinearLayout(a);
        projectRow.setGravity(Gravity.CENTER_VERTICAL);
        hero.addView(projectRow);
        projectRow.addView(apkSummary, new LinearLayout.LayoutParams(0, -2, 1f));
        if (a.getResources().getConfiguration().screenWidthDp >= 360) {
            NeonCubeView cube = new NeonCubeView(a);
            LinearLayout.LayoutParams cubeParams = new LinearLayout.LayoutParams(
                dp(a, 92), dp(a, 108));
            cubeParams.leftMargin = dp(a, 4);
            projectRow.addView(cube, cubeParams);
        }
        projectMetrics.setPadding(0, 0, 0, dp(a, 8));
        projectMetrics.setTextSize(12 * NegrescoTheme.FONT_SCALE);
        hero.addView(projectMetrics);
        choose.setText("▱  Selecionar APK   ›");
        choose.setContentDescription("Selecionar arquivo APK para analisar");
        choose.setMinHeight(dp(a, 52));
        hero.addView(choose);
        // Put live information immediately after the welcome card, exactly
        // as in the approved Home mockup; the full project card goes below
        // the six compact actions so it doesn't consume the first viewport.
        // Session-only counters and a clickable current-project row.
        home.addView(overview);
        gap(a, home, 9);

        // Quick actions, native icons, two-column layout on phones.
        shortcutsTitle.setText("Ações rápidas");
        shortcutsTitle.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        shortcutsTitle.setLetterSpacing(0.05f);
        shortcutsTitle.setPadding(0, dp(a, 2), 0, dp(a, 2));
        home.addView(shortcutsTitle);
        shortcutHint.setText("");
        shortcutHint.setPadding(0, 0, 0, dp(a, 4));
        home.addView(shortcutHint);
        home.addView(quickGrid);
        gap(a, home, 12);
        home.addView(hero);
        gap(a, home, 10);

        // Real appearance controls belong to the Design Studio, not the Home viewport.
        // Personalization panel: 11 real controls rendered as compact two-column
        // options. Their original click handlers remain authoritative.
        LinearLayout settingsPanel = card(a, true);
        customizationTitle.setText("◉  PERSONALIZAÇÃO");
        customizationTitle.setTextColor(NegrescoTheme.TEXT);
        customizationTitle.setTextSize(17 * NegrescoTheme.FONT_SCALE);
        customizationTitle.setPadding(0, 0, 0, dp(a, 4));
        settingsPanel.addView(customizationTitle);
        customizationHint.setText("Sua interface. Suas regras. Temas, cores e muito mais.");
        customizationHint.setPadding(0, 0, 0, dp(a, 8));
        settingsPanel.addView(customizationHint);
        // Keep Home focused on the project and its four main tools.
        // The user can expand the complete customization panel on demand.
        boolean expanded = a.getPreferences(Activity.MODE_PRIVATE)
            .getBoolean("studio_settings_expanded", false);
        togglePersonalization.setText(
            expanded ? "Opções de aparência  ▴" : "Opções de aparência  ▾");
        settingsPanel.addView(togglePersonalization);
        buildOptions(a, personalizationGroup, controls);
        personalizationGroup.setVisibility(expanded ? View.VISIBLE : View.GONE);
        settingsPanel.addView(personalizationGroup);
        designSettingsDestination.addView(settingsPanel);
        gap(a, designSettingsDestination, 14);

        // Actual OTA status is retained: no false claims about availability.
        LinearLayout updates = card(a, false);
        otaTitle.setText("↻  ATUALIZAÇÕES");
        otaTitle.setTextSize(12 * NegrescoTheme.FONT_SCALE);
        otaTitle.setPadding(0, 0, 0, dp(a, 8));
        updates.addView(otaTitle);
        otaStatus.setTextSize(12 * NegrescoTheme.FONT_SCALE);
        otaStatus.setPadding(dp(a, 12), dp(a, 12), dp(a, 12), dp(a, 12));
        updates.addView(otaStatus);
        gap(a, updates, 8);
        updates.addView(otaChannel);
        updates.addView(otaCheck);

        // The technical report remains selectable, with its existing buttons.
        LinearLayout technical = card(a, false);
        detailsTitle.setText("▥  RELATÓRIO TÉCNICO");
        detailsTitle.setTextSize(12 * NegrescoTheme.FONT_SCALE);
        detailsTitle.setPadding(0, 0, 0, dp(a, 8));
        technical.addView(detailsTitle);
        output.setTextSize(12 * NegrescoTheme.FONT_SCALE);
        technical.addView(output);
        technical.addView(project);

        // Keep content readable on compact portrait screens.
        int screenWidth = a.getResources().getConfiguration().screenWidthDp;
        if (screenWidth >= 480) {
            LinearLayout bottom = new LinearLayout(a);
            bottom.setOrientation(LinearLayout.HORIZONTAL);
            home.addView(bottom);
            LinearLayout.LayoutParams left = new LinearLayout.LayoutParams(0, -2, 1f);
            left.rightMargin = dp(a, 6);
            bottom.addView(updates, left);
            LinearLayout.LayoutParams right = new LinearLayout.LayoutParams(0, -2, 1f);
            right.leftMargin = dp(a, 6);
            bottom.addView(technical, right);
        } else {
            home.addView(updates);
            gap(a, home, 12);
            home.addView(technical);
        }
        gap(a, home, 18);
    }
}
