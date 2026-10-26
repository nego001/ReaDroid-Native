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
 * M2 admission gate for untrusted APK ZIPs, before manifest parsing, indexing,
 * or accepting a replacement project. Reads content in fixed-size chunks and
 * never extracts archive paths or executes code from the inspected APK.
 *
 * ZIP central-directory metadata is only a declaration: each entry's actual
 * inflated length and CRC are checked while consuming a bounded stream.
 */
public final class ApkArchiveSafety {
    private static final int MAX_ENTRIES = 150000;
    private static final long MAX_PATH_CHARS_TOTAL = 16L * 1024 * 1024;
    private static final long MAX_ENTRY_BYTES = 1024L * 1024 * 1024;
    private static final long MAX_TOTAL_BYTES = 2L * 1024 * 1024 * 1024;
    // High ratios on large files can impose excessive CPU and decompression.
    // This intentionally rejects unusually compressible inputs, not just bad ZIPs.
    private static final long RATIO_CHECK_FROM_BYTES = 8L * 1024 * 1024;
    private static final long MAX_COMPRESSION_RATIO = 500;
    private static final int BUFFER_BYTES = 64 * 1024;

    private ApkArchiveSafety() {}

    public static final class Stats {
        public final int entries;
        public final int files;
        public final long inflatedBytes;

        Stats(int entries, int files, long inflatedBytes) {
            this.entries = entries;
            this.files = files;
            this.inflatedBytes = inflatedBytes;
        }
    }

    public static Stats verify(File apk) throws IOException {
        if (apk == null || !apk.isFile() || apk.length() == 0)
            throw new IOException("APK ausente ou vazio");
        if (apk.length() > ApkImportPreflight.MAX_APK_BYTES)
            throw new IOException("APK acima do limite de importação de 1 GiB");

        int count = 0;
        int files = 0;
        long declaredTotal = 0;
        long measuredTotal = 0;
        long pathChars = 0;
        Set<String> paths = new HashSet<>();
        byte[] buffer = new byte[BUFFER_BYTES];

        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                checkInterrupted();
                ZipEntry entry = entries.nextElement();
                if (++count > MAX_ENTRIES)
                    throw new IOException("APK excede 150 mil entradas");
                String name = entry.getName();
                ApkDiskIndex.validatePath(name);
                pathChars += name.length();
                if (pathChars > MAX_PATH_CHARS_TOTAL)
                    throw new IOException("Metadados de caminhos excedem o orçamento de memória");
                if (!paths.add(name))
                    throw new IOException("Entrada ZIP duplicada: " + name);

                long size = entry.getSize();
                long compressed = entry.getCompressedSize();
                long crc = entry.getCrc();
                if (size < 0 || compressed < 0 || crc < 0)
                    throw new IOException("Metadados ZIP incompletos: " + name);
                if (entry.getMethod() != ZipEntry.STORED
                        && entry.getMethod() != ZipEntry.DEFLATED)
                    throw new IOException("Método ZIP não suportado: " + name);
                if (compressed > apk.length())
                    throw new IOException("Tamanho comprimido inválido: " + name);
                if (entry.isDirectory()) {
                    if (size != 0) throw new IOException("Diretório ZIP contém dados: " + name);
                    continue;
                }
                files++;
                if (size > MAX_ENTRY_BYTES)
                    throw new IOException("Entrada ZIP acima de 1 GiB: " + name);
                if (declaredTotal > MAX_TOTAL_BYTES - size)
                    throw new IOException("ZIP excede 2 GiB descomprimidos");
                declaredTotal += size;
                if (size > 0 && compressed == 0)
                    throw new IOException("Entrada ZIP não vazia com tamanho comprimido zero");
                if (size >= RATIO_CHECK_FROM_BYTES
                        && compressed > 0
                        && size / compressed > MAX_COMPRESSION_RATIO)
                    throw new IOException("Taxa de compressão excessiva: " + name);

                long actual = 0;
                CRC32 actualCrc = new CRC32();
                int consecutiveZeroReads = 0;
                try (InputStream stream = zip.getInputStream(entry)) {
                    if (stream == null) throw new IOException("Entrada ZIP ilegível: " + name);
                    int read;
                    while ((read = stream.read(buffer)) != -1) {
                        checkInterrupted();
                        if (read == 0) {
                            if (++consecutiveZeroReads > 16)
                                throw new IOException("Descompressão sem progresso: " + name);
                            continue;
                        }
                        consecutiveZeroReads = 0;
                        // Check before incrementing to avoid overflow and
                        // stop an entry whose real size differs from metadata.
                        if (actual > size - read || actual > MAX_ENTRY_BYTES - read
                                || measuredTotal > MAX_TOTAL_BYTES - read)
                            throw new IOException("Expansão ZIP excedeu limite declarado: " + name);
                        actual += read;
                        measuredTotal += read;
                        actualCrc.update(buffer, 0, read);
                    }
                }
                if (actual != size)
                    throw new IOException("Tamanho descomprimido divergente: " + name);
                if (actualCrc.getValue() != crc)
                    throw new IOException("CRC-32 divergente: " + name);
            }
        }
        if (count == 0) throw new IOException("Arquivo ZIP sem entradas");
        return new Stats(count, files, measuredTotal);
    }

    private static void checkInterrupted() throws InterruptedIOException {
        if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Verificação ZIP cancelada");
    }
}
