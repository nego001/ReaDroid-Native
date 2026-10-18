package com.readroid.app;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.os.Build;
import java.io.File;
import java.security.MessageDigest;

/** Confirms downloaded APK package and signer against the installed app. */
public final class OtaPackageVerifier {
    private OtaPackageVerifier() {}

    @SuppressWarnings("deprecation")
    public static void verify(Context context, File candidate, OtaRelease release) throws Exception {
        if (context == null || candidate == null || !candidate.isFile() || release == null)
            throw new SecurityException("Pacote OTA indisponível");
        PackageManager manager = context.getPackageManager();
        // Android 8.0/8.1 lacks SigningInfo; the legacy signatures field is required there.
        int flags = Build.VERSION.SDK_INT >= 28
            ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES;
        PackageInfo installed = manager.getPackageInfo(context.getPackageName(), flags);
        PackageInfo incoming = manager.getPackageArchiveInfo(candidate.getAbsolutePath(), flags);
        if (incoming == null || incoming.packageName == null
            || !context.getPackageName().equals(incoming.packageName))
            throw new SecurityException("Pacote OTA pertence a outro aplicativo");
        long installedCode = Build.VERSION.SDK_INT >= 28 ? installed.getLongVersionCode() : installed.versionCode;
        long incomingCode = Build.VERSION.SDK_INT >= 28 ? incoming.getLongVersionCode() : incoming.versionCode;
        if (incomingCode != release.versionCode || incomingCode <= installedCode)
            throw new SecurityException("Versão OTA incompatível");
        Signature[] installedSigners;
        Signature[] incomingSigners;
        if (Build.VERSION.SDK_INT >= 28) {
            if (installed.signingInfo == null || incoming.signingInfo == null)
                throw new SecurityException("Informações de assinatura indisponíveis");
            if (installed.signingInfo.hasMultipleSigners() != incoming.signingInfo.hasMultipleSigners())
                throw new SecurityException("Modelo de assinatura incompatível");
            installedSigners = installed.signingInfo.getApkContentsSigners();
            incomingSigners = incoming.signingInfo.getApkContentsSigners();
        } else {
            // Legacy fallback is used ONLY on API 26–27. Never trust a missing signer.
            installedSigners = installed.signatures;
            incomingSigners = incoming.signatures;
        }
        if (installedSigners == null || incomingSigners == null
            || installedSigners.length == 0 || incomingSigners.length == 0
            || installedSigners.length != incomingSigners.length)
            throw new SecurityException("Assinantes do APK incompatíveis");
        for (Signature signer : installedSigners) {
            boolean found = false;
            for (Signature candidateSigner : incomingSigners) {
                if (MessageDigest.isEqual(signer.toByteArray(), candidateSigner.toByteArray())) {
                    found = true;
                    break;
                }
            }
            if (!found) throw new SecurityException("Certificado OTA diferente do instalado");
        }
    }
}
