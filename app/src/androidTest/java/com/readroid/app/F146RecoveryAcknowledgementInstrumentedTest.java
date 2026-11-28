package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.KeyStore;
import java.util.Arrays;
import java.util.Collections;
import java.util.Map;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import static org.junit.Assert.*;

/**
 * F1.46: after RecoveryVault.save() has fully returned, validate the
 * accepted ZIP source before acknowledging a committed recovery.
 * Real Android Keystore in isolated per-test app-private storage.
 */
@RunWith(AndroidJUnit4.class)
public final class F146RecoveryAcknowledgementInstrumentedTest {
    private static final String ENTRY = "assets/f146-original.txt";
    private static Map<String, String> edits(char c) {
        return Collections.singletonMap(ENTRY, "F146:" + c);
    }

    private static byte[] fixtureZip() throws Exception {
        ByteArrayOutputStream result = new ByteArrayOutputStream();
        try (ZipOutputStream output = new ZipOutputStream(result)) {
            output.putNextEntry(new ZipEntry("AndroidManifest.xml"));
            output.write("F146 disposable manifest".getBytes(StandardCharsets.UTF_8));
            output.closeEntry();
            output.putNextEntry(new ZipEntry(ENTRY));
            output.write("F146 immutable original".getBytes(StandardCharsets.UTF_8));
            output.closeEntry();
        }
        return result.toByteArray();
    }

    private static final class Fixture implements AutoCloseable {
        final File root, folder, source, checkpoint;
        final String alias, expectedSha;
        final RecoveryVault vault;
        final RecoveryResumeGate.Proof proof;
        final byte[] sourceBytes, cipherA;

        Fixture() throws Exception {
            Context context = InstrumentationRegistry.getInstrumentation()
                .getTargetContext();
            root = Files.createTempDirectory(context.getFilesDir().toPath(),
                "f146_ack_").toFile();
            folder = new File(root, "vault");
            source = new File(root, "source.apk");
            sourceBytes = fixtureZip();
            Files.write(source.toPath(), sourceBytes);
            expectedSha = ApkIntegrity.sha256(source);
            proof = RecoveryResumeGate.attest(source, expectedSha);
            alias = "negrescodroid.f146.test." + UUID.randomUUID();
            vault = new RecoveryVault(folder, alias);
            vault.save(source, edits('A'));
            checkpoint = new File(folder, "edit-plan-checkpoint.v1");
            cipherA = Files.readAllBytes(checkpoint.toPath());
        }

        void commitB() throws Exception {
            vault.save(source, edits('B'), new ExportSessionGuard().begin(),
                expectedSha);
            assertFalse("B must be promoted before acknowledgement",
                Arrays.equals(cipherA, Files.readAllBytes(checkpoint.toPath())));
        }

        void assertBRecoveredAfterSourceRestored() throws Exception {
            assertArrayEquals(sourceBytes, Files.readAllBytes(source.toPath()));
            assertEquals(edits('B'), vault.loadForSource(source));
            File[] temporary = folder.listFiles((dir, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(temporary);
            assertEquals(0, temporary.length);
        }

        @Override public void close() throws Exception {
            vault.clear();
            Files.deleteIfExists(source.toPath());
            Files.deleteIfExists(folder.toPath());
            Files.deleteIfExists(root.toPath());
            KeyStore keys = KeyStore.getInstance("AndroidKeyStore");
            keys.load(null);
            if (keys.containsAlias(alias)) keys.deleteEntry(alias);
        }
    }

    @Test public void f146SourceChangedAfterSaveBeforeNoticeRejectsAck()
            throws Exception {
        try (Fixture f = new Fixture()) {
            f.commitB();
            try {
                byte[] tampered = f.sourceBytes.clone();
                tampered[tampered.length - 1] ^= 1;
                Files.write(f.source.toPath(), tampered);
                try {
                    RecoverySaveAcknowledgementGate.revalidate(
                        f.proof, f.source, f.expectedSha);
                    fail("Changed source must not produce normal success notification");
                } catch (RecoveryVault.PostCommitSourceException expected) {
                    assertTrue(expected.getMessage().contains("já gravada"));
                }
            } finally {
                Files.write(f.source.toPath(), f.sourceBytes);
            }
            f.assertBRecoveredAfterSourceRestored();
        }
    }

    @Test public void f146SourceRemovedAfterSaveBeforeNoticeRejectsAck()
            throws Exception {
        try (Fixture f = new Fixture()) {
            f.commitB();
            try {
                Files.delete(f.source.toPath());
                try {
                    RecoverySaveAcknowledgementGate.revalidate(
                        f.proof, f.source, f.expectedSha);
                    fail("Vanished source cannot be attested to caller");
                } catch (RecoveryVault.PostCommitSourceException expected) {
                    assertTrue(expected.getMessage().contains("já gravada"));
                }
            } finally {
                Files.write(f.source.toPath(), f.sourceBytes);
            }
            f.assertBRecoveredAfterSourceRestored();
        }
    }

    @Test public void f146ReboundProofAfterSaveRejectsAck() throws Exception {
        try (Fixture f = new Fixture()) {
            File other = new File(f.root, "other.apk");
            Files.write(other.toPath(), f.sourceBytes);
            try {
                RecoveryResumeGate.Proof alien =
                    RecoveryResumeGate.attest(other, f.expectedSha);
                f.commitB();
                try {
                    RecoverySaveAcknowledgementGate.revalidate(
                        alien, f.source, f.expectedSha);
                    fail("Another cached path cannot supply the proof");
                } catch (RecoveryVault.PostCommitSourceException expected) {
                    assertTrue(expected.getMessage().contains("já gravada"));
                }
                f.assertBRecoveredAfterSourceRestored();
            } finally {
                Files.deleteIfExists(other.toPath());
            }
        }
    }

    @Test public void f146StableSourceConfirmsCommittedCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            f.commitB();
            RecoverySaveAcknowledgementGate.revalidate(
                f.proof, f.source, f.expectedSha);
            f.assertBRecoveredAfterSourceRestored();
        }
    }
}
