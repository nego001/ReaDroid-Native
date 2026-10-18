package com.readroid.app;

import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.cert.Certificate;
import java.util.Arrays;

/** Local Keystore sign/verify self-test. Does not sign APK archives. */
public final class SigningSelfTest {
    private SigningSelfTest() {}

    public static String run() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        String alias = "readroid_local_apk_signing_v1";
        if (!store.containsAlias(alias)) return "Crie a identidade local antes do teste.";
        Key key = store.getKey(alias, null);
        Certificate cert = store.getCertificate(alias);
        if (!(key instanceof PrivateKey) || cert == null)
            throw new GeneralSecurityException("Chave ou certificado ausente");
        byte[] challenge = new byte[32];
        new SecureRandom().nextBytes(challenge);
        Signature signer = Signature.getInstance("SHA256withRSA");
        signer.initSign((PrivateKey) key);
        signer.update(challenge);
        byte[] signature = signer.sign();
        Signature verifier = Signature.getInstance("SHA256withRSA");
        verifier.initVerify(cert.getPublicKey());
        verifier.update(challenge);
        boolean valid = verifier.verify(signature);
        Arrays.fill(challenge, (byte) 0);
        Arrays.fill(signature, (byte) 0);
        if (!valid) throw new GeneralSecurityException("Assinatura não validou");
        return "Teste criptográfico aprovado: RSA SHA-256 assinado e verificado localmente. Nenhuma chave privada exportada. Isto NÃO significa que o assinador APK esteja pronto.";
    }
}
