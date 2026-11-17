package com.readroid.app;

import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * F1.23: independent bounded work lane for SAF imports.
 *
 * A broken DocumentsProvider may ignore interrupts while blocked in read().
 * Never let that occupy the Activity's single-thread lane for export,
 * recovery, preferences or history. Permit at most two active imports and
 * ONE waiting selection. When saturated, the latest queued selection
 * replaces the old pending (not-yet-started) selection.
 *
 * Tokens in MainActivity/ApkImportStaging provide cancellation between I/O
 * operations; this lane never assumes it can forcibly cancel provider calls.
 */
final class ImportWorkerLane {
    static final int MAX_RUNNING = 2;
    static final int MAX_PENDING = 1;

    private static final AtomicInteger THREAD_IDS = new AtomicInteger();
    private final ThreadPoolExecutor workers = new ThreadPoolExecutor(
        MAX_RUNNING, MAX_RUNNING, 0L, TimeUnit.MILLISECONDS,
        new ArrayBlockingQueue<>(MAX_PENDING),
        new ThreadFactory() {
            @Override public Thread newThread(Runnable work) {
                Thread thread = new Thread(work,
                    "ReaDroid-SAF-import-" + THREAD_IDS.incrementAndGet());
                // A permanently hung provider must not keep the process alive.
                // Process-lifetime cleanup remains best-effort.
                thread.setDaemon(true);
                return thread;
            }
        },
        (latest, pool) -> {
            if (pool.isShutdown())
                throw new RejectedExecutionException("Importações encerradas");
            // The UI invalidates the token of every older queued selection
            // before asking to enqueue the latest. Evict ONLY waiting work.
            pool.getQueue().poll();
            if (!pool.getQueue().offer(latest))
                throw new RejectedExecutionException("Fila SAF temporariamente ocupada");
        }
    );

    void execute(Runnable task) {
        if (task == null) throw new NullPointerException("import task");
        workers.execute(task);
    }

    int pendingCount() { return workers.getQueue().size(); }
    int activeCount() { return workers.getActiveCount(); }
    boolean isShutdown() { return workers.isShutdown(); }

    void shutdownNow() {
        workers.shutdownNow();
    }
}
