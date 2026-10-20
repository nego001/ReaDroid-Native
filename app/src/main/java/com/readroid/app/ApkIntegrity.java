package com.readroid.app;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;

/** Independent, bounded-memory SHA-256 verification for source and rebuilt APKs. */
public final class ApkIntegrity {
    private ApkIntegrity() {}

    public static String sha256(File file) throws IOException {
        if (file == null || !file.isFile()) throw new IOException("Arquivo indisponível para SHA-256");
        final MessageDigest hash;
        try {
            hash = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException unavailable) {
            throw new IOException("SHA-256 indisponível", unavailable);
        }
        byte[] buffer = new byte[65536];
        try (InputStream input = new FileInputStream(file)) {
            int n;
            while ((n = input.read(buffer)) != -1) {
                if (Thread.currentThread().isInterrupted())
                    throw new java.io.InterruptedIOException("Hash interrompido");
                hash.update(buffer, 0, n);
            }
        }
        StringBuilder hex = new StringBuilder(64);
        for (byte value : hash.digest())
            hex.append(String.format(Locale.ROOT, "%02x", value & 255));
        return hex.toString();
    }

    public static void confirmExpected(File file, String expected) throws IOException {
        if (expected == null || !expected.matches("[0-9a-f]{64}"))
            throw new IOException("Hash do APK original indisponível ou inválido.");
        if (!expected.equals(sha256(file)))
            throw new IOException("Integridade do APK original não confere com a importação.");
    }
}
