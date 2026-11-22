package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.KeyStore;
import java.util.Arrays;
import java.util.Collections;
import java.util.Map;
import java.util.UUID;

import static org.junit.Assert.*;

/** F1.39: explicit single-process post-rename fault boundary, Keystore real. */
@RunWith(AndroidJUnit4.class)
public final class F139PostMoveBoundaryInstrumentedTest {
    private static final String ENTRY = "assets/f139-boundary.txt";

    private static Map<String, String> edits(String revision) {
        return Collections.singletonMap(ENTRY, revision);
    }

    private static final class Fixture implements AutoCloseable {
        final File root, folder, source, checkpoint;
        final String alias;
        final RecoveryVault vault;
        final byte[] original, acceptedA;
        Fixture() throws Exception {
            Context context =
                InstrumentationRegistry.getInstrumentation().getTargetContext();
            root = Files.createTempDirectory(context.getFilesDir().toPath(),
                "f139_postmove_").toFile();
            folder = new File(root, "vault");
            source = new File(root, "source.apk");
            original = "F139 fixed original".getBytes(StandardCharsets.UTF_8);
            Files.write(source.toPath(), original);
            alias = "negrescodroid.f139.test." + UUID.randomUUID();
            vault = new RecoveryVault(folder, alias);
            vault.save(source, edits("accepted A"));
            checkpoint = new File(folder, "edit-plan-checkpoint.v1");
            acceptedA = Files.readAllBytes(checkpoint.toPath());
        }

        RecoveryVault withPostMove(RecoveryVault.AfterAtomicMove hook) {
            return new RecoveryVault(folder, alias,
                stage -> {}, RecoveryStorageBudget.forDirectory(folder),
                (verified, total) -> {}, stage -> {}, hook);
        }

        void assertNoStages() {
            File[] stages = folder.listFiles((d, name) ->
                name.startsWith("checkpoint-") && name.endsWith(".tmp"));
            assertNotNull(stages);
            assertEquals("Post-rename leaves no staged temp files", 0,
                stages.length);
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

    @Test public void f139PostMoveFailureCannotRollbackAlreadyPromotedB()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final boolean[] reached = {false};
            try {
                f.withPostMove(checkpoint -> {
                    reached[0] = true;
                    assertTrue("Post-rename checkpoint must exist",
                        checkpoint.isFile());
                    assertFalse("Prior revision was NOT replaced",
                        Arrays.equals(f.acceptedA,
                            Files.readAllBytes(checkpoint.toPath())));
                    f.assertNoStages();
                    throw new IOException("F139 intentional failure after rename");
                }).save(f.source, edits("promoted B"));
                fail("Injected post-move failure must be reported");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains(
                    "F139 intentional failure after rename"));
            }
            assertTrue("After-rename hook must actually execute", reached[0]);
            assertEquals("New committed plan B must decrypt",
                edits("promoted B"), f.vault.loadForSource(f.source));
            assertFalse(Arrays.equals(f.acceptedA,
                Files.readAllBytes(f.checkpoint.toPath())));
            assertArrayEquals(f.original, Files.readAllBytes(f.source.toPath()));
            f.assertNoStages();
            f.vault.save(f.source, edits("later C"));
            assertEquals(edits("later C"), f.vault.loadForSource(f.source));
        }
    }

    @Test public void f139NormalPostMoveBoundaryStillSyncsAndRecovers()
            throws Exception {
        try (Fixture f = new Fixture()) {
            final int[] calls = {0};
            f.withPostMove(checkpoint -> {
                calls[0]++;
                assertTrue(checkpoint.isFile());
                f.assertNoStages();
            }).save(f.source, edits("promoted B"));
            assertEquals(1, calls[0]);
            assertEquals(edits("promoted B"), f.vault.loadForSource(f.source));
            assertArrayEquals(f.original, Files.readAllBytes(f.source.toPath()));
            f.assertNoStages();
        }
    }
}
