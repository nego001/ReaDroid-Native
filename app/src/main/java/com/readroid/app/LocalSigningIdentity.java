package com.readroid.app;

import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import java.security.*;
import java.security.cert.Certificate;
import java.util.Locale;

/** Local non-exportable signing identity. Not yet an APK signer. */
public final class LocalSigningIdentity {
    private static final String STORE = "AndroidKeyStore";
    private static final String ALIAS = "readroid_local_apk_signing_v1";
    private LocalSigningIdentity() {}

    public static String describe() throws Exception {
        KeyStore store = KeyStore.getInstance(STORE);
        store.load(null);
        if (!store.containsAlias(ALIAS)) return "Nenhuma identidade local criada.";
        Certificate cert = store.getCertificate(ALIAS);
        if (cert == null) throw new GeneralSecurityException("Certificado local indisponível");
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(cert.getEncoded());
        StringBuilder hex = new StringBuilder();
        for (byte b : digest) hex.append(String.format(Locale.ROOT, "%02X", b & 255));
        return "Identidade local disponível.\nCertificado SHA-256: " + hex
            + "\nChave privada não exportável.\nAinda não assina APKs.";
    }

    public static String create() throws Exception {
        KeyStore store = KeyStore.getInstance(STORE);
        store.load(null);
        if (store.containsAlias(ALIAS)) return describe();
        KeyPairGenerator generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_RSA, STORE);
        KeyGenParameterSpec spec = new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_SIGN | KeyProperties.PURPOSE_VERIFY)
            .setKeySize(3072)
            .setDigests(KeyProperties.DIGEST_SHA256)
            .setSignaturePaddings(KeyProperties.SIGNATURE_PADDING_RSA_PKCS1)
            .setCertificateSubject(new javax.security.auth.x500.X500Principal("CN=ReaDroid Local Signing"))
            .setCertificateSerialNumber(java.math.BigInteger.ONE)
            .setCertificateNotBefore(new java.util.Date(System.currentTimeMillis() - 60000L))
            .setCertificateNotAfter(new java.util.Date(System.currentTimeMillis() + 315360000000L))
            .build();
        generator.initialize(spec);
        generator.generateKeyPair();
        return describe();
    }
}
