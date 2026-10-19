package com.readroid.app;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.os.Build;
import java.io.File;

/** End-to-end OTA verification. Does not install packages or request permissions. */
public final class OtaUpdatePipeline {
    private OtaUpdatePipeline() {}

    public static final class VerifiedUpdate {
        public final OtaRelease release;
        public final File apk;
        private VerifiedUpdate(OtaRelease release, File apk) {
            this.release = release;
            this.apk = apk;
        }
    }

    public static OtaRelease check(Context context, String endpoint, String trustedPublicKey,
                                   String channel) throws Exception {
        // Never trust arbitrary endpoints or keys passed by a caller. Pin the
        // release trust root at build time, and fail before any network request.
        if (context == null || !OtaConfig.isConfigured(channel)
            || !OtaConfig.endpointFor(channel).equals(endpoint)
            || !OtaConfig.TRUSTED_RELEASE_PUBLIC_KEY.equals(trustedPublicKey))
            throw new SecurityException("OTA não configurada ou origem não confiável");
        PackageInfo info = context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
        long code = Build.VERSION.SDK_INT >= 28 ? info.getLongVersionCode() : info.versionCode;
        if (code > Integer.MAX_VALUE)
            throw new SecurityException("VersionCode instalado fora do intervalo OTA");
        return OtaUpdateChecker.check(endpoint, trustedPublicKey, (int) code, channel);
    }

    public static VerifiedUpdate downloadAndVerify(Context context, OtaRelease release) throws Exception {
        if (context == null || release == null) throw new IllegalArgumentException("Atualização inválida");
        String channel = context.getSharedPreferences("MainActivity", Context.MODE_PRIVATE)
            .getString("ota_channel", "stable");
        // Check again at the download boundary, not only in the UI.
        // A forged/stale OtaRelease must never start a request with absent pins.
        if (!OtaConfig.isConfigured(channel))
            throw new SecurityException("OTA assinada não configurada: download bloqueado");
        // A valid-looking JSON release is NOT evidence of a trusted signature.
        // Only OtaManifestVerifier can mark metadata authenticated.
        if (!release.hasVerifiedSignature())
            throw new SecurityException("Manifesto OTA sem assinatura verificada");
        // The release still requires digest, package and signer verification.
        if (!release.channel.equals(channel))
            throw new SecurityException("Canal OTA diferente da preferência do usuário");
        File downloaded = OtaApkDownloader.download(release, context.getCacheDir());
        boolean valid = false;
        try {
            OtaPackageVerifier.verify(context, downloaded, release);
            valid = true;
            return new VerifiedUpdate(release, downloaded);
        } finally {
            if (!valid) downloaded.delete();
        }
    }
}
