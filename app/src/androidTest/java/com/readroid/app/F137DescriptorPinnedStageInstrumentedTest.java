package com.readroid.app;

import android.content.Context;
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
 * F1.37: a real open(O_NOFOLLOW) descriptor must be tied to the pathname's
 * inode across a streamed encrypted read. Aliases via hardlink are rejected.
 *
 * All paths, Keystore aliases, and source bytes are disposable app-private
 * CI fixtures; no physical-device kills or user-owned documents.
 */
@RunWith(AndroidJUnit4.class)
public final class F137DescriptorPinnedStageInstrumentedTest {
    private static final String ENTRY = "assets/f137.txt";
    private static final String ACCEPTED = "F137 accepted revision A";
    private static final String CANDIDATE = "F137 candidate revision B";

    private static String largeCandidate() {
        StringBuilder text = new StringBuilder(CANDIDATE);
        while (text.length() < 64000)
            text.append(" stage descriptor verification payload 0123456789");
        return text.toString();
    }

    private static Map<String, String> edits(String version) {
        return Collections.singletonMap(ENTRY, version);
    }

    private static long inode(File file) throws IOException {
        try {
            return Os.lstat(file.getAbsolutePath()).st_ino;
        } catch (android.system.ErrnoException invalid) {
            throw new IOException("Cannot stat isolated CI stage", invalid);
        }
    }

    private static final class Fixture implements AutoCloseable {
        final File root, vaultDir, source, acceptedCheckpoint;
        final File aliasFile;
        final String keyAlias;
        final RecoveryVault vault;
        final byte[] acceptedBytes, sourceBytes;

        Fixture() throws Exception {
            Context ctx = InstrumentationRegistry.getInstrumentation()
                .getTargetContext();
            root = Files.createTempDirectory(ctx.getFilesDir().toPath(),
                "f137_pinned_stage_").toFile();
            vaultDir = new File(root, "encrypted");
            source = new File(root, "accepted.apk");
            aliasFile = new File(root, "test_stage_alias.bin");
            sourceBytes = "F137 immutable source fixture".getBytes(
                StandardCharsets.UTF_8);
            Files.write(source.toPath(), sourceBytes);
            keyAlias = "negrescodroid.f137.instrumented." + UUID.randomUUID();
            vault = new RecoveryVault(vaultDir, keyAlias);
            vault.save(source, edits(ACCEPTED));
            acceptedCheckpoint = new File(vaultDir, "edit-plan-checkpoint.v1");
            acceptedBytes = Files.readAllBytes(acceptedCheckpoint.toPath());
        }

        RecoveryVault withStreamingMutation(RecoveryVault.StageReadObserver hook) {
            return new RecoveryVault(vaultDir, keyAlias,
                stage -> {}, RecoveryStorageBudget.forDirectory(vaultDir),
                hook);
        }

        RecoveryVault withPreMoveMutation(RecoveryVault.BeforeMove hook) {
            return new RecoveryVault(vaultDir, keyAlias,
                stage -> {}, RecoveryStorageBudget.forDirectory(vaultDir),
                (read, total) -> {}, hook);
        }

        void assertOldUntouched() throws Exception {
            assertArrayEquals("Old committed ciphertext unexpectedly replaced",
                acceptedBytes, Files.readAllBytes(acceptedCheckpoint.toPath()));
            assertEquals("Last accepted AES-GCM plan did not decrypt",
                edits(ACCEPTED), vault.loadForSource(source));
            assertArrayEquals("Original source changed",
                sourceBytes, Files.readAllBytes(source.toPath()));
            File[] stages = vaultDir.listFiles((dir, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(stages);
            assertEquals("Stage not removed after failed promotion", 0, stages.length);
        }

        @Override public void close() throws Exception {
            // A failed hardlink attack may leave a second *test-owned* link:
            // remove it before cleaning this isolated vault directory.
            Files.deleteIfExists(aliasFile.toPath());
            vault.clear();
            Files.deleteIfExists(source.toPath());
            Files.deleteIfExists(vaultDir.toPath());
            Files.deleteIfExists(root.toPath());
            KeyStore keys = KeyStore.getInstance("AndroidKeyStore");
            keys.load(null);
            if (keys.containsAlias(keyAlias)) keys.deleteEntry(keyAlias);
        }
    }

    private static void reject(Fixture f, RecoveryVault candidate)
            throws Exception {
        try {
            candidate.save(f.source, edits(largeCandidate()));
            fail("Untrusted stage alias/replacement should NOT commit");
        } catch (IOException expected) {
            assertNotNull("Stage rejection must explain the failure",
                expected.getMessage());
        }
        f.assertOldUntouched();
    }

    @Test public void f137SameBytesDifferentInodeDuringReadRejected()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] observed = {0};
            reject(f, f.withStreamingMutation((verified, total) -> {
                if (observed[0]++ != 0) return;
                assertTrue("Swap must occur while unread blocks remain",
                    total > 8192 && verified < total);
                File stage = lastPending(f.vaultDir);
                byte[] bytes = Files.readAllBytes(stage.toPath());
                long oldInode = inode(stage);
                Files.write(f.aliasFile.toPath(), bytes);
                assertNotEquals(oldInode, inode(f.aliasFile));
                Files.move(f.aliasFile.toPath(), stage.toPath(),
                    StandardCopyOption.REPLACE_EXISTING);
                assertArrayEquals(bytes, Files.readAllBytes(stage.toPath()));
            }));
            assertTrue("Streaming observer must fire", observed[0] > 0);
        }
    }

    @Test public void f137SymlinkReplacementDuringReadRejected()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] calls = {0};
            reject(f, f.withStreamingMutation((verified, total) -> {
                if (calls[0]++ != 0) return;
                assertTrue(verified < total);
                File stage = lastPending(f.vaultDir);
                byte[] bytes = Files.readAllBytes(stage.toPath());
                Files.write(f.aliasFile.toPath(), bytes);
                Files.delete(stage.toPath());
                Files.createSymbolicLink(stage.toPath(), f.aliasFile.toPath());
            }));
            assertTrue(calls[0] > 0);
        }
    }

    @Test public void f137HardlinkCreatedDuringReadRejected()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] calls = {0};
            reject(f, f.withStreamingMutation((verified, total) -> {
                if (calls[0]++ != 0) return;
                assertTrue(verified < total);
                File stage = lastPending(f.vaultDir);
                Files.createLink(f.aliasFile.toPath(), stage.toPath());
                assertEquals("A hardlink must preserve the inode",
                    inode(stage), inode(f.aliasFile));
            }));
            assertTrue(calls[0] > 0);
            assertTrue("Only disposable alias may remain after rejection",
                f.aliasFile.isFile());
        }
    }

    @Test public void f137HardlinkAfterFirstVerificationRejected()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] calls = {0};
            reject(f, f.withPreMoveMutation(stage -> {
                calls[0]++;
                Files.createLink(f.aliasFile.toPath(), stage.toPath());
            }));
            assertEquals(1, calls[0]);
            assertTrue(f.aliasFile.isFile());
        }
    }

    @Test public void f137HardlinkBeforeFirstVerificationRejected()
            throws Exception {
        try (Fixture f = new Fixture()) {
            RecoveryVault aliased = new RecoveryVault(f.vaultDir, f.keyAlias,
                stage -> Files.createLink(f.aliasFile.toPath(), stage.toPath()));
            reject(f, aliased);
            assertTrue(f.aliasFile.isFile());
        }
    }

    @Test public void f137UnaliasedStageStillCommitsAndDecrypts()
            throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.source, edits(CANDIDATE));
            assertEquals(edits(CANDIDATE), f.vault.loadForSource(f.source));
            assertFalse("New checkpoint must use a new IV",
                Arrays.equals(f.acceptedBytes,
                    Files.readAllBytes(f.acceptedCheckpoint.toPath())));
            File[] stages = f.vaultDir.listFiles((dir, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(stages);
            assertEquals(0, stages.length);
        }
    }

    /** Only discover the active test-owned *.tmp, never production paths. */
    private static File lastPending(File vault) throws IOException {
        File[] stages = vault.listFiles((dir, name) ->
            name.startsWith("checkpoint-") && name.endsWith(".tmp"));
        if (stages == null || stages.length != 1)
            throw new IOException("Expected one isolated F137 staging file");
        return stages[0];
    }
}
