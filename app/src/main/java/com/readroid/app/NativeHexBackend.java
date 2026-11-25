package com.readroid.app;

/** Debug opt-in, shadow parity migration. Java remains the trusted fallback. */
final class NativeHexBackend {
    interface Driver {
        int initialize();
        String format(byte[] bytes);
    }
    static final class Selection {
        final String dump;
        final boolean nativeUsed;
        Selection(String dump, boolean nativeUsed) {
            this.dump = dump;
            this.nativeUsed = nativeUsed;
        }
    }
    static final class Selector {
        private final Driver driver;
        private boolean ready;
        private boolean disabled;
        Selector(Driver driver) { this.driver = driver; }

        // One process-local decision; no retry loop on unavailable/mismatched ABI.
        // Calls serialized in this first migration to make the failure latch atomic.
        synchronized Selection select(byte[] bytes, String baseline, boolean enabled) {
            if (!enabled || disabled || Thread.currentThread().isInterrupted())
                return new Selection(baseline, false);
            try {
                if (!ready) {
                    if (driver.initialize() != 1) {
                        disabled = true;
                        return new Selection(baseline, false);
                    }
                    ready = true;
                }
                String candidate = driver.format(bytes);
                if (baseline.equals(candidate))
                    return new Selection(candidate, true);
                disabled = true;
            } catch (LinkageError | SecurityException | IllegalStateException | IllegalArgumentException failure) {
                disabled = true;
            }
            return new Selection(baseline, false);
        }
    }
    private static final Selector PROCESS = new Selector(new Driver() {
        public int initialize() {
            System.loadLibrary("negrodroid_hex");
            return NativeHexBridge.abiVersion();
        }
        public String format(byte[] bytes) {
            return NativeHexBridge.format(bytes, 0);
        }
    });
    private NativeHexBackend() {}
    static Selection select(byte[] bytes, String baseline, boolean enabled) {
        return PROCESS.select(bytes, baseline, enabled);
    }
}
