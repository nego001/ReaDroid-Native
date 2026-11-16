package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.Set;
import java.util.zip.CRC32;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * F1.6: stream every ZIP member, not just the central-directory index.
 * Never extract entries or trust advertised sizes/CRC without checking bytes.
 * CRC32 detects accidental ZIP corruption; it is NOT an APK signature check.
 */
public final class ApkZipIntegrity {
    static final long MAX_ENTRY_BYTES = 1024L * 1024 * 1024;
    static final long MAX_TOTAL_BYTES = 2L * 1024 * 1024 * 1024;
    static final long MAX_VERIFY_NANOS = 120L * 1000 * 1000 * 1000;
    static final int MAX_ENTRIES = 150000;
    private static final int MAX_ZERO_READS = 16;

    private ApkZipIntegrity() {}

    static final class Result {
        final int verifiedFiles;
        final long uncompressedBytes;

        Result(int verifiedFiles, long uncompressedBytes) {
            this.verifiedFiles = verifiedFiles;
            this.uncompressedBytes = uncompressedBytes;
        }
    }

    static Result verify(File apk) throws IOException {
        return verify(apk, MAX_ENTRY_BYTES, MAX_TOTAL_BYTES, MAX_VERIFY_NANOS, null);
    }

    static Result verify(File apk, ExportSessionGuard.Token token) throws IOException {
        return verify(apk, MAX_ENTRY_BYTES, MAX_TOTAL_BYTES, MAX_VERIFY_NANOS, token);
    }

    // Package-private budgets make zip-bomb tests small and deterministic.
    static Result verify(File apk, long maxEntry, long maxTotal, long maxNanos)
            throws IOException {
        return verify(apk, maxEntry, maxTotal, maxNanos, null);
    }

    static Result verify(File apk, long maxEntry, long maxTotal, long maxNanos,
            ExportSessionGuard.Token token) throws IOException {
        ExportSessionGuard.check(token);
        if (apk == null || !apk.isFile())
            throw new IOException("Arquivo APK indisponível para auditoria ZIP");
        if (maxEntry < 0 || maxTotal < 0 || maxNanos < 0)
            throw new IllegalArgumentException("Orçamento ZIP inválido");

        final long started = System.nanoTime();
        final byte[] buffer = new byte[65536];
        long total = 0;
        int entries = 0, verified = 0;
        Set<String> seen = new HashSet<>();
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> cursor = zip.entries();
            while (cursor.hasMoreElements()) {
                ensureActive(started, maxNanos, token);
                if (++entries > MAX_ENTRIES)
                    throw new IOException("APK com entradas ZIP demais");
                ZipEntry entry = cursor.nextElement();
                // F1.8: reject malformed/ambiguous paths and duplicate ZIP
                // names *before* spending CPU inflating untrusted payloads.
                // Reuse the same policy enforced by the SQLite index.
                String path = entry.getName();
                ApkDiskIndex.validatePath(path);
                if (!seen.add(path))
                    throw new IOException("Entrada ZIP duplicada: " + path);
                long size = entry.getSize();
                long compressed = entry.getCompressedSize();
                if (size < 0 || compressed < 0)
                    throw new IOException("Entrada ZIP sem tamanho verificável");
                if (size > maxEntry || compressed > ApkImportPreflight.MAX_APK_BYTES)
                    throw new IOException("Entrada ZIP excede orçamento por arquivo");
                if (size > maxTotal - total)
                    throw new IOException("APK excede orçamento total descomprimido");

                // Directory records must not conceal data.
                if (entry.isDirectory()) {
                    if (size != 0)
                        throw new IOException("Diretório ZIP com conteúdo inesperado");
                    continue;
                }
                if (entry.getMethod() != ZipEntry.STORED
                        && entry.getMethod() != ZipEntry.DEFLATED)
                    throw new IOException("Método de compressão ZIP não suportado");
                if (entry.getCrc() < 0)
                    throw new IOException("Entrada ZIP sem CRC32 declarado");

                CRC32 crc = new CRC32();
                long actual = 0;
                int zeroReads = 0;
                try (InputStream input = zip.getInputStream(entry)) {
                    if (input == null)
                        throw new IOException("Entrada ZIP não pode ser aberta");
                    while (true) {
                        ensureActive(started, maxNanos, token);
                        int n = input.read(buffer);
                        ensureActive(started, maxNanos, token);
                        if (n < 0) break;
                        if (n == 0) {
                            if (++zeroReads > MAX_ZERO_READS)
                                throw new IOException("Descompressão ZIP sem progresso");
                            continue;
                        }
                        zeroReads = 0;
                        if (n > maxEntry - actual || n > maxTotal - total)
                            throw new IOException("Descompressão ZIP excedeu orçamento");
                        if (n > size - actual)
                            throw new IOException("Tamanho real de entrada ZIP divergente");
                        actual += n;
                        total += n;
                        crc.update(buffer, 0, n);
                    }
                }
                if (actual != size)
                    throw new IOException("Tamanho descomprimido ZIP não confere");
                if (crc.getValue() != entry.getCrc())
                    throw new IOException("CRC32 ZIP divergente: entrada corrompida");
                verified++;
            }
        }
        ensureActive(started, maxNanos, token);
        if (entries == 0 || verified == 0)
            throw new IOException("ZIP/APK sem arquivos internos válidos");
        return new Result(verified, total);
    }

    private static void ensureActive(long start, long budget,
            ExportSessionGuard.Token token) throws IOException {
        ExportSessionGuard.check(token);
        if (System.nanoTime() - start > budget)
            throw new IOException("Tempo máximo de auditoria ZIP excedido");
    }
}
