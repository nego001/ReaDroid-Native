package com.readroid.app;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;

/**
 * F1.21: one owner of private import staging for untrusted SAF streams.
 *
 * Only this method creates the readroid_*.apk candidate, registers the
 * import audit lease, and rolls back if opening, streaming, flush, or close
 * fails. A SUCCESSFUL candidate remains leased until MainActivity either
 * accepts it or destroys it after later ZIP/CRC/integrity validation.
 * Never touches the original SAF document or an existing project.
 */
final class ApkImportStaging {
    interface OpenSource {
        InputStream open() throws IOException;
    }

    static final class Result {
        final File candidate;
        final ApkImportPreflight.CopyResult copied;

        Result(File candidate, ApkImportPreflight.CopyResult copied) {
            this.candidate = candidate;
            this.copied = copied;
        }
    }

    private ApkImportStaging() {}

    static Result copy(File privateCache, OpenSource source,
            ApkImportPreflight.FreeSpace space) throws IOException {
        if (privateCache == null || !privateCache.isDirectory()
                || source == null || space == null)
            throw new IOException("Origem ou cache privado indisponível para importação");
        // Create the only file we are authorized to clean on failure.
        File staged = File.createTempFile("readroid_", ".apk", privateCache);
        ImportCacheAudit.track(staged);
        boolean complete = false;
        try {
            final ApkImportPreflight.CopyResult copied;
            try (InputStream input = source.open();
                 OutputStream output = new FileOutputStream(staged)) {
                if (input == null)
                    throw new IOException("O provedor SAF não abriu o arquivo selecionado");
                copied = ApkImportPreflight.copyAndHash(input, output, space);
            }
            // Resource close can itself fail. Ownership is transferred only
            // AFTER both SAF input and private-cache output close cleanly.
            complete = true;
            return new Result(staged, copied);
        } catch (SecurityException | IllegalArgumentException accessDenied) {
            throw new IOException("Permissão ou documento SAF inválido durante importação",
                accessDenied);
        } finally {
            if (!complete) {
                try {
                    // Never delete a preexisting cache file or a user SAF URI.
                    Files.deleteIfExists(staged.toPath());
                } finally {
                    ImportCacheAudit.release(staged);
                }
            }
        }
    }
}
