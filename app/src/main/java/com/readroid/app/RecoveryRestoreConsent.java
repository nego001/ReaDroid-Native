package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.util.Map;

/** Reauthenticate the current checkpoint after explicit user consent. */
final class RecoveryRestoreConsent {
    private RecoveryRestoreConsent() {}

    /**
     * Worker-only. A changed, deleted, or invalid checkpoint must not supply
     * an earlier authenticated plan. F1.51 also binds the offer to the
     * exact encrypted checkpoint, even if a new save contains identical edits.
     * UI request cancellation is checked separately.
     */
    static RecoveryVault.RestoreApplication reauthenticate(RecoveryVault vault, File source,
            Map<String, String> offered, RecoveryVault.DeletionProof checkpointAtOffer,
            ExportSessionGuard.Token token)
            throws Exception {
        token.requireActive();
        RecoveryVault.RestoreApplication application =
            vault.prepareRestoreApplication(source, checkpointAtOffer, token);
        Map<String, String> current = application.changes();
        token.requireActive();
        if (offered == null || offered.isEmpty() || !offered.equals(current))
            throw new IOException("A cópia de recuperação mudou. "
                + "Solicite a recuperação novamente.");
        return application;
    }
}
