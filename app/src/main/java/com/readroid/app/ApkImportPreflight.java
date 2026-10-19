package com.readroid.app;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.StatFs;
import android.provider.OpenableColumns;

import java.io.IOException;

/**
 * Fast, bounded import preflight. The Android document provider's size is a
 * hint (sometimes absent or incorrect), never a substitute for byte-counting
 * while streaming a potentially hostile APK into private cache.
 */
public final class ApkImportPreflight {
    static final long MAX_APK_BYTES = 1024L * 1024 * 1024;
    private static final long RESERVE_BYTES = 64L * 1024 * 1024;
    private static final long CHECK_EVERY_BYTES = 32L * 1024 * 1024;

    private ApkImportPreflight() {}

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
