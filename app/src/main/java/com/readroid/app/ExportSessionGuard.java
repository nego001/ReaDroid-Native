package com.readroid.app;

import java.io.InterruptedIOException;
import java.util.concurrent.atomic.AtomicLong;

/**
 * F1.14. An export belongs to exactly one project/picker/activity generation.
 * Invalidation is thread-safe and can be observed by an active SAF worker.
 * A provider blocked inside its own read/write may only notice cancellation
 * when that call returns; a canceled export must never report success.
 */
final class ExportSessionGuard {
    private final AtomicLong version = new AtomicLong();

    Token begin() {
        return new Token(version, version.incrementAndGet());
    }

    void invalidate() {
        version.incrementAndGet();
    }

    static void check(Token token) throws InterruptedIOException {
        if (token != null) token.requireActive();
        else if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Operação interrompida");
    }

    static final class Token {
        private final AtomicLong version;
        private final long expected;

        private Token(AtomicLong version, long expected) {
            this.version = version;
            this.expected = expected;
        }

        boolean isActive() {
            return version.get() == expected;
        }

        void requireActive() throws InterruptedIOException {
            if (!isActive() || Thread.currentThread().isInterrupted())
                throw new InterruptedIOException(
                    "Exportação cancelada: projeto, tela ou sessão mudou");
        }
    }
}
