package com.readroid.app;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Locale;

/** Downloads a verified OTA APK to app-private cache. Never installs it. */
public final class OtaApkDownloader {
    private OtaApkDownloader() {}

    public static File download(OtaRelease release, File cacheDir) throws Exception {
        if (release == null || cacheDir == null || !cacheDir.isDirectory())
            throw new IllegalArgumentException("Atualização ou cache inválido");
        URL url = new URL(release.downloadUrl);
        if (!"https".equalsIgnoreCase(url.getProtocol()) || url.getUserInfo() != null
            || url.getRef() != null) throw new SecurityException("URL OTA inválida");
        File temporary = File.createTempFile("negresco_ota_", ".part", cacheDir);
        boolean verified = false;
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(30000);
        connection.setInstanceFollowRedirects(false);
        try {
            if (connection.getResponseCode() != 200)
                throw new java.io.IOException("Download OTA HTTP " + connection.getResponseCode());
            long declared = connection.getContentLengthLong();
            if (declared >= 0 && declared != release.sizeBytes)
                throw new SecurityException("Tamanho HTTP difere do manifesto assinado");
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            long total = 0;
            byte[] buffer = new byte[65536];
            try (InputStream input = connection.getInputStream();
                 FileOutputStream output = new FileOutputStream(temporary)) {
                int n;
                while ((n = input.read(buffer)) != -1) {
                    total += n;
                    if (total > release.sizeBytes)
                        throw new SecurityException("Download excedeu o tamanho esperado");
                    digest.update(buffer, 0, n);
                    output.write(buffer, 0, n);
                }
                output.getFD().sync();
            }
            if (total != release.sizeBytes)
                throw new SecurityException("Download incompleto");
            StringBuilder hash = new StringBuilder();
            for (byte b : digest.digest())
                hash.append(String.format(Locale.ROOT, "%02x", b & 255));
            if (!hash.toString().equals(release.sha256))
                throw new SecurityException("SHA-256 do APK não corresponde ao manifesto");
            verified = true;
            return temporary;
        } finally {
            connection.disconnect();
            if (!verified) temporary.delete();
        }
    }
}
