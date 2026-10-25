package com.readroid.app;

import android.app.Activity;
import android.graphics.Color;
import android.text.Editable;
import android.text.InputFilter;
import android.text.TextWatcher;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.HorizontalScrollView;
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
    private final P7ExplorerChrome chrome;
    private final LinearLayout quickFilters;
    private final TextView advancedSelection;
    private static final String[] QUICK_CATEGORIES = {
        "Todos", "Smali", "Recursos", "Imagens", "XML"
    };
    private final TextView breadcrumb;
    private final TextView countLabel;
    private final TextView indexWarning;
    private boolean indexUnavailable = false;
    private final Button upButton;
    private final EditText search;
    private final Button filterButton;
    private String activeCategory = "Todos";
    private int pageLimit = 120;
    private final ArrayList<JSONObject> files = new ArrayList<>();
    private String folder = "";
    private java.io.File apkFile;
    private java.io.File indexFile;
    private int indexPageOffset = 0;
    private final EditPlan editPlan = new EditPlan();
    private static final String[] CATEGORIES = {
        "Todos", "Smali", "Recursos", "Imagens", "XML",
        "Código DEX", "Bibliotecas", "Assets", "Assinaturas/metadados",
        "Manifesto", "Outros", "Editáveis", "Alterados"
    };

    /** Session-only UI state. Never persisted to disk or reused across APKs. */
    static final class BrowseState {
        final String folder;
        final String category;
        final String query;
        final int pageLimit;
        final int indexPageOffset;

        BrowseState(String folder, String category, String query, int pageLimit) {
            this(folder, category, query, pageLimit, 0);
        }

        BrowseState(String folder, String category, String query,
                int pageLimit, int indexPageOffset) {
            this.folder = folder;
            this.category = category;
            this.query = query;
            this.pageLimit = pageLimit;
            this.indexPageOffset = indexPageOffset;
        }
    }

    BrowseState snapshotBrowseState() {
        return new BrowseState(folder, activeCategory, search.getText().toString(),
            pageLimit, indexPageOffset);
    }

    void restoreBrowseState(BrowseState state) {
        if (state == null) return;
        // Do not trust a retained folder unless it still belongs to this APK.
        // The JSON fallback may contain only a small prefix of a large APK.
        // Restore a deep folder from the real SQLite index, not exclusively
        // from the partial JSON list. Never trust the retained path alone.
        folder = isRestorableFolder(state.folder) ? state.folder : "";
        activeCategory = java.util.Arrays.asList(CATEGORIES).contains(state.category)
            ? state.category : "Todos";
        filterButton.setText("▦");
        // setText invokes the TextWatcher (which resets pagination): set the
        // retained limit afterwards and render the final, validated state.
        String safeQuery = state.query == null ? "" : state.query;
        if (safeQuery.length() > 256) safeQuery = safeQuery.substring(0, 256);
        search.setText(safeQuery);
        pageLimit = Math.max(120, Math.min(state.pageLimit,
            Math.max(120, files.size() + 120)));
        indexPageOffset = Math.max(0, Math.min(state.indexPageOffset, 150000));
        render();
    }

    private boolean hasFileBelow(String prefix) {
        for (JSONObject file : files) {
            if (file.optString("path").startsWith(prefix)) return true;
        }
        return false;
    }

    private boolean isRestorableFolder(String proposed) {
        if (proposed == null) return false;
        if (proposed.isEmpty()) return true;
        if (!proposed.endsWith("/")) return false;
        try {
            // Segment-based validation allows legitimate names such as
            // "release..backup/" but rejects traversal and absolute paths.
            ApkDiskIndex.validatePath(proposed);
            if (hasFileBelow(proposed)) return true;
            // The SQLite metadata query validates the source size and mtime
            // and checks the exact directory row (including empty folders).
            return apkFile != null && indexFile != null
                && ApkDiskIndex.containsDirectory(apkFile, indexFile, proposed);
        } catch (java.io.IOException invalidOrStale) {
            return false;
        }
    }

    /**
     * Preserve the detailed search prompt for normal fonts while keeping
     * the native EditText legible at 320dp and 200% accessibility scale.
     * This changes hint text only; search terms and indexing are untouched.
     */
    static String searchHint(int widthDp, float systemFont, float appFont) {
        float effective = Math.max(0.85f, systemFont)
            * Math.max(0.85f, appFont);
        if (effective >= 1.65f) return "Buscar no APK";
        if (widthDp <= 360) return "Buscar no APK...";
        return "Buscar arquivo pelo nome ou caminho";
    }

    public ExplorerView(Activity activity, LinearLayout parent) {
        this.activity = activity;
        // Final search is initialized before the breadcrumb callback captures it.
        search = new EditText(activity);
        chrome = new P7ExplorerChrome(activity, parent, destination -> {
            folder = destination;
            pageLimit = 120;
            indexPageOffset = 0;
            if (!search.getText().toString().isEmpty())
                search.setText("");
            render();
        });
        search.setSingleLine(true);
        // ApkDiskIndex.page() allows up to 256 characters. Without the same
        // input bound, pasting a longer query looks like a broken SQLite
        // index and permanently downgrades the session to the partial JSON.
        search.setFilters(new InputFilter[]{new InputFilter.LengthFilter(256)});
        int screenWidthDp = activity.getResources().getConfiguration().screenWidthDp;
        boolean narrow = screenWidthDp <= 360;
        search.setHint(searchHint(screenWidthDp,
            activity.getResources().getConfiguration().fontScale,
            NegrescoTheme.FONT_SCALE));
        search.setTextSize((narrow ? 13 : 14) * NegrescoTheme.FONT_SCALE);
        search.setTextColor(NegrescoTheme.TEXT);
        search.setHintTextColor(NegrescoTheme.MUTED);
        search.setBackground(NegrescoTheme.panel(activity));
        search.setPadding(NegrescoTheme.dp(activity, 12), NegrescoTheme.dp(activity, 9), NegrescoTheme.dp(activity, 12), NegrescoTheme.dp(activity, 9));
        parent.addView(search);
        // Keep all five reference chips and the extra filters on ONE row.
        LinearLayout filterRow = new LinearLayout(activity);
        filterRow.setGravity(android.view.Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams filterParams = new LinearLayout.LayoutParams(-1, -2);
        filterParams.topMargin = NegrescoTheme.dp(activity, 7);
        parent.addView(filterRow, filterParams);
        HorizontalScrollView quickScroller = new HorizontalScrollView(activity);
        quickScroller.setHorizontalScrollBarEnabled(false);
        quickScroller.setFillViewport(false);
        filterRow.addView(quickScroller, new LinearLayout.LayoutParams(0, -2, 1f));
        quickFilters = new LinearLayout(activity);
        quickFilters.setOrientation(LinearLayout.HORIZONTAL);
        quickScroller.addView(quickFilters);
        filterButton = NegrescoTheme.action(activity, "▦", false);
        filterButton.setContentDescription("Abrir filtros avançados");
        filterButton.setMinHeight(NegrescoTheme.dp(activity, 48));
        filterButton.setMinimumHeight(NegrescoTheme.dp(activity, 48));
        filterButton.setTextSize(17 * NegrescoTheme.FONT_SCALE);
        filterButton.setPadding(0, 0, 0, 0);
        LinearLayout.LayoutParams advancedParams =
            new LinearLayout.LayoutParams(NegrescoTheme.dp(activity, 48),
                NegrescoTheme.dp(activity, 48));
        advancedParams.leftMargin = NegrescoTheme.dp(activity, 5);
        filterRow.addView(filterButton, advancedParams);

        // An advanced filter was previously invisible after selection because
        // none of the five quick chips remained highlighted. Show one compact,
        // accessible removable selection without hiding the reference chips.
        advancedSelection = new TextView(activity);
        advancedSelection.setTextColor(NegrescoTheme.ACCENT);
        advancedSelection.setTextSize(12 * NegrescoTheme.FONT_SCALE);
        advancedSelection.setMinHeight(NegrescoTheme.dp(activity, 48));
        advancedSelection.setGravity(android.view.Gravity.CENTER_VERTICAL);
        advancedSelection.setPadding(NegrescoTheme.dp(activity, 12), 0,
            NegrescoTheme.dp(activity, 12), 0);
        advancedSelection.setBackground(NegrescoTheme.studioCard(activity, true));
        advancedSelection.setClickable(true);
        advancedSelection.setFocusable(true);
        advancedSelection.setVisibility(View.GONE);
        LinearLayout.LayoutParams selectionParams =
            new LinearLayout.LayoutParams(-1, -2);
        selectionParams.topMargin = NegrescoTheme.dp(activity, 4);
        parent.addView(advancedSelection, selectionParams);
        advancedSelection.setOnClickListener(v -> {
            activeCategory = "Todos";
            pageLimit = 120;
            indexPageOffset = 0;
            render();
        });
        filterButton.setOnClickListener(v -> {
            new android.app.AlertDialog.Builder(activity)
                .setTitle("Filtrar arquivos")
                .setSingleChoiceItems(CATEGORIES, java.util.Arrays.asList(CATEGORIES).indexOf(activeCategory),
                    (dialog, which) -> {
                        activeCategory = CATEGORIES[which];
                        pageLimit = 120;
                        indexPageOffset = 0;
                        filterButton.setText("▦");
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
        indexWarning = new TextView(activity);
        indexWarning.setText("Índice indisponível. A lista pode estar incompleta. "
            + "Reabra o APK para analisar novamente.");
        indexWarning.setTextColor(0xffffba68);
        indexWarning.setTextSize(12 * NegrescoTheme.FONT_SCALE);
        indexWarning.setPadding(NegrescoTheme.dp(activity, 9),
            NegrescoTheme.dp(activity, 8), NegrescoTheme.dp(activity, 9),
            NegrescoTheme.dp(activity, 8));
        indexWarning.setBackground(NegrescoTheme.panel(activity));
        indexWarning.setContentDescription(
            "Aviso: índice indisponível; listagem de arquivos possivelmente incompleta");
        indexWarning.setVisibility(View.GONE);
        parent.addView(indexWarning);
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
            indexPageOffset = 0;
            search.setText("");
            render();
        });
        list = new LinearLayout(activity);
        list.setOrientation(LinearLayout.VERTICAL);
        parent.addView(list);
        search.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            public void onTextChanged(CharSequence s, int start, int before, int count) {
                pageLimit = 120; indexPageOffset = 0; render();
            }
            public void afterTextChanged(Editable e) {}
        });
        render();
    }

    /** Native Explorer back/menu controls, supplied by its actual Activity. */
    public void setNavigationActions(Runnable exit, Runnable openApk,
            Runnable reviewPlan) {
        chrome.setActions(exit, openApk, reviewPlan);
    }

    public void setFiles(JSONArray array, java.io.File apkFile) {
        this.apkFile = apkFile;
        this.indexFile = null;
        indexUnavailable = false; // A new APK starts a fresh browsing session.
        indexPageOffset = 0;
        chrome.setProject(null, -1);
        files.clear();
        folder = "";
        activeCategory = "Todos";
        pageLimit = 120;
        filterButton.setText("▦");
        search.setText("");
        if (array != null) for (int i = 0; i < array.length(); i++) {
            JSONObject file = array.optJSONObject(i);
            if (file != null) files.add(file);
        }
        render();
    }

    /** Optional indexed mode. Existing JSON listing stays as a safe fallback. */
    public void setIndexedFiles(JSONArray fallback, java.io.File source,
            java.io.File index) {
        setFiles(fallback, source);
        if (source != null && source.isFile() && index != null && index.isFile())
            indexFile = index;
        else if (source != null && source.isFile())
            indexUnavailable = true; // Expected index missing.
        render();
    }

    /** Called by MainActivity only when the real report has been accepted. */
    public void setProjectSummary(String packageName, long sourceSizeBytes) {
        chrome.setProject(packageName, sourceSizeBytes);
        chrome.setEditCount(editPlan.size());
    }

    private void refreshQuickFilters() {
        quickFilters.removeAllViews();
        for (String name : QUICK_CATEGORIES) {
            final boolean selected = name.equals(activeCategory);
            TextView chip = new TextView(activity);
            chip.setText(name);
            chip.setTextSize(12 * NegrescoTheme.FONT_SCALE);
            chip.setTextColor(selected ? NegrescoTheme.ON_ACCENT : NegrescoTheme.TEXT);
            chip.setGravity(android.view.Gravity.CENTER);
            chip.setMinHeight(NegrescoTheme.dp(activity, 48));
            chip.setPadding(NegrescoTheme.dp(activity, 10),
                NegrescoTheme.dp(activity, 6),
                NegrescoTheme.dp(activity, 10),
                NegrescoTheme.dp(activity, 6));
            android.graphics.drawable.GradientDrawable bg =
                new android.graphics.drawable.GradientDrawable();
            bg.setColor(selected ? NegrescoTheme.ACCENT : NegrescoTheme.SURFACE);
            bg.setStroke(NegrescoTheme.dp(activity, 1),
                selected ? NegrescoTheme.ACCENT : NegrescoTheme.BORDER);
            bg.setCornerRadius(NegrescoTheme.dp(activity, 14));
            chip.setBackground(bg);
            chip.setContentDescription("Filtrar por " + name
                + (selected ? ", selecionado" : ""));
            chip.setClickable(true);
            chip.setFocusable(true);
            chip.setOnClickListener(v -> {
                if (name.equals(activeCategory)) return;
                activeCategory = name;
                pageLimit = 120;
                indexPageOffset = 0;
                filterButton.setText("▦");
                render();
            });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-2, -2);
            lp.rightMargin = NegrescoTheme.dp(activity, 5);
            quickFilters.addView(chip, lp);
        }
    }

    private void refreshAdvancedSelection() {
        boolean advanced = !java.util.Arrays.asList(QUICK_CATEGORIES)
            .contains(activeCategory);
        advancedSelection.setVisibility(advanced ? View.VISIBLE : View.GONE);
        if (advanced) {
            advancedSelection.setText("Filtro ativo: " + activeCategory
                + "  •  Toque para remover");
            advancedSelection.setContentDescription(
                "Remover filtro " + activeCategory);
        } else {
            advancedSelection.setContentDescription(null);
        }
    }

    /** Filters must reflect the real archive, including XML and images in any folder. */
    private boolean matchesCategory(String path, String type) {
        if ("Todos".equals(activeCategory)) return true;
        if ("Editáveis".equals(activeCategory)) return EditPlan.isEditable(path);
        if ("Alterados".equals(activeCategory)) return editPlan.contains(path);
        String lower = path.toLowerCase(Locale.ROOT);
        if ("Smali".equals(activeCategory)) return lower.endsWith(".smali");
        if ("XML".equals(activeCategory)) return lower.endsWith(".xml");
        if ("Imagens".equals(activeCategory))
            return lower.endsWith(".png") || lower.endsWith(".webp")
                || lower.endsWith(".jpg") || lower.endsWith(".jpeg")
                || lower.endsWith(".gif") || lower.endsWith(".bmp");
        return activeCategory.equals(type);
    }

    private void render() {
        String queryText = search.getText().toString().trim();
        chrome.updateBreadcrumb(folder, !queryText.isEmpty());
        chrome.setEditCount(editPlan.size());
        refreshQuickFilters();
        refreshAdvancedSelection();
        if (indexFile != null) {
            if (renderIndexPage()) {
                indexWarning.setVisibility(View.GONE);
                return;
            }
            indexFile = null; // Fall back on a stale or unavailable index.
            indexUnavailable = true;
        }
        indexWarning.setVisibility(indexUnavailable ? View.VISIBLE : View.GONE);
        list.removeAllViews();
        String query = search.getText().toString().trim().toLowerCase(Locale.ROOT);
        breadcrumb.setText(query.isEmpty() ? "APK / " + folder : "Busca em todo o APK: " + query);
        // The segmented trail replaces the old duplicate path label. Keep
        // the search context line visible when querying the entire APK.
        breadcrumb.setVisibility(query.isEmpty() ? View.GONE : View.VISIBLE);
        upButton.setEnabled(!folder.isEmpty() || !query.isEmpty());
        upButton.setVisibility(folder.isEmpty() && query.isEmpty()
            ? View.GONE : View.VISIBLE);
        breadcrumb.setOnClickListener(v -> {
            folder = "";
            search.setText("");
            render();
        });
        LinkedHashSet<String> folders = new LinkedHashSet<>();
        ArrayList<JSONObject> visible = new ArrayList<>();
        for (JSONObject item : files) {
            String path = item.optString("path");
            if (!matchesCategory(path, item.optString("category"))) continue;
            if (!query.isEmpty()) {
                if (path.toLowerCase(Locale.ROOT).contains(query)) visible.add(item);
            } else if (path.startsWith(folder)) {
                String rest = path.substring(folder.length());
                int slash = rest.indexOf('/');
                if (slash >= 0) folders.add(rest.substring(0, slash + 1));
                else visible.add(item);
            }
        }
        countLabel.setText((indexUnavailable ? "Prévia possivelmente incompleta  •  " : "")
            + folders.size() + " pastas  •  " + visible.size()
            + " arquivos  •  " + editPlan.size() + " alterações pendentes");
        int shown = 0;
        for (String child : folders) {
            if (shown >= pageLimit) break;
            shown++;
            final String nextFolder = folder + child;
            list.addView(new P7ExplorerEntryRow(activity, child, "Pasta",
                true, false,
                v -> enterFolder(nextFolder),
                v -> showFolderActions(child, nextFolder)));
        }
        for (JSONObject file : visible) {
            if (shown >= pageLimit) break;
            shown++;
            String path = file.optString("path");
            String name = query.isEmpty() ? path.substring(folder.length()) : path;
            boolean editable = EditPlan.isEditable(path);
            final String category = file.optString("category");
            final long sizeBytes = file.optLong("sizeBytes", -1);
            list.addView(new P7ExplorerEntryRow(activity, name,
                fileDetail(category, sizeBytes, path), false,
                editPlan.contains(path),
                v -> showFileActions(name, path, category, sizeBytes, editable),
                v -> showFileActions(name, path, category, sizeBytes, editable)));
        }
        if (shown == 0) list.addView(item(apkFile == null
            ? "Abra um APK para explorar os arquivos."
            : "Nenhum arquivo nesta pasta."));
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


    /** Dispatch both edit-aware filters to the complete archive index. */
    private ApkDiskIndex.Page currentIndexPage(String query) throws java.io.IOException {
        if ("Alterados".equals(activeCategory)) {
            return ApkDiskIndex.pageChanged(apkFile, indexFile, folder, query,
                editPlan.snapshot().keySet(), indexPageOffset, 120);
        }
        return ApkDiskIndex.page(apkFile, indexFile, folder,
            query, activeCategory, indexPageOffset, 120);
    }

    /** Each visible page is bounded to 120 entries. SQLite is read-only. */
    private boolean renderIndexPage() {
        if (apkFile == null || !apkFile.isFile() || !indexFile.isFile())
            return false;
        String query = search.getText().toString().trim();
        try {
            ApkDiskIndex.Page page = currentIndexPage(query);
            if (indexPageOffset > 0 && page.items.isEmpty()) {
                indexPageOffset = 0;
                page = currentIndexPage(query);
            }
            list.removeAllViews();
            breadcrumb.setText(query.isEmpty() ? "APK / " + folder
                : "Busca em todo o APK: " + query);
            breadcrumb.setVisibility(query.isEmpty() ? View.GONE : View.VISIBLE);
            upButton.setEnabled(!folder.isEmpty() || !query.isEmpty());
            upButton.setVisibility(folder.isEmpty() && query.isEmpty()
                ? View.GONE : View.VISIBLE);
            breadcrumb.setOnClickListener(v -> {
                folder = ""; indexPageOffset = 0;
                search.setText(""); render();
            });
            countLabel.setText(page.totalMatches + " itens no índice  •  página "
                + (indexPageOffset / 120 + 1) + "  •  "
                + editPlan.size() + " alterações pendentes");
            for (ApkDiskIndex.Item file : page.items) {
                final String path = file.path;
                if (file.directory) {
                    list.addView(new P7ExplorerEntryRow(activity, file.name,
                        "Pasta", true, false,
                        v -> enterFolder(path),
                        v -> showFolderActions(file.name, path)));
                    continue;
                }
                String name = query.isEmpty() ? file.name : file.path;
                boolean editable = EditPlan.isEditable(path);
                list.addView(new P7ExplorerEntryRow(activity, name,
                    fileDetail(file.category, file.sizeBytes, path), false,
                    editPlan.contains(path),
                    v -> showFileActions(name, path, file.category,
                        file.sizeBytes, editable),
                    v -> showFileActions(name, path, file.category,
                        file.sizeBytes, editable)));
            }
            if (page.items.isEmpty()) list.addView(item("Nenhum arquivo nesta pasta."));
            if (indexPageOffset > 0) {
                Button back = NegrescoTheme.action(activity, "Página anterior", false);
                list.addView(back);
                back.setOnClickListener(v -> {
                    indexPageOffset = Math.max(0, indexPageOffset - 120);
                    render();
                });
            }
            if (page.totalMatches - indexPageOffset > page.items.size()) {
                Button next = NegrescoTheme.action(activity,
                    "Próxima página (" + Math.min(120,
                        page.totalMatches - indexPageOffset - page.items.size()) + ")", false);
                list.addView(next);
                next.setOnClickListener(v -> {
                    indexPageOffset += 120; render();
                });
            }
            return true;
        } catch (Exception staleOrInvalid) {
            // The optional index cannot destroy the open editing workspace.
            return false;
        }
    }

    /** Never invent file timestamps or child counts missing from the APK index. */
    private String fileDetail(String category, long sizeBytes, String path) {
        String status = editPlan.contains(path) ? "ALTERADO"
            : EditPlan.isEditable(path) ? "EDITÁVEL" : "LEITURA";
        return category + "  •  " + formatBytes(sizeBytes) + "  •  " + status;
    }

    private void enterFolder(String path) {
        folder = path;
        pageLimit = 120;
        indexPageOffset = 0;
        render();
    }

    private void copyPath(String path) {
        android.content.ClipboardManager clipboard =
            (android.content.ClipboardManager) activity.getSystemService(
                android.content.Context.CLIPBOARD_SERVICE);
        if (clipboard != null) clipboard.setPrimaryClip(
            android.content.ClipData.newPlainText("Caminho do arquivo APK", path));
    }

    private void showFolderActions(String label, String path) {
        new android.app.AlertDialog.Builder(activity)
            .setTitle(label)
            .setItems(new String[]{"Abrir pasta", "Copiar caminho"},
                (dialog, selected) -> {
                    if (selected == 0) enterFolder(path);
                    else copyPath(path);
                })
            .setNegativeButton("Fechar", null)
            .show();
    }

    private void showFileActions(String label, String path, String category,
            long sizeBytes, boolean editable) {
        String[] choices = editable
            ? new String[]{"Ver texto", "Planejar edição", "Detalhes técnicos",
                "Copiar caminho"}
            : new String[]{"Ver texto", "Detalhes técnicos", "Copiar caminho"};
        new android.app.AlertDialog.Builder(activity)
            .setTitle(label)
            .setMessage("Tipo: " + category + "  •  " + formatBytes(sizeBytes))
            .setItems(choices, (dialog, selected) -> {
                String action = choices[selected];
                if ("Ver texto".equals(action)) preview(path);
                else if ("Planejar edição".equals(action)) planEdit(path);
                else if ("Detalhes técnicos".equals(action)) inspectEntry(path);
                else copyPath(path);
            })
            .setNegativeButton("Fechar", null).show();
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
        // Native scalable glyphs approximate the approved blue folder/file list.
        // Keep the original text prefixes and click listeners for accessibility
        // and for the proven SQLite/legacy navigation test contracts.
        int glyph = value.startsWith("▸  ") ? R.drawable.ic_p7_folder
            : (value.contains("\n") ? R.drawable.ic_p7_file : 0);
        if (glyph != 0) {
            android.graphics.drawable.Drawable icon = activity.getDrawable(glyph);
            if (icon != null) {
                int extent = NegrescoTheme.dp(activity, 24);
                icon.setBounds(0, 0, extent, extent);
                view.setCompoundDrawables(icon, null, null, null);
                view.setCompoundDrawablePadding(NegrescoTheme.dp(activity, 12));
            }
        }
        view.setTextColor(NegrescoTheme.TEXT);
        view.setTextSize(14 * NegrescoTheme.FONT_SCALE);
        view.setLineSpacing(NegrescoTheme.dp(activity, 3), 1f);
        view.setMinHeight(NegrescoTheme.dp(activity, 51));
        view.setPadding(NegrescoTheme.dp(activity, 8), NegrescoTheme.dp(activity, 9),
            NegrescoTheme.dp(activity, 8), NegrescoTheme.dp(activity, 9));
        // Flat rows with subtle separators reproduce the file list rather
        // than stacking oversized rounded action cards.
        android.graphics.drawable.GradientDrawable row =
            new android.graphics.drawable.GradientDrawable();
        row.setColor(NegrescoTheme.BACKGROUND);
        row.setStroke(NegrescoTheme.dp(activity, 1), NegrescoTheme.BORDER);
        row.setCornerRadius(NegrescoTheme.dp(activity, 5));
        view.setBackground(row);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.bottomMargin = NegrescoTheme.dp(activity, 2);
        view.setLayoutParams(params);
        return view;
    }
}
