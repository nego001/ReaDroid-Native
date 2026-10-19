package com.readroid.app;

import android.util.Base64;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;

/** OTA metadata must be signed before any release fields are trusted. */
public final class OtaManifestVerifier {
    private OtaManifestVerifier() {}

    public static OtaRelease verify(String envelope, String trustedKeyBase64) throws Exception {
        if (envelope == null || envelope.length() > 65536)
            throw new SecurityException("Envelope OTA inválido");
        if (trustedKeyBase64 == null || trustedKeyBase64.isEmpty())
            throw new SecurityException("Chave pública OTA ainda não configurada");
        JSONObject wrapper = new JSONObject(envelope);
        String payload = wrapper.getString("payload");
        String signatureText = wrapper.getString("signature");
        if (payload.length() > 32768 || signatureText.length() > 2048)
            throw new SecurityException("Envelope OTA excede os limites");
        byte[] keyBytes = Base64.decode(trustedKeyBase64, Base64.NO_WRAP);
        PublicKey key = KeyFactory.getInstance("RSA")
            .generatePublic(new X509EncodedKeySpec(keyBytes));
        Signature verifier = Signature.getInstance("SHA256withRSA");
        verifier.initVerify(key);
        verifier.update(payload.getBytes(StandardCharsets.UTF_8));
        if (!verifier.verify(Base64.decode(signatureText, Base64.NO_WRAP)))
            throw new SecurityException("Assinatura do manifesto OTA inválida");
        OtaRelease trusted = OtaRelease.parse(payload);
        trusted.markSignatureVerified();
        return trusted;
    }
}
