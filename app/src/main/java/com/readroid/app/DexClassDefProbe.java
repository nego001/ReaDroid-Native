package com.readroid.app;

import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * M3.3, numeric class_def_item preview. All input is untrusted.
 * Reads at most 24 fixed-width class definitions after a bounded sequential
 * skip; never loads bytecode, class strings, or the complete DEX.
 * This is a metadata preview, NOT a complete DEX validation or decompiler.
 */
final class DexClassDefProbe {
    static final int MAX_PREVIEW_CLASSES = 24;
    static final long MAX_CLASS_TABLE_OFFSET = 16L * 1024 * 1024;
    private static final int CLASS_DEF_BYTES = 32;
    private static final int SKIP_CHUNK_BYTES = 16 * 1024;
    private static final long NO_INDEX = 0xffffffffL;

    private DexClassDefProbe() {}

    static final class Item {
        final long classTypeIdx;
        final long accessFlags;
        final long superclassTypeIdx;
        final long interfacesOff;
        final long sourceFileStringIdx;
        final long annotationsOff;
        final long classDataOff;
        final long staticValuesOff;

        Item(long classTypeIdx, long accessFlags, long superclassTypeIdx,
                long interfacesOff, long sourceFileStringIdx,
                long annotationsOff, long classDataOff, long staticValuesOff) {
            this.classTypeIdx = classTypeIdx;
            this.accessFlags = accessFlags;
            this.superclassTypeIdx = superclassTypeIdx;
            this.interfacesOff = interfacesOff;
            this.sourceFileStringIdx = sourceFileStringIdx;
            this.annotationsOff = annotationsOff;
            this.classDataOff = classDataOff;
            this.staticValuesOff = staticValuesOff;
        }
    }

    static final class Result {
        final String version;
        final long declaredClasses;
        final boolean previewTruncated;
        final List<Item> items;

        Result(String version, long declaredClasses, List<Item> items) {
            this.version = version;
            this.declaredClasses = declaredClasses;
            this.previewTruncated = declaredClasses > items.size();
            this.items = Collections.unmodifiableList(new ArrayList<>(items));
        }
    }

    static Result inspect(InputStream input, long expectedBytes) throws IOException {
        DexHeaderProbe.Header h = DexHeaderProbe.inspect(input, expectedBytes);
        if (h.classDefs == 0) return new Result(h.version, 0, Collections.emptyList());
        long offset = h.sectionOffsets[5];
        if (offset < DexHeaderProbe.HEADER_BYTES || offset > MAX_CLASS_TABLE_OFFSET)
            throw new IOException("Tabela de classes DEX fora do orçamento de leitura");
        skipExactly(input, offset - DexHeaderProbe.HEADER_BYTES);

        int sample = (int) Math.min(h.classDefs, MAX_PREVIEW_CLASSES);
        List<Item> classes = new ArrayList<>(sample);
        byte[] record = new byte[CLASS_DEF_BYTES];
        long previousClassType = -1;
        for (int i = 0; i < sample; i++) {
            readExactly(input, record);
            long type = u32(record, 0);
            long access = u32(record, 4);
            long superType = u32(record, 8);
            long interfaces = u32(record, 12);
            long sourceFile = u32(record, 16);
            long annotations = u32(record, 20);
            long data = u32(record, 24);
            long staticValues = u32(record, 28);
            if (type >= h.typeIds || type <= previousClassType)
                throw new IOException("Índices de classes DEX fora de ordem ou repetidos");
            if (superType != NO_INDEX && superType >= h.typeIds)
                throw new IOException("Superclasse DEX fora da tabela de tipos");
            if (sourceFile != NO_INDEX && sourceFile >= h.stringIds)
                throw new IOException("Arquivo-fonte DEX fora da tabela de strings");
            requireDataOffset("interfaces", interfaces, 4, h);
            requireDataOffset("annotations", annotations, 4, h);
            requireDataOffset("class_data", data, 1, h);
            requireDataOffset("static_values", staticValues, 1, h);
            classes.add(new Item(type, access, superType,
                interfaces, sourceFile, annotations, data, staticValues));
            previousClassType = type;
        }
        return new Result(h.version, h.classDefs, classes);
    }

    private static void requireDataOffset(String label, long at, int alignment,
            DexHeaderProbe.Header header) throws IOException {
        if (at == 0) return;
        // The header's data region was already checked against file_size.
        if (at < header.dataOffset || at - header.dataOffset >= header.dataBytes
                || (at % alignment) != 0)
            throw new IOException("Referência class_def DEX fora da região: " + label);
    }

    private static void skipExactly(InputStream input, long bytes) throws IOException {
        byte[] buffer = new byte[SKIP_CHUNK_BYTES];
        long pending = bytes;
        while (pending > 0) {
            checkInterrupted();
            int n = input.read(buffer, 0, (int) Math.min(pending, buffer.length));
            if (n <= 0) throw new IOException("Tabela class_def DEX truncada ou sem progresso");
            pending -= n;
        }
    }

    private static void readExactly(InputStream input, byte[] target) throws IOException {
        int filled = 0;
        while (filled < target.length) {
            checkInterrupted();
            int n = input.read(target, filled, target.length - filled);
            if (n <= 0) throw new IOException("Entrada class_def DEX truncada ou sem progresso");
            filled += n;
        }
    }

    private static void checkInterrupted() throws InterruptedIOException {
        if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Leitura de classes DEX cancelada");
    }

    private static long u32(byte[] b, int at) {
        return ((long) b[at] & 255)
            | (((long) b[at + 1] & 255) << 8)
            | (((long) b[at + 2] & 255) << 16)
            | (((long) b[at + 3] & 255) << 24);
    }
}
