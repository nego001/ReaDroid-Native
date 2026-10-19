package com.readroid.app;

/**
 * A deterministic admission-policy prototype for the future multiplatform
 * CTA (Controle de Análise). This is NOT an AI model or a multi-GB file engine.
 *
 * Each operation is evaluated independently using capabilities advertised by
 * the device, content provider and the operation's implementation. No single
 * universal APK-size flag is used as permission to bypass existing limits.
 */
public final class AnalysisCapacityPolicy {
    private static final long MIB = 1024L * 1024L;
    private static final long SAFETY_RESERVE = 64L * MIB;
    private static final long MIN_STREAM_WORKING_SET = 16L * MIB;
    private static final long MIN_INDEX_WORKING_SET = 32L * MIB;

    public enum Operation {
        METADATA, SHA256_STREAM, ZIP_INDEX, MODIFY_AND_EXPORT
    }

    public enum Mode {
        METADATA_ONLY, STREAM_READ_ONLY, INDEXED_RANDOM_ACCESS,
        FULL_COPY_AND_EXPORT, BLOCKED
    }

    public static final class Capabilities {
        public final long declaredSizeBytes; // -1 means unknown / untrusted
        public final long freeCacheBytes;
        public final long freeDestinationBytes;
        public final long memoryBudgetBytes;
        public final long maxStreamingBytes; // backed by a real streaming engine
        public final long maxIndexedBytes; // backed by a real ZIP64/index engine
        public final long maxWritableBytes; // backed by a real patch/export engine
        public final boolean canRead;
        public final boolean seekable;
        public final boolean indexedEngineReady;
        public final boolean writingEngineReady;
        public final boolean userApprovedExpensiveOperation;

        public Capabilities(long declaredSizeBytes, long freeCacheBytes,
                long freeDestinationBytes, long memoryBudgetBytes,
                long maxStreamingBytes, long maxIndexedBytes, long maxWritableBytes,
                boolean canRead, boolean seekable, boolean indexedEngineReady,
                boolean writingEngineReady, boolean userApprovedExpensiveOperation) {
            this.declaredSizeBytes = declaredSizeBytes;
            this.freeCacheBytes = freeCacheBytes;
            this.freeDestinationBytes = freeDestinationBytes;
            this.memoryBudgetBytes = memoryBudgetBytes;
            this.maxStreamingBytes = maxStreamingBytes;
            this.maxIndexedBytes = maxIndexedBytes;
            this.maxWritableBytes = maxWritableBytes;
            this.canRead = canRead;
            this.seekable = seekable;
            this.indexedEngineReady = indexedEngineReady;
            this.writingEngineReady = writingEngineReady;
            this.userApprovedExpensiveOperation = userApprovedExpensiveOperation;
        }
    }

    public static final class Decision {
        public final Mode mode;
        public final boolean allowed;
        public final String reason;

        private Decision(Mode mode, boolean allowed, String reason) {
            this.mode = mode;
            this.allowed = allowed;
            this.reason = reason;
        }
    }

    private AnalysisCapacityPolicy() {}

    public static Decision decide(Operation operation, Capabilities capabilities) {
        if (operation == null || capabilities == null)
            throw new IllegalArgumentException("Operação ou capacidades ausentes");

        if (!capabilities.canRead)
            return result(Mode.BLOCKED, "A origem não oferece permissão de leitura.");
        if (capabilities.declaredSizeBytes < -1)
            return result(Mode.BLOCKED, "Metadados inválidos de tamanho.");
        if (operation == Operation.METADATA)
            return result(Mode.METADATA_ONLY, "Pré-inspeção de metadados permitida; sem copiar o arquivo.");

        if (capabilities.declaredSizeBytes == -1)
            return result(Mode.METADATA_ONLY,
                "Tamanho desconhecido: obter tamanho verificável ou realizar uma sondagem "
                + "limitada antes de autorizar análise maior.");
        if (!capabilities.userApprovedExpensiveOperation)
            return result(Mode.METADATA_ONLY,
                "Aguardando autorização do usuário para esta análise.");

        switch (operation) {
            case SHA256_STREAM:
                if (capabilities.memoryBudgetBytes < MIN_STREAM_WORKING_SET)
                    return result(Mode.METADATA_ONLY,
                        "Memória insuficiente para o orçamento de streaming.");
                if (capabilities.maxStreamingBytes < capabilities.declaredSizeBytes
                        || capabilities.maxStreamingBytes < 0)
                    return result(Mode.METADATA_ONLY,
                        "Motor de leitura em blocos não homologado para este tamanho.");
                return result(Mode.STREAM_READ_ONLY,
                    "Hash somente leitura em blocos, com progresso e cancelamento; "
                    + "não copia o arquivo completo.");

            case ZIP_INDEX:
                if (!capabilities.seekable || !capabilities.indexedEngineReady)
                    return result(Mode.METADATA_ONLY,
                        "Indexação requer acesso aleatório real e motor ZIP64 validado.");
                if (capabilities.memoryBudgetBytes < MIN_INDEX_WORKING_SET
                        || capabilities.freeCacheBytes < SAFETY_RESERVE)
                    return result(Mode.METADATA_ONLY,
                        "Memória ou armazenamento de índice insuficiente.");
                if (capabilities.maxIndexedBytes < capabilities.declaredSizeBytes
                        || capabilities.maxIndexedBytes < 0)
                    return result(Mode.METADATA_ONLY,
                        "Motor indexado não homologado para este tamanho.");
                return result(Mode.INDEXED_RANDOM_ACCESS,
                    "Navegação paginada pelo índice; não materializa todos os dados.");

            case MODIFY_AND_EXPORT:
                if (!capabilities.seekable || !capabilities.writingEngineReady)
                    return result(Mode.BLOCKED,
                        "Edição/reconstrução não suportada pelo motor ou origem.");
                if (capabilities.maxWritableBytes < capabilities.declaredSizeBytes
                        || capabilities.maxWritableBytes < 0)
                    return result(Mode.BLOCKED,
                        "Motor de reconstrução não homologado para este tamanho.");
                if (capabilities.memoryBudgetBytes < MIN_INDEX_WORKING_SET)
                    return result(Mode.BLOCKED, "Memória insuficiente para reconstrução.");
                // Conservative requirement: one source copy in private cache
                // AND one complete derived output on the destination volume.
                if (!hasHeadroom(capabilities.freeCacheBytes,
                        capabilities.declaredSizeBytes, SAFETY_RESERVE)
                    || !hasHeadroom(capabilities.freeDestinationBytes,
                        capabilities.declaredSizeBytes, SAFETY_RESERVE))
                    return result(Mode.BLOCKED,
                        "Falta espaço para a cópia segura e a saída separada.");
                return result(Mode.FULL_COPY_AND_EXPORT,
                    "Cópia e exportação somente com motor homologado; "
                    + "original intocado.");

            default:
                throw new IllegalArgumentException("Operação não reconhecida");
        }
    }

    static boolean hasHeadroom(long available, long bytes, long reserve) {
        return available >= 0 && bytes >= 0 && reserve >= 0
            && available >= reserve && bytes <= available - reserve;
    }

    private static Decision result(Mode mode, String reason) {
        return new Decision(mode,
            mode != Mode.METADATA_ONLY && mode != Mode.BLOCKED, reason);
    }
}
