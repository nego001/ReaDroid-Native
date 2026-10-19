package com.readroid.app;

import android.app.Activity;
import android.graphics.Color;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.Locale;

/** Interactive read-only APK directory browser; paths are display-only. */
public final class ExplorerView {
    private final Activity activity;
    private final LinearLayout list;
    private final TextView breadcrumb;
    private final TextView countLabel;
    private final Button upButton;
    private final EditText search;
    private final Button filterButton;
    private String activeCategory = "Todos";
    private int pageLimit = 120;
    private final ArrayList<JSONObject> files = new ArrayList<>();
    private String folder = "";
    private java.io.File apkFile;
    private final EditPlan editPlan = new EditPlan();
    private static final String[] CATEGORIES = {
        "Todos", "Código DEX", "Bibliotecas", "Recursos", "Assets",
        "Assinaturas/metadados", "Manifesto", "Outros", "Editáveis", "Alterados"
    };

    /** Session-only UI state. Never persisted to disk or reused across APKs. */
    static final class BrowseState {
        final String folder;
        final String category;
        final String query;
        final int pageLimit;

        BrowseState(String folder, String category, String query, int pageLimit) {
            this.folder = folder;
            this.category = category;
            this.query = query;
            this.pageLimit = pageLimit;
        }
    }

    BrowseState snapshotBrowseState() {
        return new BrowseState(folder, activeCategory, search.getText().toString(), pageLimit);
    }

    void restoreBrowseState(BrowseState state) {
        if (state == null) return;
        // Do not trust a retained folder unless it still belongs to this APK.
        boolean validFolder = state.folder != null && (state.folder.isEmpty()
            || (state.folder.endsWith("/") && !state.folder.startsWith("/")
                && !state.folder.contains("..") && !state.folder.contains("\\")
                && hasFileBelow(state.folder)));
        folder = validFolder ? state.folder : "";
        activeCategory = java.util.Arrays.asList(CATEGORIES).contains(state.category)
            ? state.category : "Todos";
        filterButton.setText("Filtro: " + activeCategory + "  ▾");
        // setText invokes the TextWatcher (which resets pagination): set the
        // retained limit afterwards and render the final, validated state.
        String safeQuery = state.query == null ? "" : state.query;
        if (safeQuery.length() > 512) safeQuery = safeQuery.substring(0, 512);
        search.setText(safeQuery);
        pageLimit = Math.max(120, Math.min(state.pageLimit,
            Math.max(120, files.size() + 120)));
        render();
    }

    private boolean hasFileBelow(String prefix) {
        for (JSONObject file : files) {
            if (file.optString("path").startsWith(prefix)) return true;
        }
        return false;
    }

    public ExplorerView(Activity activity, LinearLayout parent) {
        this.activity = activity;
        TextView heading = new TextView(activity);
        heading.setText("CONTEÚDO DO PACOTE");
        heading.setTextColor(NegrescoTheme.ACCENT);
        heading.setTextSize(12 * NegrescoTheme.FONT_SCALE);
        heading.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        heading.setLetterSpacing(0.08f);
        heading.setPadding(0, NegrescoTheme.dp(activity, 4),
            0, NegrescoTheme.dp(activity, 12));
        parent.addView(heading);
        search = new EditText(activity);
        search.setSingleLine(true);
        boolean narrow = activity.getResources().getConfiguration().screenWidthDp <= 360;
        search.setHint(narrow ? "Buscar no APK..." : "Buscar arquivo pelo nome ou caminho");
        search.setTextSize((narrow ? 13 : 14) * NegrescoTheme.FONT_SCALE);
        search.setTextColor(NegrescoTheme.TEXT);
        search.setHintTextColor(NegrescoTheme.MUTED);
        search.setBackground(NegrescoTheme.panel(activity));
        search.setPadding(NegrescoTheme.dp(activity, 14), NegrescoTheme.dp(activity, 12), NegrescoTheme.dp(activity, 14), NegrescoTheme.dp(activity, 12));
        parent.addView(search);
        filterButton = NegrescoTheme.action(activity, "Filtro: Todos  ▾", false);
        parent.addView(filterButton);
        filterButton.setOnClickListener(v -> {
            new android.app.AlertDialog.Builder(activity)
                .setTitle("Filtrar arquivos")
                .setSingleChoiceItems(CATEGORIES, java.util.Arrays.asList(CATEGORIES).indexOf(activeCategory),
                    (dialog, which) -> {
                        activeCategory = CATEGORIES[which];
                        pageLimit = 120;
                        filterButton.setText("Filtro: " + activeCategory + "  ▾");
                        render();
                        dialog.dismiss();
                    })
                .setNegativeButton("Cancelar", null).show();
        });
        breadcrumb = new TextView(activity);
        breadcrumb.setTextColor(NegrescoTheme.ACCENT);
        breadcrumb.setPadding(0, 14, 0, 10);
        parent.addView(breadcrumb);
        countLabel = new TextView(activity);
        countLabel.setTextColor(NegrescoTheme.MUTED);
        countLabel.setTextSize(12 * NegrescoTheme.FONT_SCALE);
        parent.addView(countLabel);
        upButton = NegrescoTheme.action(activity, "← Pasta anterior", false);
        parent.addView(upButton);
        upButton.setOnClickListener(v -> {
            if (!search.getText().toString().isEmpty()) {
                search.setText("");
                return;
            }
            if (folder.isEmpty()) return;
            String current = folder.substring(0, folder.length() - 1);
            int slash = current.lastIndexOf('/');
            folder = slash < 0 ? "" : current.substring(0, slash + 1);
            pageLimit = 120;
            search.setText("");
            render();
        });
        list = new LinearLayout(activity);
        list.setOrientation(LinearLayout.VERTICAL);
        parent.addView(list);
        search.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            public void onTextChanged(CharSequence s, int start, int before, int count) { pageLimit = 120; render(); }
            public void afterTextChanged(Editable e) {}
        });
        render();
    }

    public void setFiles(JSONArray array, java.io.File apkFile) {
        this.apkFile = apkFile;
        files.clear();
        folder = "";
        activeCategory = "Todos";
        pageLimit = 120;
        filterButton.setText("Filtro: Todos  ▾");
        search.setText("");
        if (array != null) for (int i = 0; i < array.length(); i++) {
            JSONObject file = array.optJSONObject(i);
            if (file != null) files.add(file);
        }
        render();
    }

    private void render() {
        list.removeAllViews();
        String query = search.getText().toString().trim().toLowerCase(Locale.ROOT);
        breadcrumb.setText(query.isEmpty() ? "APK / " + folder : "Busca em todo o APK: " + query);
        upButton.setEnabled(!folder.isEmpty() || !query.isEmpty());
        breadcrumb.setOnClickListener(v -> {
            folder = "";
            search.setText("");
            render();
        });
        LinkedHashSet<String> folders = new LinkedHashSet<>();
        ArrayList<JSONObject> visible = new ArrayList<>();
        for (JSONObject item : files) {
            String path = item.optString("path");
            if (!activeCategory.equals("Todos")
                && !(activeCategory.equals("Editáveis") && EditPlan.isEditable(path))
                && !(activeCategory.equals("Alterados") && editPlan.contains(path))
                && !activeCategory.equals(item.optString("category"))) continue;
            if (!query.isEmpty()) {
                if (path.toLowerCase(Locale.ROOT).contains(query)) visible.add(item);
            } else if (path.startsWith(folder)) {
                String rest = path.substring(folder.length());
                int slash = rest.indexOf('/');
                if (slash >= 0) folders.add(rest.substring(0, slash + 1));
                else visible.add(item);
            }
        }
        countLabel.setText(folders.size() + " pastas  •  " + visible.size()
            + " arquivos  •  " + editPlan.size() + " alterações pendentes");
        int shown = 0;
        for (String child : folders) {
            if (shown >= pageLimit) break;
            shown++;
            TextView line = item("▸  " + child + "\nPASTA");
            list.addView(line);
            line.setOnClickListener(v -> { folder += child; pageLimit = 120; render(); });
        }
        for (JSONObject file : visible) {
            if (shown >= pageLimit) break;
            shown++;
            String path = file.optString("path");
            String name = query.isEmpty() ? path.substring(folder.length()) : path;
            boolean editable = EditPlan.isEditable(path);
            TextView line = item((editPlan.contains(path) ? "●  " : "") + name + "\n" + file.optString("category")
                + "  •  " + formatBytes(file.optLong("sizeBytes", -1))
                + (editPlan.contains(path) ? "  •  ALTERADO" : (editable ? "  •  EDITÁVEL" : "  •  LEITURA")));
            list.addView(line);
            line.setOnClickListener(v -> new android.app.AlertDialog.Builder(activity)
                .setTitle(name)
                .setMessage("Caminho: " + path + "\nTipo: " + file.optString("category") + "\nTamanho: " + file.optLong("sizeBytes", -1) + " bytes")
                .setPositiveButton("Ver texto", (dialog, which) -> preview(path))
                .setNeutralButton(editable ? "Planejar edição" : "Somente leitura", (dialog, which) -> {
                    if (editable) planEdit(path);
                })
                .setNegativeButton("Detalhes técnicos", (dialog, which) -> inspectEntry(path)).show());
        }
        if (shown == 0) list.addView(item("Nenhum arquivo nesta pasta."));
        if (shown < folders.size() + visible.size()) {
            Button more = NegrescoTheme.action(activity,
                "Carregar mais (" + Math.min(120, folders.size() + visible.size() - shown) + ")", false);
            list.addView(more);
            more.setOnClickListener(v -> {
                pageLimit += 120;
                render();
            });
        }
    }

    private static String formatBytes(long bytes) {
        if (bytes < 0) return "Tamanho desconhecido";
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1048576) return String.format(Locale.ROOT, "%.1f KB", bytes / 1024.0);
        return String.format(Locale.ROOT, "%.1f MB", bytes / 1048576.0);
    }

    public EditPlan getEditPlan() { return editPlan; }

    public void refresh() { render(); }

    private void inspectEntry(String path) {
        if (apkFile == null || !apkFile.isFile()) return;
        final java.io.File source = apkFile;
        new Thread(() -> {
            String details;
            try { details = ApkEntryInspector.inspect(source, path); }
            catch (Exception error) { details = "Inspeção indisponível: " + error.getMessage(); }
            final String message = details;
            activity.runOnUiThread(() -> new android.app.AlertDialog.Builder(activity)
                .setTitle("Propriedades do arquivo")
                .setMessage(message)
                .setPositiveButton("Fechar", null)
                .setNeutralButton("Copiar dados", (dialog, which) -> {
                    android.content.ClipboardManager clipboard = (android.content.ClipboardManager)
                        activity.getSystemService(android.content.Context.CLIPBOARD_SERVICE);
                    if (clipboard != null) clipboard.setPrimaryClip(
                        android.content.ClipData.newPlainText("Dados do arquivo", message));
                }).show());
        }).start();
    }

    private void planEdit(String path) {
        if (!EditPlan.isEditable(path)) {
            new android.app.AlertDialog.Builder(activity).setMessage("Edição textual ainda não suportada para este formato.").setPositiveButton("OK", null).show();
            return;
        }
        if (apkFile == null || !apkFile.exists()) return;
        final java.io.File source = apkFile;
        new Thread(() -> {
            String original;
            try { original = ApkPreview.readText(source, path); }
            catch (Exception error) {
                activity.runOnUiThread(() -> new android.app.AlertDialog.Builder(activity).setMessage(error.getMessage()).setPositiveButton("OK", null).show());
                return;
            }
            activity.runOnUiThread(() -> {
                EditText editor = new EditText(activity);
                editor.setText(editPlan.contains(path) ? editPlan.get(path) : original);
                editor.setTextColor(NegrescoTheme.TEXT);
                editor.setBackground(NegrescoTheme.panel(activity));
                editor.setPadding(NegrescoTheme.dp(activity, 14), NegrescoTheme.dp(activity, 14),
                    NegrescoTheme.dp(activity, 14), NegrescoTheme.dp(activity, 14));
                editor.setHorizontallyScrolling(true);
                editor.setTypeface(android.graphics.Typeface.MONOSPACE);
                editor.setMinLines(9);
                editor.setMaxLines(18);
                editor.setTextSize(13);
                new android.app.AlertDialog.Builder(activity)
                    .setTitle("Planejar alteração: " + path)
                    .setMessage("Esta edição será mantida apenas na sessão atual. "
                        + "O APK original não será alterado. "
                        + "Se o Android encerrar o aplicativo, alterações ainda não exportadas "
                        + "podem ser perdidas.")
                    .setView(editor)
                    .setNegativeButton("Cancelar", null)
                    .setPositiveButton("Salvar no plano", (dialog, which) -> {
                        try {
                            String replacement = editor.getText().toString();
                            EditPlan.EditResult result =
                                editPlan.applyTextEdit(path, original, replacement);
                            render();
                            String title;
                            String description;
                            switch (result) {
                                case ADDED:
                                case UPDATED:
                                    title = "Alteração registrada";
                                    description = "A edição está no plano temporário.";
                                    break;
                                case REMOVED:
                                    title = "Alteração desfeita";
                                    description = "O texto voltou ao original e a edição "
                                        + "deste arquivo foi retirada do plano.";
                                    break;
                                default:
                                    title = "Nenhuma alteração";
                                    description = "O texto é igual ao original ou à edição "
                                        + "que já estava no plano.";
                                    break;
                            }
                            new android.app.AlertDialog.Builder(activity)
                                .setTitle(title)
                                .setMessage(description + "\n\nItens no plano: " + editPlan.size()
                                    + "\nO plano fica apenas na memória da sessão.")
                                .setPositiveButton("OK", null).show();
                        } catch (Exception error) {
                            new android.app.AlertDialog.Builder(activity).setMessage(error.getMessage()).setPositiveButton("OK", null).show();
                        }
                    }).show();
            });
        }).start();
    }

    private void preview(String path) {
        if (apkFile == null || !apkFile.exists()) {
            new android.app.AlertDialog.Builder(activity).setMessage("APK temporário indisponível. Analise o arquivo novamente.").setPositiveButton("OK", null).show();
            return;
        }
        final java.io.File source = apkFile;
        new Thread(() -> {
            String value;
            try { value = ApkPreview.readText(source, path); }
            catch (Exception error) { value = "Não foi possível visualizar: " + error.getMessage(); }
            final String text = value;
            activity.runOnUiThread(() -> {
                ScrollView scroll = new ScrollView(activity);
                TextView content = new TextView(activity);
                content.setText(text);
                content.setTextColor(NegrescoTheme.TEXT);
                content.setTypeface(android.graphics.Typeface.MONOSPACE);
                content.setTextSize(13);
                content.setBackgroundColor(NegrescoTheme.BACKGROUND);
                content.setTextIsSelectable(true);
                content.setPadding(24, 20, 24, 20);
                scroll.addView(content);
                new android.app.AlertDialog.Builder(activity).setTitle(path).setView(scroll).setPositiveButton("Fechar", null).show();
            });
        }).start();
    }

    private TextView item(String value) {
        TextView view = new TextView(activity);
        android.text.SpannableString formatted = new android.text.SpannableString(value);
        int separator = value.indexOf('\n');
        if (separator >= 0) {
            formatted.setSpan(new android.text.style.ForegroundColorSpan(NegrescoTheme.MUTED),
                separator + 1, value.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            formatted.setSpan(new android.text.style.RelativeSizeSpan(0.82f),
                separator + 1, value.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        }
        if (value.startsWith("▸")) {
            formatted.setSpan(new android.text.style.ForegroundColorSpan(NegrescoTheme.ACCENT),
                0, Math.min(1, value.length()), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        }
        view.setText(formatted);
        view.setTextColor(NegrescoTheme.TEXT);
        view.setTextSize(14 * NegrescoTheme.FONT_SCALE);
        view.setLineSpacing(NegrescoTheme.dp(activity, 3), 1f);
        view.setMinHeight(NegrescoTheme.dp(activity, 56));
        view.setPadding(NegrescoTheme.dp(activity, 16), NegrescoTheme.dp(activity, 12),
            NegrescoTheme.dp(activity, 16), NegrescoTheme.dp(activity, 12));
        view.setBackground(NegrescoTheme.studioCard(activity, false));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.bottomMargin = NegrescoTheme.dp(activity, 7);
        view.setLayoutParams(params);
        return view;
    }
}
