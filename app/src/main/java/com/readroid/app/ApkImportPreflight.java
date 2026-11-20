package com.readroid.app;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.StatFs;
import android.provider.OpenableColumns;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.InterruptedIOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;

/**
 * Fast, bounded import preflight. The Android document provider's size is a
 * hint (sometimes absent or incorrect), never a substitute for byte-counting
 * while streaming a potentially hostile APK into private cache.
 */
public final class ApkImportPreflight {
    static final long MAX_APK_BYTES = 1024L * 1024 * 1024;
    private static final long RESERVE_BYTES = 64L * 1024 * 1024;
    private static final long CHECK_EVERY_BYTES = 32L * 1024 * 1024;
    private static final int MAX_CONSECUTIVE_ZERO_READS = 16;

    private ApkImportPreflight() {}

    /** Read-only source + private cache destination; the caller closes both. */
    interface FreeSpace {
        long availableBytes() throws IOException;
    }

    static final class CopyResult {
        final long sizeBytes;
        final String sha256;

        CopyResult(long sizeBytes, String sha256) {
            this.sizeBytes = sizeBytes;
            this.sha256 = sha256;
        }
    }

    /**
     * Never trust SAF size hints or treat EOF, a stalled provider, or a short
     * final chunk as a successful copy without checking space. On IOException
     * the calling import transaction removes the unaccepted cache file.
     *
     * Test seam takes streams and a free-space checker instead of mocking a
     * DocumentsProvider. The real import still opens its SAF stream exactly
     * once and hashes the actual bytes written to its private cache.
     */
    static CopyResult copyAndHash(InputStream in, OutputStream out, FreeSpace space)
            throws IOException {
        return copyAndHash(in, out, space, null);
    }

    static CopyResult copyAndHash(InputStream in, OutputStream out, FreeSpace space,
            ExportSessionGuard.Token token) throws IOException {
        ExportSessionGuard.check(token);
        if (in == null || out == null || space == null)
            throw new IOException("Fluxo de importação indisponível");
        final MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException unavailable) {
            throw new IOException("SHA-256 indisponível", unavailable);
        }
        final byte[] buffer = new byte[65536];
        long copied = 0;
        long lastStorageCheck = 0;
        int zeroReads = 0;
        checkProgress(0, space.availableBytes());
        ExportSessionGuard.check(token);
        while (true) {
            ExportSessionGuard.check(token);
            int count = in.read(buffer);
            // Observe newer imports immediately after a slow provider returns,
            // including EOF. A superseded copy must never be admitted.
            ExportSessionGuard.check(token);
            if (count < 0) break;
            if (count == 0) {
                if (++zeroReads > MAX_CONSECUTIVE_ZERO_READS)
                    throw new IOException("A origem parou de fornecer dados durante a importação");
                continue;
            }
            zeroReads = 0;
            if (copied > MAX_APK_BYTES - count)
                throw new IOException("Limite seguro atual de 1 GiB excedido.");
            copied += count;
            if (shouldRecheck(copied, lastStorageCheck)) {
                checkProgress(copied, space.availableBytes());
                lastStorageCheck = copied;
            }
            ExportSessionGuard.check(token);
            out.write(buffer, 0, count);
            ExportSessionGuard.check(token);
            digest.update(buffer, 0, count);
        }
        if (copied == 0)
            throw new IOException("O arquivo selecionado está vazio");
        ExportSessionGuard.check(token);
        out.flush();
        ExportSessionGuard.check(token);
        // A <32 MiB file, or the last chunk after a periodic check, can
        // exhaust the safety reserve. Check once more on real EOF.
        checkProgress(copied, space.availableBytes());
        ExportSessionGuard.check(token);
        StringBuilder hash = new StringBuilder(64);
        for (byte value : digest.digest())
            hash.append(String.format(Locale.ROOT, "%02x", value & 255));
        ExportSessionGuard.check(token);
        return new CopyResult(copied, hash.toString());
    }

    public static void beforeCopy(Context context, Uri uri) throws IOException {
        long claimed = -1;
        try (Cursor c = context.getContentResolver().query(uri,
                new String[]{OpenableColumns.SIZE}, null, null, null)) {
            if (c != null && c.moveToFirst()) {
                int col = c.getColumnIndex(OpenableColumns.SIZE);
                if (col >= 0 && !c.isNull(col)) claimed = c.getLong(col);
            }
        } catch (SecurityException e) {
            throw new IOException("Acesso ao arquivo não autorizado", e);
        } catch (RuntimeException ignored) {
            // A provider may not implement OpenableColumns. Streaming will
            // enforce the actual byte-counted limits regardless of metadata.
        }
        checkClaimedSize(claimed, availableBytes(context));
    }

    static void checkClaimedSize(long bytes, long available) throws IOException {
        if (bytes > MAX_APK_BYTES)
            throw new IOException("Este APK ultrapassa 1 GiB. O modo multi-GB ainda não "
                + "está disponível; aumentar o limite sem indexação escalável seria inseguro.");
        if (bytes >= 0 && (available < RESERVE_BYTES
                || bytes > available - RESERVE_BYTES))
            throw new IOException("Espaço insuficiente para copiar este APK ao cache "
                + "com uma reserva de segurança de 64 MiB.");
        if (available < RESERVE_BYTES)
            throw new IOException("Espaço privado livre abaixo da reserva mínima de 64 MiB.");
    }

    static void checkProgress(long actualCopied, long available) throws IOException {
        if (actualCopied > MAX_APK_BYTES)
            throw new IOException("Importação cancelada: APK ultrapassou 1 GiB.");
        if (available < RESERVE_BYTES)
            throw new IOException("Importação interrompida: pouco espaço livre no aparelho.");
    }

    public static boolean shouldRecheck(long copied, long lastChecked) {
        return copied - lastChecked >= CHECK_EVERY_BYTES;
    }

    public static long availableBytes(Context context) {
        return new StatFs(context.getCacheDir().getAbsolutePath()).getAvailableBytes();
    }
}
