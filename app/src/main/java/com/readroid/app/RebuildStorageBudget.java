package com.readroid.app;

import android.os.StatFs;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.io.OutputStream;

/**
 * F1.11: bounded, streaming disk-space guard for unsigned APK ZIP staging.
 *
 * Counts ACTUAL compressed bytes written to the private staging file,
 * including central-directory metadata. Does not hold ZIP contents in memory.
 * This is a best-effort quota in a shared filesystem: another process may
 * consume disk space between probes. Failure never authorizes publication.
 */
final class RebuildStorageBudget {
    static final long SAFETY_RESERVE = 64L * 1024 * 1024;
    static final long MAX_STAGED_BYTES = (2L * 1024 * 1024 * 1024) + SAFETY_RESERVE;
    static final long PROBE_INTERVAL = 8L * 1024 * 1024;

    interface FreeSpace {
        long availableBytes() throws IOException;
    }

    private RebuildStorageBudget() {}

    static FreeSpace forDirectory(File dir) {
        return () -> {
            if (dir == null || !dir.isDirectory())
                throw new IOException("Diretório de reconstrução indisponível");
            try {
                return new StatFs(dir.getAbsolutePath()).getAvailableBytes();
            } catch (IllegalArgumentException unavailable) {
                throw new IOException("Não foi possível consultar o espaço livre", unavailable);
            }
        };
    }

    static void preflight(FreeSpace space) throws IOException {
        checkSpace(space, SAFETY_RESERVE, 0);
    }

    static CheckedOutputStream open(File staged, FreeSpace space) throws IOException {
        if (staged == null || !staged.isFile())
            throw new IOException("Arquivo temporário de reconstrução indisponível");
        preflight(space);
        return new CheckedOutputStream(new FileOutputStream(staged), space,
            MAX_STAGED_BYTES, SAFETY_RESERVE, PROBE_INTERVAL);
    }

    private static void checkSpace(FreeSpace space, long reserve, long upcoming)
            throws IOException {
        if (space == null || reserve < 0 || upcoming < 0)
            throw new IOException("Orçamento de espaço inválido");
        if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Reconstrução interrompida");
        long free = space.availableBytes();
        // Subtract to avoid overflow if a provider claims absurdly high space.
        if (free < reserve || upcoming > free - reserve)
            throw new IOException("Espaço insuficiente: reconstrução exige "
                + "reserva livre de segurança");
    }

    static final class CheckedOutputStream extends OutputStream {
        private final OutputStream delegate;
        private final FreeSpace space;
        private final long maximum;
        private final long reserve;
        private final long interval;
        private final byte[] single = new byte[1];
        private long written;
        private long lastChecked;
        private boolean closed;

        CheckedOutputStream(OutputStream delegate, FreeSpace space,
                long maximum, long reserve, long interval) throws IOException {
            if (delegate == null || space == null || maximum < 1
                    || reserve < 0 || interval < 1)
                throw new IOException("Orçamento de reconstrução inválido");
            this.delegate = delegate;
            this.space = space;
            this.maximum = maximum;
            this.reserve = reserve;
            this.interval = interval;
            checkSpace(space, reserve, 0);
        }

        @Override public void write(int value) throws IOException {
            single[0] = (byte) value;
            write(single, 0, 1);
        }

        @Override public void write(byte[] bytes, int off, int len) throws IOException {
            if (bytes == null) throw new NullPointerException("bytes");
            if (off < 0 || len < 0 || off > bytes.length - len)
                throw new IndexOutOfBoundsException();
            if (closed) throw new IOException("Fluxo de reconstrução encerrado");
            if (Thread.currentThread().isInterrupted())
                throw new InterruptedIOException("Reconstrução interrompida");
            if (len == 0) return;
            if (written > maximum - len)
                throw new IOException("Cota máxima do ZIP temporário excedida");
            // Check before a write that crosses the interval. For small ZIPs,
            // the final check after close still ensures reserve was preserved.
            if (written + len - lastChecked >= interval) {
                checkSpace(space, reserve, len);
                lastChecked = written;
            }
            delegate.write(bytes, off, len);
            written += len;
        }

        @Override public void flush() throws IOException {
            if (closed) throw new IOException("Fluxo de reconstrução encerrado");
            delegate.flush();
        }

        @Override public void close() throws IOException {
            if (!closed) {
                closed = true;
                delegate.close();
            }
        }

        void verifyFinal() throws IOException {
            if (!closed)
                throw new IOException("ZIP temporário ainda está em gravação");
            checkSpace(space, reserve, 0);
        }

        long writtenBytes() { return written; }
    }
}
