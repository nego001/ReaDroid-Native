package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;

/**
 * F1.7: final admission gate for a SAF copy in private cache.
 *
 * The copy-time digest is an expectation, NOT proof that the on-disk cache
 * still contains those bytes after subsequent ZIP reads and SQLite indexing.
 * This gate runs immediately before publishing an analyzed candidate.
 */
public final class ApkCacheAdmission {
    private ApkCacheAdmission() {}

    static void verify(File cache, long copiedBytes, String copiedSha256)
            throws IOException {
        if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Validação final do APK interrompida");
        if (cache == null || !cache.isFile()
                || copiedBytes <= 0
                || copiedBytes > ApkImportPreflight.MAX_APK_BYTES
                || copiedSha256 == null
                || !copiedSha256.matches("[0-9a-f]{64}"))
            throw new IOException("Metadados da cópia APK inválidos");
        if (cache.length() != copiedBytes)
            throw new IOException("Tamanho do APK em cache mudou após a cópia");

        // 64 KiB streaming, no entire-file loading; checks interruption.
        ApkIntegrity.confirmExpected(cache, copiedSha256);

        if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Validação final do APK interrompida");
        if (!cache.isFile() || cache.length() != copiedBytes)
            throw new IOException("Tamanho do APK em cache mudou durante a verificação");
    }
}
