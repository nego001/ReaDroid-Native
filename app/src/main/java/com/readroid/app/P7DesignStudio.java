package com.readroid.app;

import android.app.Activity;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Button;
import android.widget.HorizontalScrollView;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.ImageView;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import java.util.Locale;

/** Native, operational P7 Design Studio. Uses the existing appearance handlers. */
public final class P7DesignStudio {
    private final Activity a;
    private final LinearLayout root;
    private final Button[] actions;
    private int activeTab = 0;
    private int selectedTheme = 0;
    private void restoreCurrentTheme() {
        selectedTheme = P7ThemeCatalog.currentTheme(a);
    }
    private void applySelectedTheme() {
        if (selectedTheme < 0 || selectedTheme >= P7ThemeCatalog.count()) {
            new android.app.AlertDialog.Builder(a)
                .setTitle("Selecione um tema")
                .setMessage("Escolha uma opção do catálogo antes de aplicar.")
                .setPositiveButton("OK", null).show();
            return;
        }
        new android.app.AlertDialog.Builder(a)
            .setTitle("Aplicar " + P7ThemeCatalog.nameAt(selectedTheme) + "?")
            .setMessage("O tema será salvo e a interface reiniciada. "
                + "O APK e o plano de edições serão preservados.")
            .setPositiveButton("Aplicar", (dialog, which) -> {
                try {
                    P7ThemeCatalog.apply(a, selectedTheme);
                } catch (Exception error) {
                    restoreCurrentTheme();
                    render();
                    new android.app.AlertDialog.Builder(a)
                        .setTitle("Não foi possível aplicar")
                        .setMessage(error.getMessage())
                        .setPositiveButton("OK", null).show();
                }
            })
            .setNegativeButton("Cancelar", (dialog, which) -> {
                restoreCurrentTheme();
                render();
            })
            .setOnCancelListener(dialog -> {
                restoreCurrentTheme();
                render();
            }).show();
    }
    private int selectedLayout = 0;
    private int selectedPreset = 0;
    private final LinearLayout body;
    private final HorizontalScrollView tabScroller;
    private final TextView[] tabViews=new TextView[4];

    private int dp(int n) { return NegrescoTheme.dp(a,n); }

    /** Expose clickable text navigation as real TalkBack button semantics. */
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

    private TextView label(String text,int size,int color,boolean bold) {
        TextView t=new TextView(a);t.setText(text);t.setTextSize(size*NegrescoTheme.FONT_SCALE);
        t.setTextColor(color);if(bold)t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        return t;
    }
    private LinearLayout column() {
        LinearLayout l=new LinearLayout(a);l.setOrientation(LinearLayout.VERTICAL);return l;
    }
    /** Dark mockup colors stay intact; light palettes need light card surfaces. */
    private static boolean lightDesignPalette() {
        return NegrescoTheme.contrastRatio(NegrescoTheme.TEXT, 0xff10171f) < 4.5;
    }

    static int cardFillColor(boolean selected) {
        if (!lightDesignPalette()) return selected ? 0xff07294b : 0xff10171f;
        return selected ? 0xffe6f0fc : NegrescoTheme.SURFACE;
    }

    static int cardOutlineColor(boolean selected) {
        if (!lightDesignPalette()) return selected ? NegrescoTheme.ACCENT : 0xff283846;
        if (!selected) return NegrescoTheme.BORDER;
        return NegrescoTheme.contrastRatio(NegrescoTheme.ACCENT, cardFillColor(true)) >= 3
            ? NegrescoTheme.ACCENT : 0xff346aa4;
    }

    static int tabLabelColor(boolean selected) {
        // On a light palette, bright custom accents do not meet text contrast.
        // A selected card retains its accented outline and spoken selected state.
        return selected && !lightDesignPalette()
            ? NegrescoTheme.ACCENT : NegrescoTheme.TEXT;
    }

    private GradientDrawable background(boolean selected) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(cardFillColor(selected));
        d.setCornerRadius(dp(12));
        d.setStroke(dp(1), cardOutlineColor(selected));
        return d;
    }
    /**
     * At 320dp with 130% font, use compact tab chrome so all four real
     * editors are visible. At 200% font allow horizontal scrolling, keeping
     * the label readable instead of shrinking or cutting the touch target.
     */
    static boolean fitsFourTabs(int widthDp, float systemFont, float appFont) {
        float effective = Math.max(0.85f, systemFont)
            * Math.max(0.85f, appFont);
        return widthDp > 0 && widthDp < 360 && effective <= 1.40f;
    }

    /** Enlarged fonts need a visible, operable affordance for the scrollable
     * four-tab strip. Normal fonts keep the existing approved layout. */
    static boolean needsTabPagingControl(int widthDp, float systemFont,
            float appFont) {
        float effective = Math.max(0.85f, systemFont)
            * Math.max(0.85f, appFont);
        return widthDp > 0 && effective >= 1.65f;
    }

    public P7DesignStudio(Activity activity,LinearLayout container,Button[] appearanceActions,
                          int restoredTab) {
        a=activity;root=container;actions=appearanceActions;
        // Rotation/Activity recreation restores navigation only. This is
        // deliberately not stored in appearance preferences or APK metadata.
        activeTab = restoredTab >= 0 && restoredTab < tabViews.length
            ? restoredTab : 0;
        restoreCurrentTheme();
        selectedLayout = P7VisualCatalog.currentLayout(a);
        selectedPreset = P7VisualCatalog.currentPreset(a);
        LinearLayout header=new LinearLayout(a);
        header.setGravity(Gravity.CENTER_VERTICAL);root.addView(header);
        NavGlyph palette=new NavGlyph(a,4);palette.setSelectedState(true);
        header.addView(palette,new LinearLayout.LayoutParams(dp(35),dp(35)));
        LinearLayout titles=column();
        LinearLayout.LayoutParams tp=new LinearLayout.LayoutParams(-1,-2);
        tp.leftMargin=dp(10);header.addView(titles,tp);
        TextView studioHeading = label("Design Studio",18,NegrescoTheme.TEXT,true);
        if (android.os.Build.VERSION.SDK_INT >= 28)
            studioHeading.setAccessibilityHeading(true);
        titles.addView(studioHeading);
        titles.addView(label("Personalize a aparência do seu app",12,NegrescoTheme.MUTED,false));
        HorizontalScrollView scroll=new HorizontalScrollView(a);
        tabScroller = scroll;
        scroll.setHorizontalScrollBarEnabled(false);
        LinearLayout tabs=new LinearLayout(a);
        tabs.setOrientation(LinearLayout.HORIZONTAL);
        scroll.addView(tabs);
        LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(-1,dp(52));
        sp.topMargin=dp(8);
        boolean showPagingControl = needsTabPagingControl(
            a.getResources().getConfiguration().screenWidthDp,
            a.getResources().getConfiguration().fontScale,
            NegrescoTheme.FONT_SCALE);
        if (showPagingControl) {
            LinearLayout strip = new LinearLayout(a);
            strip.setGravity(Gravity.CENTER_VERTICAL);
            strip.setOrientation(LinearLayout.HORIZONTAL);
            root.addView(strip, sp);
            strip.addView(scroll, new LinearLayout.LayoutParams(0, dp(52), 1f));
            TextView pager = new TextView(a);
            pager.setText("⇄");
            // This is an icon, not content: the accessible text is in the
            // explicit, fully spoken description, without font clipping.
            pager.setTextSize(android.util.TypedValue.COMPLEX_UNIT_DIP, 24);
            pager.setTextColor(NegrescoTheme.ACCENT);
            pager.setGravity(Gravity.CENTER);
            pager.setMinimumWidth(dp(48));
            pager.setMinimumHeight(dp(48));
            pager.setContentDescription("Percorrer abas do Design Studio");
            pager.setClickable(true);
            pager.setFocusable(true);
            exposeAsButton(pager);
            pager.setBackground(background(false));
            pager.setOnClickListener(view -> {
                int limit = Math.max(0, tabs.getWidth() - scroll.getWidth());
                if (limit <= 0) return;
                int destination = scroll.getScrollX() <= limit / 2 ? limit : 0;
                scroll.scrollTo(destination, 0);
            });
            strip.addView(pager,
                new LinearLayout.LayoutParams(dp(48), dp(48)));
        } else {
            root.addView(scroll, sp);
        }
        String[] names={"Temas","Layout","Ícones","Logotipo"};
        boolean fitCompact = fitsFourTabs(
            a.getResources().getConfiguration().screenWidthDp,
            a.getResources().getConfiguration().fontScale,
            NegrescoTheme.FONT_SCALE);
        for(int i=0;i<names.length;i++) {
            final int index=i;
            TextView tab=label(names[i],11,NegrescoTheme.TEXT,false);
            tab.setGravity(Gravity.CENTER);
            tab.setMinWidth(dp(fitCompact ? 66 : 79));
            tab.setMinimumWidth(dp(fitCompact ? 66 : 79));
            tab.setMinHeight(dp(48));
            // TextView.setMinHeight affects text layout. View's minimum
            // property is separate and is required by accessibility
            // measurement and touch-target contracts on Android 10/15.
            tab.setMinimumHeight(dp(48));
            tab.setPadding(dp(fitCompact ? 4 : 10),0,
                dp(fitCompact ? 4 : 10),0);
            tab.setClickable(true);
            tab.setFocusable(true);
            exposeAsButton(tab);
            LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,dp(48));
            p.rightMargin=dp(fitCompact ? 3 : 5);
            tabs.addView(tab,p);
            tabViews[i]=tab;
            tab.setOnClickListener(v->{activeTab=index;render();});
            tab.setTag(index);
        }
        body=column();root.addView(body);
        render();
    }
    /** For Activity saved-state only; never persists a navigation-only choice. */
    public int getActiveTab() {
        return activeTab;
    }

    /** Keep the active Design subtab visible after tap or Activity recreation. */
    private void revealActiveTab() {
        final int index = activeTab;
        tabScroller.post(() -> {
            if (index != activeTab || tabScroller.getWidth() <= 0) return;
            View target = tabViews[index];
            int left = target.getLeft();
            int right = target.getRight();
            int offset = tabScroller.getScrollX();
            if (left < offset) tabScroller.scrollTo(left, 0);
            else if (right > offset + tabScroller.getWidth())
                tabScroller.scrollTo(right - tabScroller.getWidth(), 0);
        });
    }

    private void heading(String title) {
        sectionHeader(title, null);
    }

    /** Short headings stay compact; enlarged text can use their natural height. */
    static boolean needsExpandedSectionHeader(int widthDp, float systemFontScale,
            float appFontScale) {
        float effective = Math.max(0.75f, systemFontScale)
            * Math.max(0.85f, appFontScale);
        return (widthDp > 0 && widthDp < 360) || effective >= 1.20f;
    }

    private void sectionHeader(String title, Runnable onViewAll) {
        boolean expanded = needsExpandedSectionHeader(
            a.getResources().getConfiguration().screenWidthDp,
            a.getResources().getConfiguration().fontScale,
            NegrescoTheme.FONT_SCALE);
        boolean stacked = expanded && onViewAll != null;
        LinearLayout row = new LinearLayout(a);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setOrientation(stacked
            ? LinearLayout.VERTICAL : LinearLayout.HORIZONTAL);
        row.setMinimumHeight(dp(48));
        LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(
            -1, expanded ? -2 : dp(48));
        rp.topMargin = dp(4);
        body.addView(row, rp);
        TextView label = label(title, 15, NegrescoTheme.TEXT, true);
        // Keep the full heading legible and navigable with TalkBack.
        if (android.os.Build.VERSION.SDK_INT >= 28)
            label.setAccessibilityHeading(true);
        row.addView(label, stacked
            ? new LinearLayout.LayoutParams(-1, -2)
            : new LinearLayout.LayoutParams(0, -2, 1f));
        if (onViewAll != null) {
            TextView viewAll = label("Ver todos  ›", 11, NegrescoTheme.ACCENT, false);
            viewAll.setGravity(Gravity.CENTER);
            viewAll.setMinHeight(dp(48));
            viewAll.setMinimumHeight(dp(48));
            viewAll.setMinimumWidth(dp(48));
            viewAll.setPadding(dp(8), 0, dp(3), 0);
            viewAll.setClickable(true);
            viewAll.setFocusable(true);
            viewAll.setContentDescription("Ver todos: " + title);
            exposeAsButton(viewAll);
            viewAll.setOnClickListener(v -> onViewAll.run());
            LinearLayout.LayoutParams actionParams = new LinearLayout.LayoutParams(
                -2, -2);
            if (stacked) actionParams.gravity = Gravity.END;
            row.addView(viewAll, actionParams);
        }
    }

    /** All preview families have a real chooser and explicit apply confirmation. */
    private void showCatalogDialog(int type) {
        final String[] names = type == 0 ? P7ThemeCatalog.names() :
            type == 1 ? P7VisualCatalog.LAYOUT_NAMES : P7VisualCatalog.PRESET_NAMES;
        int selected = type == 0 ? selectedTheme :
            type == 1 ? selectedLayout : selectedPreset;
        String title = type == 0 ? "Temas disponíveis" :
            type == 1 ? "Layouts disponíveis" : "Presets disponíveis";
        new android.app.AlertDialog.Builder(a)
            .setTitle(title)
            .setSingleChoiceItems(names, selected, (dialog, which) -> {
                if (type == 0) selectedTheme = which;
                else if (type == 1) selectedLayout = which;
                else selectedPreset = which;
                dialog.dismiss();
                render();
                if (type == 0) applySelectedTheme();
                else if (type == 1) confirmLayout();
                else confirmPreset();
            })
            .setNegativeButton("Fechar", null).show();
    }

    /** Native tiles use separate proportions for themes, layouts and presets. */
    private void tile(String name, String subtitle, int accent, boolean selected,
                      int kind, Runnable click) {
        tile(name, subtitle, accent, selected, kind, 0, false, click);
    }

    private void tile(String name, String subtitle, int accent, boolean selected,
                      int kind, int themeSurface, boolean themeGlow, Runnable click) {
        // Layout names such as "Escalonado inverso" require two lines,
        // especially at enlarged text size. Horizontal scroll keeps the
        // chooser usable without shrinking or truncating the title.
        float effectiveFontScale = a.getResources().getConfiguration().fontScale
            * NegrescoTheme.FONT_SCALE;
        boolean enlargedText = effectiveFontScale > 1.15f;
        // Preserve the canonical compact tiles at normal fonts, and give
        // longer theme/preset names actual room when accessibility text grows.
        final int width = kind == 2 ? (enlargedText ? 120 : 71)
            : kind == 1 ? (enlargedText ? 140 : 110)
            : (enlargedText ? 144 : 100);
        // Preserve 48dp controls while keeping the three catalog families
        // visible above the fold at the canonical emulator viewport.
        final int previewHeight = kind == 2 ? 46 : (kind == 1 ? 57 : 74);
        LinearLayout card = column();
        card.setPadding(dp(5), dp(6), dp(5), dp(7));
        card.setMinimumWidth(dp(width));
        card.setBackground(background(selected));

        FrameLayout previewFrame = new FrameLayout(a);
        card.addView(previewFrame, new LinearLayout.LayoutParams(-1, dp(previewHeight)));
        P7ThemePreviewView miniature =
            new P7ThemePreviewView(a, accent, kind, themeSurface, themeGlow);
        previewFrame.addView(miniature,
            new FrameLayout.LayoutParams(-1, -1));
        if (selected) {
            TextView check = label("✓", 11, android.graphics.Color.WHITE, true);
            check.setGravity(Gravity.CENTER);
            GradientDrawable bubble = new GradientDrawable();
            bubble.setColor(0xff1688ff);
            bubble.setCornerRadius(dp(20));
            bubble.setStroke(dp(1), 0xff061524);
            check.setBackground(bubble);
            FrameLayout.LayoutParams tick = new FrameLayout.LayoutParams(
                dp(20), dp(20), Gravity.RIGHT | Gravity.BOTTOM);
            tick.setMargins(0, 0, dp(1), dp(1));
            previewFrame.addView(check, tick);
            check.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        }
        TextView title = label(name, kind == 2 ? 9 : 11,
            NegrescoTheme.TEXT, selected);
        title.setMaxLines(enlargedText ? 3 : kind == 1 ? 2 : 1);
        title.setEllipsize(enlargedText || kind == 1 ? null
            : android.text.TextUtils.TruncateAt.END);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(-1, -2);
        tp.topMargin = dp(3);
        card.addView(title, tp);
        if (kind == 0 && !subtitle.isEmpty()) {
            TextView detail = label(subtitle, 9, NegrescoTheme.MUTED, false);
            detail.setMaxLines(enlargedText ? 3 : 1);
            detail.setEllipsize(enlargedText ? null
                : android.text.TextUtils.TruncateAt.END);
            detail.setGravity(Gravity.CENTER_HORIZONTAL);
            card.addView(detail);
            detail.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        }
        card.setClickable(true);
        card.setFocusable(true);
        card.setSelected(selected);
        // A theme's Glow/No-Glow and subtitle are actionable distinctions,
        // not decoration. Include them in the single spoken card description.
        // Keep its existing name/selection prefix for navigation compatibility.
        card.setContentDescription(name +
            (selected ? ", prévia selecionada" : ", selecionar prévia") +
            (kind == 0 && !subtitle.isEmpty() ? ". " + subtitle : ""));
        // The whole tile is the single interaction target. Tell TalkBack
        // it is a button and hide duplicate miniature/label announcements.
        card.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
        card.setAccessibilityDelegate(new View.AccessibilityDelegate() {
            @Override public void onInitializeAccessibilityNodeInfo(
                    View host, AccessibilityNodeInfo info) {
                super.onInitializeAccessibilityNodeInfo(host, info);
                info.setClassName(Button.class.getName());
            }
        });
        previewFrame.setImportantForAccessibility(
            View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        title.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        card.setOnClickListener(v -> click.run());
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(dp(width), -2);
        p.rightMargin = dp(kind == 2 ? 6 : 8);
        cards.addView(card, p);
    }

    private LinearLayout cards;
    private void startCards() {
        HorizontalScrollView scroll=new HorizontalScrollView(a);
        scroll.setHorizontalScrollBarEnabled(false);
        body.addView(scroll);
        cards=new LinearLayout(a);cards.setOrientation(LinearLayout.HORIZONTAL);
        scroll.addView(cards);
    }
    private void open(int index) {
        if (index == -4) {
            if (a instanceof MainActivity) P7IconWorkshop.open((MainActivity) a);
            return;
        }
        if (index == -5) {
            if (a instanceof MainActivity) P7LogoWorkshop.open((MainActivity) a);
            return;
        }
        if(index>=0 && index<actions.length && actions[index]!=null)
            actions[index].performClick();
    }
    private void actionCard(String name,String subtitle,int actionIndex) {
        TextView button=label(name+"  ↗\n"+subtitle,13,NegrescoTheme.TEXT,true);
        button.setPadding(dp(14),dp(12),dp(12),dp(12));
        button.setBackground(background(false));
        button.setMinHeight(dp(60));
        button.setMinimumHeight(dp(60));
        button.setClickable(true);
        button.setFocusable(true);
        button.setContentDescription(name + ". " + subtitle);
        exposeAsButton(button);
        button.setOnClickListener(v->{
            if (actionIndex == -1) applySelectedTheme();
            else if (actionIndex == -2) confirmLayout();
            else if (actionIndex == -3) confirmPreset();
            else open(actionIndex);
        });
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);
        p.bottomMargin=dp(8);body.addView(button,p);
    }
    private void note(String message) {
        TextView text=label(message,11,NegrescoTheme.MUTED,false);
        text.setPadding(0,dp(7),0,dp(1));
        body.addView(text);
    }
    private void confirmLayout() {
        final int choice = selectedLayout;
        new android.app.AlertDialog.Builder(a)
            .setTitle("Aplicar layout " + P7VisualCatalog.LAYOUT_NAMES[choice] + "?")
            .setMessage("O visual será atualizado sem modificar o APK aberto ou o plano de edições.")
            .setPositiveButton("Aplicar", (d, w) -> {
                try { P7VisualCatalog.applyLayout(a, choice); }
                catch (RuntimeException error) {
                    selectedLayout = P7VisualCatalog.currentLayout(a);
                    render();
                    showError(error);
                }
            })
            .setNegativeButton("Cancelar", (dialog, which) -> {
                selectedLayout = P7VisualCatalog.currentLayout(a);
                render();
            })
            .setOnCancelListener(dialog -> {
                selectedLayout = P7VisualCatalog.currentLayout(a);
                render();
            }).show();
    }

    private void confirmPreset() {
        if (selectedPreset < 0) {
            new android.app.AlertDialog.Builder(a)
                .setTitle("Selecione um preset")
                .setMessage("Escolha uma das opções de aparência antes de aplicar.")
                .setPositiveButton("OK", null).show();
            return;
        }
        final int choice = selectedPreset;
        new android.app.AlertDialog.Builder(a)
            .setTitle("Aplicar " + P7VisualCatalog.PRESET_NAMES[choice] + "?")
            .setMessage("Cores, efeito neon e densidade serão salvos. " +
                "O aplicativo reiniciará mantendo o projeto atual.")
            .setPositiveButton("Aplicar", (d, w) -> {
                try { P7VisualCatalog.applyPreset(a, choice); }
                catch (RuntimeException error) {
                    selectedPreset = P7VisualCatalog.currentPreset(a);
                    render();
                    showError(error);
                }
            })
            .setNegativeButton("Cancelar", (dialog, which) -> {
                selectedPreset = P7VisualCatalog.currentPreset(a);
                render();
            })
            .setOnCancelListener(dialog -> {
                selectedPreset = P7VisualCatalog.currentPreset(a);
                render();
            }).show();
    }

    private void showError(RuntimeException error) {
        new android.app.AlertDialog.Builder(a)
            .setTitle("Não foi possível aplicar")
            .setMessage(error.getMessage())
            .setPositiveButton("OK", null).show();
    }

    /** Native preview of the actual saved header identity, never sample logos. */
    private void liveLogoPreview() {
        android.content.SharedPreferences prefs =
            a.getSharedPreferences("v3_personalizacao", Activity.MODE_PRIVATE);
        String name = prefs.getString("display_name", "NegrecoDroid");
        if (name == null || name.trim().isEmpty()) name = "NegrecoDroid";
        String subtitle = prefs.getString("display_subtitle", "APK ENGINEERING STUDIO");
        if (subtitle == null || subtitle.trim().isEmpty())
            subtitle = "APK ENGINEERING STUDIO";
        if ("APK ENGINEERING STUDIO".equals(subtitle))
            subtitle = "ANÁLISE, EDIÇÃO E CUSTOMIZAÇÃO DE APKS";

        LinearLayout preview = new LinearLayout(a);
        preview.setOrientation(LinearLayout.HORIZONTAL);
        preview.setGravity(Gravity.CENTER_VERTICAL);
        preview.setPadding(dp(15), dp(16), dp(15), dp(16));
        preview.setBackground(background(false));
        // A preview must announce the actual saved identity, not only its type.
        // One accessible group avoids duplicate readings of the visible texts.
        preview.setContentDescription("Prévia da identidade visual atual. Nome: "
            + name + ". Subtítulo: " + subtitle);
        preview.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
        LinearLayout.LayoutParams outer = new LinearLayout.LayoutParams(-1, -2);
        outer.bottomMargin = dp(10);
        body.addView(preview, outer);

        ImageView icon = new ImageView(a);
        icon.setImageResource(R.drawable.ic_negrecodroid_foreground);
        icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        preview.addView(icon, new LinearLayout.LayoutParams(dp(54), dp(54)));

        LinearLayout names = column();
        LinearLayout.LayoutParams textParams = new LinearLayout.LayoutParams(0, -2, 1f);
        textParams.leftMargin = dp(12);
        preview.addView(names, textParams);
        names.setImportantForAccessibility(
            View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);

        TextView brand = label("", 20, NegrescoTheme.TEXT, true);
        SpannableString style = new SpannableString(name);
        int blue = name.toLowerCase(Locale.ROOT).lastIndexOf("droid");
        if (blue >= 0) style.setSpan(new ForegroundColorSpan(NegrescoTheme.ACCENT),
            blue, blue + 5, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        brand.setText(style);
        boolean largeText = a.getResources().getConfiguration().fontScale
            * NegrescoTheme.FONT_SCALE >= 1.20f;
        brand.setMaxLines(largeText ? Integer.MAX_VALUE : 2);
        names.addView(brand);

        TextView secondary = label(subtitle, 9, NegrescoTheme.MUTED, false);
        secondary.setMaxLines(largeText ? Integer.MAX_VALUE : 2);
        secondary.setLetterSpacing(0.12f);
        names.addView(secondary);
        note("Prévia do cabeçalho atual. Não altera o ícone instalado nem assina APKs.");
    }

    /** Keep two creative actions side by side only when labels can fit. */
    static boolean shouldStackCreators(int widthDp, float systemFontScale,
            float appFontScale) {
        float effective = Math.max(0.75f, systemFontScale)
            * Math.max(0.85f, appFontScale);
        return widthDp > 0 && (widthDp < 360 || effective >= 1.20f);
    }

    private void creatorRow() {
        LinearLayout row = new LinearLayout(a);
        row.setOrientation(shouldStackCreators(
            a.getResources().getConfiguration().screenWidthDp,
            a.getResources().getConfiguration().fontScale,
            NegrescoTheme.FONT_SCALE)
            ? LinearLayout.VERTICAL : LinearLayout.HORIZONTAL);
        body.addView(row);
        creator(row, "◉", "Criador de Ícones",
            "Criar e exportar PNG", -4, true);
        creator(row, "N", "Logo Studio",
            "Criar e exportar logo PNG", -5, false);
    }

    private void creator(LinearLayout row, String symbol, String title,
            String subtitle, int actionIndex, boolean first) {
        LinearLayout card = new LinearLayout(a);
        card.setGravity(Gravity.CENTER_VERTICAL);
        card.setPadding(dp(10), dp(12), dp(8), dp(12));
        card.setBackground(background(false));
        boolean stacked = row.getOrientation() == LinearLayout.VERTICAL;
        card.setMinimumHeight(dp(88));
        LinearLayout.LayoutParams cell = stacked
            ? new LinearLayout.LayoutParams(-1, -2)
            : new LinearLayout.LayoutParams(0, -2, 1f);
        cell.setMargins(0, 0, !stacked && first ? dp(4) : 0,
            stacked && first ? dp(8) : 0);
        row.addView(card, cell);
        TextView logo = label(symbol, 27, NegrescoTheme.ACCENT, true);
        card.addView(logo);
        LinearLayout description = column();
        LinearLayout.LayoutParams info = new LinearLayout.LayoutParams(0, -2, 1);
        info.leftMargin = dp(6);
        card.addView(description, info);
        description.addView(label(title, 11, NegrescoTheme.TEXT, true));
        TextView hint = label(subtitle, 9, NegrescoTheme.MUTED, false);
        hint.setMaxLines(3);
        description.addView(hint);
        card.setContentDescription(title + ": " + subtitle);
        card.setClickable(true);
        card.setFocusable(true);
        card.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
        card.setAccessibilityDelegate(new View.AccessibilityDelegate() {
            @Override public void onInitializeAccessibilityNodeInfo(
                    View host, AccessibilityNodeInfo info) {
                super.onInitializeAccessibilityNodeInfo(host, info);
                info.setClassName(Button.class.getName());
            }
        });
        logo.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        description.setImportantForAccessibility(
            View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        card.setOnClickListener(v -> open(actionIndex));
    }

    /** Four native previews exported by the exact same Canvas renderer. */
    private void iconTemplateGallery() {
        sectionHeader("Modelos de Ícones", null);
        HorizontalScrollView scroll = new HorizontalScrollView(a);
        scroll.setHorizontalScrollBarEnabled(false);
        body.addView(scroll);
        LinearLayout row = new LinearLayout(a);
        row.setOrientation(LinearLayout.HORIZONTAL);
        scroll.addView(row);
        String[] names = {"Escudo Azul", "Código Neon", "Pasta Verde",
            "Estrela Laranja"};
        P7IconWorkshop.Spec[] templates = {
            new P7IconWorkshop.Spec(0, 0, 0),
            new P7IconWorkshop.Spec(2, 1, 1),
            new P7IconWorkshop.Spec(1, 2, 2),
            new P7IconWorkshop.Spec(3, 3, 0)
        };
        for (int i = 0; i < templates.length; i++) {
            P7IconWorkshop.Spec template = templates[i];
            String name = names[i];
            LinearLayout tile = column();
            tile.setGravity(Gravity.CENTER);
            tile.setPadding(dp(7), dp(9), dp(7), dp(9));
            tile.setBackground(background(false));
            tile.setClickable(true);
            tile.setFocusable(true);
            tile.setContentDescription("Personalizar ícone " + name);
            tile.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
            tile.setAccessibilityDelegate(new View.AccessibilityDelegate() {
                @Override public void onInitializeAccessibilityNodeInfo(
                        View host, AccessibilityNodeInfo info) {
                    super.onInitializeAccessibilityNodeInfo(host, info);
                    info.setClassName(Button.class.getName());
                }
            });
            tile.setOnClickListener(v -> {
                if (a instanceof MainActivity)
                    P7IconWorkshop.open((MainActivity) a, template);
            });
            float effectiveScale = a.getResources().getConfiguration().fontScale
                * NegrescoTheme.FONT_SCALE;
            int tileWidth = effectiveScale >= 1.20f ? 136 : 106;
            tile.setMinimumHeight(dp(124));
            LinearLayout.LayoutParams tileParams = new LinearLayout.LayoutParams(
                dp(tileWidth), -2);
            tileParams.rightMargin = dp(7);
            row.addView(tile, tileParams);
            View preview = P7IconWorkshop.inlinePreview(a, template);
            preview.setImportantForAccessibility(
                View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            tile.addView(preview, new LinearLayout.LayoutParams(
                dp(70), dp(70)));
            TextView caption = label(name, 10, NegrescoTheme.TEXT, true);
            caption.setGravity(Gravity.CENTER);
            caption.setMaxLines(2);
            caption.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            LinearLayout.LayoutParams captionParams =
                new LinearLayout.LayoutParams(-1, -2);
            captionParams.topMargin = dp(7);
            tile.addView(caption, captionParams);
        }
        note("Escolha um modelo para personalizar e exportar seu próprio PNG.");
    }

    private void render(){
        for(int i=0;i<tabViews.length;i++){
            if(tabViews[i]==null)continue;
            boolean selected=i==activeTab;
            tabViews[i].setBackground(background(selected));
            tabViews[i].setTextColor(tabLabelColor(selected));
            tabViews[i].setSelected(selected);
            // Expose the real selection state to TalkBack instead of relying
            // only on blue text and a border.
            String tabName = tabViews[i].getText().toString();
            tabViews[i].setContentDescription(selected
                ? tabName + ", aba selecionada"
                : tabName + ", selecionar aba");
        }
        body.removeAllViews();
        if(activeTab==0){
            sectionHeader("Previews de Temas", () -> showCatalogDialog(0));
            startCards();
            for(int i=0;i<P7ThemeCatalog.count();i++){
                final int index=i;
                tile(P7ThemeCatalog.nameAt(i), P7ThemeCatalog.subtitleAt(i),
                    P7ThemeCatalog.previewAccentAt(i), selectedTheme==i,
                    0, P7ThemeCatalog.surfaceAt(i), P7ThemeCatalog.glowAt(i),
                    () -> {
                        selectedTheme = index;
                        render();
                        applySelectedTheme();
                    });
            }
            sectionHeader("Opções de Layout", () -> showCatalogDialog(1));
            startCards();
            String[] layouts = P7VisualCatalog.LAYOUT_NAMES;
            int[] layoutColors={0xff29acff,0xff8d9cb1,0xff7acfff,
                0xff27c99a,0xff9b6dff,0xffffa24a,0xff25bdd6,
                0xff1688ff,0xff27c99a,0xff9b6dff,0xffffa24a,0xff25bdd6};
            for(int i=0;i<layouts.length;i++){
                final int index=i;
                tile(layouts[i],"",layoutColors[i],selectedLayout==i,
                    1, i, false, () -> {
                        selectedLayout = index;
                        render();
                        confirmLayout();
                    });
            }
            creatorRow();
            sectionHeader("Presets de Aparência", () -> showCatalogDialog(2));
            startCards();
            String[] presets={"Dark OLED","Cyber Neon","Minimal","Glass","Retro"};
            int[] presetColors={0xff29acff,0xffde42ff,0xffcbd8f9,0xff56c9ff,0xffff518a};
            for(int i=0;i<presets.length;i++){
                final int index=i;
                tile(presets[i],"",presetColors[i],selectedPreset==i,
                    2, () -> {
                        selectedPreset = index;
                        render();
                        confirmPreset();
                    });
            }
            // The visible "Ver todos" control opens a real preset chooser.
        }else if(activeTab==1){
            heading("Opções de Layout");
            startCards();
            String[] modes=P7VisualCatalog.LAYOUT_NAMES;
            for(int i=0;i<modes.length;i++){
                final int choice=i;
                tile(modes[i], "Aplicável", 0xff29acff,
                    selectedLayout==i, 1, i, false, () -> {
                        selectedLayout = choice;
                        render();
                        confirmLayout();
                    });
            }
            actionCard("Aplicar layout selecionado",
                "Salvar a mudança da interface", -2);
            actionCard("Componentes e navegação","Rótulos da barra inferior",4);
            actionCard("Bordas dos cartões","Configurar o arredondamento",11);
        }else if(activeTab==2){
            heading("Criador de Ícones");
            iconTemplateGallery();
            actionCard("Abrir criador de ícones",
                "Escolher cores, símbolos e formato; exportar PNG 512×512", -4);
            note("Ícones locais em PNG ou SVG vetorial editável. Nenhum APK é alterado.");

        }else{
            heading("Logo Studio");
            liveLogoPreview();
            actionCard("Criar logo PNG", "Personalizar texto, cor e fundo; exportar PNG 1024×512", -5);
            note("No Logo Studio, também é possível exportar SVG vetorial editável.");
            actionCard("Editar nome e subtítulo", "Atualizar a identidade exibida na Home", 6);
            actionCard("Prévia de aparência", "Conferir as preferências atuais", 7);
        }
        heading("Personalização existente");
        actionCard("Cores e tons","Abrir paleta de destaques",1);
        actionCard("Exportar aparência","Salvar suas preferências em JSON",8);
        actionCard("Importar aparência","Aplicar preset validado",9);
        revealActiveTab();
    }
}
