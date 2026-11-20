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
import java.util.List;
import java.util.Locale;

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

    /**
     * F1.13: compare the user-selected import document with the SAF output
     * before a content provider is opened for writing.
     */
    public static long copyAndVerify(ContentResolver resolver, File source, Uri destination,
            Uri importedDocument) throws IOException {
        return copyAndVerifyBound(resolver, source, destination, importedDocument, null);
    }

    /** Internal worker route: keeps the project session bound through SAF I/O. */
    static long copyAndVerifyBound(ContentResolver resolver, File source, Uri destination,
            Uri importedDocument, ExportSessionGuard.Token token) throws IOException {
        checkToken(token);
        ensureDistinctDocument(importedDocument, destination);
        checkToken(token);
        return copyAndVerifyInternal(resolver, source, destination, token);
    }

    /**
     * Fail closed if the selected output is the imported document. SAF may
     * represent one item as either /document/{id} or /tree/{id}/document/{id}.
     * Queries and fragments are not document identity. Opaque aliases across
     * different authorities cannot be established without provider support.
     */
    static void ensureDistinctDocument(Uri imported, Uri destination) throws IOException {
        if (imported == null || destination == null)
            throw new IOException("Identidade do documento SAF de origem ou destino indisponível");
        String aScheme = normalizedScheme(imported);
        String bScheme = normalizedScheme(destination);
        if (!"content".equals(aScheme) && !"file".equals(aScheme))
            throw new IOException("URI de origem não suportado para exportação segura");
        if (!"content".equals(bScheme) && !"file".equals(bScheme))
            throw new IOException("URI de destino não suportado para exportação segura");
        if ("file".equals(aScheme) && "file".equals(bScheme)) {
            if (imported.getPath() == null || destination.getPath() == null)
                throw new IOException("Caminho de documento local indisponível");
            if (new File(imported.getPath()).getCanonicalFile()
                    .equals(new File(destination.getPath()).getCanonicalFile()))
                throw new IOException("O destino é o APK de origem; escolha outro documento");
            return;
        }
        if (!"content".equals(aScheme) || !"content".equals(bScheme)) return;
        String authorityA = imported.getAuthority();
        String authorityB = destination.getAuthority();
        if (authorityA == null || authorityB == null)
            throw new IOException("Autoridade SAF inválida");
        if (!authorityA.equalsIgnoreCase(authorityB)) return;
        if (imported.getPath() != null && imported.getPath().equals(destination.getPath()))
            throw new IOException("O destino é o APK de origem; escolha outro documento");
        String documentA = documentId(imported);
        String documentB = documentId(destination);
        if (documentA != null && documentA.equals(documentB))
            throw new IOException("O destino é o APK de origem; escolha outro documento");
    }

    private static String normalizedScheme(Uri uri) {
        return uri.getScheme() == null ? "" : uri.getScheme().toLowerCase(Locale.ROOT);
    }

    /** Decode only the two documented SAF document URI path shapes. */
    private static String documentId(Uri uri) {
        List<String> parts = uri.getPathSegments();
        if (parts.size() == 2 && "document".equals(parts.get(0)))
            return parts.get(1);
        if (parts.size() == 4 && "tree".equals(parts.get(0))
                && "document".equals(parts.get(2)))
            return parts.get(3);
        return null;
    }

    public static long copyAndVerify(ContentResolver resolver, File source, Uri destination)
            throws IOException {
        return copyAndVerifyInternal(resolver, source, destination, null);
    }

    private static long copyAndVerifyInternal(ContentResolver resolver, File source,
            Uri destination, ExportSessionGuard.Token token) throws IOException {
        checkToken(token);
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
                checkToken(token);
                return resolver.openOutputStream(destination, "w");
            }
            @Override public InputStream openRead() throws IOException {
                checkToken(token);
                return resolver.openInputStream(destination);
            }
        }, token);
    }

    static long copyAndVerify(File source, ExportTarget target) throws IOException {
        return copyAndVerify(source, target, null);
    }

    static long copyAndVerify(File source, ExportTarget target,
            ExportSessionGuard.Token token) throws IOException {
        checkToken(token);
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
            while ((n = readWithProgress(in, buffer, zeros, "Origem", token)) != -1) {
                if (n == 0) continue;
                sourceLength += n;
                expectedDigest.update(buffer, 0, n);
            }
        }
        final byte[] expected = expectedDigest.digest();
        checkToken(token);
        long copiedLength = 0;
        MessageDigest copiedDigest = sha256();
        try (InputStream input = new FileInputStream(source);
             OutputStream output = target.openWrite()) {
            if (output == null)
                throw new IOException("O Android não abriu o destino para gravação");
            checkToken(token);
            int[] zeros = {0};
            int n;
            while ((n = readWithProgress(input, buffer, zeros, "Origem", token)) != -1) {
                if (n == 0) continue;
                if (n > sourceLength - copiedLength)
                    throw new IOException("O APK temporário mudou durante a exportação");
                checkToken(token);
                output.write(buffer, 0, n);
                checkToken(token);
                copiedDigest.update(buffer, 0, n);
                copiedLength += n;
            }
            checkToken(token);
            output.flush();
        }
        checkToken(token);
        ensureActive("Exportação");
        if (copiedLength != sourceLength
                || !Arrays.equals(expected, copiedDigest.digest()))
            throw new IOException("O APK temporário mudou durante a exportação");

        // Never mark the SAF result successful from write/close alone.
        // Content providers can silently truncate, append, or corrupt bytes.
        long exportedLength = 0;
        MessageDigest actualDigest = sha256();
        checkToken(token);
        try (InputStream verify = target.openRead()) {
            if (verify == null)
                throw new IOException("Não foi possível reler o arquivo exportado");
            checkToken(token);
            int[] zeros = {0};
            int n;
            while ((n = readWithProgress(verify, buffer, zeros, "Releitura SAF", token)) != -1) {
                if (n == 0) continue;
                if (n > sourceLength - exportedLength)
                    throw new IOException("O destino contém bytes extras");
                actualDigest.update(buffer, 0, n);
                exportedLength += n;
            }
        }
        checkToken(token);
        ensureActive("Verificação");
        if (sourceLength != exportedLength
                || !Arrays.equals(expected, actualDigest.digest()))
            throw new IOException("O arquivo exportado não confere com o APK verificado (SHA-256)");
        checkToken(token);
        return exportedLength;
    }

    private static void checkToken(ExportSessionGuard.Token token)
            throws java.io.InterruptedIOException {
        if (token != null) token.requireActive();
    }

    /** Zero-byte provider reads are bounded, not interpreted as EOF. */
    private static int readWithProgress(InputStream stream, byte[] buffer,
            int[] consecutiveZeros, String stage, ExportSessionGuard.Token token)
            throws IOException {
        checkToken(token);
        ensureActive(stage);
        int n = stream.read(buffer);
        checkToken(token);
        ensureActive(stage);
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
