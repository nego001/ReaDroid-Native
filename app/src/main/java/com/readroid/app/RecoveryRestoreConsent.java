package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/** Reauthenticate the current checkpoint after explicit user consent. */
final class RecoveryRestoreConsent {
    private RecoveryRestoreConsent() {}

    /**
     * Worker-only. A changed, deleted, or invalid checkpoint must not supply
     * an earlier authenticated plan. Equality is about the authorized content,
     * not the random GCM IV. UI request cancellation is checked separately.
     */
    static Map<String, String> reauthenticate(RecoveryVault vault, File source,
            Map<String, String> offered, ExportSessionGuard.Token token)
            throws Exception {
        token.requireActive();
        Map<String, String> current = vault.loadForSource(source);
        token.requireActive();
        if (offered == null || offered.isEmpty() || !offered.equals(current))
            throw new IOException("A cópia de recuperação mudou. "
                + "Solicite a recuperação novamente.");
        return Collections.unmodifiableMap(new LinkedHashMap<>(current));
    }
}
