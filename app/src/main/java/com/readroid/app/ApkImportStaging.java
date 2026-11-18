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
        return copy(privateCache, source, space, null);
    }

    static Result copy(File privateCache, OpenSource source,
            ApkImportPreflight.FreeSpace space, ExportSessionGuard.Token token)
            throws IOException {
        return copy(privateCache, source, space, token, null);
    }

    static Result copy(File privateCache, OpenSource source,
            ApkImportPreflight.FreeSpace space, ExportSessionGuard.Token token,
            ImportActivityScope scope) throws IOException {
        ExportSessionGuard.check(token);
        if (privateCache == null || !privateCache.isDirectory()
                || source == null || space == null)
            throw new IOException("Origem ou cache privado indisponível para importação");
        // Create the only file we are authorized to clean on failure.
        File staged = File.createTempFile("readroid_", ".apk", privateCache);
        ImportCacheAudit.track(staged);
        boolean complete = false;
        try {
            if (scope != null) scope.track(staged);
            ExportSessionGuard.check(token);
            final ApkImportPreflight.CopyResult copied;
            ExportSessionGuard.check(token);
            // Acquire the only writable descriptor BEFORE opening an untrusted
            // provider. A blocked source.open() must never reopen this path
            // after its Activity has unlinked the temporary file onDestroy().
            try (OutputStream output = scope == null
                    ? new FileOutputStream(staged) : scope.openForWrite(staged);
                 InputStream input = source.open()) {
                ExportSessionGuard.check(token);
                if (input == null)
                    throw new IOException("O provedor SAF não abriu o arquivo selecionado");
                copied = ApkImportPreflight.copyAndHash(input, output, space, token);
                ExportSessionGuard.check(token);
            }
            ExportSessionGuard.check(token);
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
                    if (scope != null) scope.release(staged);
                }
            }
        }
    }
}
