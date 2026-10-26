package com.readroid.app;

import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.io.OutputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.function.LongSupplier;

/**
 * Bounded, zero-copy-buffer SAF stream copier. Caller owns and closes its
 * streams and deletes the temporary cache file whenever this method fails.
 * Provider size metadata never authorizes extra bytes.
 */
public final class SafImportStream {
    private static final int BUFFER_BYTES = 64 * 1024;
    private static final int MAX_ZERO_READS = 16;
    private static final char[] HEX = "0123456789abcdef".toCharArray();

    private SafImportStream() {}

    public static final class Result {
        public final long bytesCopied;
        public final String sha256;

        Result(long bytesCopied, String sha256) {
            this.bytesCopied = bytesCopied;
            this.sha256 = sha256;
        }
    }

    /** Production path always uses the same 1 GiB allowance as preflight. */
    public static Result copyAndHash(InputStream source, OutputStream destination,
            LongSupplier availableCacheBytes) throws IOException {
        return copyAndHash(source, destination, availableCacheBytes,
            ApkImportPreflight.MAX_APK_BYTES);
    }

    /** Small test allowances exercise boundary and sentinel logic without giant fixtures. */
    static Result copyAndHash(InputStream source, OutputStream destination,
            LongSupplier availableCacheBytes, long maxBytes) throws IOException {
        if (source == null || destination == null || availableCacheBytes == null)
            throw new IOException("Origem, destino ou verificação de espaço indisponível");
        if (maxBytes <= 0 || maxBytes > ApkImportPreflight.MAX_APK_BYTES)
            throw new IOException("Limite de cópia fora da política de importação");

        final MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException error) {
            throw new IOException("SHA-256 indisponível", error);
        }
        byte[] buffer = new byte[BUFFER_BYTES];
        long copied = 0;
        long lastDiskCheck = 0;
        int zeroReads = 0;
        checkInterrupted();
        ApkImportPreflight.checkProgress(0, availableCacheBytes.getAsLong());

        while (true) {
            checkInterrupted();
            // Request at most one sentinel byte past the remaining budget.
            // An untrusted provider may report a smaller document size.
            long remaining = maxBytes - copied;
            int request = (int) Math.min((long) buffer.length, remaining + 1);
            int read = source.read(buffer, 0, request);
            checkInterrupted();
            if (read == -1) break;
            if (read == 0) {
                if (++zeroReads > MAX_ZERO_READS)
                    throw new IOException("Provedor de arquivos parou de fornecer dados");
                continue;
            }
            zeroReads = 0;
            if (read > remaining)
                throw new IOException("Importação cancelada: tamanho real ultrapassou o limite seguro");
            destination.write(buffer, 0, read);
            digest.update(buffer, 0, read);
            copied += read;
            if (ApkImportPreflight.shouldRecheck(copied, lastDiskCheck)) {
                ApkImportPreflight.checkProgress(copied, availableCacheBytes.getAsLong());
                lastDiskCheck = copied;
            }
        }
        checkInterrupted();
        // Mandatory final disk check, even for very small APKs or if the
        // last 32 MiB interval was not reached after another app used storage.
        ApkImportPreflight.checkProgress(copied, availableCacheBytes.getAsLong());
        StringBuilder hash = new StringBuilder(64);
        for (byte b : digest.digest()) {
            hash.append(HEX[(b >>> 4) & 15]);
            hash.append(HEX[b & 15]);
        }
        return new Result(copied, hash.toString());
    }

    private static void checkInterrupted() throws InterruptedIOException {
        if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Cópia SAF cancelada");
    }
}
