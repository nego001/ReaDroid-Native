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
        int flags = PackageManager.GET_SIGNING_CERTIFICATES;
        PackageInfo installed = manager.getPackageInfo(context.getPackageName(), flags);
        PackageInfo incoming = manager.getPackageArchiveInfo(candidate.getAbsolutePath(), flags);
        if (incoming == null || incoming.packageName == null
            || !context.getPackageName().equals(incoming.packageName))
            throw new SecurityException("Pacote OTA pertence a outro aplicativo");
        long installedCode = Build.VERSION.SDK_INT >= 28 ? installed.getLongVersionCode() : installed.versionCode;
        long incomingCode = Build.VERSION.SDK_INT >= 28 ? incoming.getLongVersionCode() : incoming.versionCode;
        if (incomingCode != release.versionCode || incomingCode <= installedCode)
            throw new SecurityException("Versão OTA incompatível");
        if (installed.signingInfo == null || incoming.signingInfo == null)
            throw new SecurityException("Informações de assinatura indisponíveis");
        Signature[] installedSigners = installed.signingInfo.getApkContentsSigners();
        Signature[] incomingSigners = incoming.signingInfo.getApkContentsSigners();
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
