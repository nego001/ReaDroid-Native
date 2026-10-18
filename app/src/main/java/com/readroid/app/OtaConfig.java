package com.readroid.app;

/** Distribution owner must configure both values before network OTA is enabled. */
public final class OtaConfig {
    private OtaConfig() {}

    // HTTPS endpoint serving the signed JSON envelope, not an APK URL.
    public static final String RELEASE_ENDPOINT = "";
    // Base64 X.509/SPKI encoded RSA public key, paired with the offline release signing key.
    public static final String TRUSTED_RELEASE_PUBLIC_KEY = "";

    public static boolean isConfigured() {
        return RELEASE_ENDPOINT.startsWith("https://")
            && !TRUSTED_RELEASE_PUBLIC_KEY.isEmpty();
    }
}
