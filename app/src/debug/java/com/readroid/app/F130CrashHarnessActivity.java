package com.readroid.app;

import android.app.Activity;
import android.os.Bundle;
import android.net.Uri;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.StandardCopyOption;

/**
 * F1.30 debug-only Android activity driven by the CI host.
 *
 * Starts a REAL ContentResolver -> APK private staging -> ZIP admission
 * while an unrelated fixture-app provider holds an open pipe. CI kills the
 * provider by ADB AFTER observing bytes in .apk.pending. A separate host
 * then reads the durable result; AndroidJUnitRunner is never involved.
 *
 * Fixed URI, fixed disposable sandbox, never accepts user input or SAF writes.
 */
public final class F130CrashHarnessActivity extends Activity {
    private static final Uri SOURCE = Uri.parse(
        "content://com.readroid.f130fixture.provider/interrupted.zip");
    private static final String DIR = "f130_crash_sandbox";
    private static final String RESULT = "f130_crash_result";
    private static final String[] NAMES = {
        "readroid_F130accepted123.apk",
        "readroid_F130accepted123.apk.idx.db",
        "recovery_f130.enc"
    };
    private static final String[] VALUES = {
        "accepted before crash", "saved index", "saved checkpoint"
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        final File root = new File(getCacheDir(), DIR);
        try {
            if (!root.mkdir())
                throw new IOException("Sandbox already exists; refusing to overwrite");
            for (int i = 0; i < NAMES.length; i++) {
                Files.write(new File(root, NAMES[i]).toPath(),
                    VALUES[i].getBytes(StandardCharsets.UTF_8));
            }
            publish("RUNNING");
        } catch (Exception setupError) {
            try { publish("FAIL_SETUP"); } catch (IOException ignored) {}
            return;
        }
        final ImportActivityScope scope = new ImportActivityScope(root);
        new Thread(() -> runImport(root, scope), "F130-standalone-APK-import").start();
    }

    private void runImport(File root, ImportActivityScope scope) {
        ApkImportStaging.Result copied = null;
        String verdict = "FAIL_UNEXPECTED";
        try {
            copied = ApkImportStaging.copy(root,
                () -> getContentResolver().openInputStream(SOURCE),
                () -> ApkImportPreflight.availableBytes(this), null, scope);
            try {
                ApkZipIntegrity.verify(copied.candidate);
                verdict = "FAIL_ACCEPTED_TRUNCATED_ZIP";
            } catch (IOException invalidArchive) {
                verdict = "PASS_ZIP_REJECTED";
            }
        } catch (IOException | SecurityException deniedOrBrokenPipe) {
            verdict = "PASS_TRANSPORT_REJECTED";
        } catch (Throwable unexpected) {
            verdict = "FAIL_UNEXPECTED";
        } finally {
            try {
                if (copied != null) {
                    copied.candidate.delete();
                    ImportCacheAudit.release(copied.candidate);
                    scope.release(copied.candidate);
                }
                scope.close();
                if (!preserved(root)) verdict = "FAIL_CACHE_CHANGED";
                publish(verdict);
            } catch (Exception failure) {
                try { publish("FAIL_CLEANUP"); } catch (IOException ignored) {}
            }
        }
    }

    private boolean preserved(File root) throws IOException {
        File[] entries = root.listFiles();
        if (entries == null || entries.length != NAMES.length) return false;
        for (int i = 0; i < NAMES.length; i++) {
            File original = new File(root, NAMES[i]);
            if (!Files.isRegularFile(original.toPath(), LinkOption.NOFOLLOW_LINKS))
                return false;
            String observed = new String(Files.readAllBytes(original.toPath()),
                StandardCharsets.UTF_8);
            if (!VALUES[i].equals(observed)) return false;
        }
        return true;
    }

    private void publish(String status) throws IOException {
        File destination = new File(getFilesDir(), RESULT);
        File temp = new File(getFilesDir(), RESULT + ".tmp");
        Files.write(temp.toPath(), status.getBytes(StandardCharsets.US_ASCII));
        Files.move(temp.toPath(), destination.toPath(),
            StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }
}
