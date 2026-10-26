package com.readroid.app;

import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * M3.2: inspect only the bounded DEX map_list, never load or decode the
 * remainder of the DEX file. The source APK must pass M2 ZIP admission first.
 * This checks structural declarations, NOT bytecode validity/verification.
 */
final class DexMapProbe {
    static final int MAX_MAP_ITEMS = 64;
    static final long MAX_MAP_OFFSET = 16L * 1024 * 1024;
    private static final int ITEM_BYTES = 12;
    private static final int BUFFER_BYTES = 16 * 1024;

    private DexMapProbe() {}

    static final class Item {
        final int type;
        final String label;
        final long count;
        final long offset;

        Item(int type, long count, long offset) throws IOException {
            this.type = type;
            this.label = label(type);
            this.count = count;
            this.offset = offset;
        }
    }

    static final class Result {
        final String version;
        final long mapOffset;
        final List<Item> items;

        Result(String version, long mapOffset, List<Item> items) {
            this.version = version;
            this.mapOffset = mapOffset;
            this.items = Collections.unmodifiableList(new ArrayList<>(items));
        }
    }

    static Result inspect(InputStream input, long expectedBytes) throws IOException {
        // Header probe consumes exactly 112 bytes. Bounded map offset limits
        // the additional decompression work that a malicious ZIP can induce.
        DexHeaderProbe.Header h = DexHeaderProbe.inspect(input, expectedBytes);
        if (h.mapOffset > MAX_MAP_OFFSET || h.mapOffset < DexHeaderProbe.HEADER_BYTES)
            throw new IOException("Mapa DEX além do orçamento de leitura");
        skipExactly(input, h.mapOffset - DexHeaderProbe.HEADER_BYTES);

        byte[] word = new byte[4];
        readExactly(input, word, 4);
        long declared = u32(word, 0);
        if (declared < 2 || declared > MAX_MAP_ITEMS
                || 4 + declared * ITEM_BYTES > expectedBytes - h.mapOffset)
            throw new IOException("Quantidade de seções DEX inválida");

        List<Item> entries = new ArrayList<>((int) declared);
        Set<Integer> types = new HashSet<>();
        byte[] itemBytes = new byte[ITEM_BYTES];
        long previousOffset = -1;
        for (int i = 0; i < declared; i++) {
            readExactly(input, itemBytes, ITEM_BYTES);
            int type = u16(itemBytes, 0);
            int unused = u16(itemBytes, 2);
            long size = u32(itemBytes, 4);
            long offset = u32(itemBytes, 8);
            if (unused != 0 || size == 0 || offset >= expectedBytes
                    || offset <= previousOffset || !types.add(type))
                throw new IOException("Mapa DEX contém seção duplicada ou deslocamento inválido");
            Item item = new Item(type, size, offset);
            entries.add(item);
            previousOffset = offset;
        }
        if (entries.get(0).type != 0 || entries.get(0).offset != 0
                || entries.get(0).count != 1)
            throw new IOException("Mapa DEX sem cabeçalho inicial válido");

        boolean mapPresent = false;
        for (int i = 0; i < entries.size(); i++) {
            Item entry = entries.get(i);
            if (entry.type == 0x1000) {
                if (mapPresent || entry.count != 1 || entry.offset != h.mapOffset)
                    throw new IOException("Auto-referência inválida do mapa DEX");
                mapPresent = true;
            }
            long next = i + 1 < entries.size()
                ? entries.get(i + 1).offset : expectedBytes;
            long width = fixedWidth(entry.type);
            if (entry.type == 0x1000)
                width = 4 + declared * ITEM_BYTES;
            if (width > 0 && (entry.count > (next - entry.offset) / width))
                throw new IOException("Seções fixas DEX sobrepostas ou truncadas");
            if (entry.type == 0x1000 && next - entry.offset < width)
                throw new IOException("Lista de seções DEX truncada");
            if (entry.type >= 0x1000 && entry.offset < h.dataOffset)
                throw new IOException("Seção DEX de dados fora da região de dados");
        }
        if (!mapPresent)
            throw new IOException("Mapa DEX não contém map_list");

        int[] headerTypes = {1, 2, 3, 4, 5, 6};
        long[] headerCounts = {h.stringIds, h.typeIds, h.protoIds,
            h.fieldIds, h.methodIds, h.classDefs};
        for (int i = 0; i < headerTypes.length; i++) {
            Item found = null;
            for (Item item : entries)
                if (item.type == headerTypes[i]) found = item;
            if (headerCounts[i] == 0 && found != null)
                throw new IOException("Mapa DEX contradiz seção vazia do cabeçalho");
            if (headerCounts[i] > 0
                    && (found == null || found.count != headerCounts[i]
                        || found.offset != h.sectionOffsets[i]))
                throw new IOException("Mapa DEX contradiz seção declarada no cabeçalho");
        }
        return new Result(h.version, h.mapOffset, entries);
    }

    private static void skipExactly(InputStream input, long bytes) throws IOException {
        byte[] buffer = new byte[BUFFER_BYTES];
        long remaining = bytes;
        while (remaining > 0) {
            checkInterrupted();
            int received = input.read(buffer, 0, (int) Math.min(buffer.length, remaining));
            if (received <= 0)
                throw new IOException("Mapa DEX truncado ou leitura sem progresso");
            remaining -= received;
        }
    }

    private static void readExactly(InputStream input, byte[] buffer, int length)
            throws IOException {
        int offset = 0;
        while (offset < length) {
            checkInterrupted();
            int received = input.read(buffer, offset, length - offset);
            if (received <= 0)
                throw new IOException("Mapa DEX truncado ou leitura sem progresso");
            offset += received;
        }
    }

    private static void checkInterrupted() throws InterruptedIOException {
        if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Leitura do mapa DEX cancelada");
    }

    private static long u32(byte[] bytes, int offset) {
        return ((long) bytes[offset] & 255)
            | (((long) bytes[offset + 1] & 255) << 8)
            | (((long) bytes[offset + 2] & 255) << 16)
            | (((long) bytes[offset + 3] & 255) << 24);
    }

    private static int u16(byte[] bytes, int offset) {
        return (bytes[offset] & 255) | ((bytes[offset + 1] & 255) << 8);
    }

    private static long fixedWidth(int type) {
        switch (type) {
            case 0x0000: return 112;
            case 0x0001: case 0x0002: case 0x0007: return 4;
            case 0x0003: return 12;
            case 0x0004: case 0x0005: case 0x0008: return 8;
            case 0x0006: return 32;
            default: return 0; // Variable-length sections: only offsets inspected.
        }
    }

    private static String label(int type) throws IOException {
        switch (type) {
            case 0x0000: return "header";
            case 0x0001: return "string_ids";
            case 0x0002: return "type_ids";
            case 0x0003: return "proto_ids";
            case 0x0004: return "field_ids";
            case 0x0005: return "method_ids";
            case 0x0006: return "class_defs";
            case 0x0007: return "call_site_ids";
            case 0x0008: return "method_handles";
            case 0x1000: return "map_list";
            case 0x1001: return "type_list";
            case 0x1002: return "annotation_set_ref_list";
            case 0x1003: return "annotation_set_item";
            case 0x2000: return "class_data_item";
            case 0x2001: return "code_item";
            case 0x2002: return "string_data_item";
            case 0x2003: return "debug_info_item";
            case 0x2004: return "annotation_item";
            case 0x2005: return "encoded_array_item";
            case 0x2006: return "annotations_directory_item";
            case 0xf000: return "hiddenapi_class_data";
            default: throw new IOException("Tipo de seção DEX não suportado");
        }
    }
}
