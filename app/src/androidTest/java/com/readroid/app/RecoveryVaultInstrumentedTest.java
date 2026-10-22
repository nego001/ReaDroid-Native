package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.KeyStore;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

import static org.junit.Assert.*;

/**
 * Uses a unique test Keystore alias and directory per test, so running this
 * on a device never overwrites the user's production recovery checkpoint.
 */
@RunWith(AndroidJUnit4.class)
public final class RecoveryVaultInstrumentedTest {
    private static final class Fixture implements AutoCloseable {
        final File folder;
        final File original;
        final File other;
        final String alias;
        final RecoveryVault vault;

        Fixture() throws Exception {
            Context ctx = InstrumentationRegistry.getInstrumentation().getTargetContext();
            String id = UUID.randomUUID().toString();
            folder = new File(ctx.getFilesDir(), "v3_recovery_test_" + id);
            assertTrue(folder.mkdir());
            alias = "negrescodroid.instrumented.recovery." + id;
            vault = new RecoveryVault(folder, alias);
            original = new File(folder, "original.apk");
            other = new File(folder, "other.apk");
            Files.write(original.toPath(), "APK A for isolated recovery test"
                .getBytes(StandardCharsets.UTF_8));
            Files.write(other.toPath(), "APK B for isolated recovery test"
                .getBytes(StandardCharsets.UTF_8));
        }

        @Override public void close() throws Exception {
            vault.clear();
            Files.deleteIfExists(original.toPath());
            Files.deleteIfExists(other.toPath());
            Files.deleteIfExists(folder.toPath());
            KeyStore store = KeyStore.getInstance("AndroidKeyStore");
            store.load(null);
            if (store.containsAlias(alias)) store.deleteEntry(alias);
        }
    }

    private static Map<String, String> example() {
        Map<String, String> edits = new LinkedHashMap<>();
        edits.put("assets/settings.json", "{\"token\":\"private-local-test\"}");
        edits.put("assets/readme.txt", "Somente em memória");
        return edits;
    }

    @Test public void encryptedCheckpointCanBeRestoredAfterNewVaultInstance()
            throws Exception {
        try (Fixture f = new Fixture()) {
            byte[] original = Files.readAllBytes(f.original.toPath());
            Map<String, String> expected = example();
            f.vault.save(f.original, expected);
            assertTrue(f.vault.hasCheckpoint());
            byte[] encoded = Files.readAllBytes(
                new File(f.folder, "edit-plan-checkpoint.v1").toPath());
            assertFalse("Plaintext must not appear on disk",
                new String(encoded, StandardCharsets.ISO_8859_1)
                    .contains("private-local-test"));
            // A fresh object simulates a restarted process, not Activity recreation.
            RecoveryVault reopened = new RecoveryVault(f.folder, f.alias);
            assertEquals(expected, reopened.loadForSource(f.original));
            assertArrayEquals("Source file must be byte-for-byte unchanged",
                original, Files.readAllBytes(f.original.toPath()));
        }
    }

    @Test public void wrongApkIsRejectedWithoutChangingCheckpoint() throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            try {
                f.vault.loadForSource(f.other);
                fail("Cannot restore edits from another APK");
            } catch (SecurityException expected) {
                assertTrue(expected.getMessage().contains("outro APK"));
            }
            assertEquals(example(), f.vault.loadForSource(f.original));
        }
    }

    @Test public void modificationOfEncryptedBytesIsRejected() throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            File saved = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] ciphertext = Files.readAllBytes(saved.toPath());
            ciphertext[ciphertext.length - 1] ^= 1;
            Files.write(saved.toPath(), ciphertext);
            try {
                f.vault.loadForSource(f.original);
                fail("Tampered checkpoint passed AES-GCM authentication");
            } catch (javax.crypto.AEADBadTagException expected) {
                // Authenticated encryption must reject the payload before JSON parse.
            }
        }
    }

    @Test public void invalidAndOversizedPlansNeverOverwriteValidBackup()
            throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            Map<String, String> invalid = example();
            invalid.put("../escape.json", "bad");
            try {
                f.vault.save(f.original, invalid);
                fail("Unsafe path should not be checkpointed");
            } catch (IllegalArgumentException expected) {
                assertEquals(example(), f.vault.loadForSource(f.original));
            }
            Map<String, String> huge = new LinkedHashMap<>();
            for (int i = 0; i < 5; i++) {
                char[] text = new char[128000];
                Arrays.fill(text, 'x');
                huge.put("assets/oversize_" + i + ".txt", new String(text));
            }
            try {
                f.vault.save(f.original, huge);
                fail("Oversized plaintext must be refused");
            } catch (IllegalArgumentException expected) {
                assertEquals(example(), f.vault.loadForSource(f.original));
            }
        }
    }

    @Test public void malformedUnicodeDoesNotOverwriteEncryptedCheckpoint()
            throws Exception {
        try (Fixture f = new Fixture()) {
            Map<String, String> previous = example();
            f.vault.save(f.original, previous);
            File checkpoint = new File(f.folder, "edit-plan-checkpoint.v1");
            byte[] immutable = Files.readAllBytes(checkpoint.toPath());
            Map<String, String> invalid = example();
            invalid.put("assets/config.json", "abc" + (char) 0xD83D);
            try {
                f.vault.save(f.original, invalid);
                fail("Malformed UTF-16 must not replace valid ciphertext");
            } catch (IllegalArgumentException expected) {
                assertArrayEquals(immutable, Files.readAllBytes(checkpoint.toPath()));
                assertEquals(previous, f.vault.loadForSource(f.original));
            }
        }
    }

    @Test public void deletionRemovesCheckpointButNotOriginal() throws Exception {
        try (Fixture f = new Fixture()) {
            f.vault.save(f.original, example());
            f.vault.clear();
            assertFalse(f.vault.hasCheckpoint());
            assertTrue(f.original.isFile());
            try {
                f.vault.loadForSource(f.original);
                fail("Deleted backup must not be loadable");
            } catch (java.io.IOException expected) {
                assertFalse(f.vault.hasCheckpoint());
            }
        }
    }
}
