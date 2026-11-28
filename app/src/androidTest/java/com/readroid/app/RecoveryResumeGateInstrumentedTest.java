package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class RecoveryResumeGateInstrumentedTest {
    private File apk() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File source = File.createTempFile("f118_resume_", ".apk", context.getCacheDir());
        try (ZipOutputStream out = new ZipOutputStream(Files.newOutputStream(source.toPath()))) {
            ZipEntry manifest = new ZipEntry("AndroidManifest.xml");
            out.putNextEntry(manifest);
            out.write("manifest".getBytes(StandardCharsets.UTF_8));
            out.closeEntry();
            ZipEntry dex = new ZipEntry("classes.dex");
            out.putNextEntry(dex);
            out.write(new byte[]{100, 101, 120, 10, 0, 0, 0});
            out.closeEntry();
            ZipEntry data = new ZipEntry("assets/config.json");
            out.putNextEntry(data);
            out.write("{\"safe\":true}".getBytes(StandardCharsets.UTF_8));
            out.closeEntry();
        }
        return source;
    }

    @Test public void matchingValidSourceCanBeAttestedAndRevalidated()
            throws Exception {
        File source = apk();
        try {
            byte[] original = Files.readAllBytes(source.toPath());
            String hash = ApkIntegrity.sha256(source);
            RecoveryResumeGate.Proof proof = RecoveryResumeGate.attest(source, hash);
            RecoveryResumeGate.revalidate(proof, source, hash);
            assertEquals(source.length(), proof.length);
            assertEquals(hash, proof.expectedSha256);
            assertArrayEquals(original, Files.readAllBytes(source.toPath()));
        } finally { source.delete(); }
    }

    @Test public void differentReportedIdentityFailsBeforeRecovery() throws Exception {
        File source = apk();
        try {
            String wrong = String.format(java.util.Locale.ROOT, "%064d", 1);
            try {
                RecoveryResumeGate.attest(source, wrong);
                fail("Wrong reported SHA cannot authorize recovery");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("Integridade"));
            }
            assertTrue(source.isFile());
        } finally { source.delete(); }
    }

    @Test public void corruptZipWithItsOwnCorrectShaIsRejected() throws Exception {
        File source = apk();
        try {
            Files.write(source.toPath(), "not a zip".getBytes(StandardCharsets.UTF_8));
            String hash = ApkIntegrity.sha256(source);
            try {
                RecoveryResumeGate.attest(source, hash);
                fail("A matching hash alone must not accept invalid archive");
            } catch (IOException expected) {
                assertNotNull(expected.getMessage());
            }
            assertTrue(source.isFile());
        } finally { source.delete(); }
    }

    @Test public void alteredSourceBetweenPromptAndConsentCannotRestore()
            throws Exception {
        File source = apk();
        try {
            String hash = ApkIntegrity.sha256(source);
            RecoveryResumeGate.Proof proof = RecoveryResumeGate.attest(source, hash);
            byte[] bytes = Files.readAllBytes(source.toPath());
            bytes[bytes.length / 3] ^= 1;
            Files.write(source.toPath(), bytes);
            try {
                RecoveryResumeGate.revalidate(proof, source, hash);
                fail("Mutated source cannot commit a restored plan");
            } catch (IOException expected) {
                assertNotNull(expected.getMessage());
            }
        } finally { source.delete(); }
    }

    @Test public void anotherFileWithIdenticalContentsIsNotSameWorkspace()
            throws Exception {
        File original = apk();
        File alias = File.createTempFile("f118_other_", ".apk", original.getParentFile());
        try {
            Files.copy(original.toPath(), alias.toPath(),
                java.nio.file.StandardCopyOption.REPLACE_EXISTING);
            String hash = ApkIntegrity.sha256(original);
            RecoveryResumeGate.Proof proof = RecoveryResumeGate.attest(original, hash);
            try {
                RecoveryResumeGate.revalidate(proof, alias, hash);
                fail("A different project file cannot borrow the pending consent");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("mudou"));
            }
            assertTrue(alias.isFile() && original.isFile());
        } finally {
            original.delete();
            alias.delete();
        }
    }

    @Test public void changedReportedHashAfterPromptIsRejected() throws Exception {
        File source = apk();
        try {
            String hash = ApkIntegrity.sha256(source);
            RecoveryResumeGate.Proof proof = RecoveryResumeGate.attest(source, hash);
            try {
                RecoveryResumeGate.revalidate(proof, source,
                    "0000000000000000000000000000000000000000000000000000000000000000");
                fail("A newly reported identity may not silently change");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("mudou"));
            }
        } finally { source.delete(); }
    }

    @Test public void interruptedRecoveryIsRejectedAndLeavesSourceUntouched()
            throws Exception {
        File source = apk();
        try {
            byte[] before = Files.readAllBytes(source.toPath());
            String hash = ApkIntegrity.sha256(source);
            Thread.currentThread().interrupt();
            try {
                RecoveryResumeGate.attest(source, hash);
                fail("Interrupted restore cannot proceed");
            } catch (java.io.InterruptedIOException expected) {
                assertNotNull(expected.getMessage());
            } finally {
                Thread.interrupted();
            }
            assertArrayEquals(before, Files.readAllBytes(source.toPath()));
        } finally {
            Thread.interrupted();
            source.delete();
        }
    }
}
