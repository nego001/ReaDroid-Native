package com.readroid.app;

import android.content.ContentResolver;
import android.net.Uri;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;

/**
 * Small read-only magic-byte preflight. Format is a hint, NOT a trusted parser,
 * malware verdict, APK validity check or proof of a Windows PE signature.
 * Opens the SAF stream once and never copies the original to private cache.
 */
public final class FileHeaderProbe {
    private static final int SAMPLE_BYTES = 64;

    private FileHeaderProbe() {}

    public static final class Result {
        public final String format;
        public final String description;
        public final int sampleBytes;
        public final boolean recognized;

        Result(String format, String description, int sampleBytes, boolean recognized) {
            this.format = format;
            this.description = description;
            this.sampleBytes = sampleBytes;
            this.recognized = recognized;
        }
    }

    public static Result inspect(ContentResolver resolver, Uri uri) throws IOException {
        if (resolver == null || uri == null)
            throw new IOException("Origem SAF não especificada");
        try (InputStream in = resolver.openInputStream(uri)) {
            if (in == null) throw new IOException("Arquivo SAF inacessível");
            return inspect(in);
        } catch (SecurityException denied) {
            throw new IOException("Permissão de leitura negada", denied);
        }
    }

    public static Result inspect(File file) throws IOException {
        if (file == null || !file.isFile())
            throw new IOException("Arquivo de inspeção não encontrado");
        try (InputStream in = new FileInputStream(file)) {
            return inspect(in);
        }
    }

    /** Caller retains ownership of the supplied stream. */
    public static Result inspect(InputStream in) throws IOException {
        if (in == null) throw new IOException("Fluxo de arquivo inválido");
        byte[] header = new byte[SAMPLE_BYTES];
        int total = 0;
        int zeroReads = 0;
        while (total < header.length) {
            if (Thread.currentThread().isInterrupted())
                throw new java.io.InterruptedIOException("Sondagem cancelada");
            int n = in.read(header, total, header.length - total);
            if (n == -1) break;
            if (n == 0) {
                if (++zeroReads > 16)
                    throw new IOException("A origem parou de fornecer dados");
                continue;
            }
            zeroReads = 0;
            total += n;
        }

        if (matches(header, total, 0, 0x50, 0x4b, 0x03, 0x04)
                || matches(header, total, 0, 0x50, 0x4b, 0x05, 0x06))
            return new Result("ZIP", "Contêiner ZIP (APK ainda não confirmado)", total, true);
        if (matches(header, total, 0, 0x7f, 0x45, 0x4c, 0x46))
            return new Result("ELF", "Binário ELF (Linux/Android)", total, true);
        if (matches(header, total, 0, 0x64, 0x65, 0x78, 0x0a))
            return new Result("DEX", "Código DEX (Android)", total, true);
        if (matches(header, total, 0, 0x4d, 0x5a))
            return new Result("MZ_CANDIDATE",
                "Cabeçalho MZ (PE/EXE não confirmado)", total, true);
        if (matches(header, total, 0, 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a))
            return new Result("PNG", "Imagem PNG", total, true);
        if (matches(header, total, 0, 0x25, 0x50, 0x44, 0x46, 0x2d))
            return new Result("PDF", "Documento PDF", total, true);
        if (matches(header, total, 0, 0x53, 0x51, 0x4c, 0x69, 0x74, 0x65, 0x20,
                0x66, 0x6f, 0x72, 0x6d, 0x61, 0x74, 0x20, 0x33, 0x00))
            return new Result("SQLITE", "Banco SQLite", total, true);
        if (matches(header, total, 0, 0x37, 0x7a, 0xbc, 0xaf, 0x27, 0x1c))
            return new Result("7Z", "Arquivo compactado 7z", total, true);
        if (matches(header, total, 0, 0x52, 0x61, 0x72, 0x21, 0x1a, 0x07))
            return new Result("RAR", "Arquivo compactado RAR", total, true);
        if (matches(header, total, 0, 0x1f, 0x8b))
            return new Result("GZIP", "Fluxo comprimido GZIP", total, true);
        return new Result("UNKNOWN", "Formato não identificado pelos bytes iniciais",
            total, false);
    }

    private static boolean matches(byte[] actual, int read, int offset, int... signature) {
        if (read < offset + signature.length) return false;
        for (int i = 0; i < signature.length; i++)
            if ((actual[offset + i] & 255) != signature[i]) return false;
        return true;
    }
}
