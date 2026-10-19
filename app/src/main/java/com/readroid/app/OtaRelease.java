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
    // Never infer authenticity from successfully parsing attacker-controlled JSON.
    private boolean signatureVerified;

    boolean hasVerifiedSignature() { return signatureVerified; }

    void markSignatureVerified() { signatureVerified = true; }

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
        // JSONObject's getInt/getString silently coerce some malformed JSON
        // (including fractional versions and numeric values passed as strings).
        // Reject type confusion before trusting fields from a signed manifest.
        Object codeValue = data.opt("versionCode");
        Object sizeValue = data.opt("sizeBytes");
        if (!isJsonInteger(codeValue) || !isJsonInteger(sizeValue)
            || !(data.opt("versionName") instanceof String)
            || !(data.opt("channel") instanceof String)
            || !(data.opt("downloadUrl") instanceof String)
            || !(data.opt("sha256") instanceof String)
            || (data.has("notes") && !(data.opt("notes") instanceof String)))
            throw new IllegalArgumentException("Tipos OTA inválidos");
        long rawCode = ((Number) codeValue).longValue();
        if (rawCode < 1 || rawCode > Integer.MAX_VALUE)
            throw new IllegalArgumentException("VersionCode OTA inválido");
        int code = (int) rawCode;
        String name = (String) data.opt("versionName");
        String track = ((String) data.opt("channel")).toLowerCase(Locale.ROOT);
        String url = (String) data.opt("downloadUrl");
        String hash = ((String) data.opt("sha256")).toLowerCase(Locale.ROOT);
        long size = ((Number) sizeValue).longValue();
        String notes = data.has("notes") ? (String) data.opt("notes") : "";
        if (code < 1 || name.length() > 80 || name.isEmpty()
            || !(track.equals("stable") || track.equals("beta"))
            || !hash.matches("[0-9a-f]{64}") || size < 1 || size > 1073741824L
            || notes.length() > 8000) throw new IllegalArgumentException("Campos OTA inválidos");
        URI uri = new URI(url);
        if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
            || uri.getUserInfo() != null || uri.getFragment() != null
            || (uri.getPort() != -1 && uri.getPort() != 443)
            || url.length() > 2048) throw new IllegalArgumentException("URL OTA insegura");
        return new OtaRelease(code, name, track, url, hash, size, notes);
    }

    private static boolean isJsonInteger(Object value) {
        // org.json on supported Android versions parses integer tokens as
        // Integer/Long; Double/BigDecimal and numeric strings are not accepted.
        return value instanceof Integer || value instanceof Long;
    }

    public boolean isUpgrade(int installedCode, String selectedChannel) {
        return versionCode > installedCode && channel.equals(selectedChannel);
    }
}
