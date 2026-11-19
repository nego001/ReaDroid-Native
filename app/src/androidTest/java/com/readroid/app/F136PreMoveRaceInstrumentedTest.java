package com.readroid.app;

import android.content.Context;
import android.system.Os;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.KeyStore;
import java.util.Arrays;
import java.util.Collections;
import java.util.Map;
import java.util.UUID;
import static org.junit.Assert.*;

/**
 * F1.36: intervene AFTER the normal complete, fsynced ciphertext verification
 * but BEFORE its atomic move. The last accepted AES-GCM checkpoint must be
 * untouched even when the temporary's NAME is rebound to an identical file.
 *
 * This does not claim immunity from a hostile same-UID actor racing after the
 * final identity check, nor from power loss or filesystem hardware faults.
 */
@RunWith(AndroidJUnit4.class)
public final class F136PreMoveRaceInstrumentedTest {
    private static final String PATH = "assets/f136-confirmed.txt";
    private static final String ACCEPTED = "F136 accepted revision A";
    private static final String CANDIDATE = "F136 candidate revision B";
    private static Map<String, String> revision(String v) {
        return Collections.singletonMap(PATH, v);
    }
    private static long inode(File file) throws IOException {
        try {
            return Os.lstat(file.getAbsolutePath()).st_ino;
        } catch (android.system.ErrnoException lookupFailure) {
            throw new IOException("Unable to inspect isolated test inode",
                lookupFailure);
        }
    }
    private static final class Fixture implements AutoCloseable {
        final File root, vaultDir, source, checkpoint;
        final String alias;
        final RecoveryVault vault;
        final byte[] acceptedCiphertext, sourceBytes;
        Fixture() throws Exception {
            Context ctx = InstrumentationRegistry.getInstrumentation()
                .getTargetContext();
            root = Files.createTempDirectory(ctx.getFilesDir().toPath(),
                "f136_verified_premove_").toFile();
            vaultDir = new File(root, "vault");
            source = new File(root, "original.apk");
            sourceBytes = "F136 accepted source bytes".getBytes(StandardCharsets.UTF_8);
            Files.write(source.toPath(), sourceBytes);
            alias = "negrescodroid.f136.instrumented." + UUID.randomUUID();
            checkpoint = new File(vaultDir, "edit-plan-checkpoint.v1");
            vault = new RecoveryVault(vaultDir, alias);
            vault.save(source, revision(ACCEPTED));
            acceptedCiphertext = Files.readAllBytes(checkpoint.toPath());
        }
        RecoveryVault withPreMove(RecoveryVault.BeforeMove hook) {
            return new RecoveryVault(vaultDir, alias,
                stage -> {}, RecoveryStorageBudget.forDirectory(vaultDir),
                (verified, total) -> {}, hook);
        }
        void oldStillSafe() throws Exception {
            assertArrayEquals("Last committed ciphertext overwritten",
                acceptedCiphertext, Files.readAllBytes(checkpoint.toPath()));
            assertEquals("Last accepted edits must decrypt", revision(ACCEPTED),
                vault.loadForSource(source));
            assertArrayEquals("Original source changed", sourceBytes,
                Files.readAllBytes(source.toPath()));
            File[] temps = vaultDir.listFiles((d, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(temps);
            assertEquals("Rejected transaction left active staging behind",
                0, temps.length);
        }
        @Override public void close() throws Exception {
            vault.clear();
            Files.deleteIfExists(source.toPath());
            Files.deleteIfExists(vaultDir.toPath());
            Files.deleteIfExists(root.toPath());
            KeyStore keys = KeyStore.getInstance("AndroidKeyStore");
            keys.load(null);
            if (keys.containsAlias(alias)) keys.deleteEntry(alias);
        }
    }

    private static void reject(Fixture fixture, RecoveryVault.BeforeMove mutation)
            throws Exception {
        try {
            fixture.withPreMove(mutation).save(fixture.source, revision(CANDIDATE));
            fail("A modified pre-move stage must not be committed");
        } catch (IOException expected) {
            assertNotNull("Missing stage-failure diagnostics", expected.getMessage());
        }
        fixture.oldStillSafe();
    }

    @Test public void f136BitFlipBetweenVerifyAndMoveCannotCommit()
            throws Exception {
        try (Fixture f = new Fixture()) {
            reject(f, stage -> {
                byte[] bytes = Files.readAllBytes(stage.toPath());
                bytes[bytes.length / 2] ^= (byte) 0x5a;
                Files.write(stage.toPath(), bytes);
            });
        }
    }

    @Test public void f136TruncationBetweenVerifyAndMoveCannotCommit()
            throws Exception {
        try (Fixture f = new Fixture()) {
            reject(f, stage -> {
                byte[] bytes = Files.readAllBytes(stage.toPath());
                assertTrue(bytes.length > 33);
                Files.write(stage.toPath(), Arrays.copyOf(bytes, bytes.length - 1));
            });
        }
    }

    @Test public void f136DeletionBetweenVerifyAndMoveCannotCommit()
            throws Exception {
        try (Fixture f = new Fixture()) {
            reject(f, stage ->
                assertTrue("The pre-move stage should exist",
                    Files.deleteIfExists(stage.toPath())));
        }
    }

    @Test public void f136SameBytesNewInodeBetweenVerifyAndMoveRejected()
            throws Exception {
        try (Fixture f = new Fixture()) {
            reject(f, stage -> {
                File alternate = new File(f.root, "alternate.tmp");
                byte[] bytes = Files.readAllBytes(stage.toPath());
                long originalInode = inode(stage);
                Files.write(alternate.toPath(), bytes);
                long replacementInode = inode(alternate);
                assertNotEquals("Different files must have distinct inodes",
                    originalInode, replacementInode);
                Files.move(alternate.toPath(), stage.toPath(),
                    StandardCopyOption.REPLACE_EXISTING);
                assertArrayEquals("Bytes deliberately identical",
                    bytes, Files.readAllBytes(stage.toPath()));
            });
        }
    }

    @Test public void f136SymlinkSwapWithMatchingBytesBetweenVerifyAndMoveRejected()
            throws Exception {
        try (Fixture f = new Fixture()) {
            File alternate = new File(f.root, "matching-stage.bin");
            try {
                reject(f, stage -> {
                    byte[] bytes = Files.readAllBytes(stage.toPath());
                    Files.write(alternate.toPath(), bytes);
                    Files.delete(stage.toPath());
                    Files.createSymbolicLink(stage.toPath(), alternate.toPath());
                });
                assertTrue("Test-controlled symlink target must survive",
                    alternate.isFile());
            } finally {
                Files.deleteIfExists(alternate.toPath());
            }
        }
    }

    @Test public void f136InterruptedBeforeMovePreservesLastGoodCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault cancel = f.withPreMove(stage ->
                Thread.currentThread().interrupt());
            try {
                cancel.save(f.source, revision(CANDIDATE));
                fail("Interrupted thread must not commit");
            } catch (InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("interrompida"));
            } finally {
                Thread.interrupted();
            }
            f.oldStillSafe();
        }
    }

    @Test public void f136UnmodifiedStageStillAtomicallyReplacesCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] observed = {0};
            f.withPreMove(stage -> {
                assertTrue("Verified stage must be a regular file",
                    stage.isFile());
                observed[0]++;
            }).save(f.source, revision(CANDIDATE));
            assertEquals(1, observed[0]);
            assertEquals(revision(CANDIDATE), f.vault.loadForSource(f.source));
            assertFalse("A completed AES-GCM save must use a fresh IV",
                Arrays.equals(f.acceptedCiphertext,
                    Files.readAllBytes(f.checkpoint.toPath())));
            File[] temps = f.vaultDir.listFiles((d, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(temps);
            assertEquals(0, temps.length);
        }
    }
}
