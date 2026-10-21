package com.readroid.app;

import android.app.Activity;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
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
    private static final String[] THEME_NAMES =
        {"Negreco Blue", "Carbon Dark", "Matrix Green", "Sunset"};
    private void restoreCurrentTheme() {
        android.content.SharedPreferences prefs =
            a.getSharedPreferences("v3_personalizacao", Activity.MODE_PRIVATE);
        String theme = prefs.getString("theme", "oled");
        String accent = prefs.getString("accent", "blue");
        if ("graphite".equals(theme)) selectedTheme = 1;
        else if ("green".equals(accent)) selectedTheme = 2;
        else if ("orange".equals(accent)) selectedTheme = 3;
        else selectedTheme = 0;
    }
    private void applySelectedTheme() {
        new android.app.AlertDialog.Builder(a)
            .setTitle("Aplicar " + THEME_NAMES[selectedTheme] + "?")
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
    private final TextView[] tabViews=new TextView[4];

    private int dp(int n) { return NegrescoTheme.dp(a,n); }
    private TextView label(String text,int size,int color,boolean bold) {
        TextView t=new TextView(a);t.setText(text);t.setTextSize(size*NegrescoTheme.FONT_SCALE);
        t.setTextColor(color);if(bold)t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        return t;
    }
    private LinearLayout column() {
        LinearLayout l=new LinearLayout(a);l.setOrientation(LinearLayout.VERTICAL);return l;
    }
    private GradientDrawable background(boolean selected) {
        GradientDrawable d=new GradientDrawable();
        d.setColor(selected ? 0xff07294b : 0xff10171f);
        d.setCornerRadius(dp(12));
        d.setStroke(dp(1),selected?NegrescoTheme.ACCENT:0xff283846);
        return d;
    }
    public P7DesignStudio(Activity activity,LinearLayout container,Button[] appearanceActions) {
        a=activity;root=container;actions=appearanceActions;
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
        titles.addView(label("Design Studio",18,NegrescoTheme.TEXT,true));
        titles.addView(label("Personalize a aparência do seu app",12,NegrescoTheme.MUTED,false));
        HorizontalScrollView scroll=new HorizontalScrollView(a);
        scroll.setHorizontalScrollBarEnabled(false);
        LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(-1,dp(43));
        sp.topMargin=dp(12);root.addView(scroll,sp);
        LinearLayout tabs=new LinearLayout(a);tabs.setOrientation(LinearLayout.HORIZONTAL);
        scroll.addView(tabs);
        String[] names={"Temas","Layout","Ícones","Logotipo"};
        for(int i=0;i<names.length;i++) {
            final int index=i;
            TextView tab=label(names[i],11,NegrescoTheme.TEXT,false);
            tab.setGravity(Gravity.CENTER);
            tab.setMinWidth(dp(79));tab.setMinHeight(dp(36));
            tab.setPadding(dp(10),0,dp(10),0);
            LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,dp(36));
            p.rightMargin=dp(5);tabs.addView(tab,p);
            tabViews[i]=tab;
            tab.setOnClickListener(v->{activeTab=index;render();});
            tab.setTag(index);
        }
        body=column();root.addView(body);
        render();
    }
    private void heading(String title) {
        sectionHeader(title, null);
    }

    /** Compact section heading replaces the old full-width apply buttons. */
    private void sectionHeader(String title, Runnable onViewAll) {
        LinearLayout row = new LinearLayout(a);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(-1, dp(37));
        rp.topMargin = dp(6);
        body.addView(row, rp);
        TextView label = label(title, 15, NegrescoTheme.TEXT, true);
        row.addView(label, new LinearLayout.LayoutParams(0, -2, 1f));
        if (onViewAll != null) {
            TextView viewAll = label("Ver todos  ›", 11, NegrescoTheme.ACCENT, false);
            viewAll.setGravity(Gravity.CENTER);
            viewAll.setMinHeight(dp(37));
            viewAll.setPadding(dp(8), 0, dp(3), 0);
            viewAll.setClickable(true);
            viewAll.setFocusable(true);
            viewAll.setContentDescription("Ver todos: " + title);
            viewAll.setOnClickListener(v -> onViewAll.run());
            row.addView(viewAll);
        }
    }

    /** All preview families have a real chooser and explicit apply confirmation. */
    private void showCatalogDialog(int type) {
        final String[] names = type == 0 ? THEME_NAMES :
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
        final int width = kind == 2 ? 71 : (kind == 1 ? 100 : 100);
        final int previewHeight = kind == 2 ? 56 : (kind == 1 ? 69 : 88);
        LinearLayout card = column();
        card.setPadding(dp(5), dp(6), dp(5), dp(7));
        card.setMinimumWidth(dp(width));
        card.setBackground(background(selected));

        FrameLayout previewFrame = new FrameLayout(a);
        card.addView(previewFrame, new LinearLayout.LayoutParams(-1, dp(previewHeight)));
        P7ThemePreviewView miniature = new P7ThemePreviewView(a, accent, kind);
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
        title.setMaxLines(1);
        title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(-1, -2);
        tp.topMargin = dp(5);
        card.addView(title, tp);
        if (kind == 0 && !subtitle.isEmpty()) {
            TextView detail = label(subtitle, 9, NegrescoTheme.MUTED, false);
            detail.setMaxLines(1);
            detail.setEllipsize(android.text.TextUtils.TruncateAt.END);
            detail.setGravity(Gravity.CENTER_HORIZONTAL);
            card.addView(detail);
        }
        card.setClickable(true);
        card.setFocusable(true);
        card.setSelected(selected);
        card.setContentDescription(name +
            (selected ? ", prévia selecionada" : ", selecionar prévia"));
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
        if(index>=0 && index<actions.length && actions[index]!=null)
            actions[index].performClick();
    }
    private void actionCard(String name,String subtitle,int actionIndex) {
        TextView button=label(name+"  ↗\n"+subtitle,13,NegrescoTheme.TEXT,true);
        button.setPadding(dp(14),dp(12),dp(12),dp(12));
        button.setBackground(background(false));
        button.setMinHeight(dp(60));button.setClickable(true);button.setFocusable(true);
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
        preview.setContentDescription("Prévia da identidade visual atual");
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

        TextView brand = label("", 20, NegrescoTheme.TEXT, true);
        SpannableString style = new SpannableString(name);
        int blue = name.toLowerCase(Locale.ROOT).lastIndexOf("droid");
        if (blue >= 0) style.setSpan(new ForegroundColorSpan(NegrescoTheme.ACCENT),
            blue, blue + 5, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        brand.setText(style);
        brand.setMaxLines(2);
        names.addView(brand);

        TextView secondary = label(subtitle, 9, NegrescoTheme.MUTED, false);
        secondary.setMaxLines(2);
        secondary.setLetterSpacing(0.12f);
        names.addView(secondary);
        note("Prévia do cabeçalho atual. Não altera o ícone instalado nem assina APKs.");
    }

    /** The two creative cards occupy one row as in the approved reference. */
    private void creatorRow() {
        LinearLayout row = new LinearLayout(a);
        row.setOrientation(LinearLayout.HORIZONTAL);
        body.addView(row);
        creator(row, "◉", "Criador de Ícones",
            "Criar e exportar PNG", -4, true);
        creator(row, "N", "Logo Studio",
            "Personalizar nome e logo", 6, false);
    }

    private void creator(LinearLayout row, String symbol, String title,
            String subtitle, int actionIndex, boolean first) {
        LinearLayout card = new LinearLayout(a);
        card.setGravity(Gravity.CENTER_VERTICAL);
        card.setPadding(dp(10), dp(12), dp(8), dp(12));
        card.setBackground(background(false));
        LinearLayout.LayoutParams cell = new LinearLayout.LayoutParams(0, dp(88), 1f);
        cell.setMargins(0, 0, first ? dp(4) : 0, 0);
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
            tile.setOnClickListener(v -> {
                if (a instanceof MainActivity)
                    P7IconWorkshop.open((MainActivity) a, template);
            });
            LinearLayout.LayoutParams tileParams = new LinearLayout.LayoutParams(
                dp(106), dp(124));
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
            tabViews[i].setTextColor(selected?NegrescoTheme.ACCENT:NegrescoTheme.TEXT);
            tabViews[i].setSelected(selected);
        }
        body.removeAllViews();
        if(activeTab==0){
            sectionHeader("Previews de Temas", () -> showCatalogDialog(0));
            startCards();
            String[] themes={"Negreco Blue","Carbon Dark","Matrix Green","Sunset"};
            String[] subtitles={"Profissional","Minimalista","Hacker Style","Vibrante"};
            int[] colors={0xff29acff,0xffa8b3c0,0xff16d995,0xffff7080};
            for(int i=0;i<themes.length;i++){
                final int index=i;
                tile(themes[i],subtitles[i],colors[i],selectedTheme==i,
                    0, () -> {
                        selectedTheme = index;
                        render();
                        applySelectedTheme();
                    });
            }
            sectionHeader("Opções de Layout", () -> showCatalogDialog(1));
            startCards();
            String[] layouts={"Padrão","Compacto","Moderno"};
            int[] layoutColors={0xff29acff,0xff8d9cb1,0xff7acfff};
            for(int i=0;i<layouts.length;i++){
                final int index=i;
                tile(layouts[i],"",layoutColors[i],selectedLayout==i,
                    1, () -> {
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
            String[] modes={"Padrão","Compacto","Moderno"};
            for(int i=0;i<modes.length;i++){
                final int choice=i;
                tile(modes[i], "Aplicável", 0xff29acff,
                    selectedLayout==i, 1, () -> {
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
            note("Ícones originais gerados localmente. Nenhum APK é alterado.");

        }else{
            heading("Logo Studio");
            liveLogoPreview();
            actionCard("Editar nome e subtítulo", "Atualizar a identidade exibida na Home", 6);
            actionCard("Prévia de aparência", "Conferir as preferências atuais", 7);
        }
        heading("Personalização existente");
        actionCard("Cores e tons","Abrir paleta de destaques",1);
        actionCard("Exportar aparência","Salvar suas preferências em JSON",8);
        actionCard("Importar aparência","Aplicar preset validado",9);
    }
}
