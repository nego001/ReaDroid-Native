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
        return sha256(file, null);
    }

    static String sha256(File file, ExportSessionGuard.Token token) throws IOException {
        ExportSessionGuard.check(token);
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
            while (true) {
                ExportSessionGuard.check(token);
                n = input.read(buffer);
                ExportSessionGuard.check(token);
                if (n == -1) break;
                hash.update(buffer, 0, n);
            }
        }
        StringBuilder hex = new StringBuilder(64);
        for (byte value : hash.digest())
            hex.append(String.format(Locale.ROOT, "%02x", value & 255));
        ExportSessionGuard.check(token);
        return hex.toString();
    }

    public static void confirmExpected(File file, String expected) throws IOException {
        confirmExpected(file, expected, null);
    }

    static void confirmExpected(File file, String expected, ExportSessionGuard.Token token)
            throws IOException {
        ExportSessionGuard.check(token);
        if (expected == null || !expected.matches("[0-9a-f]{64}"))
            throw new IOException("Hash do APK original indisponível ou inválido.");
        if (!expected.equals(sha256(file, token)))
            throw new IOException("Integridade do APK original não confere com a importação.");
    }
}
