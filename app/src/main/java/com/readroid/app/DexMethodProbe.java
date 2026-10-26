package com.readroid.app;

import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * M3.5 bounded preview of method_id_item (class_idx u16, proto_idx u16,
 * name_idx u32) and optional validated method names. DEX v035-v040 only.
 *
 * Method IDs include external references: these are NOT necessarily locally
 * implemented methods. This reader never touches code_item or executes code.
 */
final class DexMethodProbe {
    static final int MAX_METHODS = 8;
    static final int MAX_NAME_UTF16 = 128;
    static final long MAX_OFFSET = 16L * 1024 * 1024;
    static final long TOTAL_READ_BUDGET = 32L * 1024 * 1024;
    private static final int ITEM_BYTES = 8;
    private static final int SKIP_CHUNK = 16 * 1024;

    interface Source {
        InputStream open() throws IOException;
    }

    static final class Item {
        final int methodIndex;
        final int declaringTypeIdx;
        final int prototypeIdx;
        final long nameStringIdx;
        final String name;

        Item(int methodIndex, int declaringTypeIdx, int prototypeIdx,
                long nameStringIdx, String name) {
            this.methodIndex = methodIndex;
            this.declaringTypeIdx = declaringTypeIdx;
            this.prototypeIdx = prototypeIdx;
            this.nameStringIdx = nameStringIdx;
            this.name = name;
        }
    }

    static final class Result {
        final String version;
        final long totalMethodIds;
        final boolean truncated;
        final List<Item> methods;

        Result(String version, long totalMethodIds, List<Item> methods) {
            this.version = version;
            this.totalMethodIds = totalMethodIds;
            this.truncated = totalMethodIds > methods.size();
            this.methods = Collections.unmodifiableList(new ArrayList<>(methods));
        }
    }

    private static final class Budget {
        long consumed;
        void charge(long bytes) throws IOException {
            if (bytes < 0 || bytes > TOTAL_READ_BUDGET - consumed)
                throw new IOException("Orçamento cumulativo de leitura DEX excedido");
            consumed += bytes;
        }
    }

    private DexMethodProbe() {}

    static Result inspect(Source source, long fileBytes) throws IOException {
        if (source == null)
            throw new IOException("Origem DEX não encontrada");
        Budget budget = new Budget();
        DexHeaderProbe.Header header;
        List<long[]> ids = new ArrayList<>(MAX_METHODS);
        try (InputStream stream = requireStream(source)) {
            header = DexHeaderProbe.inspect(stream, fileBytes);
            budget.charge(DexHeaderProbe.HEADER_BYTES);
            if (header.methodIds == 0)
                return new Result(header.version, 0, Collections.emptyList());
            long methodOff = header.sectionOffsets[4];
            if (methodOff < DexHeaderProbe.HEADER_BYTES || methodOff > MAX_OFFSET
                    || methodOff > fileBytes - ITEM_BYTES)
                throw new IOException("Tabela method_ids fora do limite de leitura");
            skipExactly(stream, methodOff - DexHeaderProbe.HEADER_BYTES, budget);
            byte[] item = new byte[ITEM_BYTES];
            long prevClass = -1, prevName = -1, prevProto = -1;
            int preview = (int) Math.min(header.methodIds, MAX_METHODS);
            for (int i = 0; i < preview; i++) {
                readFully(stream, item, budget);
                int classIdx = u16(item, 0);
                int protoIdx = u16(item, 2);
                long nameIdx = u32(item, 4);
                if (classIdx >= header.typeIds || protoIdx >= header.protoIds
                        || nameIdx >= header.stringIds)
                    throw new IOException("Índice de método DEX fora das tabelas");
                // DEX method_ids are ordered by class, name, then prototype.
                if (classIdx < prevClass
                        || (classIdx == prevClass && nameIdx < prevName)
                        || (classIdx == prevClass && nameIdx == prevName
                            && protoIdx <= prevProto))
                    throw new IOException("Identificadores de métodos fora de ordem ou duplicados");
                ids.add(new long[]{classIdx, protoIdx, nameIdx});
                prevClass = classIdx;
                prevName = nameIdx;
                prevProto = protoIdx;
            }
        }
        List<Item> output = new ArrayList<>(ids.size());
        for (int i = 0; i < ids.size(); i++) {
            checkInterrupted();
            long[] row = ids.get(i);
            long stringIdAt = header.sectionOffsets[0] + row[2] * 4;
            long stringDataAt = uintAt(source, stringIdAt, fileBytes, budget);
            if (stringDataAt < header.dataOffset
                    || stringDataAt - header.dataOffset >= header.dataBytes)
                throw new IOException("Nome de método fora da região de dados DEX");
            String name = nameAt(source, stringDataAt, fileBytes, budget);
            output.add(new Item(i, (int) row[0], (int) row[1], row[2], name));
        }
        return new Result(header.version, header.methodIds, output);
    }

    private static long uintAt(Source source, long position, long size, Budget budget)
            throws IOException {
        if (position < DexHeaderProbe.HEADER_BYTES || position > size - 4
                || position > MAX_OFFSET)
            throw new IOException("Índice de string de método fora da cota");
        try (InputStream in = requireStream(source)) {
            skipExactly(in, position, budget);
            byte[] four = new byte[4];
            readFully(in, four, budget);
            return u32(four, 0);
        }
    }

    private static String nameAt(Source source, long position, long size,
            Budget budget) throws IOException {
        if (position < DexHeaderProbe.HEADER_BYTES || position >= size
                || position > MAX_OFFSET)
            throw new IOException("String de método fora da cota de leitura");
        try (InputStream in = requireStream(source)) {
            skipExactly(in, position, budget);
            int units = uleb128(in, budget);
            if (units < 1 || units > MAX_NAME_UTF16)
                throw new IOException("Nome de método excede o limite UTF-16");
            StringBuilder builder = new StringBuilder(units);
            for (int i = 0; i < units; i++) {
                int b0 = take(in, budget), unit;
                if (b0 == 0)
                    throw new IOException("Nome de método terminado antes do esperado");
                if (b0 < 128) {
                    unit = b0;
                } else if ((b0 & 0xe0) == 0xc0) {
                    int b1 = continuation(in, budget);
                    unit = ((b0 & 31) << 6) | b1;
                    if (unit < 128 && unit != 0)
                        throw new IOException("MUTF-8 não canônico");
                } else if ((b0 & 0xf0) == 0xe0) {
                    int b1 = continuation(in, budget), b2 = continuation(in, budget);
                    unit = ((b0 & 15) << 12) | (b1 << 6) | b2;
                    if (unit < 0x800)
                        throw new IOException("MUTF-8 excessivamente longo");
                } else {
                    throw new IOException("MUTF-8 inválido no nome de método");
                }
                builder.append((char) unit);
            }
            if (take(in, budget) != 0)
                throw new IOException("String de método sem terminador");
            String name = builder.toString();
            validateMemberName(name);
            return name;
        }
    }

    private static void validateMemberName(String name) throws IOException {
        if ("<init>".equals(name) || "<clinit>".equals(name)) return;
        if (name.isEmpty())
            throw new IOException("Nome de método vazio");
        for (int i = 0; i < name.length(); i++) {
            char ch = name.charAt(i);
            if (Character.isHighSurrogate(ch)) {
                if (i + 1 >= name.length()
                        || !Character.isLowSurrogate(name.charAt(i + 1)))
                    throw new IOException("Nome de método com surrogate isolado");
                int codePoint = Character.toCodePoint(ch, name.charAt(++i));
                if (!Character.isJavaIdentifierPart(codePoint))
                    throw new IOException("Identificador de método inválido");
            } else if (Character.isLowSurrogate(ch)
                    || (i == 0 ? !Character.isJavaIdentifierStart(ch)
                        : !Character.isJavaIdentifierPart(ch))) {
                throw new IOException("Identificador de método inválido");
            }
        }
    }

    private static int uleb128(InputStream in, Budget budget) throws IOException {
        int first = take(in, budget);
        if (first < 128) return first;
        int second = take(in, budget);
        if ((second & 128) != 0)
            throw new IOException("Comprimento de nome de método excessivo");
        int result = (first & 127) | (second << 7);
        if (result < 128) throw new IOException("ULEB128 não canônico");
        return result;
    }

    private static int continuation(InputStream in, Budget budget) throws IOException {
        int b = take(in, budget);
        if ((b & 0xc0) != 0x80)
            throw new IOException("MUTF-8 sem byte de continuação");
        return b & 63;
    }

    private static void skipExactly(InputStream in, long count, Budget budget)
            throws IOException {
        byte[] temp = new byte[SKIP_CHUNK];
        while (count > 0) {
            checkInterrupted();
            int n = in.read(temp, 0, (int) Math.min(count, temp.length));
            if (n <= 0)
                throw new IOException("Fluxo DEX truncado ou sem progresso");
            budget.charge(n);
            count -= n;
        }
    }

    private static void readFully(InputStream in, byte[] dest, Budget budget)
            throws IOException {
        int pos = 0;
        while (pos < dest.length) {
            checkInterrupted();
            int n = in.read(dest, pos, dest.length - pos);
            if (n <= 0)
                throw new IOException("Entrada method_id DEX truncada");
            budget.charge(n);
            pos += n;
        }
    }

    private static int take(InputStream in, Budget budget) throws IOException {
        checkInterrupted();
        int b = in.read();
        if (b < 0) throw new IOException("String DEX truncada");
        budget.charge(1);
        return b;
    }

    private static InputStream requireStream(Source src) throws IOException {
        InputStream stream = src.open();
        if (stream == null) throw new IOException("Fluxo DEX indisponível");
        return stream;
    }

    private static void checkInterrupted() throws InterruptedIOException {
        if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Leitura de métodos DEX cancelada");
    }

    private static int u16(byte[] bytes, int offset) {
        return (bytes[offset] & 255) | ((bytes[offset + 1] & 255) << 8);
    }

    private static long u32(byte[] bytes, int offset) {
        return ((long) bytes[offset] & 255)
            | (((long) bytes[offset + 1] & 255) << 8)
            | (((long) bytes[offset + 2] & 255) << 16)
            | (((long) bytes[offset + 3] & 255) << 24);
    }
}
