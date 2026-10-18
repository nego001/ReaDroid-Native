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
    private final ArrayList<JSONObject> files = new ArrayList<>();
    private String folder = "";
    private java.io.File apkFile;
    private final EditPlan editPlan = new EditPlan();

    public ExplorerView(Activity activity, LinearLayout parent) {
        this.activity = activity;
        TextView heading = new TextView(activity);
        heading.setText("EXPLORADOR  /  ARQUIVOS DO APK");
        heading.setTextColor(NegrescoTheme.TEXT);
        heading.setTextSize(19);
        heading.setPadding(0, 24, 0, 10);
        parent.addView(heading);
        search = new EditText(activity);
        search.setSingleLine(true);
        search.setHint("Buscar arquivo pelo nome ou caminho");
        search.setTextColor(Color.WHITE);
        search.setHintTextColor(NegrescoTheme.MUTED);
        search.setBackground(NegrescoTheme.panel(activity));
        search.setPadding(NegrescoTheme.dp(activity, 14), NegrescoTheme.dp(activity, 12), NegrescoTheme.dp(activity, 14), NegrescoTheme.dp(activity, 12));
        parent.addView(search);
        breadcrumb = new TextView(activity);
        breadcrumb.setTextColor(NegrescoTheme.ACCENT);
        breadcrumb.setPadding(0, 14, 0, 10);
        parent.addView(breadcrumb);
        countLabel = new TextView(activity);
        countLabel.setTextColor(NegrescoTheme.MUTED);
        countLabel.setTextSize(12);
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
            search.setText("");
            render();
        });
        list = new LinearLayout(activity);
        list.setOrientation(LinearLayout.VERTICAL);
        parent.addView(list);
        search.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            public void onTextChanged(CharSequence s, int start, int before, int count) { render(); }
            public void afterTextChanged(Editable e) {}
        });
        render();
    }

    public void setFiles(JSONArray array, java.io.File apkFile) {
        this.apkFile = apkFile;
        files.clear();
        folder = "";
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
            if (!query.isEmpty()) {
                if (path.toLowerCase(Locale.ROOT).contains(query)) visible.add(item);
            } else if (path.startsWith(folder)) {
                String rest = path.substring(folder.length());
                int slash = rest.indexOf('/');
                if (slash >= 0) folders.add(rest.substring(0, slash + 1));
                else visible.add(item);
            }
        }
        countLabel.setText(folders.size() + " pastas  •  " + visible.size() + " arquivos");
        int shown = 0;
        for (String child : folders) {
            if (shown++ >= 120) break;
            TextView line = item("▸  " + child + "\nPASTA");
            list.addView(line);
            line.setOnClickListener(v -> { folder += child; render(); });
        }
        for (JSONObject file : visible) {
            if (shown++ >= 120) break;
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
                .setNegativeButton("Fechar", null).show());
        }
        if (shown == 0) list.addView(item("Nenhum arquivo nesta pasta."));
        if (folders.size() + visible.size() > 120) list.addView(item("Mostrando os primeiros 120 itens. Use a busca para filtrar."));
    }

    private static String formatBytes(long bytes) {
        if (bytes < 0) return "Tamanho desconhecido";
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1048576) return String.format(Locale.ROOT, "%.1f KB", bytes / 1024.0);
        return String.format(Locale.ROOT, "%.1f MB", bytes / 1048576.0);
    }

    public EditPlan getEditPlan() { return editPlan; }

    public void refresh() { render(); }

    private void planEdit(String path) {
        if (!EditPlan.isEditable(path)) {
            new android.app.AlertDialog.Builder(activity).setMessage("Edição textual ainda não suportada para este formato.").setPositiveButton("OK", null).show();
            return;
        }
        if (apkFile == null || !apkFile.exists()) return;
        new Thread(() -> {
            String original;
            try { original = ApkPreview.readText(apkFile, path); }
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
                    .setMessage("A edição será registrada no plano. O APK original não será alterado.")
                    .setView(editor)
                    .setNegativeButton("Cancelar", null)
                    .setPositiveButton("Salvar no plano", (dialog, which) -> {
                        try {
                            editPlan.addTextReplacement(path, editor.getText().toString());
                            render();
                            new android.app.AlertDialog.Builder(activity).setMessage("Alteração registrada. Itens no plano: " + editPlan.size()).setPositiveButton("OK", null).show();
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
        new Thread(() -> {
            String value;
            try { value = ApkPreview.readText(apkFile, path); }
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
        view.setText(value);
        view.setTextColor(NegrescoTheme.TEXT);
        view.setTextSize(14);
        view.setPadding(NegrescoTheme.dp(activity, 14), NegrescoTheme.dp(activity, 14), NegrescoTheme.dp(activity, 14), NegrescoTheme.dp(activity, 14));
        view.setBackground(NegrescoTheme.panel(activity));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.bottomMargin = 5;
        view.setLayoutParams(params);
        return view;
    }
}
