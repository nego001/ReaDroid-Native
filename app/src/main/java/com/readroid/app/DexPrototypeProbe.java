package com.readroid.app;

import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * M3.6: read-only, bounded prototype signature preview for method_id entries.
 *
 * DEX proto_id_item: shorty_idx u32, return_type_idx u32, parameters_off u32.
 * The method_id table can include EXTERNAL references. No code_item is read,
 * no method implementation or APK installability is inferred.
 *
 * Run only on the M2-admitted APK copy; Source.open() reopens the same ZIP
 * entry, without extracting or buffering the complete DEX.
 */
final class DexPrototypeProbe {
    static final int MAX_METHODS = 4;
    static final int MAX_PARAMETERS = 8;
    static final int MAX_UTF16 = 240;
    static final long MAX_OFFSET = 16L * 1024 * 1024;
    static final long MAX_STREAMED_BYTES = 64L * 1024 * 1024;
    private static final int SKIP_CHUNK = 16 * 1024;

    interface Source {
        InputStream open() throws IOException;
    }

    static final class MethodSignature {
        final int methodIndex;
        final String methodName;
        final long prototypeIndex;
        final String returnType;
        final List<String> parameterTypes;
        final String descriptor;

        MethodSignature(int methodIndex, String methodName, long prototypeIndex,
                String returnType, List<String> parameterTypes) {
            this.methodIndex = methodIndex;
            this.methodName = methodName;
            this.prototypeIndex = prototypeIndex;
            this.returnType = returnType;
            this.parameterTypes = Collections.unmodifiableList(new ArrayList<>(parameterTypes));
            StringBuilder signature = new StringBuilder("(");
            for (String parameter : parameterTypes) signature.append(parameter);
            this.descriptor = signature.append(')').append(returnType).toString();
        }
    }

    static final class Result {
        final long totalMethodIds;
        final boolean truncated;
        final List<MethodSignature> signatures;

        Result(long totalMethodIds, List<MethodSignature> signatures) {
            this.totalMethodIds = totalMethodIds;
            this.truncated = totalMethodIds > signatures.size();
            this.signatures = Collections.unmodifiableList(new ArrayList<>(signatures));
        }
    }

    private static final class Budget {
        long used;
        void charge(long amount) throws IOException {
            if (amount < 0 || amount > MAX_STREAMED_BYTES - used)
                throw new IOException("Orçamento de leitura de protótipos DEX excedido");
            used += amount;
        }
    }

    private DexPrototypeProbe() {}

    static Result inspect(Source source, long fileSize) throws IOException {
        if (source == null) throw new IOException("Origem DEX indisponível");
        // M3.5 validates method_id ordering and method name strings.
        DexMethodProbe.Result methods = DexMethodProbe.inspect(source::open, fileSize);
        if (methods.methods.isEmpty())
            return new Result(methods.totalMethodIds, Collections.emptyList());
        DexHeaderProbe.Header h;
        try (InputStream in = open(source)) {
            h = DexHeaderProbe.inspect(in, fileSize);
        }
        Budget budget = new Budget();
        List<MethodSignature> output = new ArrayList<>(MAX_METHODS);
        int sample = Math.min(MAX_METHODS, methods.methods.size());
        for (int i = 0; i < sample; i++) {
            checkInterrupted();
            DexMethodProbe.Item method = methods.methods.get(i);
            long protoAt = h.sectionOffsets[2] + (long) method.prototypeIdx * 12;
            byte[] raw = readAt(source, protoAt, 12, fileSize, budget);
            long shortyIdx = u32(raw, 0);
            long returnIdx = u32(raw, 4);
            long parametersOff = u32(raw, 8);
            if (shortyIdx >= h.stringIds || returnIdx >= h.typeIds)
                throw new IOException("Protótipo DEX com índices fora do cabeçalho");

            List<String> parameters = new ArrayList<>(MAX_PARAMETERS);
            if (parametersOff != 0) {
                if ((parametersOff & 3) != 0 || parametersOff < h.dataOffset
                        || parametersOff - h.dataOffset >= h.dataBytes)
                    throw new IOException("Parâmetros de método fora da região DEX");
                byte[] prefix = readAt(source, parametersOff, 4, fileSize, budget);
                long count = u32(prefix, 0);
                if (count == 0 || count > MAX_PARAMETERS
                        || count > (fileSize - parametersOff - 4) / 2)
                    throw new IOException("Lista de parâmetros DEX excede a cota");
                byte[] list = readAt(source, parametersOff + 4,
                    (int) count * 2, fileSize, budget);
                for (int j = 0; j < (int) count; j++) {
                    int typeIdx = u16(list, j * 2);
                    if (typeIdx >= h.typeIds)
                        throw new IOException("Parâmetro DEX referencia tipo inválido");
                    parameters.add(resolveType(source, h, typeIdx, fileSize,
                        false, budget));
                }
            }

            String returns = resolveType(source, h, returnIdx, fileSize, true, budget);
            String shorty = resolveString(source, h, shortyIdx, fileSize, budget);
            if (shorty.length() != parameters.size() + 1
                    || shorty.charAt(0) != shortyChar(returns))
                throw new IOException("Assinatura curta DEX contradiz retorno/parâmetros");
            for (int j = 0; j < parameters.size(); j++)
                if (shorty.charAt(j + 1) != shortyChar(parameters.get(j)))
                    throw new IOException("Shorty DEX contradiz os tipos dos parâmetros");
            output.add(new MethodSignature(method.methodIndex, method.name,
                method.prototypeIdx, returns, parameters));
        }
        return new Result(methods.totalMethodIds, output);
    }

    private static String resolveType(Source source, DexHeaderProbe.Header h,
            long typeIdx, long fileSize, boolean allowVoid, Budget budget)
            throws IOException {
        if (typeIdx >= h.typeIds)
            throw new IOException("Índice de tipo do protótipo fora do limite");
        byte[] type = readAt(source, h.sectionOffsets[1] + typeIdx * 4,
            4, fileSize, budget);
        long stringIdx = u32(type, 0);
        if (stringIdx >= h.stringIds)
            throw new IOException("Descritor DEX aponta para string inexistente");
        String value = resolveString(source, h, stringIdx, fileSize, budget);
        validateTypeDescriptor(value, allowVoid);
        return value;
    }

    private static String resolveString(Source source, DexHeaderProbe.Header h,
            long stringIdx, long fileSize, Budget budget) throws IOException {
        if (stringIdx >= h.stringIds)
            throw new IOException("Índice de string DEX fora da tabela");
        byte[] pointer = readAt(source, h.sectionOffsets[0] + stringIdx * 4,
            4, fileSize, budget);
        long at = u32(pointer, 0);
        if (at < h.dataOffset || at - h.dataOffset >= h.dataBytes)
            throw new IOException("Texto de protótipo fora da região de dados");
        if (at < DexHeaderProbe.HEADER_BYTES || at > MAX_OFFSET)
            throw new IOException("Texto de protótipo além da cota");
        try (InputStream in = open(source)) {
            skipExactly(in, at, budget);
            int utf16Length = readLength(in, budget);
            if (utf16Length < 1 || utf16Length > MAX_UTF16)
                throw new IOException("String do protótipo muito grande");
            StringBuilder result = new StringBuilder(utf16Length);
            for (int i = 0; i < utf16Length; i++) {
                int b0 = take(in, budget);
                if (b0 == 0) throw new IOException("String DEX terminada antes do previsto");
                int unit;
                if (b0 < 128) {
                    unit = b0;
                } else if ((b0 & 0xe0) == 0xc0) {
                    unit = ((b0 & 31) << 6) | continuation(in, budget);
                    if (unit < 128 && unit != 0)
                        throw new IOException("MUTF-8 DEX não canônico");
                } else if ((b0 & 0xf0) == 0xe0) {
                    unit = ((b0 & 15) << 12)
                        | (continuation(in, budget) << 6) | continuation(in, budget);
                    if (unit < 0x800)
                        throw new IOException("MUTF-8 DEX excessivamente longo");
                } else {
                    throw new IOException("MUTF-8 inválido no protótipo");
                }
                result.append((char) unit);
            }
            if (take(in, budget) != 0)
                throw new IOException("String de protótipo sem terminador");
            return result.toString();
        }
    }

    private static void validateTypeDescriptor(String value, boolean allowVoid)
            throws IOException {
        int start = 0;
        while (start < value.length() && value.charAt(start) == '[') start++;
        if (start > 8 || start >= value.length())
            throw new IOException("Dimensões do tipo DEX inválidas");
        if (value.length() == start + 1) {
            char type = value.charAt(start);
            if ("ZBSCIJFD".indexOf(type) >= 0) return;
            if (allowVoid && start == 0 && type == 'V') return;
            throw new IOException("Tipo primitivo ou void DEX inválido");
        }
        if (value.charAt(start) != 'L' || !value.endsWith(";")
                || value.length() < start + 3)
            throw new IOException("Descritor de objeto DEX inválido");
        if (value.charAt(start + 1) == '/'
                || value.charAt(value.length() - 2) == '/')
            throw new IOException("Segmento de tipo DEX vazio");
        for (int i = start + 1; i < value.length() - 1; i++) {
            char ch = value.charAt(i);
            if (ch <= 32 || ch == 127 || ch == '.' || ch == '['
                    || ch == ';' || ch == '\\' || ch == '<' || ch == '>'
                    || (ch == '/' && value.charAt(i - 1) == '/'))
                throw new IOException("Nome de tipo DEX inválido");
            if (Character.isHighSurrogate(ch)) {
                if (i + 1 >= value.length() - 1
                        || !Character.isLowSurrogate(value.charAt(i + 1)))
                    throw new IOException("Tipo DEX com surrogate incompleto");
                i++;
            } else if (Character.isLowSurrogate(ch)) {
                throw new IOException("Tipo DEX com surrogate isolado");
            }
        }
    }

    private static char shortyChar(String descriptor) {
        char start = descriptor.charAt(0);
        return start == 'L' || start == '[' ? 'L' : start;
    }

    private static int readLength(InputStream in, Budget budget) throws IOException {
        long value = 0;
        for (int i = 0; i < 5; i++) {
            int b = take(in, budget);
            value |= (long) (b & 127) << (7 * i);
            if ((b & 128) == 0) {
                if (value > MAX_UTF16) throw new IOException("ULEB128 excessivo");
                return (int) value;
            }
        }
        throw new IOException("ULEB128 malformado");
    }

    private static int continuation(InputStream in, Budget budget) throws IOException {
        int b = take(in, budget);
        if ((b & 0xc0) != 0x80)
            throw new IOException("Byte de continuação MUTF-8 inválido");
        return b & 63;
    }

    private static byte[] readAt(Source source, long position, int count,
            long fileSize, Budget budget) throws IOException {
        if (count <= 0 || position < DexHeaderProbe.HEADER_BYTES
                || position > MAX_OFFSET || position > fileSize - count)
            throw new IOException("Seção do protótipo DEX fora do limite de leitura");
        try (InputStream in = open(source)) {
            skipExactly(in, position, budget);
            byte[] value = new byte[count];
            readExactly(in, value, budget);
            return value;
        }
    }

    private static InputStream open(Source source) throws IOException {
        InputStream in = source.open();
        if (in == null) throw new IOException("Fluxo DEX indisponível");
        return in;
    }

    private static void skipExactly(InputStream in, long count, Budget budget)
            throws IOException {
        byte[] buffer = new byte[SKIP_CHUNK];
        while (count > 0) {
            checkInterrupted();
            int n = in.read(buffer, 0, (int) Math.min(count, buffer.length));
            if (n <= 0)
                throw new IOException("Fluxo de protótipo DEX truncado ou sem progresso");
            budget.charge(n);
            count -= n;
        }
    }

    private static void readExactly(InputStream in, byte[] target, Budget budget)
            throws IOException {
        int offset = 0;
        while (offset < target.length) {
            checkInterrupted();
            int n = in.read(target, offset, target.length - offset);
            if (n <= 0) throw new IOException("Registro de protótipo DEX truncado");
            budget.charge(n);
            offset += n;
        }
    }

    private static int take(InputStream in, Budget budget) throws IOException {
        checkInterrupted();
        int b = in.read();
        if (b < 0) throw new IOException("String de protótipo DEX truncada");
        budget.charge(1);
        return b;
    }

    private static void checkInterrupted() throws InterruptedIOException {
        if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Leitura de protótipos DEX cancelada");
    }

    private static long u32(byte[] b, int p) {
        return ((long) b[p] & 255) | (((long) b[p+1] & 255) << 8)
            | (((long) b[p+2] & 255) << 16) | (((long) b[p+3] & 255) << 24);
    }

    private static int u16(byte[] b, int p) {
        return (b[p] & 255) | ((b[p+1] & 255) << 8);
    }
}
