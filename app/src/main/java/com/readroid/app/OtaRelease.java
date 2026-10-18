package com.readroid.app;

import org.json.JSONObject;
import java.net.URI;
import java.util.Locale;

/** Strict parser for untrusted OTA release metadata. Parsing is not signature verification. */
public final class OtaRelease {
    public final int versionCode;
    public final String versionName;
    public final String channel;
    public final String downloadUrl;
    public final String sha256;
    public final long sizeBytes;
    public final String notes;

    private OtaRelease(int code, String name, String track, String url,
                       String hash, long size, String changelog) {
        versionCode = code;
        versionName = name;
        channel = track;
        downloadUrl = url;
        sha256 = hash;
        sizeBytes = size;
        notes = changelog;
    }

    public static OtaRelease parse(String json) throws Exception {
        if (json == null || json.length() > 32768) throw new IllegalArgumentException("Manifesto OTA inválido");
        JSONObject data = new JSONObject(json);
        int code = data.getInt("versionCode");
        String name = data.getString("versionName");
        String track = data.getString("channel").toLowerCase(Locale.ROOT);
        String url = data.getString("downloadUrl");
        String hash = data.getString("sha256").toLowerCase(Locale.ROOT);
        long size = data.getLong("sizeBytes");
        String notes = data.optString("notes", "");
        if (code < 1 || name.length() > 80 || name.isEmpty()
            || !(track.equals("stable") || track.equals("beta"))
            || !hash.matches("[0-9a-f]{64}") || size < 1 || size > 1073741824L
            || notes.length() > 8000) throw new IllegalArgumentException("Campos OTA inválidos");
        URI uri = new URI(url);
        if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
            || uri.getUserInfo() != null || uri.getFragment() != null
            || url.length() > 2048) throw new IllegalArgumentException("URL OTA insegura");
        return new OtaRelease(code, name, track, url, hash, size, notes);
    }

    public boolean isUpgrade(int installedCode, String selectedChannel) {
        return versionCode > installedCode && channel.equals(selectedChannel);
    }
}
