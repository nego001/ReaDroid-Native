package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.zip.CRC32;
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
            if (entry.getSize() < 0 || entry.getCompressedSize() < 0
                    || entry.getCrc() < 0)
                throw new IOException("Metadados ZIP incompletos: " + path);
            if (entry.getSize() > 1073741824L)
                throw new IOException("Limite de inspeção: 1 GiB");
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            CRC32 crc = new CRC32();
            long total = 0;
            byte[] buffer = new byte[65536];
            try (InputStream in = zip.getInputStream(entry)) {
                int n;
                while ((n = in.read(buffer)) != -1) {
                    if (Thread.currentThread().isInterrupted())
                        throw new java.io.InterruptedIOException("Inspeção interrompida");
                    total += n;
                    if (total > 1073741824L)
                        throw new IOException("Limite de inspeção: 1 GiB");
                    digest.update(buffer, 0, n);
                    crc.update(buffer, 0, n);
                }
            }
            if (total != entry.getSize())
                throw new IOException("Tamanho descomprimido divergente: " + path);
            if (crc.getValue() != entry.getCrc())
                throw new IOException("CRC-32 divergente: " + path);
            byte[] hash = digest.digest();
            StringBuilder hex = new StringBuilder(hash.length * 2);
            for (byte b : hash) hex.append(String.format(Locale.ROOT, "%02x", b & 255));
            String method = entry.getMethod() == ZipEntry.STORED ? "Armazenado" :
                entry.getMethod() == ZipEntry.DEFLATED ? "Deflate" : "Outro";
            return "CAMINHO\n" + path + "\n\nTAMANHO REAL\n" + total
                + " bytes\n\nTAMANHO COMPRIMIDO\n" + entry.getCompressedSize()
                + " bytes\n\nCOMPRESSÃO\n" + method
                + "\n\nCRC-32\n" + Long.toHexString(crc.getValue())
                + "\n\nSHA-256\n" + hex;
        }
    }
}
