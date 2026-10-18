package com.readroid.app;

/**
 * Trust roots are pinned at build time and are NEVER learned from an OTA response.
 * Owner must publish per-channel signed envelopes and provision the RSA public key.
 * Private signing keys must never be included in this repository or in the APK.
 */
public final class OtaConfig {
    private OtaConfig() {}

    // Endpoints return signed JSON envelopes (payload + signature), not APKs.
    public static final String STABLE_RELEASE_ENDPOINT = "";
    public static final String BETA_RELEASE_ENDPOINT = "";

    // Base64 of the X.509/SPKI DER RSA public key, generated from offline PEM key.
    public static final String TRUSTED_RELEASE_PUBLIC_KEY = "";

    public static String endpointFor(String channel) {
        if ("stable".equals(channel)) return STABLE_RELEASE_ENDPOINT;
        if ("beta".equals(channel)) return BETA_RELEASE_ENDPOINT;
        throw new IllegalArgumentException("Canal OTA inválido");
    }

    public static boolean isConfigured(String channel) {
        String endpoint = endpointFor(channel);
        return endpoint.startsWith("https://") && endpoint.length() <= 2048
            && !TRUSTED_RELEASE_PUBLIC_KEY.isEmpty();
    }
}
