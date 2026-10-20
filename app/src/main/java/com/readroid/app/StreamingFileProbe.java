package com.readroid.app;

import android.content.ContentResolver;
import android.net.Uri;

import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;

/**
 * Read-only byte-stream inspection for user-authorized Android SAF files.
 *
 * No full-file copy, ZIP extraction or unbounded in-memory buffering.
 * This primitive is not a complete ZIP64/APK explorer or 500 GB guarantee.
 * Callers must run it off the UI thread, supply an approved byte budget and
 * apply cancellation/thermal/battery policies before expensive analysis.
 */
public final class StreamingFileProbe {
    private static final int BUFFER_BYTES = 65536;
    private static final long PROGRESS_INTERVAL = 4L * 1024 * 1024;

    private StreamingFileProbe() {}

    public interface Progress {
        void onBytesRead(long bytes);
    }

    public static final class Result {
        public final long bytesRead;
        public final String sha256;

        Result(long bytesRead, String sha256) {
            this.bytesRead = bytesRead;
            this.sha256 = sha256;
        }
    }

    /** Reads an explicitly selected content URI. Ownership of input is local. */
    public static Result inspect(ContentResolver resolver, Uri uri, long maxBytes,
            Progress progress) throws IOException {
        if (resolver == null || uri == null)
            throw new IOException("Origem SAF não especificada");
        try (InputStream in = resolver.openInputStream(uri)) {
            if (in == null) throw new IOException("Não foi possível ler o arquivo selecionado");
            return inspect(in, maxBytes, progress);
        } catch (SecurityException denied) {
            throw new IOException("Sem autorização para ler o arquivo selecionado", denied);
        }
    }

    /** Streaming overload used by deterministic tests and future adapters. */
    public static Result inspect(InputStream in, long maxBytes, Progress progress)
            throws IOException {
        if (in == null) throw new IOException("Fluxo de arquivo indisponível");
        if (maxBytes <= 0)
            throw new IOException("O limite de leitura deve ser positivo e autorizado");

        final MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException unavailable) {
            throw new IOException("SHA-256 indisponível", unavailable);
        }

        byte[] buffer = new byte[BUFFER_BYTES];
        long total = 0;
        long lastProgress = 0;
        int zeroReads = 0;
        while (true) {
            if (Thread.currentThread().isInterrupted())
                throw new java.io.InterruptedIOException("Leitura de arquivo cancelada");
            // Read only the remaining allowance plus a single sentinel byte
            // to distinguish an exact-sized file from one exceeding the limit.
            // This never requests an unchecked extra 64 KiB past the budget.
            long remaining = maxBytes - total;
            int request = remaining >= buffer.length
                ? buffer.length : (int) (remaining + 1L);
            int read = in.read(buffer, 0, request);
            if (read < 0) break;
            if (read == 0) {
                if (++zeroReads > 16)
                    throw new IOException("A origem parou de fornecer dados");
                continue;
            }
            zeroReads = 0;
            if (read > maxBytes - total)
                throw new IOException("Limite autorizado para leitura excedido");
            digest.update(buffer, 0, read);
            total += read;
            if (progress != null && total - lastProgress >= PROGRESS_INTERVAL) {
                progress.onBytesRead(total);
                lastProgress = total;
            }
        }
        if (progress != null && lastProgress != total) progress.onBytesRead(total);
        StringBuilder hex = new StringBuilder(64);
        for (byte value : digest.digest())
            hex.append(String.format(Locale.ROOT, "%02x", value & 255));
        return new Result(total, hex.toString());
    }
}
