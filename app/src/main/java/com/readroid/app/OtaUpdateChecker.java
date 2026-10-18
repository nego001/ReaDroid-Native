package com.readroid.app;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** Fetches a bounded OTA envelope. Call only on a worker thread. */
public final class OtaUpdateChecker {
    private OtaUpdateChecker() {}

    public static OtaRelease check(String endpoint, String trustedKey, int installedCode,
                                   String channel) throws Exception {
        if (endpoint == null || !endpoint.startsWith("https://") || endpoint.length() > 2048)
            throw new SecurityException("Endpoint OTA deve usar HTTPS");
        URL url = new URL(endpoint);
        if (!"https".equalsIgnoreCase(url.getProtocol()) || url.getUserInfo() != null
            || url.getRef() != null || url.getHost().isEmpty()) throw new SecurityException("Endpoint OTA inválido");
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setConnectTimeout(10000);
        connection.setReadTimeout(10000);
        connection.setInstanceFollowRedirects(false);
        connection.setRequestProperty("Accept", "application/json");
        try {
            if (connection.getResponseCode() != 200)
                throw new java.io.IOException("Servidor OTA respondeu: " + connection.getResponseCode());
            byte[] buffer = new byte[4096];
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            try (InputStream input = connection.getInputStream()) {
                int n;
                while ((n = input.read(buffer)) != -1) {
                    if (output.size() + n > 65536)
                        throw new java.io.IOException("Manifesto OTA excede 64 KB");
                    output.write(buffer, 0, n);
                }
            }
            java.nio.charset.CharsetDecoder decoder = java.nio.charset.StandardCharsets.UTF_8
                .newDecoder()
                .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
                .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT);
            String envelope = decoder.decode(java.nio.ByteBuffer.wrap(output.toByteArray())).toString();
            OtaRelease release = OtaManifestVerifier.verify(envelope, trustedKey);
            return release.isUpgrade(installedCode, channel) ? release : null;
        } finally {
            connection.disconnect();
        }
    }
}
