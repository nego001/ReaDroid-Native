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
    private Button apkAdvisor;
    private static final int REQUEST_EXPORT_APK = 2;
    private static final int REQUEST_COMPARE_APK = 3;
    private static final int REQUEST_EXPORT_APPEARANCE = 41;
    private static final int REQUEST_IMPORT_APPEARANCE = 42;
    private static final int REQUEST_EXPORT_P7_ICON = 43;
    private static final int REQUEST_EXPORT_P7_LOGO = 44;
    private P7IconWorkshop.Spec pendingIconExport;
    private P7LogoWorkshop.Spec pendingLogoExport;
    private JSONObject report;
    private File currentApk;
    private File currentIndex;
    private ExplorerView explorerView;
    private LinearLayout homeSection;
    private LinearLayout filesSection;
    private LinearLayout securitySection;
    private LinearLayout buildSection;
    private LinearLayout aiSection;
    private LinearLayout designSection;
    private TextView[] navigationItems;
    private NavGlyph[] navigationIcons;
    private View[] navigationIndicators;
    private LinearLayout[] navigationContainers;
    private int selectedSection = 0;
    private Uri selectedApkUri;
    private volatile int analysisSequence = 0;

    /** Keep worker output separate from the Activity's current project. */
    private static final class AnalyzedApk {
        final JSONObject report;
        final File file;
        final File indexFile;
        AnalyzedApk(JSONObject report, File file, File indexFile) {
            this.report = report;
            this.file = file;
            this.indexFile = indexFile;
        }
    }
    private TextView apkSummary;
    private TextView projectMetrics;
    private P7HomeOverview homeOverview;
    private ScrollView contentScroll;

    /** Holds a project in memory across theme changes and rotation only. */
    private static final class WorkspaceState {
        final File apk;
        final File indexFile;
        final JSONObject report;
        final Map<String, String> changes;
        final int activeSection;
        final ExplorerView.BrowseState browse;
        WorkspaceState(File apk, File indexFile, JSONObject report,
                Map<String, String> changes, int section,
                ExplorerView.BrowseState browse) {
            this.apk = apk;
            this.indexFile = indexFile;
            this.report = report;
            this.changes = changes;
            this.activeSection = section;
            this.browse = browse;
        }
    }

    @Override public void onCreate(Bundle state) {
        NegrescoTheme.apply(this);
        String activeTheme = getSharedPreferences("v3_personalizacao", MODE_PRIVATE)
            .getString("theme", "oled");
        setTheme("light".equals(activeTheme)
            ? android.R.style.Theme_Material_Light_NoActionBar
            : android.R.style.Theme_Material_NoActionBar);
        super.onCreate(state);
        if (state != null && state.containsKey("p7_icon_export")) {
            int[] selected = state.getIntArray("p7_icon_export");
            if (selected != null && selected.length == 3) {
                try {
                    pendingIconExport = new P7IconWorkshop.Spec(
                        selected[0], selected[1], selected[2]);
                } catch (IllegalArgumentException ignored) {
                    pendingIconExport = null;
                }
            }
        }
        if (state != null && state.containsKey("p7_logo_export")) {
            String[] selected = state.getStringArray("p7_logo_export");
            if (selected != null && selected.length == 4) {
                try {
                    pendingLogoExport = new P7LogoWorkshop.Spec(selected[0], selected[1],
                        Integer.parseInt(selected[2]), Integer.parseInt(selected[3]));
                } catch (IllegalArgumentException ignored) {
                    pendingLogoExport = null;
                }
            }
        }
        // Window insets are not available until after the content view is attached.
        // Calling Window.getInsetsController here crashes on Android 15.
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(NegrescoTheme.dp(this, NegrescoTheme.COMPACT ? 12 : 15), NegrescoTheme.dp(this, NegrescoTheme.COMPACT ? 8 : 12), NegrescoTheme.dp(this, NegrescoTheme.COMPACT ? 12 : 15), NegrescoTheme.dp(this, NegrescoTheme.COMPACT ? 10 : 14));
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
        if (android.os.Build.VERSION.SDK_INT >= 35) {
            // Android 15 enforces edge-to-edge for targetSdk 35. Reserve the
            // actual system-bar and cutout insets so the header and tabs are
            // not obscured, regardless of gesture or three-button navigation.
            shell.setOnApplyWindowInsetsListener((view, windowInsets) -> {
                android.graphics.Insets safe = windowInsets.getInsets(
                    android.view.WindowInsets.Type.systemBars()
                        | android.view.WindowInsets.Type.displayCutout());
                view.setPadding(safe.left, safe.top, safe.right, safe.bottom);
                return windowInsets;
            });
        }
        setContentView(shell);
        shell.post(() -> NegrescoTheme.applySystemBars(this));

        android.content.SharedPreferences appearance =
            getSharedPreferences("v3_personalizacao", MODE_PRIVATE);
        String displayName = appearance.getString("display_name", "NegrecoDroid");
        // Migrate only the old built-in brand; user-supplied names are retained.
        if ("NEGRESCODROID".equals(displayName) || "NegrescoDroid".equals(displayName)) {
            displayName = "NegrecoDroid";
            appearance.edit().putString("display_name", displayName).apply();
        }
        String displaySubtitle = appearance.getString("display_subtitle", "APK ENGINEERING STUDIO");
        LinearLayout brandRow = new LinearLayout(this);
        brandRow.setGravity(android.view.Gravity.CENTER_VERTICAL);
        brandRow.setPadding(0, NegrescoTheme.dp(this, 2), 0, NegrescoTheme.dp(this, 9));
        android.widget.ImageView brandMark = new android.widget.ImageView(this);
        brandMark.setImageResource(R.drawable.ic_negrecodroid_foreground);
        brandMark.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        brandRow.addView(brandMark, new LinearLayout.LayoutParams(
            NegrescoTheme.dp(this, 34), NegrescoTheme.dp(this, 34)));
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
        title.setTextSize(22 * NegrescoTheme.FONT_SCALE);
        title.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        title.setMaxLines(2);
        brandText.addView(title);
        TextView brandSubtitleView = new TextView(this);
        brandSubtitleView.setText("APK ENGINEERING STUDIO".equals(displaySubtitle)
            ? "ANÁLISE, EDIÇÃO E CUSTOMIZAÇÃO DE APKS" : displaySubtitle);
        brandSubtitleView.setTextColor(NegrescoTheme.MUTED);
        brandSubtitleView.setTextSize(8.5f * NegrescoTheme.FONT_SCALE);
        brandSubtitleView.setLetterSpacing(0.13f);
        brandSubtitleView.setMaxLines(2);
        brandText.addView(brandSubtitleView);
        P7HomeToolbar homeToolbar = new P7HomeToolbar(this,
            v -> showHomeMenu(), v -> showSection(4));
        root.addView(homeToolbar);
        root.addView(brandRow);
        String[] tabs = {"Início", "Arquivos", "Segurança", "Build", "Design"};
        boolean showNavLabels = getSharedPreferences("v3_personalizacao", MODE_PRIVATE)
            .getBoolean("nav_labels", true);
        navigationItems = new TextView[tabs.length];
        navigationIcons = new NavGlyph[tabs.length];
        navigationIndicators = new View[tabs.length];
        navigationContainers = new LinearLayout[tabs.length];
        for (int index = 0; index < tabs.length; index++) {
            final int target = index;
            LinearLayout tabContainer = new LinearLayout(this);
            tabContainer.setOrientation(LinearLayout.VERTICAL);
            tabContainer.setGravity(android.view.Gravity.CENTER);
            tabContainer.setMinimumHeight(NegrescoTheme.dp(this, 56));
            tabContainer.setFocusable(true);
            tabContainer.setClickable(true);
            // Stable IDs allow real DPAD left/right navigation between tabs.
            tabContainer.setId(View.generateViewId());
            tabContainer.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
            tabContainer.setAccessibilityDelegate(new View.AccessibilityDelegate() {
                @Override public void onInitializeAccessibilityNodeInfo(
                        View host, android.view.accessibility.AccessibilityNodeInfo info) {
                    super.onInitializeAccessibilityNodeInfo(host, info);
                    info.setClassName(Button.class.getName());
                }
            });
            navigationContainers[index] = tabContainer;
            LinearLayout.LayoutParams navParams =
                new LinearLayout.LayoutParams(0, NegrescoTheme.dp(this, 64), 1f);
            navParams.setMargins(NegrescoTheme.dp(this, 2), 0, NegrescoTheme.dp(this, 2), 0);
            nav.addView(tabContainer, navParams);
            // A narrow electric-blue dash above the active icon matches the
            // approved five-tab bar, while preserving 64dp touch targets.
            View indicator = new View(this);
            android.graphics.drawable.GradientDrawable marker =
                new android.graphics.drawable.GradientDrawable();
            marker.setColor(NegrescoTheme.ACCENT);
            marker.setCornerRadius(NegrescoTheme.dp(this, 5));
            indicator.setBackground(marker);
            indicator.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            indicator.setVisibility(View.INVISIBLE);
            LinearLayout.LayoutParams markerParams = new LinearLayout.LayoutParams(
                NegrescoTheme.dp(this, 28), NegrescoTheme.dp(this, 3));
            markerParams.bottomMargin = NegrescoTheme.dp(this, 4);
            tabContainer.addView(indicator, markerParams);
            navigationIndicators[index] = indicator;
            int[] tabIcons = {0, 1, 3, 2, 4};
            NavGlyph glyph = new NavGlyph(this, tabIcons[index]);
            tabContainer.addView(glyph, new LinearLayout.LayoutParams(NegrescoTheme.dp(this, 27), NegrescoTheme.dp(this, 27)));
            navigationIcons[index] = glyph;
            TextView label = new TextView(this);
            label.setText(tabs[index]);
            label.setGravity(android.view.Gravity.CENTER);
            boolean narrow = getResources().getConfiguration().screenWidthDp < 360;
            label.setTextSize((narrow ? 9 : 10) * NegrescoTheme.FONT_SCALE);
            label.setMaxLines(2);
            label.setEllipsize(android.text.TextUtils.TruncateAt.END);
            label.setIncludeFontPadding(false);
            label.setPadding(NegrescoTheme.dp(this, 2), 0, NegrescoTheme.dp(this, 2), 0);
            label.setVisibility(showNavLabels ? View.VISIBLE : View.GONE);
            label.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            label.setTextColor(NegrescoTheme.MUTED);
            tabContainer.addView(label, new LinearLayout.LayoutParams(
                -1, -2));
            navigationItems[index] = label;
            tabContainer.setContentDescription("Abrir seção " + tabs[index]);
            tabContainer.setOnClickListener(v -> showSection(target));
            tabContainer.setOnFocusChangeListener((v, focused) ->
                tabContainer.setBackground(NegrescoTheme.navigationSurface(
                    this, tabContainer.isSelected(), focused)));
        }
        // Explicit horizontal DPAD traversal; do not trap TAB/Shift+TAB
        // navigation, which must remain free to reach the screen's actions.
        for (int index = 0; index < navigationContainers.length; index++) {
            if (index > 0) navigationContainers[index].setNextFocusLeftId(
                navigationContainers[index - 1].getId());
            if (index + 1 < navigationContainers.length)
                navigationContainers[index].setNextFocusRightId(
                    navigationContainers[index + 1].getId());
        }
        homeSection = section(root);
        filesSection = section(root);
        buildSection = section(root);
        securitySection = section(root);
        aiSection = section(root);
        designSection = section(root);

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
                        .putString("theme", values[which])
                        .remove("p7_active_preset").apply();
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
                            .putString("accent", values[which])
                            .remove("p7_active_preset").apply();
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
                            Runnable applyCustomColor = () -> {
                                getSharedPreferences("v3_personalizacao", MODE_PRIVATE).edit()
                                    .putString("accent", "custom").putString("custom_accent", color)
                                    .remove("p7_active_preset").apply();
                                recreate();
                            };
                            double contrast = NegrescoTheme.contrastRatio(
                                Color.parseColor(color), NegrescoTheme.BACKGROUND);
                            if (contrast < 3.0) {
                                new android.app.AlertDialog.Builder(this)
                                    .setTitle("Cor com pouco contraste")
                                    .setMessage("Essa cor pode deixar ícones e indicadores difíceis de ver neste tema. Deseja usá-la mesmo assim?")
                                    .setPositiveButton("Usar mesmo assim", (confirm, choice) ->
                                        applyCustomColor.run())
                                    .setNegativeButton("Cancelar", null).show();
                            } else {
                                applyCustomColor.run();
                            }
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
                            .putBoolean("compact", which == 1)
                            .putInt("layout_variant", which == 1 ? 1 : 0)
                            .remove("p7_active_preset").apply();
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
                .getString("display_name", "NegrecoDroid"));
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
                    if (name.isEmpty()) name = "NegrecoDroid";
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
                    .getString("display_name", "NegrecoDroid"),
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
            getPreferences(MODE_PRIVATE).edit().putBoolean("studio_settings_expanded", expand).apply();
            togglePersonalization.setText(
                expand ? "Opções de aparência  ▴" : "Opções de aparência  ▾");
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
        apkAdvisor = NegrescoTheme.action(this, "Ferramentas recomendadas para este APK", false);
        apkAdvisor.setEnabled(false);
        homeSection.addView(apkAdvisor);
        apkAdvisor.setOnClickListener(v -> {
            if (report == null) return;
            String details = ApkIntelligence.describe(report.optJSONObject("intelligence"));
            ScrollView scroll = new ScrollView(this);
            TextView text = new TextView(this);
            text.setText(details);
            text.setTextColor(NegrescoTheme.TEXT);
            text.setTextSize(14 * NegrescoTheme.FONT_SCALE);
            text.setPadding(NegrescoTheme.dp(this, 18), NegrescoTheme.dp(this, 16),
                NegrescoTheme.dp(this, 18), NegrescoTheme.dp(this, 16));
            scroll.addView(text);
            new android.app.AlertDialog.Builder(this)
                .setTitle("Diagnóstico inteligente (offline)")
                .setView(scroll)
                .setPositiveButton("Fechar", null).show();
        });

        output = new TextView(this);
        output.setText("Selecione um APK para começar.");
        output.setTextColor(NegrescoTheme.MUTED);
        output.setTextSize(15);
        output.setTextIsSelectable(true);
        output.setPadding(NegrescoTheme.dp(this, 12), NegrescoTheme.dp(this, 16), NegrescoTheme.dp(this, 12), NegrescoTheme.dp(this, 16));
        output.setBackground(NegrescoTheme.panel(this));
        apkSummary = new TextView(this);
        apkSummary.setText("Nenhum APK selecionado\nSelecione um arquivo para começar.");
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
        // P7: match the approved two-row / three-column action composition.
        // Every tile opens an actual existing workflow; unsupported operations
        // remain in the Build/Security sections and are not falsely enabled.
        String[] actionNames = {"Abrir APK", "Analisar", "Build APK",
            "Decompilar", "Editar Smali", "Assinar APK"};
        // Faithful six-action symbols: folder, search, wrench, code,
        // editable document and verified shield instead of nav placeholders.
        int[] actionGlyphs = {
            R.drawable.ic_p7_folder, R.drawable.ic_p7_search,
            R.drawable.ic_p7_wrench, R.drawable.ic_p7_code,
            R.drawable.ic_p7_file, R.drawable.ic_p7_shield
        };
        View.OnClickListener[] actionHandlers = new View.OnClickListener[]{
            v -> {
                Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                pick.addCategory(Intent.CATEGORY_OPENABLE);
                pick.setType("*/*");
                startActivityForResult(pick, 1);
            },
            v -> {
                if (report == null) {
                    Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                    pick.addCategory(Intent.CATEGORY_OPENABLE);
                    pick.setType("*/*");
                    startActivityForResult(pick, 1);
                } else {
                    showSection(0);
                    new android.app.AlertDialog.Builder(this)
                        .setTitle("Análise do APK atual")
                        .setMessage("O relatório técnico está disponível na Home.")
                        .setPositiveButton("Ver relatório", (d, w) ->
                            output.post(() -> output.requestRectangleOnScreen(
                                new android.graphics.Rect(0, 0,
                                    Math.max(1, output.getWidth()), 90), true)))
                        .setNegativeButton("Fechar", null).show();
                }
            },
            v -> showSection(3),
            v -> new android.app.AlertDialog.Builder(this)
                .setTitle("Decompilação")
                .setMessage("Decompilação Smali completa ainda não disponível.")
                .setPositiveButton("Fechar", null).show(),
            v -> showSection(1),
            v -> new android.app.AlertDialog.Builder(this)
                .setTitle("Assinar APK")
                .setMessage("A assinatura de APKs reconstruídos ainda não está "
                    + "disponível. A seção Segurança permite inspecionar "
                    + "certificados e testar uma identidade local.")
                .setPositiveButton("Ver segurança", (d, w) -> showSection(2))
                .setNegativeButton("Fechar", null).show()
        };
        for (int rowIndex = 0; rowIndex < 2; rowIndex++) {
            LinearLayout actionRow = new LinearLayout(this);
            actionRow.setOrientation(LinearLayout.HORIZONTAL);
            quickGrid.addView(actionRow);
            for (int col = 0; col < 3; col++) {
                int index = rowIndex * 3 + col;
                LinearLayout tile = StudioDashboard.referenceAction(this,
                    actionNames[index], actionGlyphs[index], actionHandlers[index]);
                LinearLayout.LayoutParams params =
                    new LinearLayout.LayoutParams(0, -2, 1f);
                params.setMargins(col == 0 ? 0 : NegrescoTheme.dp(this, 3), 0,
                    col == 2 ? 0 : NegrescoTheme.dp(this, 3),
                    NegrescoTheme.dp(this, 7));
                actionRow.addView(tile, params);
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
        explorerView.setNavigationActions(() -> showSection(0), () -> {
            Intent chooser = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            chooser.addCategory(Intent.CATEGORY_OPENABLE);
            chooser.setType("*/*");
            startActivityForResult(chooser, 1);
        }, this::reviewEditPlan);
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
            if (explorerView.getEditPlan().size() == 0) {
                new android.app.AlertDialog.Builder(this)
                    .setMessage("Não há alterações para compartilhar.")
                    .setPositiveButton("OK", null).show();
                return;
            }
            new android.app.AlertDialog.Builder(this)
                .setTitle("Compartilhar alterações sem criptografia?")
                .setMessage("Este compartilhamento pode incluir textos internos do APK e "
                    + "enviará o conteúdo ao aplicativo escolhido. "
                    + "Para guardar uma cópia privada neste aparelho, prefira "
                    + "a recuperação criptografada.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Compartilhar", (dialog, which) -> {
                    try {
                        String content = explorerView.getEditPlan().toJson().toString(2);
                        Intent send = new Intent(Intent.ACTION_SEND);
                        send.setType("text/plain");
                        send.putExtra(Intent.EXTRA_TEXT, content);
                        startActivity(Intent.createChooser(send, "Compartilhar plano"));
                    } catch (Exception error) {
                        output.setText("Erro ao preparar plano: " + error.getMessage());
                    }
                }).show();
        });

        Button saveRecovery = NegrescoTheme.action(this,
            "Salvar cópia de recuperação criptografada", false);
        buildSection.addView(saveRecovery);
        saveRecovery.setOnClickListener(v -> {
            if (currentApk == null || !currentApk.isFile() || report == null
                || explorerView.getEditPlan().size() == 0) {
                new android.app.AlertDialog.Builder(this)
                    .setMessage("Abra um APK e registre pelo menos uma alteração antes "
                        + "de criar a cópia de recuperação.")
                    .setPositiveButton("OK", null).show();
                return;
            }
            new android.app.AlertDialog.Builder(this)
                .setTitle("Salvar plano neste aparelho?")
                .setMessage("O plano será criptografado com Android Keystore e guardado "
                    + "apenas no armazenamento privado. Substitui a cópia anterior; "
                    + "não inclui o APK original, não usa nuvem e não é salvamento automático. "
                    + "Para recuperar, será necessário abrir novamente o mesmo APK.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Criptografar e salvar", (dialog, which) -> {
                    final File source = currentApk;
                    final Map<String, String> changes = explorerView.getEditPlan().snapshot();
                    executor.execute(() -> {
                        try {
                            new RecoveryVault(this).save(source, changes);
                            runOnUiThread(() -> {
                                if (isFinishing() || isDestroyed()) return;
                                new android.app.AlertDialog.Builder(this)
                                    .setTitle("Cópia protegida")
                                    .setMessage("Plano salvo localmente com criptografia. "
                                        + "Novas edições não entram na cópia até salvar outra vez.")
                                    .setPositiveButton("OK", null).show();
                            });
                        } catch (Exception error) {
                            showRecoveryError("Falha ao salvar cópia", error);
                        }
                    });
                }).show();
        });

        Button restoreRecovery = NegrescoTheme.action(this,
            "Recuperar plano salvo neste aparelho", false);
        buildSection.addView(restoreRecovery);
        restoreRecovery.setOnClickListener(v -> {
            if (!new RecoveryVault(this).hasCheckpoint()) {
                new android.app.AlertDialog.Builder(this)
                    .setMessage("Nenhuma cópia de recuperação foi encontrada.")
                    .setPositiveButton("OK", null).show();
                return;
            }
            if (currentApk == null || !currentApk.isFile() || report == null) {
                new android.app.AlertDialog.Builder(this)
                    .setMessage("Abra novamente o APK original para verificar sua "
                        + "identidade antes de recuperar as alterações.")
                    .setPositiveButton("OK", null).show();
                return;
            }
            final File source = currentApk;
            executor.execute(() -> {
                try {
                    final Map<String, String> changes =
                        new RecoveryVault(this).loadForSource(source);
                    runOnUiThread(() -> {
                        if (isFinishing() || isDestroyed() || source != currentApk) return;
                        new android.app.AlertDialog.Builder(this)
                            .setTitle("Recuperar " + changes.size() + " alterações?")
                            .setMessage("A cópia foi autenticada e pertence a este APK "
                                + "(SHA-256 conferido). Recuperar substituirá todas "
                                + "as alterações atualmente pendentes; o APK original "
                                + "não será modificado.")
                            .setNegativeButton("Cancelar", null)
                            .setPositiveButton("Substituir plano", (dialog, which) -> {
                                if (source != currentApk) return;
                                EditPlan plan = explorerView.getEditPlan();
                                plan.clear();
                                for (Map.Entry<String, String> edit : changes.entrySet())
                                    plan.addTextReplacement(edit.getKey(), edit.getValue());
                                explorerView.refresh();
                                new android.app.AlertDialog.Builder(this)
                                    .setMessage("Plano recuperado. Revise as alterações antes "
                                        + "de exportar um APK modificado.")
                                    .setPositiveButton("OK", null).show();
                            }).show();
                    });
                } catch (Exception error) {
                    showRecoveryError("Recuperação bloqueada", error);
                }
            });
        });

        Button removeRecovery = NegrescoTheme.action(this,
            "Excluir cópia de recuperação local", false);
        buildSection.addView(removeRecovery);
        removeRecovery.setOnClickListener(v ->
            new android.app.AlertDialog.Builder(this)
                .setTitle("Excluir a cópia protegida?")
                .setMessage("Esta ação não altera o APK nem as edições abertas, "
                    + "mas remove o ponto de recuperação salvo no aparelho.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Excluir cópia", (dialog, which) ->
                    // Same single-thread executor as Save/Restore: a deletion
                    // cannot be undone by a previously queued background save.
                    executor.execute(() -> {
                        try {
                            new RecoveryVault(this).clear();
                            runOnUiThread(() -> {
                                if (isFinishing() || isDestroyed()) return;
                                new android.app.AlertDialog.Builder(this)
                                    .setMessage("Cópia de recuperação removida.")
                                    .setPositiveButton("OK", null).show();
                            });
                        } catch (Exception error) {
                            showRecoveryError("Não foi possível excluir", error);
                        }
                    })).show());

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
            .setMessage("O APK exportado ainda não pode ser considerado instalável. Para assinar corretamente, precisamos de alinhamento ZIP, assinatura APK Signature Scheme v2/v3 e verificação criptográfica.\\n\\nUma chave própria deve ser gerada e protegida, nunca enviada ao ChatGPT ou ao GitHub. A nova assinatura não substitui a identidade do desenvolvedor original e pode exigir desinstalar a versão anterior.\\n\\nO NegrecoDroid ainda NÃO assina APKs modificados.")
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
        StudioDashboard.featureHeader(this, buildSection, 2, "Construir",
            "Revise suas alterações e exporte o APK sem assinatura.");
        StudioDashboard.featureHeader(this, securitySection, 3, "Segurança",
            "Inspecione certificados, assinaturas e sua identidade local.");
        StudioDashboard.featureHeader(this, aiSection, 4, "Assistente IA",
            "Compartilhe um relatório técnico para análise no ChatGPT.");
        homeOverview = new P7HomeOverview(this, v -> showSection(1));
        homeOverview.setHistoryCallbacks(this::openRecentProject,
            v -> showAllRecentProjects());
        refreshRecentProjects();
        // Home-only branding and a separate, functional Design page.
        // Remove the global header so Explorer and Design do not show a
        // second title above their own headers.
        root.removeView(homeToolbar);
        root.removeView(brandRow);
        new P7DesignStudio(this, designSection, new Button[]{
            themePicker, accentPicker, textScale, densityPicker, navLabels,
            favoriteShortcut, identityPicker, appearancePreview,
            exportAppearance, importAppearance, glowPicker, cornersPicker,
            resetAppearance
        });
        StudioDashboard.compose(this, homeSection, designSection,
            apkSummary, projectMetrics, choose,
            homeOverview, shortcutsTitle, shortcutHint, quickGrid,
            customizationTitle, customizationHint, togglePersonalization, personalizationGroup,
            new Button[]{themePicker, accentPicker, textScale, densityPicker, navLabels,
                favoriteShortcut, identityPicker, appearancePreview,
                exportAppearance, importAppearance, glowPicker, cornersPicker, resetAppearance},
            otaTitle, otaStatus, otaChannel, otaCheck,
            detailsTitle, output, project);
        homeSection.addView(homeToolbar, 0);
        homeSection.addView(brandRow, 1);
        // Legacy AI controls remain accessible in Design without losing them.
        ((android.view.ViewGroup) aiSection.getParent()).removeView(aiSection);
        designSection.addView(aiSection);
        showSection(state == null ? 0 : state.getInt("active_studio_section", 0));
        boolean retained = restoreWorkspace();
        if (state != null) {
            selectedApkUri = state.getParcelable("selected_apk_uri");
            if (!retained && selectedApkUri != null) analyzeSelectedApk(selectedApkUri);
        }
        refreshRecentProjects();
    }

    /** The same report renderer is used for fresh APKs and retained workspaces. */
    private void displayAnalyzedReport(JSONObject resultJson) {
        report = resultJson;
        if (homeOverview != null)
            homeOverview.update(report, explorerView.getEditPlan().size());
        output.setText(formatReport(resultJson));
        JSONObject info = resultJson.optJSONObject("manifestAnalysis");
        String packageName = info == null ? "Desconhecido" : info.optString("packageName", "Desconhecido");
        String headline = packageName == null || packageName.isEmpty()
            ? "Pacote desconhecido" : packageName;
        String details = resultJson.optInt("entries") + " arquivos  •  "
            + (resultJson.optLong("sizeBytes") / 1024) + " KB";
        String combined = headline + "\n" + details;
        android.text.SpannableString styled = new android.text.SpannableString(combined);
        styled.setSpan(new android.text.style.RelativeSizeSpan(0.79f),
            headline.length() + 1, combined.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        styled.setSpan(new android.text.style.ForegroundColorSpan(NegrescoTheme.MUTED),
            headline.length() + 1, combined.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        apkSummary.setText(styled);
        JSONObject profile = resultJson.optJSONObject("intelligence");
        projectMetrics.setText("DEX  " + (resultJson.optJSONArray("dexFiles") == null ? 0 : resultJson.optJSONArray("dexFiles").length())
            + "     •     BIBLIOTECAS  " + (resultJson.optJSONArray("nativeLibraries") == null ? 0 : resultJson.optJSONArray("nativeLibraries").length())
            + "     •     ASSETS  " + resultJson.optInt("assets")
            + (profile == null ? "" : "\nPERFIL  " + profile.optString("platformHint", "Android/ZIP")));
        JSONObject tree = resultJson.optJSONObject("explorer");
        JSONArray paths = tree == null ? null : tree.optJSONArray("files");
        if (currentIndex != null && currentIndex.isFile())
            explorerView.setIndexedFiles(paths, currentApk, currentIndex);
        else explorerView.setFiles(paths, currentApk);
        explorerView.setProjectSummary(headline, resultJson.optLong("sizeBytes", -1));
        refreshRecentProjects();
        share.setEnabled(true);
        ai.setEnabled(true);
        apkAdvisor.setEnabled(profile != null);
        project.setEnabled(true);
        rebuild.setEnabled(true);
        signatureInfo.setEnabled(true);
    }

    @Override public Object onRetainNonConfigurationInstance() {
        if (currentApk == null || !currentApk.isFile() || report == null
            || explorerView == null) return null;
        return new WorkspaceState(currentApk, currentIndex, report,
            explorerView.getEditPlan().snapshot(), selectedSection,
            explorerView.snapshotBrowseState());
    }

    private boolean restoreWorkspace() {
        Object previous = getLastNonConfigurationInstance();
        if (!(previous instanceof WorkspaceState)) return false;
        WorkspaceState workspace = (WorkspaceState) previous;
        if (!workspace.apk.isFile()) return false;
        currentApk = workspace.apk;
        currentIndex = workspace.indexFile;
        displayAnalyzedReport(workspace.report);
        for (Map.Entry<String, String> edit : workspace.changes.entrySet()) {
            try {
                explorerView.getEditPlan().addTextReplacement(edit.getKey(), edit.getValue());
            } catch (IllegalArgumentException ignored) {
                // Invalid or outdated edits are never reapplied without validation.
            }
        }
        explorerView.restoreBrowseState(workspace.browse);
        homeOverview.update(report, explorerView.getEditPlan().size());
        showSection(workspace.activeSection);
        return true;
    }

    private void showRecoveryError(String title, Exception error) {
        runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            String message = error.getMessage();
            new android.app.AlertDialog.Builder(this)
                .setTitle(title)
                .setMessage(message == null || message.isEmpty()
                    ? "Verificação criptográfica ou armazenamento indisponível."
                    : message)
                .setPositiveButton("OK", null).show();
        });
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

    /** Home menu from the approved reference, routing only to real workflows. */
    private void showHomeMenu() {
        String[] commands = {"Abrir APK", "Explorador de Arquivos",
            "Segurança", "Build APK", "Design Studio"};
        new android.app.AlertDialog.Builder(this)
            .setTitle("NegrecoDroid")
            .setItems(commands, (dialog, choice) -> {
                if (choice == 0) {
                    Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                    picker.addCategory(Intent.CATEGORY_OPENABLE);
                    picker.setType("*/*");
                    startActivityForResult(picker, 1);
                } else if (choice == 1) showSection(1);
                else if (choice == 2) showSection(2);
                else if (choice == 3) showSection(3);
                else if (choice == 4) showSection(4);
            })
            .setNegativeButton("Fechar", null).show();
    }

    private void showSection(int index) {
        LinearLayout[] sections = {homeSection, filesSection, securitySection, buildSection, designSection};
        if (index < 0 || index >= sections.length) return;
        selectedSection = index;
        if (index == 0 && homeOverview != null) {
            homeOverview.update(report, explorerView == null ? 0
                : explorerView.getEditPlan().size());
            refreshRecentProjects();
        }
        for (int i = 0; i < sections.length; i++) {
            boolean selected = i == index;
            sections[i].setVisibility(selected ? View.VISIBLE : View.GONE);
            navigationItems[i].setTextColor(selected ? NegrescoTheme.ACCENT : NegrescoTheme.MUTED);
            navigationIcons[i].setSelectedState(selected);
            navigationIndicators[i].setVisibility(selected ? View.VISIBLE : View.INVISIBLE);
            navigationContainers[i].setBackground(NegrescoTheme.navigationSurface(
                this, selected, navigationContainers[i].hasFocus()));
            navigationContainers[i].setSelected(selected);
            navigationContainers[i].setActivated(selected);
            navigationContainers[i].setContentDescription(
                "Seção " + navigationItems[i].getText()
                    + (selected ? ", selecionada" : ""));
            navigationItems[i].setTypeface(null,
                selected ? android.graphics.Typeface.BOLD : android.graphics.Typeface.NORMAL);
        }
        contentScroll.scrollTo(0, 0);
    }

    /** Uses the Android document picker, never broad storage write access. */
    public void startP7IconExport(P7IconWorkshop.Spec icon) {
        pendingIconExport = icon;
        Intent create = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        create.addCategory(Intent.CATEGORY_OPENABLE);
        create.setType("image/png");
        create.putExtra(Intent.EXTRA_TITLE, "NegrecoDroid-icone.png");
        startActivityForResult(create, REQUEST_EXPORT_P7_ICON);
    }

    /** Logo export uses the same explicit SAF consent as the icon workshop. */
    public void startP7LogoExport(P7LogoWorkshop.Spec logo) {
        pendingLogoExport = logo;
        Intent create = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        create.addCategory(Intent.CATEGORY_OPENABLE);
        create.setType("image/png");
        create.putExtra(Intent.EXTRA_TITLE, "NegrecoDroid-logo.png");
        startActivityForResult(create, REQUEST_EXPORT_P7_LOGO);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == REQUEST_EXPORT_P7_LOGO) {
            P7LogoWorkshop.Spec requested = pendingLogoExport;
            pendingLogoExport = null;
            if (result != RESULT_OK || data == null ||
                    data.getData() == null || requested == null) return;
            try {
                P7LogoWorkshop.export(this, requested, data.getData());
                new android.app.AlertDialog.Builder(this)
                    .setTitle("Logo exportado")
                    .setMessage("PNG 1024×512 salvo no destino escolhido. " +
                        "O APK e a identidade instalada não foram alterados.")
                    .setPositiveButton("OK", null).show();
            } catch (Exception error) {
                new android.app.AlertDialog.Builder(this)
                    .setTitle("Falha ao exportar logo")
                    .setMessage(error.getMessage())
                    .setPositiveButton("OK", null).show();
            }
            return;
        }
        if (request == REQUEST_EXPORT_P7_ICON) {
            P7IconWorkshop.Spec requested = pendingIconExport;
            pendingIconExport = null;
            if (result != RESULT_OK || data == null ||
                    data.getData() == null || requested == null) return;
            try {
                P7IconWorkshop.export(this, requested, data.getData());
                new android.app.AlertDialog.Builder(this)
                    .setTitle("Ícone exportado")
                    .setMessage("PNG 512×512 salvo no destino escolhido. " +
                        "O APK e a identidade instalada não foram alterados.")
                    .setPositiveButton("OK", null).show();
            } catch (Exception error) {
                new android.app.AlertDialog.Builder(this)
                    .setTitle("Falha ao exportar ícone")
                    .setMessage(error.getMessage())
                    .setPositiveButton("OK", null).show();
            }
            return;
        }
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
                    String preview;
                    try {
                        preview = AppearancePreset.describeSettings(json);
                    } catch (Exception invalid) {
                        new android.app.AlertDialog.Builder(this)
                            .setTitle("Arquivo de personalização inválido")
                            .setMessage(invalid.getMessage())
                            .setPositiveButton("OK", null).show();
                        return;
                    }
                    new android.app.AlertDialog.Builder(this)
                        .setTitle("Prévia da personalização")
                        .setMessage(preview + "\n\nAplicar somente as preferências visuais? O projeto aberto e as configurações de segurança serão preservados.")
                        .setPositiveButton("Aplicar visual", (dialog, which) -> {
                            try {
                                AppearancePreset.importSettings(this, json);
                                android.widget.Toast.makeText(this,
                                    "Personalização importada com sucesso",
                                    android.widget.Toast.LENGTH_LONG).show();
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
        selectApkWithConfirmation(data.getData(), true);
    }

    private void refreshRecentProjects() {
        if (homeOverview == null) return;
        homeOverview.setRecentProjects(P7ProjectHistory.list(this),
            report == null ? null : selectedApkUri);
    }

    private void openRecentProject(P7ProjectHistory.Entry item) {
        if (!P7ProjectHistory.hasPermission(this, item.uri)) {
            refreshRecentProjects();
            new android.app.AlertDialog.Builder(this)
                .setTitle("Permissão expirada")
                .setMessage("O Android não permite mais acessar este APK. Selecione-o "
                    + "novamente pelo gerenciador de arquivos.")
                .setPositiveButton("OK", null).show();
            return;
        }
        selectApkWithConfirmation(item.uri, false);
    }

    private void showAllRecentProjects() {
        List<P7ProjectHistory.Entry> entries = P7ProjectHistory.list(this);
        if (entries.isEmpty()) {
            refreshRecentProjects();
            return;
        }
        String[] names = new String[entries.size()];
        for (int i = 0; i < entries.size(); i++) {
            P7ProjectHistory.Entry item = entries.get(i);
            names[i] = item.name + "  •  " + item.packageName;
        }
        new android.app.AlertDialog.Builder(this)
            .setTitle("Projetos recentes")
            .setItems(names, (dialog, which) -> openRecentProject(entries.get(which)))
            .setNeutralButton("Limpar lista", (dialog, which) ->
                new android.app.AlertDialog.Builder(this)
                    .setTitle("Limpar histórico?")
                    .setMessage("Remove apenas a lista de projetos recentes deste "
                        + "aplicativo. Não exclui APKs nem planos de edição.")
                    .setNegativeButton("Cancelar", null)
                    .setPositiveButton("Limpar", (d, w) -> {
                        P7ProjectHistory.clear(this);
                        P7RecentAppIcons.prune(this, P7ProjectHistory.list(this));
                        refreshRecentProjects();
                    }).show())
            .setNegativeButton("Fechar", null).show();
    }

    private void selectApkWithConfirmation(Uri uri, boolean fromPicker) {
        if (uri == null || !"content".equals(uri.getScheme())) {
            new android.app.AlertDialog.Builder(this)
                .setMessage("Selecione um APK pelo gerenciador de arquivos do Android.")
                .setPositiveButton("OK", null).show();
            return;
        }
        Runnable open = () -> {
            if (fromPicker) {
                try {
                    getContentResolver().takePersistableUriPermission(uri,
                        Intent.FLAG_GRANT_READ_URI_PERMISSION);
                } catch (SecurityException | IllegalArgumentException denied) {
                    // Import works for this session, but must NOT appear
                    // in the persistent list without a real SAF permission.
                }
            }
            analyzeSelectedApk(uri);
        };
        if (explorerView != null && explorerView.getEditPlan().size() > 0) {
            new android.app.AlertDialog.Builder(this)
                .setTitle("Trocar de APK?")
                .setMessage("Existem " + explorerView.getEditPlan().size()
                    + " alterações pendentes. Ao abrir outro projeto, "
                    + "essas alterações não exportadas serão descartadas. "
                    + "Salve uma cópia de recuperação antes, se necessário.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Descartar e abrir", (d, which) -> open.run())
                .show();
        } else {
            open.run();
        }
    }

    private void analyzeSelectedApk(Uri uri) {
        final int sequence = ++analysisSequence;
        selectedApkUri = uri;
        report = null;
        if (homeOverview != null) homeOverview.update(null, 0);
        if (currentApk != null) { currentApk.delete(); currentApk = null; }
        if (currentIndex != null) {
            android.database.sqlite.SQLiteDatabase.deleteDatabase(currentIndex);
            currentIndex = null;
        }
        output.setText("Analisando...");
        apkSummary.setText("ANÁLISE EM ANDAMENTO");
        projectMetrics.setText("ESTRUTURA   •   Analisando...");
        share.setEnabled(false);
        ai.setEnabled(false);
        apkAdvisor.setEnabled(false);
        project.setEnabled(false);
        rebuild.setEnabled(false);
        signatureInfo.setEnabled(false);
        explorerView.getEditPlan().clear();
        explorerView.setFiles(null, null);
        executor.execute(() -> {
            try {
                AnalyzedApk result = analyze(uri);
                // Only authorized SAF grants are saved; never persist APK bytes.
                // Metadata lookup happens off the UI thread.
                if (sequence == analysisSequence) {
                    JSONObject manifest = result.report.optJSONObject("manifestAnalysis");
                    String packageName = manifest == null ? "" :
                        manifest.optString("packageName", "");
                    if (P7ProjectHistory.record(this, uri, packageName)) {
                        P7RecentAppIcons.capture(this, uri, result.file);
                        P7RecentAppIcons.prune(this, P7ProjectHistory.list(this));
                    }
                }
                runOnUiThread(() -> {
                    if (sequence != analysisSequence || isFinishing() || isDestroyed()) {
                        result.file.delete();
                        if (result.indexFile != null)
                            android.database.sqlite.SQLiteDatabase.deleteDatabase(result.indexFile);
                        return;
                    }
                    currentApk = result.file;
                    currentIndex = result.indexFile;
                    displayAnalyzedReport(result.report);
                    refreshRecentProjects();
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (sequence != analysisSequence || isFinishing() || isDestroyed()) return;
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

    /** Short result first; the technical verification is available on demand. */
    private void showExportSuccess(long bytes, String verification, String preflight,
            String sourceSha256, String rebuiltSha256) {
        final String details = verification + "\n\n" + preflight
            + "\n\nSHA-256 da origem (antes e depois):\n" + sourceSha256
            + "\n\nSHA-256 do APK reconstruído e exportado:\n" + rebuiltSha256
            + "\n\nArquivo original conferido; saída relida e comparada por SHA-256.";
        new android.app.AlertDialog.Builder(this)
            .setTitle("Exportação verificada")
            .setMessage("✓ Arquivo gravado e verificado por SHA-256 (" + bytes + " bytes)."
                + "\n\nO APK original não foi modificado."
                + "\n\nEste arquivo NÃO está assinado e NÃO deve ser instalado como APK final.")
            .setNeutralButton("Detalhes técnicos", (dialog, which) -> {
                ScrollView scroll = new ScrollView(this);
                TextView view = new TextView(this);
                view.setText(details);
                view.setTextColor(NegrescoTheme.TEXT);
                view.setTextSize(13 * NegrescoTheme.FONT_SCALE);
                view.setTextIsSelectable(true);
                view.setPadding(NegrescoTheme.dp(this, 18), NegrescoTheme.dp(this, 16),
                    NegrescoTheme.dp(this, 18), NegrescoTheme.dp(this, 16));
                scroll.addView(view);
                new android.app.AlertDialog.Builder(this)
                    .setTitle("Verificação técnica do APK")
                    .setView(scroll)
                    .setPositiveButton("Fechar", null).show();
            })
            .setPositiveButton("Concluir", null).show();
    }

    private void exportRebuilt(Uri destination) {
        if (currentApk == null) return;
        final File source = currentApk;
        final Map<String, String> changes = explorerView.getEditPlan().snapshot();
        if (changes.isEmpty()) return;
        final String originalImportHash = report == null
            ? "" : report.optString("sha256", "");
        rebuild.setEnabled(false);
        executor.execute(() -> {
            File temp = null;
            try {
                // The cached original must match the imported APK, and cannot
                // change while the export is being reconstructed or verified.
                ApkIntegrity.confirmExpected(source, originalImportHash);
                temp = File.createTempFile("readroid_unsigned_", ".apk", getCacheDir());
                ApkRebuilder.rebuild(source, temp, changes);
                final String verification = RebuildVerifier.verifyAgainstOriginal(
                    source, temp, changes);
                final String preflight = SigningPreflight.inspect(temp);
                final String rebuiltSha256 = ApkIntegrity.sha256(temp);
                // Check again immediately before and after read-back from SAF.
                ApkIntegrity.confirmExpected(source, originalImportHash);
                final long exportedBytes = SafExportVerifier.copyAndVerify(
                    getContentResolver(), temp, destination);
                ApkIntegrity.confirmExpected(source, originalImportHash);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed())
                        showExportSuccess(exportedBytes, verification, preflight,
                            originalImportHash, rebuiltSha256);
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    new android.app.AlertDialog.Builder(this)
                        .setTitle("Falha ao exportar")
                        .setMessage(error.getMessage()
                            + "\n\nA exportação não foi confirmada. Se um arquivo parcial aparecer"
                            + " em Downloads, descarte-o. O APK original permanece intacto.")
                        .setPositiveButton("OK", null).show();
                });
            } finally {
                if (temp != null) temp.delete();
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) rebuild.setEnabled(true);
                });
            }
        });
    }

    private AnalyzedApk analyze(Uri uri) throws Exception {
        // Reserve private storage before copying the untrusted document.
        // The provider may lie about its size: streaming checks remain required.
        ApkImportPreflight.beforeCopy(this, uri);
        File file = File.createTempFile("readroid_", ".apk", getCacheDir());
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            long size = 0;
            try (InputStream in = getContentResolver().openInputStream(uri);
                 OutputStream out = new FileOutputStream(file)) {
                if (in == null) throw new IOException("Arquivo inacessível");
                byte[] buffer = new byte[65536];
                int count;
                long lastStorageCheck = 0;
                while ((count = in.read(buffer)) != -1) {
                    if (Thread.currentThread().isInterrupted())
                        throw new java.io.InterruptedIOException("Análise interrompida");
                    size += count;
                    if (size > ApkImportPreflight.MAX_APK_BYTES)
                        throw new IOException("Limite seguro atual de 1 GiB excedido.");
                    digest.update(buffer, 0, count);
                    out.write(buffer, 0, count);
                    if (ApkImportPreflight.shouldRecheck(size, lastStorageCheck)) {
                        ApkImportPreflight.checkProgress(size,
                            ApkImportPreflight.availableBytes(this));
                        lastStorageCheck = size;
                    }
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
                    if (Thread.currentThread().isInterrupted())
                        throw new java.io.InterruptedIOException("Análise interrompida");
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
            FileHeaderProbe.Result header = FileHeaderProbe.inspect(file);
            JSONObject formatHint = new JSONObject();
            formatHint.put("format", header.format);
            formatHint.put("description", header.description);
            formatHint.put("sampleBytes", header.sampleBytes);
            formatHint.put("recognized", header.recognized);
            json.put("fileHeader", formatHint);
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
            json.put("intelligence", ApkIntelligence.inspect(json));
            json.put("note", "Análise estática preliminar: não decodifica manifesto binário nem valida assinatura.");
            if (Thread.currentThread().isInterrupted())
                throw new java.io.InterruptedIOException("Análise interrompida");
            // Experimental UI indexing only; legacy JSON analysis retained.
            File diskIndex = null;
            if (entries >= 200) {
                File candidate = new File(file.getAbsolutePath() + ".idx.db");
                try {
                    ApkDiskIndex.build(file, candidate);
                    diskIndex = candidate;
                } catch (IOException optionalIndexError) {
                    android.database.sqlite.SQLiteDatabase.deleteDatabase(candidate);
                }
            }
            return new AnalyzedApk(json, file, diskIndex);
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
        JSONObject header = data.optJSONObject("fileHeader");
        if (header != null)
            out.append("Formato identificado: ")
                .append(header.optString("description", "Não identificado"))
                .append(" (pré-inspeção)\\n");
        out.append("Tamanho: ").append(data.optLong("sizeBytes") / 1024).append(" KB\\n");
        out.append("SHA-256: ").append(data.optString("sha256")).append("\\n\\n");
        JSONObject explorer = data.optJSONObject("explorer");
        if (explorer != null) out.append("Arquivos no APK: ").append(explorer.optInt("fileCount")).append("\\n");
        out.append("\\nNavegue pelas pastas e pesquise os arquivos abaixo.\\n");
        out.append("\\nRelatório completo disponível em Compartilhar JSON.");
        return out.toString();
    }

    @Override public void onBackPressed() {
        if (selectedSection != 0) {
            showSection(0);
        } else {
            super.onBackPressed();
        }
    }

    @Override protected void onSaveInstanceState(Bundle outState) {
        outState.putInt("active_studio_section", selectedSection);
        if (pendingIconExport != null)
            outState.putIntArray("p7_icon_export", new int[] {
                pendingIconExport.color, pendingIconExport.symbol,
                pendingIconExport.shape });
        if (pendingLogoExport != null)
            outState.putStringArray("p7_logo_export", new String[] {
                pendingLogoExport.name, pendingLogoExport.subtitle,
                Integer.toString(pendingLogoExport.color),
                Integer.toString(pendingLogoExport.background) });
        if (selectedApkUri != null) outState.putParcelable("selected_apk_uri", selectedApkUri);
        super.onSaveInstanceState(outState);
    }

    @Override protected void onDestroy() {
        analysisSequence++;
        executor.shutdownNow();
        // The new Activity owns this cache file after a configuration change.
        if (!isChangingConfigurations()) {
            if (currentApk != null) currentApk.delete();
            if (currentIndex != null)
                android.database.sqlite.SQLiteDatabase.deleteDatabase(currentIndex);
        }
        super.onDestroy();
    }
}
