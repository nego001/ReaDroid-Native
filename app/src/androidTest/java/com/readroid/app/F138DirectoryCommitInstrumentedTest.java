package com.readroid.app;

import android.content.Context;
import android.system.ErrnoException;
import android.system.Os;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.IOException;
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
 * F1.38: pin a private vault DIRECTORY while a staged file is validated,
 * reject symlink/path rebinding, then sync the committed directory.
 * No physical-device kill, production Keystore or real user document.
 */
@RunWith(AndroidJUnit4.class)
public final class F138DirectoryCommitInstrumentedTest {
    private static final String ENTRY = "assets/f138-accepted.txt";
    private static final String A = "F138 accepted A";
    private static final String B = "F138 confirmed B";

    private static Map<String, String> edits(String value) {
        return Collections.singletonMap(ENTRY, value);
    }

    private static long inode(File path) throws IOException {
        try { return Os.lstat(path.getAbsolutePath()).st_ino; }
        catch (ErrnoException error) {
            throw new IOException("Could not identify test file inode", error);
        }
    }

    private static final class Fixture implements AutoCloseable {
        final File root, vaultDir, acceptedSource, checkpoint;
        final String alias;
        final RecoveryVault vault;
        final byte[] cipherA, sourceBytes;

        Fixture() throws Exception {
            Context ctx = InstrumentationRegistry.getInstrumentation()
                .getTargetContext();
            root = Files.createTempDirectory(ctx.getFilesDir().toPath(),
                "f138_dir_commit_").toFile();
            vaultDir = new File(root, "vault");
            acceptedSource = new File(root, "accepted.apk");
            sourceBytes = "F138 isolated source bytes".getBytes(
                StandardCharsets.UTF_8);
            Files.write(acceptedSource.toPath(), sourceBytes);
            alias = "negrescodroid.f138.instrumented." + UUID.randomUUID();
            vault = new RecoveryVault(vaultDir, alias);
            vault.save(acceptedSource, edits(A));
            checkpoint = new File(vaultDir, "edit-plan-checkpoint.v1");
            cipherA = Files.readAllBytes(checkpoint.toPath());
        }

        RecoveryVault duringPreMove(RecoveryVault.BeforeMove hook) {
            return new RecoveryVault(vaultDir, alias, stage -> {},
                RecoveryStorageBudget.forDirectory(vaultDir),
                (verified, total) -> {}, hook);
        }

        void checkA() throws Exception {
            assertArrayEquals("Previously committed ciphertext was modified",
                cipherA, Files.readAllBytes(checkpoint.toPath()));
            assertEquals(edits(A), vault.loadForSource(acceptedSource));
            assertArrayEquals(sourceBytes,
                Files.readAllBytes(acceptedSource.toPath()));
        }

        void deletePendingStages() throws Exception {
            File[] stages = vaultDir.listFiles((folder, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(stages);
            for (File stage : stages) {
                assertTrue("Delete only F138 test stage", stage.delete());
            }
        }

        @Override public void close() throws Exception {
            vault.clear();
            Files.deleteIfExists(acceptedSource.toPath());
            Files.deleteIfExists(vaultDir.toPath());
            Files.deleteIfExists(root.toPath());
            KeyStore keys = KeyStore.getInstance("AndroidKeyStore");
            keys.load(null);
            if (keys.containsAlias(alias)) keys.deleteEntry(alias);
        }
    }

    @Test public void f138RejectsSymlinkedVaultDirectoryBeforeStaging()
            throws Exception {
        try (Fixture f = new Fixture()) {
            File symlink = new File(f.root, "symlinked-vault");
            try {
                Files.createSymbolicLink(symlink.toPath(), f.vaultDir.toPath());
                RecoveryVault viaLink = new RecoveryVault(symlink, f.alias);
                try {
                    viaLink.save(f.acceptedSource, edits(B));
                    fail("Save through symlinked vault directory must be rejected");
                } catch (IOException expected) {
                    assertNotNull(expected.getMessage());
                }
                f.checkA();
            } finally {
                Files.deleteIfExists(symlink.toPath());
            }
        }
    }

    @Test public void f138DirectoryRebindingBeforeRenameIsRejected()
            throws Exception {
        try (Fixture f = new Fixture()) {
            File parked = new File(f.root, "parked-original-vault");
            final boolean[] swapped = {false};
            try {
                RecoveryVault save = f.duringPreMove(stage -> {
                    Files.move(f.vaultDir.toPath(), parked.toPath());
                    Files.createDirectory(f.vaultDir.toPath());
                    swapped[0] = true;
                });
                try {
                    save.save(f.acceptedSource, edits(B));
                    fail("A pathname rebound to a new vault directory must fail");
                } catch (IOException expected) {
                    assertTrue("Must detect changed private directory",
                        expected.getMessage() != null
                            && expected.getMessage().contains("Diretório privado alterado"));
                }
                assertTrue("Real directory swap hook was not reached", swapped[0]);
                assertFalse("Replacement directory may not receive a checkpoint",
                    new File(f.vaultDir, "edit-plan-checkpoint.v1").exists());
            } finally {
                if (swapped[0]) {
                    Files.deleteIfExists(f.vaultDir.toPath());
                    Files.move(parked.toPath(), f.vaultDir.toPath());
                    // Only the fixture's interrupted stage may remain after
                    // the original directory was restored.
                    f.deletePendingStages();
                }
            }
            f.checkA();
        }
    }

    @Test public void f138PinnedDirectoryDetectsRebindingIndependently()
            throws Exception {
        try (Fixture f = new Fixture()) {
            File parked = new File(f.root, "parked-held-directory");
            try (RecoveryDirectoryGuard guard =
                    RecoveryDirectoryGuard.open(f.vaultDir)) {
                guard.requireSameDirectory();
                Files.move(f.vaultDir.toPath(), parked.toPath());
                Files.createDirectory(f.vaultDir.toPath());
                try {
                    guard.requireSameDirectory();
                    fail("Pinned directory must reject a different inode");
                } catch (IOException expected) {
                    assertTrue(expected.getMessage().contains("Diretório privado alterado"));
                }
            } finally {
                Files.deleteIfExists(f.vaultDir.toPath());
                if (parked.exists()) Files.move(parked.toPath(), f.vaultDir.toPath());
            }
            f.checkA();
        }
    }

    @Test public void f138ValidAtomicMoveKeepsStageInodeAndDecrypts()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final long[] stageInode = {-1L};
            f.duringPreMove(stage -> {
                assertTrue(stage.isFile());
                stageInode[0] = inode(stage);
            }).save(f.acceptedSource, edits(B));
            assertTrue(stageInode[0] > 0);
            assertEquals("Promoted checkpoint must be exact same inode",
                stageInode[0], inode(f.checkpoint));
            assertEquals(edits(B), f.vault.loadForSource(f.acceptedSource));
            assertFalse("A completed save should use a new AES-GCM IV",
                Arrays.equals(f.cipherA,
                    Files.readAllBytes(f.checkpoint.toPath())));
            File[] stages = f.vaultDir.listFiles((directory, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(stages);
            assertEquals(0, stages.length);
        }
    }

    @Test public void f138DirectoryFdSyncSucceedsOnPrivateEmulatorStorage()
            throws Exception {
        try (Fixture f = new Fixture()) {
            try (RecoveryDirectoryGuard guard =
                    RecoveryDirectoryGuard.open(f.vaultDir)) {
                guard.requireSameDirectory();
                guard.syncAfterRename();
            }
            f.checkA();
        }
    }
}
