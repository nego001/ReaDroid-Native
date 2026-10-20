package com.readroid.app;

import android.app.Activity;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Native, operational P7 Design Studio. Uses the existing appearance handlers. */
public final class P7DesignStudio {
    private final Activity a;
    private final LinearLayout root;
    private final Button[] actions;
    private int activeTab = 0;
    private int selectedTheme = 0;
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
        LinearLayout header=new LinearLayout(a);
        header.setGravity(Gravity.CENTER_VERTICAL);root.addView(header);
        NavGlyph palette=new NavGlyph(a,4);palette.setSelectedState(true);
        header.addView(palette,new LinearLayout.LayoutParams(dp(35),dp(35)));
        LinearLayout titles=column();
        LinearLayout.LayoutParams tp=new LinearLayout.LayoutParams(-1,-2);
        tp.leftMargin=dp(10);header.addView(titles,tp);
        titles.addView(label("Design Studio",22,NegrescoTheme.TEXT,true));
        titles.addView(label("Personalize a aparência do seu app",12,NegrescoTheme.MUTED,false));
        HorizontalScrollView scroll=new HorizontalScrollView(a);
        scroll.setHorizontalScrollBarEnabled(false);
        LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(-1,dp(56));
        sp.topMargin=dp(12);root.addView(scroll,sp);
        LinearLayout tabs=new LinearLayout(a);tabs.setOrientation(LinearLayout.HORIZONTAL);
        scroll.addView(tabs);
        String[] names={"Temas","Layout","Ícones","Logotipo"};
        for(int i=0;i<names.length;i++) {
            final int index=i;
            TextView tab=label(names[i],12,NegrescoTheme.TEXT,false);
            tab.setGravity(Gravity.CENTER);
            tab.setMinWidth(dp(82));tab.setMinHeight(dp(44));
            tab.setPadding(dp(10),0,dp(10),0);
            LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,dp(44));
            p.rightMargin=dp(5);tabs.addView(tab,p);
            tabViews[i]=tab;
            tab.setOnClickListener(v->{activeTab=index;render();});
            tab.setTag(index);
        }
        body=column();root.addView(body);
        render();
    }
    private void heading(String title) {
        TextView t=label(title,16,NegrescoTheme.TEXT,true);
        t.setPadding(0,dp(20),0,dp(12));body.addView(t);
    }
    private void tile(String name,String subtitle,int accent,boolean selected,
                      Runnable click) {
        LinearLayout card=column();
        card.setPadding(dp(12),dp(10),dp(12),dp(10));
        card.setMinimumWidth(dp(111));card.setBackground(background(selected));
        P7ThemePreviewView preview=new P7ThemePreviewView(a,accent);
        card.addView(preview,new LinearLayout.LayoutParams(-1,dp(95)));
        TextView title=label(name,12,NegrescoTheme.TEXT,true);card.addView(title);
        TextView detail=label(subtitle,10,NegrescoTheme.MUTED,false);card.addView(detail);
        card.setClickable(true);card.setFocusable(true);card.setContentDescription(name);
        card.setOnClickListener(v->click.run());
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(dp(116),-2);
        p.rightMargin=dp(8);
        cards.addView(card,p);
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
        if(index>=0 && index<actions.length && actions[index]!=null)
            actions[index].performClick();
    }
    private void actionCard(String name,String subtitle,int actionIndex) {
        TextView button=label(name+"  ↗\n"+subtitle,13,NegrescoTheme.TEXT,true);
        button.setPadding(dp(16),dp(18),dp(14),dp(18));
        button.setBackground(background(false));
        button.setMinHeight(dp(76));button.setClickable(true);button.setFocusable(true);
        button.setOnClickListener(v->open(actionIndex));
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);
        p.bottomMargin=dp(8);body.addView(button,p);
    }
    private void note(String message) {
        TextView text=label(message,11,NegrescoTheme.MUTED,false);
        text.setPadding(0,dp(7),0,dp(1));
        body.addView(text);
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
            heading("Previews de Temas");startCards();
            String[] themes={"Negreco Blue","Carbon Dark","Matrix Green","Sunset"};
            String[] subtitles={"Profissional","Minimalista","Hacker Style","Vibrante"};
            int[] colors={0xff29acff,0xffa8b3c0,0xff16d995,0xffff7080};
            for(int i=0;i<themes.length;i++){
                final int index=i;
                tile(themes[i],subtitles[i],colors[i],selectedTheme==i,
                    ()->{selectedTheme=index;render();});
            }
            note("Seleção de prévia. Para alterar as cores reais, use Cores e tons.");
            heading("Opções de Layout");startCards();
            String[] layouts={"Padrão","Compacto","Moderno"};
            int[] layoutColors={0xff29acff,0xff8d9cb1,0xff7acfff};
            for(int i=0;i<layouts.length;i++){
                final int index=i;
                tile(layouts[i],"Prévia",layoutColors[i],selectedLayout==i,
                    ()->{selectedLayout=index;render();});
            }
            note("Layout selecionado apenas nesta prévia. O ajuste real de densidade fica na aba Layout.");
            heading("Ferramentas criativas");
            actionCard("Criador de Ícones","Editor em desenvolvimento",7);
            actionCard("Logo Studio","Identidade visual e prévia",6);
            heading("Presets de Aparência");startCards();
            String[] presets={"Dark OLED","Cyber Neon","Minimal","Glass","Retro"};
            int[] presetColors={0xff29acff,0xffde42ff,0xffcbd8f9,0xff56c9ff,0xffff518a};
            for(int i=0;i<presets.length;i++){
                final int index=i;
                tile(presets[i],"Prévia",presetColors[i],selectedPreset==i,
                    ()->{selectedPreset=index;render();});
            }
            note("Presets de exemplo: ainda não são arquivos salvos nem estilos aplicados.");
        }else if(activeTab==1){
            heading("Opções de Layout");
            actionCard("Padrão / Compacto","Alterar densidade real da interface",3);
            actionCard("Componentes e navegação","Rótulos da barra inferior",4);
            actionCard("Bordas dos cartões","Configurar o arredondamento",11);
        }else if(activeTab==2){
            heading("Criador de Ícones");
            actionCard("Prévia visual","A ferramenta de edição de ícones ainda não está pronta",7);
        }else{
            heading("Logo Studio");
            actionCard("Identidade da interface","Configurar o nome e subtítulo",6);
            actionCard("Prévia da logo","Conferir antes de aplicar",7);
        }
        heading("Personalização existente");
        actionCard("Cores e tons","Abrir paleta de destaques",1);
        actionCard("Exportar aparência","Salvar suas preferências em JSON",8);
        actionCard("Importar aparência","Aplicar preset validado",9);
    }
}
