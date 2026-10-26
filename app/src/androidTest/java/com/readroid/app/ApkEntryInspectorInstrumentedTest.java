package com.readroid.app;

import static org.junit.Assert.*;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

@RunWith(AndroidJUnit4.class)
public class ApkEntryInspectorInstrumentedTest {
    private File fixture() throws Exception {
        File file = File.createTempFile("m2_inspect_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(file))) {
            out.putNextEntry(new ZipEntry("assets/ok.txt"));
            out.write("hello M2".getBytes(StandardCharsets.UTF_8));
            out.closeEntry();
        }
        return file;
    }

    private void corruptCentralCrc(File file) throws Exception {
        byte[] bytes = Files.readAllBytes(file.toPath());
        for (int i = 0; i + 46 <= bytes.length; i++) {
            if ((bytes[i]&255) == 0x50 && (bytes[i+1]&255) == 0x4b
                    && (bytes[i+2]&255) == 1 && (bytes[i+3]&255) == 2) {
                bytes[i+16] ^= 0x40;
                Files.write(file.toPath(), bytes);
                return;
            }
        }
        fail("No ZIP central directory entry found");
    }

    @Test public void inspectValidEntryReturnsTrueDigestAndCrc() throws Exception {
        File apk = fixture();
        try {
            String report = ApkEntryInspector.inspect(apk, "assets/ok.txt");
            assertTrue(report.contains("CAMINHO"));
            assertTrue(report.contains("SHA-256"));
            assertTrue(report.contains("CRC-32"));
            assertTrue(report.contains("8 bytes"));
        } finally { apk.delete(); }
    }

    @Test public void inspectRejectsDeclaredCrcCorruption() throws Exception {
        File apk = fixture();
        try {
            corruptCentralCrc(apk);
            try {
                ApkEntryInspector.inspect(apk, "assets/ok.txt");
                fail("Corrupt CRC must not be reported as valid");
            } catch (java.io.IOException expected) {
                assertTrue(expected.getMessage(), expected.getMessage().contains("CRC-32"));
            }
        } finally { apk.delete(); }
    }

    @Test public void inspectCancellationDoesNotReturnPartialHash() throws Exception {
        File apk = fixture();
        boolean old = Thread.currentThread().isInterrupted();
        try {
            Thread.currentThread().interrupt();
            try {
                ApkEntryInspector.inspect(apk, "assets/ok.txt");
                fail("Interrupted inspection must abort");
            } catch (java.io.InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("interrompida"));
            }
        } finally {
            if (!old) Thread.interrupted();
            apk.delete();
        }
    }

    @Test public void inspectRejectsUnsafePath() throws Exception {
        File apk = fixture();
        try {
            try {
                ApkEntryInspector.inspect(apk, "../assets/ok.txt");
                fail("Traversal");
            } catch (java.io.IOException expected) {
                assertTrue(expected.getMessage().contains("Caminho"));
            }
        } finally { apk.delete(); }
    }
}
