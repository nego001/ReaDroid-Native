package com.readroid.app;

import org.json.JSONArray;
import org.json.JSONObject;
import java.util.LinkedHashMap;
import java.util.Map;

/** In-memory edit plan only. Does not change the source APK. */
public final class EditPlan {
    private final LinkedHashMap<String, String> replacements = new LinkedHashMap<>();

    public void addTextReplacement(String path, String replacement) {
        if (path == null || path.isEmpty() || path.startsWith("/") || path.contains("..") || path.contains("\\"))
            throw new IllegalArgumentException("Caminho inválido");
        if (!isEditable(path)) throw new IllegalArgumentException("Tipo de arquivo não suportado para edição textual");
        if (replacement == null || replacement.length() > 131072)
            throw new IllegalArgumentException("Texto excede o limite de 128 KB");
        replacements.put(path, replacement);
    }

    /** The functional result of an edit, separate from visual presentation. */
    public enum EditResult { ADDED, UPDATED, REMOVED, UNCHANGED }

    /**
     * Keeps the plan minimal: do not store the original text as a replacement.
     * Re-saving an identical value is not falsely reported as a new change.
     */
    public EditResult applyTextEdit(String path, String original, String replacement) {
        if (original == null || replacement == null)
            throw new IllegalArgumentException("Texto de origem ou edição ausente");
        // Validate paths and text even when user submits unchanged content.
        if (path == null || path.isEmpty() || path.startsWith("/")
            || path.contains("..") || path.contains("\\")
            || !isEditable(path) || replacement.length() > 131072)
            throw new IllegalArgumentException("Caminho ou edição inválida");
        if (replacement.equals(original))
            return replacements.remove(path) == null ? EditResult.UNCHANGED : EditResult.REMOVED;
        String previous = replacements.get(path);
        if (replacement.equals(previous)) return EditResult.UNCHANGED;
        addTextReplacement(path, replacement);
        return previous == null ? EditResult.ADDED : EditResult.UPDATED;
    }

    public static boolean isEditable(String path) {
        String p = path.toLowerCase(java.util.Locale.ROOT);
        return p.endsWith(".txt") || p.endsWith(".json") || p.endsWith(".html")
            || p.endsWith(".css") || p.endsWith(".js") || p.endsWith(".properties")
            || p.endsWith(".md") || p.endsWith(".csv");
    }

    public int size() { return replacements.size(); }

    public boolean remove(String path) { return replacements.remove(path) != null; }

    public boolean contains(String path) { return replacements.containsKey(path); }

    public String get(String path) { return replacements.get(path); }

    public Map<String, String> snapshot() { return new LinkedHashMap<>(replacements); }

    public void clear() { replacements.clear(); }

    public JSONObject toJson() throws Exception {
        JSONObject result = new JSONObject();
        result.put("format", "readroid-edit-plan-v1");
        result.put("applied", false);
        JSONArray changes = new JSONArray();
        for (Map.Entry<String, String> change : replacements.entrySet()) {
            JSONObject item = new JSONObject();
            item.put("path", change.getKey());
            item.put("replacementText", change.getValue());
            changes.put(item);
        }
        result.put("changes", changes);
        return result;
    }
}
