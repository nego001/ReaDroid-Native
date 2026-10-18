package com.readroid.app;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.content.pm.SigningInfo;
import android.os.Build;
import java.io.File;
import java.security.MessageDigest;
import java.util.Locale;

/** Reads Android's package signing metadata. This is not an APK signing implementation. */
public final class ApkSignatureInspector {
    private ApkSignatureInspector() {}

    public static String inspect(Context context, File apk) {
        if (apk == null || !apk.isFile()) return "Arquivo APK não encontrado.";
        try {
            PackageManager pm = context.getPackageManager();
            int flags = Build.VERSION.SDK_INT >= 28
                ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES;
            PackageInfo info = pm.getPackageArchiveInfo(apk.getAbsolutePath(), flags);
            if (info == null) return "Android não reconheceu os metadados deste APK.";
            Signature[] certificates = null;
            if (Build.VERSION.SDK_INT >= 28) {
                SigningInfo signing = info.signingInfo;
                if (signing != null) {
                    certificates = signing.hasMultipleSigners()
                        ? signing.getApkContentsSigners() : signing.getSigningCertificateHistory();
                }
            } else {
                certificates = info.signatures;
            }
            if (certificates == null || certificates.length == 0)
                return "Nenhum certificado retornado pelo Android. Não significa verificação criptográfica concluída.";
            StringBuilder result = new StringBuilder();
            result.append("Pacote: ").append(info.packageName).append("\n");
            result.append("Certificados detectados: ").append(certificates.length).append("\n");
            for (int i = 0; i < certificates.length; i++) {
                byte[] hash = MessageDigest.getInstance("SHA-256").digest(certificates[i].toByteArray());
                result.append("Certificado ").append(i + 1).append(" SHA-256: ");
                for (byte b : hash) result.append(String.format(Locale.ROOT, "%02X", b & 255));
                result.append("\n");
            }
            result.append("Inspeção de metadados apenas; não substitui apksigner verify.");
            return result.toString();
        } catch (Exception error) {
            return "Não foi possível inspecionar assinatura: " + error.getMessage();
        }
    }
}
