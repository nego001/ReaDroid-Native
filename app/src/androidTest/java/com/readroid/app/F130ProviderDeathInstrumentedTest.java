package com.readroid.app;

import android.content.Context;
import android.os.Bundle;
import android.os.Process;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** Android instrumentation against a separately installed disposable fixture APK. */
@RunWith(AndroidJUnit4.class)
public final class F130ProviderDeathInstrumentedTest {
    private static final long SPACE = 128L * 1024 * 1024;
    private static final String REMOTE_AUTHORITY = "com.readroid.f130fixture.provider";
    private static final android.net.Uri REMOTE_SOURCE = android.net.Uri.parse(
        "content://" + REMOTE_AUTHORITY + "/interrupted.zip");

    private static Context app() {
        return InstrumentationRegistry.getInstrumentation().getTargetContext();
    }

    private static File root() throws IOException {
        return Files.createTempDirectory(app().getCacheDir().toPath(),
            "f130_crash_").toFile();
    }

    private static void clean(File dir) {
        if (dir == null) return;
        File[] entries = dir.listFiles();
        if (entries != null) for (File entry : entries) entry.delete();
        dir.delete();
    }

    private static File[] preservationFixture(File dir) throws IOException {
        File accepted = new File(dir, "readroid_F130accepted123.apk");
        File sqlite = new File(dir, "readroid_F130accepted123.apk.idx.db");
        File recovery = new File(dir, "recovery_f130.enc");
        Files.write(accepted.toPath(), "accepted before crash".getBytes(StandardCharsets.UTF_8));
        Files.write(sqlite.toPath(), "saved index".getBytes(StandardCharsets.UTF_8));
        Files.write(recovery.toPath(), "saved checkpoint".getBytes(StandardCharsets.UTF_8));
        return new File[]{accepted, sqlite, recovery};
    }

    private static void assertPreserved(File dir, File[] saved) throws IOException {
        String[] expected = {"accepted before crash", "saved index", "saved checkpoint"};
        File[] entries = dir.listFiles();
        assertNotNull(entries);
        assertEquals("Orphaned candidate survived provider crash", saved.length, entries.length);
        for (int i = 0; i < saved.length; i++) {
            assertTrue("Existing project/index/checkpoint was deleted", saved[i].isFile());
            assertEquals(expected[i], new String(
                Files.readAllBytes(saved[i].toPath()), StandardCharsets.UTF_8));
        }
    }

    private static Bundle provider(String command) {
        Bundle response = app().getContentResolver().call(
            REMOTE_AUTHORITY, command, null, null);
        assertNotNull("Crashable AndroidTest provider not available", response);
        return response;
    }

    @Test public void f130RemoteProviderProcessDeathRejectsPartialApk()
            throws Exception {
        File dir = root();
        ImportActivityScope scope = new ImportActivityScope(dir);
        AtomicReference<ApkImportStaging.Result> copied = new AtomicReference<>();
        AtomicReference<Throwable> error = new AtomicReference<>();
        CountDownLatch ended = new CountDownLatch(1);
        Thread reader = null;
        try {
            File[] saved = preservationFixture(dir);
            ApkImportPreflight.beforeCopy(app(), REMOTE_SOURCE);
            int oldProviderPid = provider("pid").getInt("pid", -1);
            assertTrue("Provider process PID unavailable", oldProviderPid > 0);
            assertNotEquals("Provider must be in a DIFFERENT Android process",
                Process.myPid(), oldProviderPid);

            reader = new Thread(() -> {
                try {
                    copied.set(ApkImportStaging.copy(dir,
                        () -> app().getContentResolver().openInputStream(
                            REMOTE_SOURCE), () -> SPACE, null, scope));
                } catch (Throwable ex) { error.set(ex); }
                finally { ended.countDown(); }
            }, "F130-staging-client");
            reader.start();

            assertTrue("Pipe producer never emitted ZIP header",
                provider("await-bytes").getBoolean("ready"));
            assertEquals("Source must be uncommitted while provider is alive",
                1, scope.pendingCount());
            assertEquals(saved.length + 1, dir.listFiles().length);
            // Real remote PID dies, not just a simulated IOException.
            assertEquals(oldProviderPid, provider("die").getInt("pid", -1));
            assertTrue("Reader stalled after remote provider termination",
                ended.await(15, TimeUnit.SECONDS));

            ApkImportStaging.Result returned = copied.get();
            if (returned == null) {
                assertNotNull("Crash must fail or return an incomplete candidate",
                    error.get());
                assertTrue("Only Android/IO provider failure is acceptable: " + error.get(),
                    error.get() instanceof IOException
                        || error.get() instanceof SecurityException);
            } else {
                assertEquals("Only streamed files can have .apk suffix",
                    true, returned.candidate.getName().endsWith(".apk"));
                try {
                    ApkZipIntegrity.verify(returned.candidate);
                    fail("ZIP missing central directory was improperly accepted");
                } catch (IOException expected) {
                    // Clean EOF after provider death is NOT validation.
                } finally {
                    returned.candidate.delete();
                    ImportCacheAudit.release(returned.candidate);
                    scope.release(returned.candidate);
                }
            }
            int newProviderPid = -1;
            for (int attempt = 0; attempt < 15; attempt++) {
                try { newProviderPid = provider("pid").getInt("pid", -1); }
                catch (RuntimeException inaccessible) { /* rebind after Binder death */ }
                if (newProviderPid > 0 && newProviderPid != oldProviderPid) break;
                Thread.sleep(250);
            }
            assertTrue("Provider was not really killed and recreated",
                newProviderPid > 0 && newProviderPid != oldProviderPid);
            assertPreserved(dir, saved);
        } finally {
            scope.close();
            if (reader != null) reader.join(15000);
            clean(dir);
        }
    }

    private static byte[] intactZip() throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(bytes)) {
            ZipEntry manifest = new ZipEntry("AndroidManifest.xml");
            zip.putNextEntry(manifest);
            zip.write("manifest test data".getBytes(StandardCharsets.UTF_8));
            zip.closeEntry();
            ZipEntry asset = new ZipEntry("assets/important.dat");
            zip.putNextEntry(asset);
            zip.write("a legitimate ZIP member".getBytes(StandardCharsets.UTF_8));
            zip.closeEntry();
        }
        return bytes.toByteArray();
    }

    @Test public void f130ValidLocalEntriesButMissingZipEndAreRejected()
            throws Exception {
        File dir = root();
        ImportActivityScope scope = new ImportActivityScope(dir);
        File valid = null, candidate = null;
        try {
            File[] saved = preservationFixture(dir);
            byte[] entire = intactZip();
            valid = new File(dir, "original_reference.zip");
            Files.write(valid.toPath(), entire);
            assertEquals("Intact ZIP fixture must be accepted by audit", 2,
                ApkZipIntegrity.verify(valid).verifiedFiles);
            // Remove the 22-byte End of Central Directory, leaving valid local
            // file headers, member bytes and central directory entries.
            byte[] broken = Arrays.copyOf(entire, entire.length - 22);
            assertTrue(entire.length > 100);
            ApkImportStaging.Result copied = ApkImportStaging.copy(dir,
                () -> new ByteArrayInputStream(broken), () -> SPACE, null, scope);
            candidate = copied.candidate;
            assertEquals(broken.length, copied.copied.sizeBytes);
            assertTrue(candidate.getName().endsWith(".apk"));
            assertArrayEquals(broken, Files.readAllBytes(candidate.toPath()));
            try {
                ApkZipIntegrity.verify(candidate);
                fail("A ZIP missing its central-directory ending cannot be accepted");
            } catch (IOException expected) {
                assertNotNull(expected.getMessage());
            }
            candidate.delete();
            ImportCacheAudit.release(candidate);
            scope.release(candidate);
            candidate = null;
            valid.delete();
            valid = null;
            assertPreserved(dir, saved);
        } finally {
            if (candidate != null) {
                candidate.delete();
                ImportCacheAudit.release(candidate);
                scope.release(candidate);
            }
            if (valid != null) valid.delete();
            scope.close();
            clean(dir);
        }
    }
}
