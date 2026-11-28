package com.readroid.app;

import java.io.File;

/**
 * F1.46: a completed encrypted checkpoint is NOT automatically a confirmed
 * recovery for an original that changed after RecoveryVault.save() returned.
 * Never claim rollback: the new checkpoint was already committed.
 */
final class RecoverySaveAcknowledgementGate {
    private RecoverySaveAcknowledgementGate() {}

    /** Must run on the worker, not the UI thread, after the save returns. */
    static void revalidate(RecoveryResumeGate.Proof preSaveProof,
            File originalSource, String acceptedSha256)
            throws RecoveryVault.PostCommitSourceException {
        try {
            RecoveryResumeGate.revalidate(preSaveProof, originalSource,
                acceptedSha256);
        } catch (Exception invalidSource) {
            throw new RecoveryVault.PostCommitSourceException(
                "Cópia criptografada já gravada, mas a identidade ou "
                    + "integridade do APK original mudou antes da confirmação. "
                    + "Reabra o APK original antes de recuperar as alterações.",
                invalidSource);
        }
    }
}
