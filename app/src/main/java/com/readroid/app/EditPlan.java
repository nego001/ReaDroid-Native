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

    public static boolean isEditable(String path) {
        String p = path.toLowerCase(java.util.Locale.ROOT);
        return p.endsWith(".txt") || p.endsWith(".json") || p.endsWith(".html")
            || p.endsWith(".css") || p.endsWith(".js") || p.endsWith(".properties")
            || p.endsWith(".md") || p.endsWith(".csv");
    }

    public int size() { return replacements.size(); }

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
