package com.readroid.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.UriPermission;
import android.net.Uri;
import android.provider.OpenableColumns;
import android.database.Cursor;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Private, bounded history of SAF document references, not APK contents.
 * Only persisted read grants can become history entries.
 */
public final class P7ProjectHistory {
    private static final String PREFS = "p7_recent_apks";
    private static final String KEY = "entries";
    private static final int MAX = 12;
    private static final int MAX_URI_LENGTH = 2048;
    private static final int MAX_TEXT_LENGTH = 100;

    public static final class Entry {
        public final Uri uri;
        public final String name;
        public final String packageName;
        public final long openedAt;

        Entry(Uri uri, String name, String packageName, long openedAt) {
            this.uri = uri;
            this.name = name;
            this.packageName = packageName;
            this.openedAt = openedAt;
        }
    }

    private P7ProjectHistory() {}

    /** No guessed grant: a URI must actually be persisted by the system. */
    private static Set<String> authorized(Context context) {
        Set<String> allowed = new HashSet<>();
        for (UriPermission grant : context.getContentResolver().getPersistedUriPermissions()) {
            if (grant.isReadPermission() && grant.getUri() != null)
                allowed.add(grant.getUri().toString());
        }
        return allowed;
    }

    private static boolean safeUri(Uri uri) {
        return uri != null && "content".equals(uri.getScheme())
            && uri.toString().length() <= MAX_URI_LENGTH;
    }

    private static String clean(String value, String fallback) {
        if (value == null) return fallback;
        String cleaned = value.replaceAll("[\\p{Cntrl}]", " ").trim();
        if (cleaned.isEmpty()) return fallback;
        return cleaned.length() > MAX_TEXT_LENGTH
            ? cleaned.substring(0, MAX_TEXT_LENGTH) : cleaned;
    }

    public static String documentName(Context context, Uri uri) {
        if (!safeUri(uri)) return "APK";
        try (Cursor cursor = context.getContentResolver().query(
                uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst())
                return clean(cursor.getString(0), "APK");
        } catch (Exception ignored) {
            // Untrusted document providers may not support metadata queries.
        }
        return "APK";
    }

    static List<Entry> decode(String encoded, Set<String> allowed) {
        if (encoded == null || encoded.length() > 65536) return Collections.emptyList();
        List<Entry> result = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        try {
            JSONArray array = new JSONArray(encoded);
            for (int i = 0; i < array.length() && result.size() < MAX; i++) {
                JSONObject item = array.optJSONObject(i);
                if (item == null) continue;
                String source = item.optString("uri", "");
                Uri uri = Uri.parse(source);
                if (!safeUri(uri) || !allowed.contains(source) || !seen.add(source)) continue;
                result.add(new Entry(uri, clean(item.optString("name"), "APK"),
                    clean(item.optString("package"), "Pacote desconhecido"),
                    Math.max(0, item.optLong("openedAt", 0))));
            }
        } catch (Exception ignored) {
            return Collections.emptyList();
        }
        return result;
    }

    public static List<Entry> list(Context context) {
        String raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY, "[]");
        return decode(raw, authorized(context));
    }

    private static String encode(List<Entry> entries) throws Exception {
        JSONArray array = new JSONArray();
        for (int i = 0; i < Math.min(MAX, entries.size()); i++) {
            Entry e = entries.get(i);
            JSONObject item = new JSONObject();
            item.put("uri", e.uri.toString());
            item.put("name", clean(e.name, "APK"));
            item.put("package", clean(e.packageName, "Pacote desconhecido"));
            item.put("openedAt", Math.max(0, e.openedAt));
            array.put(item);
        }
        return array.toString();
    }

    /** Called after analysis succeeds, never for failed/cancelled imports. */
    public static boolean record(Context context, Uri uri, String packageName) {
        if (!safeUri(uri) || !authorized(context).contains(uri.toString())) return false;
        List<Entry> items = new ArrayList<>(list(context));
        items.removeIf(e -> e.uri.equals(uri));
        items.add(0, new Entry(uri, documentName(context, uri),
            clean(packageName, "Pacote desconhecido"), System.currentTimeMillis()));
        try {
            return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putString(KEY, encode(items)).commit();
        } catch (Exception invalid) {
            return false;
        }
    }

    /** Remove only one recent reference; leave the original APK untouched. */
    public static boolean forget(Context context, Uri uri) {
        if (!safeUri(uri)) return false;
        List<Entry> items = new ArrayList<>(list(context));
        if (!items.removeIf(e -> uri.equals(e.uri))) return false;
        try {
            return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putString(KEY, encode(items)).commit();
        } catch (Exception invalid) {
            return false;
        }
    }

    public static boolean hasPermission(Context context, Uri uri) {
        return safeUri(uri) && authorized(context).contains(uri.toString());
    }

    /** Clears recent-history metadata, not the current project or its edits. */
    public static boolean clear(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().remove(KEY).commit();
    }
}
