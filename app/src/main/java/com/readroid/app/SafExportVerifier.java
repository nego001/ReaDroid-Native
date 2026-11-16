package com.readroid.app;

import android.content.ContentResolver;
import android.net.Uri;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;

/**
 * Confirm that the exported file really contains the complete rebuilt ZIP.
 * SAF providers are allowed to acknowledge a write without necessarily
 * preserving every byte; only a full readback can confirm success.
 */
public final class SafExportVerifier {
    // A provider can legally produce short reads, including transient zero
    // reads. Persistent zero reads must never spin the export worker forever.
    private static final int MAX_ZERO_READS = 16;

    private SafExportVerifier() {}

    // Internal seam for exercising untrusted provider behavior without
    // granting storage access or installing a mock DocumentsProvider.
    interface ExportTarget {
        OutputStream openWrite() throws IOException;
        InputStream openRead() throws IOException;
    }

    public static long copyAndVerify(ContentResolver resolver, File source, Uri destination)
            throws IOException {
        if (resolver == null || source == null || !source.isFile() || destination == null)
            throw new IOException("Arquivo ou destino inválido");
        // Do not let a direct file:// caller truncate its own source while
        // "exporting". Normal SAF documents use content://; this checks the
        // local-file route used in tests and in any future trusted caller.
        if ("file".equals(destination.getScheme())) {
            String path = destination.getPath();
            if (path == null || path.isEmpty())
                throw new IOException("Destino de arquivo inválido");
            if (source.getCanonicalFile().equals(new File(path).getCanonicalFile()))
                throw new IOException("Destino não pode ser o APK de origem");
        }
        return copyAndVerify(source, new ExportTarget() {
            @Override public OutputStream openWrite() throws IOException {
                return resolver.openOutputStream(destination, "w");
            }
            @Override public InputStream openRead() throws IOException {
                return resolver.openInputStream(destination);
            }
        });
    }

    static long copyAndVerify(File source, ExportTarget target) throws IOException {
        if (source == null || !source.isFile() || target == null)
            throw new IOException("Arquivo ou destino inválido");
        // The initial digest pins the bytes expected from the local staging
        // file; the second digest catches changes between hashing and writing.
        MessageDigest expectedDigest = sha256();
        byte[] buffer = new byte[65536];
        long sourceLength = 0;
        try (InputStream in = new FileInputStream(source)) {
            int[] zeros = {0};
            int n;
            while ((n = readWithProgress(in, buffer, zeros, "Origem")) != -1) {
                if (n == 0) continue;
                sourceLength += n;
                expectedDigest.update(buffer, 0, n);
            }
        }
        final byte[] expected = expectedDigest.digest();
        long copiedLength = 0;
        MessageDigest copiedDigest = sha256();
        try (InputStream input = new FileInputStream(source);
             OutputStream output = target.openWrite()) {
            if (output == null)
                throw new IOException("O Android não abriu o destino para gravação");
            int[] zeros = {0};
            int n;
            while ((n = readWithProgress(input, buffer, zeros, "Origem")) != -1) {
                if (n == 0) continue;
                if (n > sourceLength - copiedLength)
                    throw new IOException("O APK temporário mudou durante a exportação");
                output.write(buffer, 0, n);
                copiedDigest.update(buffer, 0, n);
                copiedLength += n;
            }
            output.flush();
        }
        ensureActive("Exportação");
        if (copiedLength != sourceLength
                || !Arrays.equals(expected, copiedDigest.digest()))
            throw new IOException("O APK temporário mudou durante a exportação");

        // Never mark the SAF result successful from write/close alone.
        // Content providers can silently truncate, append, or corrupt bytes.
        long exportedLength = 0;
        MessageDigest actualDigest = sha256();
        try (InputStream verify = target.openRead()) {
            if (verify == null)
                throw new IOException("Não foi possível reler o arquivo exportado");
            int[] zeros = {0};
            int n;
            while ((n = readWithProgress(verify, buffer, zeros, "Releitura SAF")) != -1) {
                if (n == 0) continue;
                if (n > sourceLength - exportedLength)
                    throw new IOException("O destino contém bytes extras");
                actualDigest.update(buffer, 0, n);
                exportedLength += n;
            }
        }
        ensureActive("Verificação");
        if (sourceLength != exportedLength
                || !Arrays.equals(expected, actualDigest.digest()))
            throw new IOException("O arquivo exportado não confere com o APK verificado (SHA-256)");
        return exportedLength;
    }

    /** Zero-byte provider reads are bounded, not interpreted as EOF. */
    private static int readWithProgress(InputStream stream, byte[] buffer,
            int[] consecutiveZeros, String stage) throws IOException {
        ensureActive(stage);
        int n = stream.read(buffer);
        if (n == 0) {
            if (++consecutiveZeros[0] > MAX_ZERO_READS)
                throw new IOException(stage + " sem progresso: provedor não retornou dados");
        } else if (n > 0) {
            consecutiveZeros[0] = 0;
        }
        return n;
    }

    private static void ensureActive(String stage) throws java.io.InterruptedIOException {
        if (Thread.currentThread().isInterrupted())
            throw new java.io.InterruptedIOException(stage + " interrompida");
    }

    private static MessageDigest sha256() throws IOException {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException unavailable) {
            throw new IOException("SHA-256 indisponível", unavailable);
        }
    }
}
