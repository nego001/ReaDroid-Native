package com.readroid.app;

import org.json.JSONArray;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/** In-memory edit plan only. Does not change the source APK. */
public final class EditPlan {
    private static final int MAX_REPLACEMENT_BYTES = 128 * 1024;
    private final LinkedHashMap<String, String> replacements = new LinkedHashMap<>();

    /**
     * Reject over-budget text and malformed UTF-16 (unpaired surrogates).
     * String.getBytes(UTF_8) silently replaces unpaired surrogates with '?',
     * which would otherwise corrupt the user's edit on export/recovery.
     */
    private static boolean invalidReplacement(String text) {
        if (text == null || text.length() > MAX_REPLACEMENT_BYTES) return true;
        for (int i = 0; i < text.length(); i++) {
            char unit = text.charAt(i);
            if (Character.isHighSurrogate(unit)) {
                if (i + 1 >= text.length()
                    || !Character.isLowSurrogate(text.charAt(i + 1))) return true;
                i++; // A valid supplementary code point uses a surrogate pair.
            } else if (Character.isLowSurrogate(unit)) {
                return true;
            }
        }
        return text.getBytes(StandardCharsets.UTF_8).length > MAX_REPLACEMENT_BYTES;
    }

    public void addTextReplacement(String path, String replacement) {
        if (path == null || path.isEmpty() || path.startsWith("/") || path.contains("..") || path.contains("\\"))
            throw new IllegalArgumentException("Caminho inválido");
        if (!isEditable(path)) throw new IllegalArgumentException("Tipo de arquivo não suportado para edição textual");
        if (invalidReplacement(replacement))
            throw new IllegalArgumentException("Texto inválido ou acima de 128 KiB em UTF-8");
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
            || !isEditable(path) || invalidReplacement(replacement))
            throw new IllegalArgumentException("Caminho ou edição inválida (UTF-8, máximo 128 KiB)");
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
