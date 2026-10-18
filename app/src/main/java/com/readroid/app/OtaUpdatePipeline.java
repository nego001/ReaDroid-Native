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
        PackageInfo info = context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
        long code = Build.VERSION.SDK_INT >= 28 ? info.getLongVersionCode() : info.versionCode;
        if (code > Integer.MAX_VALUE)
            throw new SecurityException("VersionCode instalado fora do intervalo OTA");
        return OtaUpdateChecker.check(endpoint, trustedPublicKey, (int) code, channel);
    }

    public static VerifiedUpdate downloadAndVerify(Context context, OtaRelease release) throws Exception {
        if (context == null || release == null) throw new IllegalArgumentException("Atualização inválida");
        String channel = context.getSharedPreferences(context.getClass().getSimpleName(), Context.MODE_PRIVATE)
            .getString("ota_channel", "stable");
        // The caller must provide a release obtained through OtaUpdatePipeline.check.
        // This stage additionally enforces the user-selected channel.
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
