package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Fail-closed central-directory admission for untrusted APK/ZIP input.
 * Never inflates an entry, follows an archive path or writes extracted files.
 *
 * This is a metadata and expansion-risk gate, NOT evidence that uncompressed
 * CRC, signatures or Android binary resources have been fully authenticated.
 */
public final class ApkArchiveBudget {
    static final int MAX_ENTRIES = 150000;
    static final long MAX_ENTRY_BYTES = 1024L * 1024 * 1024;
    static final long MAX_TOTAL_BYTES = 2L * 1024 * 1024 * 1024;
    static final long RATIO_CHECK_MIN_BYTES = 16L * 1024 * 1024;
    static final long MAX_EXPANSION_RATIO = 1000;

    private final Set<String> paths = new HashSet<>();
    private int entryCount;
    private long totalUncompressed;

    private ApkArchiveBudget() {}

    /** Validate one central-directory entry and consume its declared budget. */
    public static final class Scan {
        private final ApkArchiveBudget budget = new ApkArchiveBudget();

        public void accept(ZipEntry entry) throws IOException {
            if (Thread.currentThread().isInterrupted())
                throw new java.io.InterruptedIOException("Inspeção ZIP cancelada");
            if (entry == null) throw new IOException("Entrada ZIP ausente");
            if (++budget.entryCount > MAX_ENTRIES)
                throw new IOException("APK com entradas demais (limite de 150 mil)");
            String name = entry.getName();
            ApkDiskIndex.validatePath(name);
            if (!budget.paths.add(name))
                throw new IOException("Entrada ZIP duplicada: " + name);
            if (entry.isDirectory()) return;

            long declared = entry.getSize();
            long compressed = entry.getCompressedSize();
            if (declared < 0 || compressed < 0)
                throw new IOException("Tamanho ZIP desconhecido: " + name);
            if (declared > MAX_ENTRY_BYTES)
                throw new IOException("Entrada maior que 1 GiB: " + name);
            if (declared > MAX_TOTAL_BYTES - budget.totalUncompressed)
                throw new IOException("APK excede 2 GiB descomprimidos");
            if (declared > 0 && compressed == 0)
                throw new IOException("Entrada ZIP sem tamanho comprimido válido: " + name);
            // Check ratio without multiplication overflow. The floor avoids
            // rejecting tiny, compressible text and standard small metadata.
            if (declared >= RATIO_CHECK_MIN_BYTES && compressed > 0
                    && declared / compressed > MAX_EXPANSION_RATIO)
                throw new IOException("Taxa de expansão ZIP suspeita: " + name);
            budget.totalUncompressed += declared;
        }

        public long uncompressedBytes() { return budget.totalUncompressed; }
        public int entries() { return budget.entryCount; }
    }

    /**
     * Check the full directory BEFORE Manifest/DEX parsing or SQLite indexing.
     * The caller continues to enforce the 1 GiB compressed SAF-copy quota.
     */
    public static void verifyArchive(File archive) throws IOException {
        if (archive == null || !archive.isFile())
            throw new IOException("APK para inspeção não encontrado");
        try (ZipFile zip = new ZipFile(archive)) {
            Scan scan = new Scan();
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) scan.accept(entries.nextElement());
        }
    }
}
