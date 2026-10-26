package com.readroid.app;

import java.io.IOException;
import java.io.InputStream;

/**
 * M3.1, read-only DEX v035-v040 HEADER preview. Never loads the executable,
 * resolves types, executes code, or claims that the DEX body is valid.
 * Run only after M2 ZIP admission has verified the underlying APK entry.
 *
 * Android 16's experimental DEX 041 container is deliberately unsupported:
 * its header/offset rules differ from traditional DEX 035-040.
 */
final class DexHeaderProbe {
    static final int HEADER_BYTES = 112;
    private static final long MAX_DEX_BYTES = 1024L * 1024 * 1024;
    private DexHeaderProbe() {}

    static final class Header {
        final String version;
        final long sizeBytes;
        final long stringIds;
        final long typeIds;
        final long protoIds;
        final long fieldIds;
        final long methodIds;
        final long classDefs;
        final long mapOffset;
        final long dataOffset;
        final long dataBytes;
        final long[] sectionOffsets;

        Header(String version, long sizeBytes, long stringIds, long typeIds,
                long protoIds, long fieldIds, long methodIds, long classDefs,
                long mapOffset, long dataOffset, long dataBytes,
                long[] sectionOffsets) {
            this.version = version;
            this.sizeBytes = sizeBytes;
            this.stringIds = stringIds;
            this.typeIds = typeIds;
            this.protoIds = protoIds;
            this.fieldIds = fieldIds;
            this.methodIds = methodIds;
            this.classDefs = classDefs;
            this.mapOffset = mapOffset;
            this.dataOffset = dataOffset;
            this.dataBytes = dataBytes;
            this.sectionOffsets = sectionOffsets.clone();
        }
    }

    static Header inspect(InputStream stream, long expectedBytes) throws IOException {
        if (stream == null || expectedBytes < HEADER_BYTES + 4
                || expectedBytes > MAX_DEX_BYTES)
            throw new IOException("Entrada DEX com tamanho inválido");
        byte[] bytes = new byte[HEADER_BYTES];
        int read = 0;
        while (read < bytes.length) {
            if (Thread.currentThread().isInterrupted())
                throw new java.io.InterruptedIOException("Leitura DEX cancelada");
            int n = stream.read(bytes, read, bytes.length - read);
            if (n < 0) throw new IOException("Cabeçalho DEX truncado");
            if (n == 0) throw new IOException("Fluxo DEX sem progresso");
            read += n;
        }
        if (bytes[0] != 'd' || bytes[1] != 'e' || bytes[2] != 'x'
                || bytes[3] != '\n' || bytes[7] != 0)
            throw new IOException("Assinatura mágica DEX inválida");
        for (int i = 4; i < 7; i++)
            if (bytes[i] < '0' || bytes[i] > '9')
                throw new IOException("Versão DEX inválida");
        String version = new String(bytes, 4, 3, java.nio.charset.StandardCharsets.US_ASCII);
        int v = Integer.parseInt(version);
        if (v < 35 || v > 40)
            throw new IOException("Versão DEX não suportada: " + version);

        long fileSize = u32(bytes, 32);
        long headerSize = u32(bytes, 36);
        long endian = u32(bytes, 40);
        long linkSize = u32(bytes, 44);
        long linkOff = u32(bytes, 48);
        long mapOff = u32(bytes, 52);
        long dataSize = u32(bytes, 104);
        long dataOff = u32(bytes, 108);
        if (fileSize != expectedBytes || headerSize != HEADER_BYTES)
            throw new IOException("Cabeçalho DEX declara tamanho inconsistente");
        if (endian != 0x12345678L)
            throw new IOException("Endianness DEX não suportado");
        requireSection("link", linkSize, linkOff, 1, fileSize);
        if (dataSize < 4 || dataOff < HEADER_BYTES || (dataOff & 3) != 0
                || dataOff > fileSize || dataSize > fileSize - dataOff)
            throw new IOException("Região de dados DEX fora dos limites");
        if (mapOff < dataOff || (mapOff & 3) != 0 || mapOff > fileSize - 4)
            throw new IOException("Mapa DEX fora da região de dados");

        long strings = requireSection("strings", u32(bytes, 56),
            u32(bytes, 60), 4, fileSize);
        long types = requireSection("types", u32(bytes, 64),
            u32(bytes, 68), 4, fileSize);
        long protos = requireSection("protos", u32(bytes, 72),
            u32(bytes, 76), 12, fileSize);
        long fields = requireSection("fields", u32(bytes, 80),
            u32(bytes, 84), 8, fileSize);
        long methods = requireSection("methods", u32(bytes, 88),
            u32(bytes, 92), 8, fileSize);
        long classes = requireSection("classes", u32(bytes, 96),
            u32(bytes, 100), 32, fileSize);
        return new Header(version, fileSize, strings, types, protos, fields,
            methods, classes, mapOff, dataOff, dataSize, new long[] {
                u32(bytes, 60), u32(bytes, 68), u32(bytes, 76),
                u32(bytes, 84), u32(bytes, 92), u32(bytes, 100)
            });
    }

    private static long requireSection(String label, long count, long offset,
            long itemBytes, long fileSize) throws IOException {
        if (count == 0) {
            if (offset != 0)
                throw new IOException("Seção DEX vazia com deslocamento: " + label);
            return 0;
        }
        // Subtraction avoids overflow from malicious 32-bit unsigned fields.
        if (offset < HEADER_BYTES || (offset & 3) != 0
                || offset >= fileSize || count > (fileSize - offset) / itemBytes)
            throw new IOException("Seção DEX fora dos limites: " + label);
        return count;
    }

    private static long u32(byte[] b, int offset) {
        return ((long) b[offset] & 255)
            | (((long) b[offset + 1] & 255) << 8)
            | (((long) b[offset + 2] & 255) << 16)
            | (((long) b[offset + 3] & 255) << 24);
    }
}
