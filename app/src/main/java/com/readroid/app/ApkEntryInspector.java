package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Read-only, bounded inspection of one APK ZIP entry. */
public final class ApkEntryInspector {
    private ApkEntryInspector() {}

    public static String inspect(File apk, String path) throws Exception {
        if (apk == null || !apk.isFile()) throw new IOException("APK indisponível");
        if (path == null || path.isEmpty() || path.startsWith("/") || path.contains("\\")
            || path.contains("../") || path.equals("..")) throw new IOException("Caminho inválido");
        try (ZipFile zip = new ZipFile(apk)) {
            ZipEntry entry = zip.getEntry(path);
            if (entry == null || entry.isDirectory()) throw new IOException("Arquivo não encontrado");
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            long total = 0;
            byte[] buffer = new byte[65536];
            try (InputStream in = zip.getInputStream(entry)) {
                int n;
                while ((n = in.read(buffer)) != -1) {
                    total += n;
                    if (total > 1073741824L) throw new IOException("Limite de inspeção: 1 GB");
                    digest.update(buffer, 0, n);
                }
            }
            byte[] hash = digest.digest();
            StringBuilder hex = new StringBuilder(hash.length * 2);
            for (byte b : hash) hex.append(String.format(Locale.ROOT, "%02x", b & 255));
            String method = entry.getMethod() == ZipEntry.STORED ? "Armazenado" :
                entry.getMethod() == ZipEntry.DEFLATED ? "Deflate" : "Outro";
            return "CAMINHO\n" + path + "\n\nTAMANHO REAL\n" + total
                + " bytes\n\nTAMANHO COMPRIMIDO\n" + entry.getCompressedSize()
                + " bytes\n\nCOMPRESSÃO\n" + method
                + "\n\nCRC-32\n" + Long.toHexString(entry.getCrc())
                + "\n\nSHA-256\n" + hex;
        }
    }
}
