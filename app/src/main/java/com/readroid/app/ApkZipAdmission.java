package com.readroid.app;

import java.io.IOException;
import java.util.zip.ZipEntry;

/**
 * M2: fail-closed admission of hostile ZIP metadata before creating in-memory
 * explorer rows or SQLite index records. This is a metadata *preflight*, not
 * proof that a forged ZIP really decompresses to its claimed length. Actual
 * reads/rebuilds still require bounded streaming and cryptographic checks.
 */
public final class ApkZipAdmission {
    static final int MAX_PATH_CHARS = 4096;
    static final int MAX_DEPTH = 128;
    static final int MAX_ENTRIES = 150000;
    static final long MAX_ENTRY_BYTES = 1024L * 1024 * 1024;
    static final long MAX_TOTAL_BYTES = 2L * 1024 * 1024 * 1024;
    // Do not trust metadata claiming 16 MiB+ expansion from tiny input.
    // A legitimate exceptional archive can be assessed by a later safe mode.
    static final long RATIO_CHECK_BYTES = 16L * 1024 * 1024;
    static final long MAX_COMPRESSION_RATIO = 1000;

    private ApkZipAdmission() {}

    static void validatePath(String path) throws IOException {
        if (path == null || path.isEmpty() || path.length() > MAX_PATH_CHARS
                || path.startsWith("/") || path.indexOf('\\') >= 0)
            throw new IOException("Caminho ZIP inseguro ou grande demais");
        for (int i = 0; i < path.length(); i++) {
            if (Character.isISOControl(path.charAt(i)))
                throw new IOException("Caminho ZIP contém caractere de controle");
        }
        String[] segments = path.split("/", -1);
        if (segments.length > MAX_DEPTH + 1)
            throw new IOException("Profundidade excessiva de diretórios");
        for (int i = 0; i < segments.length; i++) {
            if (segments[i].isEmpty() && i == segments.length - 1) continue;
            if (segments[i].isEmpty() || ".".equals(segments[i])
                    || "..".equals(segments[i]))
                throw new IOException("Caminho ZIP potencialmente inseguro");
        }
    }

    static void validateEntry(ZipEntry entry) throws IOException {
        if (entry == null) throw new IOException("Entrada ZIP ausente");
        validatePath(entry.getName());
        long size = entry.getSize();
        long compressed = entry.getCompressedSize();
        if (size < 0 || compressed < 0)
            throw new IOException("Entrada ZIP com tamanho desconhecido: "
                + entry.getName());
        if (entry.isDirectory()) {
            if (size != 0 || compressed != 0)
                throw new IOException("Diretório ZIP com dados inesperados");
            return;
        }
        if (size > MAX_ENTRY_BYTES)
            throw new IOException("Entrada ZIP acima de 1 GiB: "
                + entry.getName());
        int method = entry.getMethod();
        if (method != ZipEntry.STORED && method != ZipEntry.DEFLATED)
            throw new IOException("Método de compressão ZIP não suportado");
        if (method == ZipEntry.STORED && compressed != size)
            throw new IOException("Entrada armazenada com tamanho divergente");
        if (size > 0 && compressed == 0)
            throw new IOException("Entrada ZIP declara expansão sem dados");
        // No multiplication of attacker-controlled longs: avoid overflow.
        if (size >= RATIO_CHECK_BYTES && compressed > 0
                && size / compressed > MAX_COMPRESSION_RATIO)
            throw new IOException("Taxa de expansão ZIP suspeita: "
                + entry.getName());
    }

    static long cumulativeBytes(long previous, ZipEntry entry)
            throws IOException {
        validateEntry(entry);
        if (previous < 0 || previous > MAX_TOTAL_BYTES)
            throw new IOException("Total ZIP anterior inválido");
        if (entry.isDirectory()) return previous;
        long size = entry.getSize();
        if (size > MAX_TOTAL_BYTES - previous)
            throw new IOException("Total descomprimido excede 2 GiB");
        return previous + size;
    }
}
