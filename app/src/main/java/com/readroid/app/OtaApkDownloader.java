package com.readroid.app;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Locale;

/**
 * Downloads to private cache, checks exact size and SHA-256, and never installs.
 * Redirects are bounded and may only remain on the original host or move from
 * github.com to the official GitHub release-assets CDN.
 */
public final class OtaApkDownloader {
    private static final int MAX_REDIRECTS = 3;
    private OtaApkDownloader() {}

    private static void validateHttps(URL url) {
        if (!"https".equalsIgnoreCase(url.getProtocol())
            || url.getHost() == null || url.getHost().isEmpty()
            || url.getUserInfo() != null || url.getRef() != null
            || (url.getPort() != -1 && url.getPort() != 443))
            throw new SecurityException("URL OTA deve usar HTTPS válido");
    }

    private static boolean allowedRedirect(URL from, URL to) {
        String source = from.getHost().toLowerCase(Locale.ROOT);
        String target = to.getHost().toLowerCase(Locale.ROOT);
        if (source.equals(target)) return true;
        return "github.com".equals(source)
            && ("release-assets.githubusercontent.com".equals(target)
                || "objects.githubusercontent.com".equals(target));
    }

    private static HttpURLConnection connect(URL initial) throws Exception {
        URL current = initial;
        for (int redirects = 0; redirects <= MAX_REDIRECTS; redirects++) {
            validateHttps(current);
            HttpURLConnection connection = (HttpURLConnection) current.openConnection();
            connection.setConnectTimeout(15000);
            connection.setReadTimeout(30000);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("Accept", "application/vnd.android.package-archive");
            int code;
            try {
                code = connection.getResponseCode();
                if (code == HttpURLConnection.HTTP_OK) return connection;
                if (code != HttpURLConnection.HTTP_MOVED_PERM
                    && code != HttpURLConnection.HTTP_MOVED_TEMP
                    && code != HttpURLConnection.HTTP_SEE_OTHER
                    && code != 307 && code != 308)
                    throw new java.io.IOException("Download OTA HTTP " + code);
                if (redirects == MAX_REDIRECTS)
                    throw new SecurityException("Excesso de redirecionamentos OTA");
                String location = connection.getHeaderField("Location");
                if (location == null || location.isEmpty() || location.length() > 4096)
                    throw new SecurityException("Redirecionamento OTA sem destino válido");
                URL next = new URL(current, location);
                validateHttps(next);
                if (!allowedRedirect(current, next))
                    throw new SecurityException("Redirecionamento OTA para domínio não autorizado");
                current = next;
            } finally {
                connection.disconnect();
            }
        }
        throw new SecurityException("Redirecionamentos OTA excedidos");
    }

    public static File download(OtaRelease release, File cacheDir) throws Exception {
        if (release == null || cacheDir == null || !cacheDir.isDirectory())
            throw new IllegalArgumentException("Atualização ou cache inválido");
        URL url = new URL(release.downloadUrl);
        validateHttps(url);
        File temporary = File.createTempFile("negresco_ota_", ".part", cacheDir);
        boolean verified = false;
        HttpURLConnection connection = null;
        try {
            connection = connect(url);
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
            if (!MessageDigest.isEqual(hash.toString().getBytes(java.nio.charset.StandardCharsets.US_ASCII),
                release.sha256.getBytes(java.nio.charset.StandardCharsets.US_ASCII)))
                throw new SecurityException("SHA-256 do APK não corresponde ao manifesto");
            verified = true;
            return temporary;
        } finally {
            if (connection != null) connection.disconnect();
            if (!verified) temporary.delete();
        }
    }
}
