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
 * F1.40: real Keystore and app-private storage. The post-fsync callback is
 * used only to inject faults after atomic promotion and directory sync.
 * No user files, production aliases, physical devices or installers.
 */
@RunWith(AndroidJUnit4.class)
public final class F140PostSyncIntegrityInstrumentedTest {
    private static final String ENTRY = "assets/f140-postsync.txt";
    private static Map<String, String> edits(String v) {
        return Collections.singletonMap(ENTRY, v);
    }

    private static final class Fixture implements AutoCloseable {
        final File root, folder, source, checkpoint;
        final RecoveryVault vault;
        final String alias;
        final byte[] sourceBytes, cipherA;

        Fixture() throws Exception {
            Context ctx = InstrumentationRegistry.getInstrumentation().getTargetContext();
            root = Files.createTempDirectory(ctx.getFilesDir().toPath(),
                "f140_synced_").toFile();
            folder = new File(root, "vault");
            source = new File(root, "original.apk");
            sourceBytes = "F140 immutable test source".getBytes(
                StandardCharsets.UTF_8);
            Files.write(source.toPath(), sourceBytes);
            alias = "negrescodroid.f140.instrumented." + UUID.randomUUID();
            vault = new RecoveryVault(folder, alias);
            vault.save(source, edits("A"));
            checkpoint = new File(folder, "edit-plan-checkpoint.v1");
            cipherA = Files.readAllBytes(checkpoint.toPath());
        }

        RecoveryVault injected(RecoveryVault.BeforeMove before,
                RecoveryVault.AfterDirectorySync after) {
            return new RecoveryVault(folder, alias,
                stage -> {}, RecoveryStorageBudget.forDirectory(folder),
                (read, total) -> {}, before, promoted -> {}, after);
        }

        void assertNoStages() {
            File[] stages = folder.listFiles((d, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(stages);
            assertEquals(0, stages.length);
        }

        void assertSourceUnchanged() throws Exception {
            assertArrayEquals(sourceBytes, Files.readAllBytes(source.toPath()));
        }

        @Override public void close() throws Exception {
            vault.clear();
            Files.deleteIfExists(source.toPath());
            Files.deleteIfExists(folder.toPath());
            Files.deleteIfExists(root.toPath());
            KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
            ks.load(null);
            if (ks.containsAlias(alias)) ks.deleteEntry(alias);
        }
    }

    private static long inode(File file) throws IOException {
        try { return Os.lstat(file.getAbsolutePath()).st_ino; }
        catch (ErrnoException e) {
            throw new IOException("F140 could not inspect fixture inode", e);
        }
    }

    @Test public void f140PostSyncExceptionLeavesNewCheckpointRecoverable()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] observed = {0};
            try {
                f.injected(stage -> {}, promoted -> {
                    observed[0]++;
                    assertTrue(promoted.isFile());
                    f.assertNoStages();
                    throw new IOException("F140 deliberate post-sync cancellation");
                }).save(f.source, edits("B"));
                fail("A post-sync IOException must still be surfaced");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains(
                    "F140 deliberate post-sync cancellation"));
            }
            assertEquals(1, observed[0]);
            assertEquals(edits("B"), f.vault.loadForSource(f.source));
            assertFalse(Arrays.equals(f.cipherA,
                Files.readAllBytes(f.checkpoint.toPath())));
            f.assertSourceUnchanged();
            f.assertNoStages();
        }
    }

    @Test public void f140PostSyncSameLengthBitFlipIsDetected()
            throws Exception {
        try (Fixture f = new Fixture()) {
            try {
                f.injected(stage -> {}, promoted -> {
                    byte[] data = Files.readAllBytes(promoted.toPath());
                    data[data.length / 2] ^= 0x23;
                    Files.write(promoted.toPath(), data);
                }).save(f.source, edits("B"));
                fail("Same-length post-sync ciphertext corruption must fail");
            } catch (IOException expected) {
                assertTrue("Must reject altered ciphertext after sync: " + expected,
                    expected.getMessage().contains("Conteúdo do estágio"));
            }
            assertFalse(Arrays.equals(f.cipherA,
                Files.readAllBytes(f.checkpoint.toPath())));
            assertNotEquals("Old ciphertext must NOT silently reappear",
                Arrays.toString(f.cipherA),
                Arrays.toString(Files.readAllBytes(f.checkpoint.toPath())));
            try {
                Map<String, String> recovered = f.vault.loadForSource(f.source);
                assertNotEquals("Corrupt AES-GCM must not yield plan B",
                    edits("B"), recovered);
            } catch (IOException | java.security.GeneralSecurityException expected) {
                // The Android Keystore may report AES-GCM tampering as a
                // cryptographic exception rather than an IOException.
            }
            f.assertSourceUnchanged();
            f.assertNoStages();
        }
    }

    @Test public void f140PostSyncDifferentInodeWithSameBytesIsRejected()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final long[] originalStage = {-1};
            try {
                f.injected(stage -> originalStage[0] = inode(stage),
                    promoted -> {
                        File impostor = new File(f.root, "same_ciphertext.bin");
                        byte[] data = Files.readAllBytes(promoted.toPath());
                        Files.write(impostor.toPath(), data);
                        assertNotEquals(inode(promoted), inode(impostor));
                        Files.move(impostor.toPath(), promoted.toPath(),
                            StandardCopyOption.REPLACE_EXISTING);
                    }).save(f.source, edits("B"));
                fail("Different inode with identical ciphertext must fail");
            } catch (IOException expected) {
                assertTrue("Must detect post-sync inode replacement",
                    expected.getMessage().contains(
                        "Identidade do checkpoint promovido divergiu"));
            }
            assertTrue(originalStage[0] > 0);
            assertNotEquals(originalStage[0], inode(f.checkpoint));
            assertEquals(edits("B"), f.vault.loadForSource(f.source));
            f.assertSourceUnchanged();
            f.assertNoStages();
        }
    }

    @Test public void f140NormalSyncedPromotionIsFullyAttested()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] calls = {0};
            final long[] sourceInode = {-1};
            f.injected(stage -> sourceInode[0] = inode(stage),
                promoted -> {
                    calls[0]++;
                    assertTrue(promoted.isFile());
                    assertEquals(sourceInode[0], inode(promoted));
                }).save(f.source, edits("B"));
            assertEquals(1, calls[0]);
            assertEquals(sourceInode[0], inode(f.checkpoint));
            assertEquals(edits("B"), f.vault.loadForSource(f.source));
            f.assertSourceUnchanged();
            f.assertNoStages();
        }
    }
}
