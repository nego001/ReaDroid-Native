package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.util.Locale;

/**
 * F1.18: verify an imported private-cache APK before offering an encrypted
 * edit-plan recovery, and verify it again after the user's consent.
 *
 * Never stores APK bytes or plaintext edits. RecoveryVault authenticates its
 * own checkpoint and binds the edit plan to the same SHA-256 separately.
 * No implicit restore, deletion, APK signing, or SAF write occurs here.
 */
final class RecoveryResumeGate {
    static final long MAX_SOURCE_BYTES = 1024L * 1024 * 1024;

    private RecoveryResumeGate() {}

    static final class Proof {
        final File source;
        final String expectedSha256;
        final long length;

        private Proof(File source, String expectedSha256, long length) {
            this.source = source;
            this.expectedSha256 = expectedSha256;
            this.length = length;
        }
    }

    /** Both byte-level SHA-256 and fully inflated ZIP CRCs must be valid. */
    static Proof attest(File source, String reportedSha256) throws IOException {
        if (source == null || !source.isFile() || source.length() <= 0
                || source.length() > MAX_SOURCE_BYTES
                || reportedSha256 == null
                || !reportedSha256.matches("[0-9a-f]{64}"))
            throw new IOException("Origem da recuperação indisponível ou inválida");
        ExportSessionGuard.check(null);
        final File canonical = source.getCanonicalFile();
        final long length = source.length();
        ApkIntegrity.confirmExpected(source, reportedSha256);
        ApkZipIntegrity.verify(source);
        ApkIntegrity.confirmExpected(source, reportedSha256);
        ExportSessionGuard.check(null);
        if (source.length() != length || !source.isFile())
            throw new IOException("O APK mudou durante a verificação de recuperação");
        return new Proof(canonical, reportedSha256, length);
    }

    /** Run off UI after affirmative user consent, before editing the live plan. */
    static void revalidate(Proof proof, File currentSource, String reportedSha256)
            throws IOException {
        if (proof == null || currentSource == null
                || reportedSha256 == null
                || !proof.expectedSha256.equals(reportedSha256)
                || !proof.source.equals(currentSource.getCanonicalFile())
                || currentSource.length() != proof.length)
            throw new IOException("A origem ou o projeto da recuperação mudou");
        Proof current = attest(currentSource, reportedSha256);
        if (!current.source.equals(proof.source) || current.length != proof.length)
            throw new IOException("A origem da recuperação mudou durante a verificação");
    }
}
