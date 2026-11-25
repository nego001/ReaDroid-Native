package com.readroid.app;

import java.io.InterruptedIOException;
import java.util.concurrent.Semaphore;
import java.util.concurrent.atomic.AtomicBoolean;

/** Single-use, owner-thread scope; no persistent JNI handles or stored file bytes. */
final class NativeHexSession implements AutoCloseable {
    interface Backend {
        NativeHexBackend.Selection select(byte[] bytes, String baseline, boolean enabled);
    }
    static final class Manager {
        private final Semaphore slots;
        private final Backend backend;
        Manager(int capacity, Backend backend) {
            if (capacity < 1 || capacity > 4 || backend == null)
                throw new IllegalArgumentException("invalid native session configuration");
            this.slots = new Semaphore(capacity);
            this.backend = backend;
        }
        NativeHexSession open() { return new NativeHexSession(this); }
    }
    private static final Manager PROCESS = new Manager(4, NativeHexBackend::select);
    static NativeHexSession open() { return PROCESS.open(); }

    private final Manager manager;
    private final Thread owner = Thread.currentThread();
    private final AtomicBoolean cancelled = new AtomicBoolean();
    private boolean used;
    private boolean closed;
    private NativeHexSession(Manager manager) { this.manager = manager; }

    /** May be called from another thread. Does not forcibly terminate native code. */
    void cancel() { cancelled.set(true); }
    private void requireOwner() {
        if (Thread.currentThread() != owner)
            throw new IllegalStateException("native session owner mismatch");
    }
    private void checkCancellation() throws InterruptedIOException {
        if (cancelled.get() || Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Prévia interrompida");
    }
    NativeHexBackend.Selection format(byte[] bytes, String baseline, boolean enabled)
            throws InterruptedIOException {
        requireOwner();
        if (closed || used) throw new IllegalStateException("native session already consumed");
        used = true;
        if (bytes == null || bytes.length > 4096 || baseline == null || baseline.length() > 22017)
            throw new IllegalArgumentException("invalid hex window");
        checkCancellation();
        // Saturation never blocks a caller waiting for an admission slot.
        if (!enabled || !manager.slots.tryAcquire()) {
            checkCancellation();
            return new NativeHexBackend.Selection(baseline, false);
        }
        try {
            checkCancellation();
            NativeHexBackend.Selection result = manager.backend.select(bytes, baseline, true);
            checkCancellation();
            return result;
        } finally {
            // Release only after the call exits, even if cancelled in flight.
            manager.slots.release();
        }
    }
    @Override public void close() {
        requireOwner();
        closed = true;
        cancelled.set(true);
    }
}
