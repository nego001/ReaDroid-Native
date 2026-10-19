package com.readroid.app;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.net.Uri;
import android.graphics.Color;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

public class MainActivity extends Activity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private TextView output;
    private Button share;
    private Button ai;
    private Button project;
    private Button editExport;
    private Button reviewChanges;
    private Button rebuild;
    private Button signatureInfo;
    private Button signingGuide;
    private Button localIdentity;
    private Button signingTest;
    private static final int REQUEST_EXPORT_APK = 2;
    private static final int REQUEST_COMPARE_APK = 3;
    private static final int REQUEST_EXPORT_APPEARANCE = 41;
    private static final int REQUEST_IMPORT_APPEARANCE = 42;
    private JSONObject report;
    private File currentApk;
    private ExplorerView explorerView;
    private LinearLayout homeSection;
    private LinearLayout filesSection;
    private LinearLayout securitySection;
    private LinearLayout buildSection;
    private LinearLayout aiSection;
    private TextView[] navigationItems;
    private NavGlyph[] navigationIcons;
    private TextView apkSummary;
    private TextView projectMetrics;
    private ScrollView contentScroll;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        NegrescoTheme.apply(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(NegrescoTheme.dp(this, NegrescoTheme.COMPACT ? 12 : 20), NegrescoTheme.dp(this, NegrescoTheme.COMPACT ? 18 : 34), NegrescoTheme.dp(this, NegrescoTheme.COMPACT ? 12 : 20), NegrescoTheme.dp(this, NegrescoTheme.COMPACT ? 12 : 24));
        root.setBackgroundColor(NegrescoTheme.BACKGROUND);
        LinearLayout shell = new LinearLayout(this);
        shell.setOrientation(LinearLayout.VERTICAL);
        shell.setBackgroundColor(NegrescoTheme.BACKGROUND);
        contentScroll = new ScrollView(this);
        contentScroll.setFillViewport(true);
        contentScroll.addView(root);
        shell.addView(contentScroll, new LinearLayout.LayoutParams(-1, 0, 1f));
        LinearLayout nav = new LinearLayout(this);
        nav.setOrientation(LinearLayout.HORIZONTAL);
        nav.setPadding(NegrescoTheme.dp(this, 6), NegrescoTheme.dp(this, 7), NegrescoTheme.dp(this, 6), NegrescoTheme.dp(this, 8));
        nav.setBackground(NegrescoTheme.studioCard(this, false));
        shell.addView(nav);
        setContentView(shell);

        android.content.SharedPreferences appearance =
            getSharedPreferences("v3_personalizacao", MODE_PRIVATE);
        String displayName = appearance.getString("display_name", "NEGRESCODROID");
        String displaySubtitle = appearance.getString("display_subtitle", "APK ENGINEERING STUDIO");
        LinearLayout brandRow = new LinearLayout(this);
        brandRow.setGravity(android.view.Gravity.CENTER_VERTICAL);
        brandRow.setPadding(0, NegrescoTheme.dp(this, 2), 0, NegrescoTheme.dp(this, 14));
        NavGlyph brandMark = new NavGlyph(this, 2);
        brandMark.setSelectedState(true);
        brandRow.addView(brandMark, new LinearLayout.LayoutParams(
            NegrescoTheme.dp(this, 38), NegrescoTheme.dp(this, 38)));
        LinearLayout brandText = new LinearLayout(this);
        brandText.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams brandParams = new LinearLayout.LayoutParams(0, -2, 1f);
        brandParams.leftMargin = NegrescoTheme.dp(this, 10);
        brandRow.addView(brandText, brandParams);
        TextView title = new TextView(this);
        android.text.SpannableString brandName = new android.text.SpannableString(displayName);
        int droid = displayName.toLowerCase(java.util.Locale.ROOT).lastIndexOf("droid");
        if (droid >= 0) brandName.setSpan(new android.text.style.ForegroundColorSpan(NegrescoTheme.ACCENT),
            droid, droid + 5, android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        title.setText(brandName);
        title.setTextColor(NegrescoTheme.TEXT);
        title.setTextSize(21 * NegrescoTheme.FONT_SCALE);
        title.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        title.setMaxLines(2);
        brandText.addView(title);
        TextView brandSubtitleView = new TextView(this);
        brandSubtitleView.setText(displaySubtitle);
        brandSubtitleView.setTextColor(NegrescoTheme.MUTED);
        brandSubtitleView.setTextSize(9.5f * NegrescoTheme.FONT_SCALE);
        brandSubtitleView.setLetterSpacing(0.13f);
        brandSubtitleView.setMaxLines(2);
        brandText.addView(brandSubtitleView);
        root.addView(brandRow);
        String[] tabs = {"Início", "Arquivos", "Construir", "Segurança", "IA"};
        boolean showNavLabels = getSharedPreferences("v3_personalizacao", MODE_PRIVATE)
            .getBoolean("nav_labels", true);
        navigationItems = new TextView[tabs.length];
        navigationIcons = new NavGlyph[tabs.length];
        for (int index = 0; index < tabs.length; index++) {
            final int target = index;
            LinearLayout tabContainer = new LinearLayout(this);
            tabContainer.setOrientation(LinearLayout.VERTICAL);
            tabContainer.setGravity(android.view.Gravity.CENTER);
            nav.addView(tabContainer, new LinearLayout.LayoutParams(0, NegrescoTheme.dp(this, 62), 1f));
            NavGlyph glyph = new NavGlyph(this, index);
            tabContainer.addView(glyph, new LinearLayout.LayoutParams(NegrescoTheme.dp(this, 27), NegrescoTheme.dp(this, 27)));
            navigationIcons[index] = glyph;
            TextView label = new TextView(this);
            label.setText(tabs[index]);
            label.setGravity(android.view.Gravity.CENTER);
            label.setTextSize(10 * NegrescoTheme.FONT_SCALE);
            label.setVisibility(showNavLabels ? View.VISIBLE : View.GONE);
            label.setTextColor(NegrescoTheme.MUTED);
            tabContainer.addView(label);
            navigationItems[index] = label;
            tabContainer.setContentDescription("Abrir seção " + tabs[index]);
            tabContainer.setOnClickListener(v -> showSection(target));
        }
        homeSection = section(root);
        filesSection = section(root);
        buildSection = section(root);
        securitySection = section(root);
        aiSection = section(root);

        TextView customizationTitle = new TextView(this);
        customizationTitle.setText("V3 • PERSONALIZAÇÃO");
        customizationTitle.setTextColor(NegrescoTheme.ACCENT);
        customizationTitle.setTextSize(12);
        customizationTitle.setPadding(0, NegrescoTheme.dp(this, 18), 0, NegrescoTheme.dp(this, 8));
        homeSection.addView(customizationTitle);
        customizationTitle.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        customizationTitle.setLetterSpacing(0.08f);
        TextView customizationHint = new TextView(this);
        customizationHint.setText("Deixe o estúdio com a sua cara");
        customizationHint.setTextSize(13 * NegrescoTheme.FONT_SCALE);
        customizationHint.setTextColor(NegrescoTheme.MUTED);
        customizationHint.setPadding(0, 0, 0, NegrescoTheme.dp(this, 12));
        homeSection.addView(customizationHint);
        customizationHint.setText("Ajuste temas, cores e identidade no painel abaixo.");
        LinearLayout personalizationGroup = new LinearLayout(this);
        personalizationGroup.setOrientation(LinearLayout.VERTICAL);
        homeSection.addView(personalizationGroup);
        Button themePicker = NegrescoTheme.action(this, "Tema visual", false);
        personalizationGroup.addView(themePicker);
        themePicker.setOnClickListener(v -> {
            String[] options = {"OLED preto", "Grafite", "Claro"};
            String[] values = {"oled", "graphite", "light"};
            String current = getSharedPreferences("v3_personalizacao", MODE_PRIVATE).getString("theme", "oled");
            int selected = java.util.Arrays.asList(values).indexOf(current);
            new android.app.AlertDialog.Builder(this).setTitle("Tema visual")
                .setSingleChoiceItems(options, Math.max(0, selected), (dialog, which) -> {
                    getSharedPreferences("v3_personalizacao", MODE_PRIVATE).edit()
                        .putString("theme", values[which]).apply();
                    dialog.dismiss();
                    recreate();
                }).setNegativeButton("Cancelar", null).show();
        });
        Button accentPicker = NegrescoTheme.action(this, "Cor de destaque", false);
        personalizationGroup.addView(accentPicker);
        accentPicker.setOnClickListener(v -> {
            String[] options = {"Azul", "Roxo", "Verde", "Laranja", "Minha cor (HEX)"};
            String[] values = {"blue", "purple", "green", "orange", "custom"};
            String current = getSharedPreferences("v3_personalizacao", MODE_PRIVATE).getString("accent", "blue");
            int selected = java.util.Arrays.asList(values).indexOf(current);
            new android.app.AlertDialog.Builder(this).setTitle("Cor de destaque")
                .setSingleChoiceItems(options, Math.max(0, selected), (dialog, which) -> {
                    dialog.dismiss();
                    if (which != 4) {
                        getSharedPreferences("v3_personalizacao", MODE_PRIVATE).edit()
                            .putString("accent", values[which]).apply();
                        recreate();
                        return;
                    }
                    android.widget.EditText colorInput = new android.widget.EditText(this);
                    colorInput.setSingleLine(true);
                    colorInput.setHint("#1688FF");
                    colorInput.setText(getSharedPreferences("v3_personalizacao", MODE_PRIVATE)
                        .getString("custom_accent", "#1688FF"));
                    colorInput.setFilters(new android.text.InputFilter[]{
                        new android.text.InputFilter.LengthFilter(7)});
                    new android.app.AlertDialog.Builder(this)
                        .setTitle("Cor personalizada")
                        .setMessage("Digite um código hexadecimal com seis dígitos, por exemplo #1688FF.")
                        .setView(colorInput)
                        .setPositiveButton("Aplicar", (d, w) -> {
                            String color = colorInput.getText().toString().trim();
                            if (!color.matches("#[0-9a-fA-F]{6}")) {
                                new android.app.AlertDialog.Builder(this)
                                    .setTitle("Cor inválida")
                                    .setMessage("Use o formato #RRGGBB com seis dígitos.")
                                    .setPositiveButton("OK", null).show();
                                return;
                            }
                            getSharedPreferences("v3_personalizacao", MODE_PRIVATE).edit()
                                .putString("accent", "custom").putString("custom_accent", color)
                                .apply();
                            recreate();
                        }).setNegativeButton("Cancelar", null).show();
                }).setNegativeButton("Cancelar", null).show();
        });
        Button textScale = NegrescoTheme.action(this, "Tamanho do texto", false);
        personalizationGroup.addView(textScale);
        textScale.setOnClickListener(v -> {
            String[] labels = {"Pequeno (90%)", "Padrão (100%)", "Grande (115%)", "Muito grande (130%)"};
            int[] values = {90, 100, 115, 130};
            int current = getSharedPreferences("v3_personalizacao", MODE_PRIVATE).getInt("font_percent", 100);
            int selected = 1;
            for (int i = 0; i < values.length; i++) if (values[i] == current) selected = i;
            new android.app.AlertDialog.Builder(this).setTitle("Tamanho do texto")
                .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                    getSharedPreferences("v3_personalizacao", MODE_PRIVATE).edit()
                        .putInt("font_percent", values[which]).apply();
                    dialog.dismiss();
                    recreate();
                }).setNegativeButton("Cancelar", null).show();
        });
        Button densityPicker = NegrescoTheme.action(this, "Espaçamento da interface", false);
        personalizationGroup.addView(densityPicker);
        densityPicker.setOnClickListener(v -> {
            boolean compact = getSharedPreferences("v3_personalizacao", MODE_PRIVATE).getBoolean("compact", false);
            new android.app.AlertDialog.Builder(this).setTitle("Espaçamento da interface")
                .setSingleChoiceItems(new String[]{"Confortável", "Compacto"}, compact ? 1 : 0,
                    (dialog, which) -> {
                        getSharedPreferences("v3_personalizacao", MODE_PRIVATE).edit()
                            .putBoolean("compact", which == 1).apply();
                        dialog.dismiss();
                        recreate();
                    }).setNegativeButton("Cancelar", null).show();
        });
        Button navLabels = NegrescoTheme.action(this, "Rótulos da navegação", false);
        personalizationGroup.addView(navLabels);
        navLabels.setOnClickListener(v -> {
            boolean visible = getSharedPreferences("v3_personalizacao", MODE_PRIVATE)
                .getBoolean("nav_labels", true);
            new android.app.AlertDialog.Builder(this).setTitle("Rótulos da navegação")
                .setSingleChoiceItems(new String[]{"Mostrar nomes e ícones", "Somente ícones"},
                    visible ? 0 : 1, (dialog, which) -> {
                        getSharedPreferences("v3_personalizacao", MODE_PRIVATE).edit()
                            .putBoolean("nav_labels", which == 0).apply();
                        dialog.dismiss();
                        recreate();
                    }).setNegativeButton("Cancelar", null).show();
        });
        Button favoriteShortcut = NegrescoTheme.action(this, "Atalho favorito", false);
        personalizationGroup.addView(favoriteShortcut);
        favoriteShortcut.setOnClickListener(v -> {
            String[] names = {"Arquivos", "Construir", "Segurança", "IA"};
            int current = getSharedPreferences("v3_personalizacao", MODE_PRIVATE)
                .getInt("favorite_tab", 1);
            new android.app.AlertDialog.Builder(this).setTitle("Primeiro atalho da tela inicial")
                .setSingleChoiceItems(names, Math.max(0, Math.min(3, current - 1)),
                    (dialog, which) -> {
                        getSharedPreferences("v3_personalizacao", MODE_PRIVATE).edit()
                            .putInt("favorite_tab", which + 1).apply();
                        dialog.dismiss();
                        recreate();
                    }).setNegativeButton("Cancelar", null).show();
        });
        Button identityPicker = NegrescoTheme.action(this, "Identidade da tela inicial", false);
        personalizationGroup.addView(identityPicker);
        identityPicker.setOnClickListener(v -> {
            android.widget.LinearLayout form = new android.widget.LinearLayout(this);
            form.setOrientation(android.widget.LinearLayout.VERTICAL);
            form.setPadding(NegrescoTheme.dp(this, 20), NegrescoTheme.dp(this, 8),
                NegrescoTheme.dp(this, 20), NegrescoTheme.dp(this, 8));
            android.widget.EditText nameInput = new android.widget.EditText(this);
            nameInput.setSingleLine(true);
            nameInput.setHint("Nome exibido");
            nameInput.setInputType(android.text.InputType.TYPE_CLASS_TEXT
                | android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
            nameInput.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(30)});
            nameInput.setText(getSharedPreferences("v3_personalizacao", MODE_PRIVATE)
                .getString("display_name", "NEGRESCODROID"));
            form.addView(nameInput);
            android.widget.EditText subtitleInput = new android.widget.EditText(this);
            subtitleInput.setSingleLine(true);
            subtitleInput.setHint("Subtítulo");
            subtitleInput.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(48)});
            subtitleInput.setText(getSharedPreferences("v3_personalizacao", MODE_PRIVATE)
                .getString("display_subtitle", "APK ENGINEERING STUDIO"));
            form.addView(subtitleInput);
            new android.app.AlertDialog.Builder(this)
                .setTitle("Identidade visual")
                .setMessage("Altera somente o cabeçalho do aplicativo. Não muda o nome instalado nem a assinatura.")
                .setView(form)
                .setPositiveButton("Salvar", (dialog, which) -> {
                    String name = nameInput.getText().toString().trim();
                    String subtitle = subtitleInput.getText().toString().trim();
                    if (name.isEmpty()) name = "NEGRESCODROID";
                    if (subtitle.isEmpty()) subtitle = "APK ENGINEERING STUDIO";
                    getSharedPreferences("v3_personalizacao", MODE_PRIVATE).edit()
                        .putString("display_name", name)
                        .putString("display_subtitle", subtitle).apply();
                    recreate();
                })
                .setNegativeButton("Cancelar", null).show();
        });
        Button appearancePreview = NegrescoTheme.action(this, "Prévia da aparência", false);
        personalizationGroup.addView(appearancePreview);
        appearancePreview.setOnClickListener(v -> {
            android.widget.LinearLayout preview = new android.widget.LinearLayout(this);
            preview.setOrientation(android.widget.LinearLayout.VERTICAL);
            preview.setPadding(NegrescoTheme.dp(this, 20), NegrescoTheme.dp(this, 20),
                NegrescoTheme.dp(this, 20), NegrescoTheme.dp(this, 20));
            preview.setBackgroundColor(NegrescoTheme.BACKGROUND);
            TextView previewTitle = NegrescoTheme.heading(this,
                getSharedPreferences("v3_personalizacao", MODE_PRIVATE)
                    .getString("display_name", "NEGRESCODROID"),
                getSharedPreferences("v3_personalizacao", MODE_PRIVATE)
                    .getString("display_subtitle", "APK ENGINEERING STUDIO"));
            preview.addView(previewTitle);
            TextView previewCard = new TextView(this);
            previewCard.setText("PROJETO DE EXEMPLO\n\nArquivos  •  Construção  •  Segurança");
            previewCard.setTextSize(14 * NegrescoTheme.FONT_SCALE);
            previewCard.setTextColor(NegrescoTheme.TEXT);
            previewCard.setPadding(NegrescoTheme.dp(this, 16), NegrescoTheme.dp(this, 16),
                NegrescoTheme.dp(this, 16), NegrescoTheme.dp(this, 16));
            previewCard.setBackground(NegrescoTheme.panel(this));
            preview.addView(previewCard);
            Button previewButton = NegrescoTheme.action(this, "Ação principal de exemplo", true);
            preview.addView(previewButton);
            previewButton.setEnabled(false);
            new android.app.AlertDialog.Builder(this)
                .setTitle("Prévia do tema atual")
                .setView(preview)
                .setPositiveButton("Fechar", null).show();
        });
        Button exportAppearance = NegrescoTheme.action(this, "Exportar personalização", false);
        personalizationGroup.addView(exportAppearance);
        exportAppearance.setOnClickListener(v -> {
            Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("application/json");
            intent.putExtra(Intent.EXTRA_TITLE, "negrescodroid-v3-visual.json");
            startActivityForResult(intent, REQUEST_EXPORT_APPEARANCE);
        });
        Button importAppearance = NegrescoTheme.action(this, "Importar personalização", false);
        personalizationGroup.addView(importAppearance);
        importAppearance.setOnClickListener(v -> {
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("application/json");
            startActivityForResult(intent, REQUEST_IMPORT_APPEARANCE);
        });
        Button glowPicker = NegrescoTheme.action(this, "Efeito neon dos cartões", false);
        personalizationGroup.addView(glowPicker);
        glowPicker.setOnClickListener(v -> {
            boolean active = getSharedPreferences("v3_personalizacao", MODE_PRIVATE)
                .getBoolean("studio_glow", true);
            new android.app.AlertDialog.Builder(this).setTitle("Efeito neon dos cartões")
                .setSingleChoiceItems(new String[]{"Neon suave", "Minimalista sem brilho"},
                    active ? 0 : 1, (dialog, which) -> {
                        getSharedPreferences("v3_personalizacao", MODE_PRIVATE).edit()
                            .putBoolean("studio_glow", which == 0).apply();
                        dialog.dismiss();
                        recreate();
                    }).setNegativeButton("Cancelar", null).show();
        });
        Button cornersPicker = NegrescoTheme.action(this, "Cantos dos cartões", false);
        personalizationGroup.addView(cornersPicker);
        cornersPicker.setOnClickListener(v -> {
            int[] values = {12, 18, 26};
            int current = getSharedPreferences("v3_personalizacao", MODE_PRIVATE)
                .getInt("card_radius", 18);
            int selected = current == 12 ? 0 : current == 26 ? 2 : 1;
            new android.app.AlertDialog.Builder(this).setTitle("Cantos dos cartões")
                .setSingleChoiceItems(new String[]{"Discretos", "Equilibrados", "Arredondados"},
                    selected, (dialog, which) -> {
                        getSharedPreferences("v3_personalizacao", MODE_PRIVATE).edit()
                            .putInt("card_radius", values[which]).apply();
                        dialog.dismiss();
                        recreate();
                    }).setNegativeButton("Cancelar", null).show();
        });
        Button resetAppearance = NegrescoTheme.action(this, "Restaurar aparência", false);
        personalizationGroup.addView(resetAppearance);
        resetAppearance.setOnClickListener(v -> new android.app.AlertDialog.Builder(this)
            .setTitle("Restaurar aparência?")
            .setMessage("Os temas e as cores voltarão ao padrão. Seus projetos não serão alterados.")
            .setPositiveButton("Restaurar", (dialog, which) -> {
                getSharedPreferences("v3_personalizacao", MODE_PRIVATE).edit().clear().apply();
                recreate();
            }).setNegativeButton("Cancelar", null).show());

        Button togglePersonalization = NegrescoTheme.action(this, "Personalização  ▾", false);
        homeSection.addView(togglePersonalization);
        homeSection.removeView(personalizationGroup);
        homeSection.addView(personalizationGroup);
        personalizationGroup.setVisibility(View.GONE);
        togglePersonalization.setOnClickListener(v -> {
            boolean expand = personalizationGroup.getVisibility() != View.VISIBLE;
            personalizationGroup.setVisibility(expand ? View.VISIBLE : View.GONE);
            togglePersonalization.setText(expand ? "Personalização  ▴" : "Personalização  ▾");
        });

        TextView otaTitle = new TextView(this);
        otaTitle.setText("ATUALIZAÇÕES DO APLICATIVO");
        otaTitle.setTextColor(NegrescoTheme.ACCENT);
        otaTitle.setTextSize(12);
        otaTitle.setPadding(0, NegrescoTheme.dp(this, 18), 0, NegrescoTheme.dp(this, 8));
        homeSection.addView(otaTitle);
        TextView otaStatus = new TextView(this);
        otaStatus.setTextColor(NegrescoTheme.TEXT);
        otaStatus.setTextSize(13);
        otaStatus.setPadding(NegrescoTheme.dp(this, 14), NegrescoTheme.dp(this, 14),
            NegrescoTheme.dp(this, 14), NegrescoTheme.dp(this, 14));
        otaStatus.setBackground(NegrescoTheme.panel(this));
        homeSection.addView(otaStatus);
        Button otaChannel = NegrescoTheme.action(this, "Selecionar canal OTA", false);
        homeSection.addView(otaChannel);
        Runnable refreshOta = () -> {
            String channel = getPreferences(MODE_PRIVATE).getString("ota_channel", "stable");
            String version = "0.1.0";
            try {
                version = getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
            } catch (Exception ignored) { }
            otaStatus.setText("Versão instalada: " + version
                + "\nCanal: " + (channel.equals("beta") ? "Beta" : "Estável")
                + "\nOTA: em desenvolvimento. Nenhum download ou instalação automática.");
        };
        otaChannel.setOnClickListener(v -> new android.app.AlertDialog.Builder(this)
            .setTitle("Canal de atualizações")
            .setSingleChoiceItems(new String[]{"Estável", "Beta"},
                getPreferences(MODE_PRIVATE).getString("ota_channel", "stable").equals("beta") ? 1 : 0,
                (dialog, selected) -> {
                    getPreferences(MODE_PRIVATE).edit()
                        .putString("ota_channel", selected == 1 ? "beta" : "stable").apply();
                    refreshOta.run();
                    dialog.dismiss();
                })
            .setNegativeButton("Cancelar", null).show());
        refreshOta.run();

        Button otaCheck = NegrescoTheme.action(this, "Verificar atualizações", true);
        homeSection.addView(otaCheck);
        otaCheck.setOnClickListener(v -> {
            String selectedOtaChannel = getPreferences(MODE_PRIVATE).getString("ota_channel", "stable");
            if (!OtaConfig.isConfigured(selectedOtaChannel)) {
                new android.app.AlertDialog.Builder(this)
                    .setTitle("OTA assinada ainda não configurada")
                    .setMessage("O canal " + (selectedOtaChannel.equals("beta") ? "Beta" : "Estável")
                        + " ainda precisa de um manifesto assinado e de uma chave pública confiável. "
                        + "Você pode consultar as versões oficiais no GitHub; nenhum APK será baixado automaticamente.")
                    .setPositiveButton("Ver Releases", (dialog, which) -> {
                        try {
                            startActivity(new Intent(Intent.ACTION_VIEW,
                                Uri.parse("https://github.com/nego001/ReaDroid-Native/releases")));
                        } catch (android.content.ActivityNotFoundException error) {
                            new android.app.AlertDialog.Builder(this)
                                .setMessage("Nenhum navegador disponível para abrir o GitHub.")
                                .setPositiveButton("OK", null).show();
                        }
                    })
                    .setNegativeButton("Fechar", null).show();
                return;
            }
            otaCheck.setEnabled(false);
            otaStatus.setText("Verificando atualizações assinadas...");
            executor.execute(() -> {
                try {
                    String channel = getPreferences(MODE_PRIVATE).getString("ota_channel", "stable");
                    OtaRelease release = OtaUpdatePipeline.check(this,
                        OtaConfig.endpointFor(channel), OtaConfig.TRUSTED_RELEASE_PUBLIC_KEY, channel);
                    runOnUiThread(() -> {
                        otaCheck.setEnabled(true);
                        refreshOta.run();
                        if (release == null) {
                            new android.app.AlertDialog.Builder(this)
                                .setTitle("Nenhuma atualização")
                                .setMessage("Não há uma versão mais recente no canal selecionado.")
                                .setPositiveButton("OK", null).show();
                        } else {
                            new android.app.AlertDialog.Builder(this)
                                .setTitle("Nova versão: " + release.versionName)
                                .setMessage("Versão " + release.versionCode + "\nCanal: "
                                    + release.channel + "\nTamanho: " + release.sizeBytes
                                    + " bytes\n\n" + release.notes
                                    + "\n\nO download pode ser verificado. A instalação ainda não está disponível.")
                                .setPositiveButton("Baixar e verificar", (dialog, which) ->
                                    confirmOtaDownload(release))
                                .setNegativeButton("Cancelar", null).show();
                        }
                    });
                } catch (Exception error) {
                    String message = error.getMessage();
                    runOnUiThread(() -> {
                        otaCheck.setEnabled(true);
                        refreshOta.run();
                        new android.app.AlertDialog.Builder(this)
                            .setTitle("Falha na verificação OTA")
                            .setMessage(message == null ? "Erro desconhecido" : message)
                            .setPositiveButton("OK", null).show();
                    });
                }
            });
        });
        Button choose = NegrescoTheme.action(this, "ABRIR APK", true);
        choose.setText("Selecionar APK");
        homeSection.addView(choose);
        choose.setOnClickListener(v -> {
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("*/*");
            startActivityForResult(intent, 1);
        });

        output = new TextView(this);
        output.setText("Selecione um APK para começar.");
        output.setTextColor(NegrescoTheme.MUTED);
        output.setTextSize(15);
        output.setTextIsSelectable(true);
        output.setPadding(NegrescoTheme.dp(this, 12), NegrescoTheme.dp(this, 16), NegrescoTheme.dp(this, 12), NegrescoTheme.dp(this, 16));
        output.setBackground(NegrescoTheme.panel(this));
        apkSummary = new TextView(this);
        apkSummary.setText("NENHUM PROJETO ABERTO\n\nSelecione um APK para visualizar seus detalhes.");
        apkSummary.setTextColor(NegrescoTheme.TEXT);
        apkSummary.setTextSize(15);
        apkSummary.setPadding(NegrescoTheme.dp(this, 20), NegrescoTheme.dp(this, 24), NegrescoTheme.dp(this, 20), NegrescoTheme.dp(this, 24));
        apkSummary.setBackground(NegrescoTheme.panel(this));
        homeSection.addView(apkSummary);
        projectMetrics = new TextView(this);
        projectMetrics.setText("ESTRUTURA   •   Aguardando APK");
        projectMetrics.setTextColor(NegrescoTheme.MUTED);
        projectMetrics.setTextSize(13);
        projectMetrics.setPadding(NegrescoTheme.dp(this, 12), NegrescoTheme.dp(this, 14),
            NegrescoTheme.dp(this, 12), NegrescoTheme.dp(this, 14));
        homeSection.addView(projectMetrics);

        TextView shortcutHint = new TextView(this);
        shortcutHint.setText("Continue de onde parou");
        shortcutHint.setTextColor(NegrescoTheme.MUTED);
        shortcutHint.setTextSize(13 * NegrescoTheme.FONT_SCALE);
        shortcutHint.setPadding(0, 0, 0, NegrescoTheme.dp(this, 8));
        TextView shortcutsTitle = new TextView(this);
        shortcutsTitle.setText("ACESSO RÁPIDO");
        shortcutsTitle.setTextColor(NegrescoTheme.ACCENT);
        shortcutsTitle.setTextSize(12);
        shortcutsTitle.setPadding(0, NegrescoTheme.dp(this, 18), 0, NegrescoTheme.dp(this, 8));
        homeSection.addView(shortcutsTitle);
        homeSection.addView(shortcutHint);
        LinearLayout quickGrid = new LinearLayout(this);
        quickGrid.setOrientation(LinearLayout.VERTICAL);
        homeSection.addView(quickGrid);
        String[] quickLabels = {"Arquivos", "Construir", "Segurança", "IA"};
        String[] quickSubtitles = {
            "Explore e organize arquivos APK",
            "Revise e exporte alterações",
            "Verifique certificados e riscos",
            "Compartilhe análises com IA"
        };
        int[] quickTargets = {1, 2, 3, 4};
        int favorite = getSharedPreferences("v3_personalizacao", MODE_PRIVATE).getInt("favorite_tab", 1);
        if (favorite < 1 || favorite > 4) favorite = 1;
        for (int rowIndex = 0; rowIndex < 2; rowIndex++) {
            LinearLayout shortcutRow = new LinearLayout(this);
            shortcutRow.setOrientation(LinearLayout.HORIZONTAL);
            quickGrid.addView(shortcutRow);
            for (int column = 0; column < 2; column++) {
                int index = rowIndex * 2 + column;
                final int target = quickTargets[index];
                LinearLayout tile = StudioDashboard.quickTile(this, quickLabels[index],
                    quickSubtitles[index], target, target == favorite,
                    v -> showSection(target));
                LinearLayout.LayoutParams tileParams = new LinearLayout.LayoutParams(
                    0, NegrescoTheme.dp(this, NegrescoTheme.COMPACT ? 122 : 142), 1f);
                tileParams.setMargins(column == 0 ? 0 : NegrescoTheme.dp(this, 5), 0,
                    column == 0 ? NegrescoTheme.dp(this, 5) : 0, NegrescoTheme.dp(this, 10));
                shortcutRow.addView(tile, tileParams);
            }
        }

        TextView detailsTitle = new TextView(this);
        detailsTitle.setText("RELATÓRIO TÉCNICO");
        detailsTitle.setTextSize(12);
        detailsTitle.setTextColor(NegrescoTheme.ACCENT);
        detailsTitle.setPadding(0, NegrescoTheme.dp(this, 22), 0, NegrescoTheme.dp(this, 8));
        homeSection.addView(detailsTitle);
        homeSection.addView(output);

        explorerView = new ExplorerView(this, filesSection);
        Button compare = NegrescoTheme.action(this, "Comparar com outro APK", false);
        filesSection.addView(compare);
        compare.setOnClickListener(v -> {
            if (currentApk == null) {
                new android.app.AlertDialog.Builder(this)
                    .setMessage("Abra primeiro o APK principal.")
                    .setPositiveButton("OK", null).show();
                return;
            }
            Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            pick.addCategory(Intent.CATEGORY_OPENABLE);
            pick.setType("*/*");
            startActivityForResult(pick, REQUEST_COMPARE_APK);
        });

        ai = NegrescoTheme.action(this, "", false);
        ai.setText("Analisar com ChatGPT / IA");
        ai.setEnabled(false);
        aiSection.addView(ai);
        ai.setOnClickListener(v -> AiBridge.shareReport(this, report));

        project = NegrescoTheme.action(this, "", false);
        project.setText("Criar minha versão");
        project.setEnabled(false);
        homeSection.addView(project);
        project.setOnClickListener(v -> ProjectBrief.create(this, report));

        reviewChanges = NegrescoTheme.action(this, "Revisar alterações pendentes", true);
        buildSection.addView(reviewChanges);
        reviewChanges.setOnClickListener(v -> reviewEditPlan());
        editExport = NegrescoTheme.action(this, "", false);
        editExport.setText("Compartilhar plano de alterações");
        buildSection.addView(editExport);
        editExport.setOnClickListener(v -> {
            try {
                String content = explorerView.getEditPlan().toJson().toString(2);
                Intent send = new Intent(Intent.ACTION_SEND);
                send.setType("text/plain");
                send.putExtra(Intent.EXTRA_TEXT, content);
                startActivity(Intent.createChooser(send, "Compartilhar plano"));
            } catch (Exception error) {
                output.setText("Erro ao preparar plano: " + error.getMessage());
            }
        });

        signatureInfo = NegrescoTheme.action(this, "", false);
        signatureInfo.setText("Ver certificado de assinatura");
        signatureInfo.setEnabled(false);
        securitySection.addView(signatureInfo);
        signatureInfo.setOnClickListener(v -> {
            if (currentApk == null) return;
            final File file = currentApk;
            executor.execute(() -> {
                final String details = ApkSignatureInspector.inspect(this, file);
                runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                    .setTitle("Certificado do APK")
                    .setMessage(details)
                    .setPositiveButton("OK", null).show());
            });
        });

        signingGuide = NegrescoTheme.action(this, "", false);
        signingGuide.setText("Assinatura: requisitos e segurança");
        securitySection.addView(signingGuide);
        signingGuide.setOnClickListener(v -> new android.app.AlertDialog.Builder(this)
            .setTitle("Assinatura de APK modificado")
            .setMessage("O APK exportado ainda não pode ser considerado instalável. Para assinar corretamente, precisamos de alinhamento ZIP, assinatura APK Signature Scheme v2/v3 e verificação criptográfica.\\n\\nUma chave própria deve ser gerada e protegida, nunca enviada ao ChatGPT ou ao GitHub. A nova assinatura não substitui a identidade do desenvolvedor original e pode exigir desinstalar a versão anterior.\\n\\nO ReaDroid ainda NÃO assina APKs modificados.")
            .setPositiveButton("Entendi", null).show());

        localIdentity = NegrescoTheme.action(this, "", false);
        localIdentity.setText("Minha chave de assinatura local");
        securitySection.addView(localIdentity);
        localIdentity.setOnClickListener(v -> executor.execute(() -> {
            String status;
            try { status = LocalSigningIdentity.describe(); }
            catch (Exception error) { status = "Erro: " + error.getMessage(); }
            final String result = status;
            runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                .setTitle("Identidade local")
                .setMessage(result + "\n\nA chave pode ser perdida ao desinstalar o ReaDroid ou limpar seus dados. Faça isso somente se compreender que atualizações assinadas por outra chave não são compatíveis.")
                .setNegativeButton("Fechar", null)
                .setPositiveButton("Criar se necessário", (dialog, which) ->
                    new android.app.AlertDialog.Builder(this)
                        .setTitle("Criar identidade?")
                        .setMessage("A chave privada ficará no Android Keystore. Ela não será enviada nem exportada. Criar?")
                        .setNegativeButton("Cancelar", null)
                        .setPositiveButton("Criar", (d, w) -> executor.execute(() -> {
                            String detail;
                            try { detail = LocalSigningIdentity.create(); }
                            catch (Exception error) { detail = "Falha: " + error.getMessage(); }
                            final String message = detail;
                            runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                                .setTitle("Identidade de assinatura")
                                .setMessage(message).setPositiveButton("OK", null).show());
                        })).show())
                .show());
        }));

        signingTest = NegrescoTheme.action(this, "", false);
        signingTest.setText("Testar assinatura da chave local");
        securitySection.addView(signingTest);
        signingTest.setOnClickListener(v -> {
            signingTest.setEnabled(false);
            executor.execute(() -> {
                String message;
                try { message = SigningSelfTest.run(); }
                catch (Exception error) { message = "Teste falhou: " + error.getMessage(); }
                final String result = message;
                runOnUiThread(() -> {
                    signingTest.setEnabled(true);
                    new android.app.AlertDialog.Builder(this).setTitle("Autoteste criptográfico")
                        .setMessage(result).setPositiveButton("OK", null).show();
                });
            });
        });

        rebuild = NegrescoTheme.action(this, "", false);
        rebuild.setText("Exportar APK modificado (sem assinatura)");
        rebuild.setEnabled(false);
        buildSection.addView(rebuild);
        rebuild.setOnClickListener(v -> {
            if (currentApk == null || explorerView.getEditPlan().size() == 0) {
                new android.app.AlertDialog.Builder(this).setMessage("Primeiro registre uma alteração textual no explorador.").setPositiveButton("OK", null).show();
                return;
            }
            new android.app.AlertDialog.Builder(this)
                .setTitle("Reconstrução experimental")
                .setMessage("O resultado NÃO estará assinado e pode não instalar ou funcionar. O APK original será preservado. Continuar?")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Escolher destino", (dialog, which) -> {
                    Intent create = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    create.addCategory(Intent.CATEGORY_OPENABLE);
                    create.setType("application/vnd.android.package-archive");
                    create.putExtra(Intent.EXTRA_TITLE, "negrescodroid-modificado-unsigned.apk");
                    startActivityForResult(create, REQUEST_EXPORT_APK);
                }).show();
        });

        share = NegrescoTheme.action(this, "", false);
        share.setText("Compartilhar relatório JSON");
        share.setEnabled(false);
        aiSection.addView(share);
        share.setOnClickListener(v -> {
            if (report == null) return;
            Intent intent = new Intent(Intent.ACTION_SEND);
            intent.setType("application/json");
            intent.putExtra(Intent.EXTRA_TEXT, report.toString());
            startActivity(Intent.createChooser(intent, "Compartilhar relatório"));
        });
        StudioDashboard.styleFeatureButton(this, reviewChanges, "▤",
            "Confira o plano de modificações antes de exportar", true);
        StudioDashboard.styleFeatureButton(this, editExport, "↗",
            "Envie o plano de alterações em JSON", false);
        StudioDashboard.styleFeatureButton(this, rebuild, "⬡",
            "Gere o APK sem assinatura de instalação", false);
        StudioDashboard.styleFeatureButton(this, signatureInfo, "▣",
            "Veja o certificado de assinatura do arquivo", false);
        StudioDashboard.styleFeatureButton(this, signingGuide, "◈",
            "Entenda a assinatura e os cuidados necessários", false);
        StudioDashboard.styleFeatureButton(this, localIdentity, "⚿",
            "Consulte a identidade do Android Keystore", false);
        StudioDashboard.styleFeatureButton(this, signingTest, "◇",
            "Execute o teste criptográfico da chave", false);
        StudioDashboard.styleFeatureButton(this, ai, "✧",
            "Compartilhe o relatório com o ChatGPT", true);
        StudioDashboard.styleFeatureButton(this, share, "▤",
            "Exporte o relatório técnico em JSON", false);
        StudioDashboard.compose(this, homeSection, apkSummary, projectMetrics, choose,
            shortcutsTitle, shortcutHint, quickGrid,
            customizationTitle, customizationHint, togglePersonalization, personalizationGroup,
            new Button[]{themePicker, accentPicker, textScale, densityPicker, navLabels,
                favoriteShortcut, identityPicker, appearancePreview,
                exportAppearance, importAppearance, glowPicker, cornersPicker, resetAppearance},
            otaTitle, otaStatus, otaChannel, otaCheck,
            detailsTitle, output, project);
        showSection(0);
    }

    private void reviewEditPlan() {
        Map<String, String> changes = explorerView.getEditPlan().snapshot();
        if (changes.isEmpty()) {
            new android.app.AlertDialog.Builder(this)
                .setTitle("Plano de alterações")
                .setMessage("Nenhuma alteração pendente. Abra Arquivos e selecione um texto compatível para editar.")
                .setPositiveButton("OK", null).show();
            return;
        }
        String[] paths = changes.keySet().toArray(new String[0]);
        String[] labels = new String[paths.length];
        for (int i = 0; i < paths.length; i++) {
            labels[i] = paths[i] + "  •  " + changes.get(paths[i]).length() + " caracteres";
        }
        new android.app.AlertDialog.Builder(this)
            .setTitle("Alterações pendentes (" + paths.length + ")")
            .setItems(labels, (dialog, index) -> reviewChange(paths[index]))
            .setNegativeButton("Fechar", null)
            .setNeutralButton("Limpar plano", (dialog, which) ->
                new android.app.AlertDialog.Builder(this)
                    .setTitle("Descartar todas as alterações?")
                    .setMessage("O APK original não será modificado.")
                    .setNegativeButton("Cancelar", null)
                    .setPositiveButton("Descartar", (d, w) -> {
                        explorerView.getEditPlan().clear();
                        explorerView.refresh();
                    })
                    .show())
            .show();
    }

    private void reviewChange(String path) {
        String content = explorerView.getEditPlan().get(path);
        if (content == null) return;
        android.widget.ScrollView scroll = new android.widget.ScrollView(this);
        TextView preview = new TextView(this);
        preview.setText(content);
        preview.setTextColor(NegrescoTheme.TEXT);
        preview.setTextSize(12);
        preview.setTypeface(android.graphics.Typeface.MONOSPACE);
        preview.setPadding(NegrescoTheme.dp(this, 16), NegrescoTheme.dp(this, 16),
            NegrescoTheme.dp(this, 16), NegrescoTheme.dp(this, 16));
        scroll.addView(preview);
        new android.app.AlertDialog.Builder(this)
            .setTitle(path)
            .setView(scroll)
            .setPositiveButton("Manter", null)
            .setNegativeButton("Remover alteração", (dialog, which) -> {
                explorerView.getEditPlan().remove(path);
                explorerView.refresh();
                reviewEditPlan();
            }).show();
    }

    private LinearLayout section(LinearLayout parent) {
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        parent.addView(content);
        return content;
    }

    private void showSection(int index) {
        LinearLayout[] sections = {homeSection, filesSection, buildSection, securitySection, aiSection};
        for (int i = 0; i < sections.length; i++) {
            sections[i].setVisibility(i == index ? View.VISIBLE : View.GONE);
            navigationItems[i].setTextColor(i == index ? NegrescoTheme.ACCENT : NegrescoTheme.MUTED);
            navigationIcons[i].setSelectedState(i == index);
            navigationItems[i].setTypeface(null, i == index ? android.graphics.Typeface.BOLD : android.graphics.Typeface.NORMAL);
        }
        contentScroll.scrollTo(0, 0);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if ((request == REQUEST_EXPORT_APPEARANCE || request == REQUEST_IMPORT_APPEARANCE)
            && result == RESULT_OK && data != null && data.getData() != null) {
            Uri uri = data.getData();
            try {
                if (request == REQUEST_EXPORT_APPEARANCE) {
                    byte[] bytes = AppearancePreset.exportSettings(this)
                        .getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    try (OutputStream out = getContentResolver().openOutputStream(uri, "w")) {
                        if (out == null) throw new IOException("Destino indisponível");
                        out.write(bytes);
                    }
                    new android.app.AlertDialog.Builder(this).setTitle("Personalização exportada")
                        .setMessage("O arquivo contém somente preferências visuais.")
                        .setPositiveButton("OK", null).show();
                } else {
                    java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
                    try (InputStream in = getContentResolver().openInputStream(uri)) {
                        if (in == null) throw new IOException("Arquivo indisponível");
                        byte[] buffer = new byte[2048];
                        int n;
                        while ((n = in.read(buffer)) != -1) {
                            if (bytes.size() + n > 8192) throw new IOException("Arquivo muito grande");
                            bytes.write(buffer, 0, n);
                        }
                    }
                    String json = bytes.toString("UTF-8");
                    new android.app.AlertDialog.Builder(this).setTitle("Importar personalização?")
                        .setMessage("Substituir apenas as preferências visuais atuais? Projetos e configurações de segurança serão preservados.")
                        .setPositiveButton("Importar", (dialog, which) -> {
                            try {
                                AppearancePreset.importSettings(this, json);
                                recreate();
                            } catch (Exception error) {
                                new android.app.AlertDialog.Builder(this)
                                    .setTitle("Arquivo inválido").setMessage(error.getMessage())
                                    .setPositiveButton("OK", null).show();
                            }
                        }).setNegativeButton("Cancelar", null).show();
                }
            } catch (Exception error) {
                new android.app.AlertDialog.Builder(this).setTitle("Falha nas preferências")
                    .setMessage(error.getMessage()).setPositiveButton("OK", null).show();
            }
            return;
        }

        if (result != RESULT_OK || data == null || data.getData() == null) return;
        if (request == REQUEST_EXPORT_APK) { exportRebuilt(data.getData()); return; }
        if (request == REQUEST_COMPARE_APK) { compareApk(data.getData()); return; }
        if (request != 1) return;
        Uri uri = data.getData();
        report = null;
        if (currentApk != null) { currentApk.delete(); currentApk = null; }
        output.setText("Analisando...");
        apkSummary.setText("ANÁLISE EM ANDAMENTO");
        projectMetrics.setText("ESTRUTURA   •   Analisando...");
        share.setEnabled(false);
        ai.setEnabled(false);
        project.setEnabled(false);
        rebuild.setEnabled(false);
        signatureInfo.setEnabled(false);
        explorerView.getEditPlan().clear();
        explorerView.setFiles(null, null);
        executor.execute(() -> {
            try {
                JSONObject resultJson = analyze(uri);
                runOnUiThread(() -> {
                    report = resultJson;
                    output.setText(formatReport(resultJson));
                    JSONObject info = resultJson.optJSONObject("manifestAnalysis");
                    String packageName = info == null ? "Desconhecido" : info.optString("packageName", "Desconhecido");
                    apkSummary.setText("PROJETO CARREGADO\n\n" + packageName
                        + "\n\n" + resultJson.optInt("entries") + " arquivos  •  "
                        + (resultJson.optLong("sizeBytes") / 1024) + " KB"
                        + "\n\nSHA-256\n" + resultJson.optString("sha256"));
                    projectMetrics.setText("DEX  " + (resultJson.optJSONArray("dexFiles") == null ? 0 : resultJson.optJSONArray("dexFiles").length())
                        + "     •     BIBLIOTECAS  " + (resultJson.optJSONArray("nativeLibraries") == null ? 0 : resultJson.optJSONArray("nativeLibraries").length())
                        + "     •     ASSETS  " + resultJson.optInt("assets"));
                    JSONObject tree = resultJson.optJSONObject("explorer");
                    explorerView.setFiles(tree == null ? null : tree.optJSONArray("files"), currentApk);
                    share.setEnabled(true);
                    ai.setEnabled(true);
                    project.setEnabled(true);
                    rebuild.setEnabled(true);
                    signatureInfo.setEnabled(true);
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    output.setText("Erro: " + error.getMessage());
                    apkSummary.setText("FALHA AO ABRIR PROJETO");
                    projectMetrics.setText("ESTRUTURA   •   Indisponível");
                });
            }
        });
    }

    private void confirmOtaDownload(OtaRelease release) {
        new android.app.AlertDialog.Builder(this)
            .setTitle("Baixar atualização verificada?")
            .setMessage("O arquivo será baixado no cache privado e verificado por SHA-256, pacote e certificado Android. A instalação ainda não está disponível.")
            .setPositiveButton("Baixar", (dialog, which) -> {
                executor.execute(() -> {
                    try {
                        OtaUpdatePipeline.VerifiedUpdate verified =
                            OtaUpdatePipeline.downloadAndVerify(this, release);
                        // Installation is deliberately not enabled until a consent-based
                        // PackageInstaller flow and real-device tests are complete.
                        verified.apk.delete();
                        runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                            .setTitle("Atualização verificada")
                            .setMessage("O APK passou nas verificações e foi removido do cache. A instalação OTA será habilitada em uma etapa posterior.")
                            .setPositiveButton("OK", null).show());
                    } catch (Exception error) {
                        final String message = error.getMessage();
                        runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                            .setTitle("Falha no download OTA")
                            .setMessage(message == null ? "Erro desconhecido" : message)
                            .setPositiveButton("OK", null).show());
                    }
                });
            })
            .setNegativeButton("Cancelar", null).show();
    }

    private void compareApk(Uri uri) {
        if (currentApk == null) return;
        final File baseline = currentApk;
        executor.execute(() -> {
            File candidate = null;
            try {
                candidate = File.createTempFile("negresco_compare_", ".apk", getCacheDir());
                try (InputStream in = getContentResolver().openInputStream(uri);
                     OutputStream out = new FileOutputStream(candidate)) {
                    if (in == null) throw new IOException("Arquivo inacessível");
                    byte[] buffer = new byte[65536];
                    int n;
                    long total = 0;
                    while ((n = in.read(buffer)) != -1) {
                        total += n;
                        if (total > 1073741824L) throw new IOException("Limite de 1 GB excedido");
                        out.write(buffer, 0, n);
                    }
                }
                String result = ApkDiff.compare(baseline, candidate);
                runOnUiThread(() -> {
                    ScrollView scroll = new ScrollView(this);
                    TextView details = new TextView(this);
                    details.setText(result);
                    details.setTextColor(NegrescoTheme.TEXT);
                    details.setTextSize(13);
                    details.setTypeface(android.graphics.Typeface.MONOSPACE);
                    details.setTextIsSelectable(true);
                    details.setPadding(24, 20, 24, 20);
                    scroll.addView(details);
                    new android.app.AlertDialog.Builder(this)
                        .setTitle("Comparação de APKs")
                        .setView(scroll)
                        .setPositiveButton("Fechar", null).show();
                });
            } catch (Exception error) {
                final String message = error.getMessage();
                runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                    .setTitle("Falha na comparação").setMessage(message)
                    .setPositiveButton("OK", null).show());
            } finally {
                if (candidate != null) candidate.delete();
            }
        });
    }

    private void exportRebuilt(Uri destination) {
        if (currentApk == null) return;
        final File source = currentApk;
        final Map<String, String> changes = explorerView.getEditPlan().snapshot();
        if (changes.isEmpty()) return;
        rebuild.setEnabled(false);
        executor.execute(() -> {
            File temp = null;
            try {
                temp = File.createTempFile("readroid_unsigned_", ".apk", getCacheDir());
                ApkRebuilder.rebuild(source, temp, changes);
                final String verification = RebuildVerifier.verify(temp, changes);
                final String preflight = SigningPreflight.inspect(temp);
                try (InputStream in = new FileInputStream(temp);
                     OutputStream out = getContentResolver().openOutputStream(destination, "w")) {
                    if (out == null) throw new IOException("Destino inacessível");
                    byte[] buffer = new byte[65536];
                    int n;
                    while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
                }
                runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                    .setTitle("APK não assinado exportado")
                    .setMessage(verification + "\\n\\n" + preflight + "\\n\\nO arquivo original foi preservado.")
                    .setPositiveButton("OK", null).show());
            } catch (Exception error) {
                runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                    .setTitle("Falha na reconstrução").setMessage(error.getMessage())
                    .setPositiveButton("OK", null).show());
            } finally {
                if (temp != null) temp.delete();
                runOnUiThread(() -> rebuild.setEnabled(true));
            }
        });
    }

    private JSONObject analyze(Uri uri) throws Exception {
        File file = File.createTempFile("readroid_", ".apk", getCacheDir());
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            long size = 0;
            try (InputStream in = getContentResolver().openInputStream(uri);
                 OutputStream out = new FileOutputStream(file)) {
                if (in == null) throw new IOException("Arquivo inacessível");
                byte[] buffer = new byte[65536];
                int count;
                while ((count = in.read(buffer)) != -1) {
                    size += count;
                    if (size > 1073741824L) throw new IOException("Limite de 1 GB excedido");
                    digest.update(buffer, 0, count);
                    out.write(buffer, 0, count);
                }
            }
            StringBuilder hash = new StringBuilder();
            for (byte b : digest.digest()) hash.append(String.format(Locale.ROOT, "%02x", b & 255));
            JSONArray dex = new JSONArray();
            JSONArray libraries = new JSONArray();
            int entries = 0, assets = 0;
            boolean manifest = false;
            try (ZipFile zip = new ZipFile(file)) {
                Enumeration<? extends ZipEntry> items = zip.entries();
                while (items.hasMoreElements()) {
                    ZipEntry entry = items.nextElement();
                    String name = entry.getName();
                    if (++entries > 150000) throw new IOException("Entradas demais");
                    if (name.matches("classes([0-9]+)?\\.dex")) dex.put(name);
                    if (name.startsWith("lib/") && name.endsWith(".so")) libraries.put(name);
                    if (name.startsWith("assets/") && !entry.isDirectory()) assets++;
                    if (name.equals("AndroidManifest.xml")) manifest = true;
                }
            }
            JSONObject json = new JSONObject();
            json.put("manifestAnalysis", ManifestInspector.inspect(this, file));
            json.put("explorer", ApkExplorer.inspect(file));
            json.put("sizeBytes", size);
            json.put("sha256", hash.toString());
            json.put("entries", entries);
            json.put("dexFiles", dex);
            json.put("nativeLibraries", libraries);
            json.put("assets", assets);
            json.put("hasManifest", manifest);
            try (ZipFile securityZip = new ZipFile(file)) { json.put("security", SecurityScanner.scan(securityZip)); }
            json.put("note", "Análise estática preliminar: não decodifica manifesto binário nem valida assinatura.");
            currentApk = file;
            return json;
        } catch (Exception error) {
            file.delete();
            throw error;
        }
    }

    private String formatReport(JSONObject data) {
        StringBuilder out = new StringBuilder();
        JSONObject manifest = data.optJSONObject("manifestAnalysis");
        out.append("VISÃO GERAL\\n\\n");
        if (manifest != null) {
            out.append("Pacote: ").append(manifest.optString("packageName", "Desconhecido")).append("\\n");
            out.append("Versão: ").append(manifest.optString("versionName", "Desconhecida")).append("\\n");
            out.append("Android mínimo (API): ").append(manifest.optString("minSdk", "?")).append("\\n");
            out.append("Android alvo (API): ").append(manifest.optString("targetSdk", "?")).append("\\n");
            out.append("Permissões: ").append(manifest.optJSONArray("requestedPermissions") == null ? 0 : manifest.optJSONArray("requestedPermissions").length()).append("\\n");
        }
        out.append("Tamanho: ").append(data.optLong("sizeBytes") / 1024).append(" KB\\n");
        out.append("SHA-256: ").append(data.optString("sha256")).append("\\n\\n");
        JSONObject explorer = data.optJSONObject("explorer");
        if (explorer != null) out.append("Arquivos no APK: ").append(explorer.optInt("fileCount")).append("\\n");
        out.append("\\nNavegue pelas pastas e pesquise os arquivos abaixo.\\n");
        out.append("\\nRelatório completo disponível em Compartilhar JSON.");
        return out.toString();
    }

    @Override protected void onDestroy() {
        executor.shutdownNow();
        if (currentApk != null) currentApk.delete();
        super.onDestroy();
    }
}
