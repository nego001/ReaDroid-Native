package com.readroid.app;

import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * M3.4: resolves at most six class names from traditional DEX v035-v040.
 *
 * Reopens the already M2-admitted ZIP entry for sparse reads. No extraction,
 * bytecode execution or whole-DEX buffering. Rejects forged indexes, offsets,
 * malformed MUTF-8, non-class descriptors, and cumulative scan over-budget.
 *
 * A resolved descriptor proves only that sampled references are readable,
 * not that the whole DEX is well-formed or installable.
 */
final class DexClassNameProbe {
    static final int MAX_NAMES = 6;
    static final int MAX_UTF16_UNITS = 240;
    static final long MAX_SINGLE_OFFSET = 16L * 1024 * 1024;
    static final long MAX_TOTAL_STREAM_BYTES = 64L * 1024 * 1024;
    private static final int SKIP_BYTES = 16 * 1024;

    interface Source {
        InputStream open() throws IOException;
    }

    static final class Item {
        final long classTypeIdx;
        final String descriptor;
        final String name;

        Item(long classTypeIdx, String descriptor) {
            this.classTypeIdx = classTypeIdx;
            this.descriptor = descriptor;
            this.name = descriptor.substring(1, descriptor.length() - 1)
                .replace('/', '.');
        }
    }

    static final class Result {
        final long declaredClasses;
        final boolean truncated;
        final List<Item> items;

        Result(long total, List<Item> items) {
            declaredClasses = total;
            truncated = total > items.size();
            this.items = Collections.unmodifiableList(new ArrayList<>(items));
        }
    }

    private static final class Budget {
        long used;

        void charge(long amount) throws IOException {
            if (amount < 0 || amount > MAX_TOTAL_STREAM_BYTES - used)
                throw new IOException("Leitura de nomes DEX acima da cota");
            used += amount;
        }
    }

    private DexClassNameProbe() {}

    static Result inspect(Source source, long expectedBytes) throws IOException {
        if (source == null)
            throw new IOException("Origem de DEX ausente");
        DexClassDefProbe.Result classes;
        DexHeaderProbe.Header header;
        try (InputStream first = requireStream(source)) {
            classes = DexClassDefProbe.inspect(first, expectedBytes);
        }
        if (classes.items.isEmpty())
            return new Result(classes.declaredClasses, Collections.emptyList());
        try (InputStream second = requireStream(source)) {
            header = DexHeaderProbe.inspect(second, expectedBytes);
        }

        Budget budget = new Budget();
        List<Item> resolved = new ArrayList<>(MAX_NAMES);
        int limit = Math.min(classes.items.size(), MAX_NAMES);
        for (int i = 0; i < limit; i++) {
            checkInterrupted();
            long typeIdx = classes.items.get(i).classTypeIdx;
            long typeLocation = addOffset(header.sectionOffsets[1], typeIdx, 4);
            long descriptorStringIdx = readUintAt(source, typeLocation, expectedBytes, budget);
            if (descriptorStringIdx >= header.stringIds)
                throw new IOException("Tipo DEX referencia string fora da tabela");
            long stringLocation = addOffset(header.sectionOffsets[0],
                descriptorStringIdx, 4);
            long dataLocation = readUintAt(source, stringLocation, expectedBytes, budget);
            if (dataLocation < header.dataOffset
                    || dataLocation - header.dataOffset >= header.dataBytes)
                throw new IOException("Descritor DEX fora da área de dados");
            String descriptor = readDescriptorAt(source, dataLocation, expectedBytes, budget);
            resolved.add(new Item(typeIdx, descriptor));
        }
        return new Result(classes.declaredClasses, resolved);
    }

    private static InputStream requireStream(Source source) throws IOException {
        InputStream opened = source.open();
        if (opened == null)
            throw new IOException("Fluxo DEX indisponível");
        return opened;
    }

    private static long addOffset(long base, long index, long width)
            throws IOException {
        if (base < DexHeaderProbe.HEADER_BYTES || index < 0
                || index > (Long.MAX_VALUE - base) / width)
            throw new IOException("Índice DEX fora dos limites");
        return base + index * width;
    }

    private static long readUintAt(Source source, long at, long fileSize, Budget budget)
            throws IOException {
        if (at < DexHeaderProbe.HEADER_BYTES || at > fileSize - 4
                || at > MAX_SINGLE_OFFSET)
            throw new IOException("Tabela DEX fora da cota de leitura");
        try (InputStream stream = requireStream(source)) {
            skipTo(stream, at, budget);
            long value = 0;
            for (int i = 0; i < 4; i++)
                value |= (long) take(stream, budget) << (8 * i);
            return value;
        }
    }

    private static String readDescriptorAt(Source source, long at,
            long fileSize, Budget budget) throws IOException {
        if (at < DexHeaderProbe.HEADER_BYTES || at >= fileSize
                || at > MAX_SINGLE_OFFSET)
            throw new IOException("String DEX acima da cota de leitura");
        try (InputStream stream = requireStream(source)) {
            skipTo(stream, at, budget);
            int length = readUleb128(stream, budget);
            if (length < 3 || length > MAX_UTF16_UNITS)
                throw new IOException("Comprimento de descritor DEX não permitido");
            StringBuilder output = new StringBuilder(length);
            for (int i = 0; i < length; i++) {
                int first = take(stream, budget);
                if (first == 0)
                    throw new IOException("Descritor DEX terminou antes do tamanho declarado");
                int unit;
                if (first <= 0x7f) {
                    unit = first;
                } else if ((first & 0xe0) == 0xc0) {
                    int next = takeContinuation(stream, budget);
                    unit = ((first & 31) << 6) | next;
                    if (unit < 0x80 && unit != 0)
                        throw new IOException("MUTF-8 DEX com codificação não mínima");
                } else if ((first & 0xf0) == 0xe0) {
                    int b1 = takeContinuation(stream, budget);
                    int b2 = takeContinuation(stream, budget);
                    unit = ((first & 15) << 12) | (b1 << 6) | b2;
                    if (unit < 0x800)
                        throw new IOException("MUTF-8 DEX com codificação excessiva");
                } else {
                    throw new IOException("MUTF-8 DEX malformado");
                }
                output.append((char) unit);
            }
            if (take(stream, budget) != 0)
                throw new IOException("Descritor DEX sem terminador");
            String descriptor = output.toString();
            checkClassDescriptor(descriptor);
            return descriptor;
        }
    }

    private static int readUleb128(InputStream stream, Budget budget) throws IOException {
        long value = 0;
        for (int i = 0; i < 5; i++) {
            int next = take(stream, budget);
            value |= (long) (next & 127) << (7 * i);
            if ((next & 128) == 0) {
                if (value > MAX_UTF16_UNITS)
                    throw new IOException("String DEX excessivamente longa");
                return (int) value;
            }
        }
        throw new IOException("Comprimento ULEB128 inválido");
    }

    private static int takeContinuation(InputStream stream, Budget budget)
            throws IOException {
        int next = take(stream, budget);
        if ((next & 0xc0) != 0x80)
            throw new IOException("MUTF-8 DEX com byte de continuação inválido");
        return next & 63;
    }

    private static void checkClassDescriptor(String value) throws IOException {
        if (!value.startsWith("L") || !value.endsWith(";") || value.length() < 3)
            throw new IOException("Descritor DEX não representa classe");
        if (value.charAt(1) == '/' || value.charAt(value.length() - 2) == '/')
            throw new IOException("Descritor DEX com segmento vazio");
        for (int i = 1; i < value.length() - 1; i++) {
            char ch = value.charAt(i);
            if (ch <= 32 || ch == 127 || ch == '.' || ch == '['
                    || ch == ';' || ch == '\\' || ch == '<' || ch == '>'
                    || (ch == '/' && value.charAt(i - 1) == '/'))
                throw new IOException("Nome de classe DEX inseguro");
            if (Character.isHighSurrogate(ch)) {
                if (i + 1 >= value.length() - 1
                        || !Character.isLowSurrogate(value.charAt(i + 1)))
                    throw new IOException("Surrogate DEX incompleto");
                i++;
            } else if (Character.isLowSurrogate(ch)) {
                throw new IOException("Surrogate DEX isolado");
            }
        }
    }

    private static void skipTo(InputStream stream, long offset, Budget budget)
            throws IOException {
        byte[] buffer = new byte[SKIP_BYTES];
        long pending = offset;
        while (pending > 0) {
            checkInterrupted();
            int read = stream.read(buffer, 0, (int) Math.min(pending, buffer.length));
            if (read <= 0)
                throw new IOException("Fluxo DEX truncado ou sem progresso");
            budget.charge(read);
            pending -= read;
        }
    }

    private static int take(InputStream stream, Budget budget) throws IOException {
        checkInterrupted();
        int one = stream.read();
        if (one < 0)
            throw new IOException("String ou tabela DEX truncada");
        budget.charge(1);
        return one;
    }

    private static void checkInterrupted() throws InterruptedIOException {
        if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Leitura de nomes DEX cancelada");
    }
}
