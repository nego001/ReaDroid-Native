package com.readroid.app;

import android.app.Activity;
import android.os.Bundle;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.Collections;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/**
 * F1.39: fixed-identity, DEBUG-ONLY process-death probe.
 * ADB kills the process AFTER an atomic checkpoint rename but AFTER
 * RecoveryDirectoryGuard.syncAfterRename(). This is NOT a power-loss test.
 */
public final class F140PostSyncCrashHarnessActivity extends Activity {
    static final String LAB = "f140_ci_postsync_lab";
    static final String ALIAS = "negrescodroid.f140.ci.postsync.v1";
    static final String ENTRY = "assets/f140-postsync.txt";
    static final String REV_A = "F140 accepted A";
    static final String REV_B = "F140 promoted B after crash";
    static final String REV_C = "F140 promoted C after crash";
    static final String REV_D = "F140 completed D";
    static final String FILE = "edit-plan-checkpoint.v1";

    private File dir() { return new File(getFilesDir(), LAB); }
    private File source() { return new File(dir(), "accepted_source.apk"); }
    private File folder() { return new File(dir(), "vault"); }
    private File checkpoint() { return new File(folder(), FILE); }
    private Map<String, String> edits(String value) {
        return Collections.singletonMap(ENTRY, value);
    }
    private static String read(File file) throws IOException {
        return new String(Files.readAllBytes(file.toPath()),
            StandardCharsets.US_ASCII);
    }

    private void status(String value) throws IOException {
        File staging = new File(dir(), "status.new");
        Files.write(staging.toPath(),
            value.getBytes(StandardCharsets.US_ASCII));
        Files.move(staging.toPath(), new File(dir(), "status").toPath(),
            StandardCopyOption.ATOMIC_MOVE,
            StandardCopyOption.REPLACE_EXISTING);
    }

    private static byte[] testZip() throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(bytes)) {
            zip.putNextEntry(new ZipEntry("AndroidManifest.xml"));
            zip.write("F140 disposable manifest".getBytes(StandardCharsets.UTF_8));
            zip.closeEntry();
            zip.putNextEntry(new ZipEntry(ENTRY));
            zip.write("F140 immutable original member".getBytes(
                StandardCharsets.UTF_8));
            zip.closeEntry();
        }
        return bytes.toByteArray();
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        String phase = getIntent().getStringExtra("phase");
        if (!"seed".equals(phase) && !"promote_b".equals(phase)
                && !"promote_c".equals(phase) && !"commit_d".equals(phase)) {
            finish();
            return;
        }
        new Thread(() -> execute(phase), "F140-postsync").start();
    }

    private void seed() throws Exception {
        if (!dir().mkdir())
            throw new IOException("F140 isolated sandbox already exists");
        Files.write(source().toPath(), testZip(),
            StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        ApkZipIntegrity.verify(source());
        new RecoveryVault(folder(), ALIAS).save(source(), edits(REV_A));
        Files.write(new File(dir(), "accepted.sha256").toPath(),
            ApkIntegrity.sha256(checkpoint()).getBytes(StandardCharsets.US_ASCII));
        Files.write(new File(dir(), "accepted.version").toPath(),
            "A".getBytes(StandardCharsets.US_ASCII));
        status("SEEDED_A");
    }

    private void promote(String phase, String previous, String revision,
            String marker) throws Exception {
        if (!previous.equals(read(new File(dir(), "accepted.version"))))
            throw new IOException("F140 refused out-of-order post-rename crash");
        if (!ApkIntegrity.sha256(checkpoint()).equals(
                read(new File(dir(), "accepted.sha256"))))
            throw new IOException("F140 last accepted SHA changed before crash");
        RecoveryVault held = new RecoveryVault(folder(), ALIAS,
            stage -> {}, RecoveryStorageBudget.forDirectory(folder()),
            (read, total) -> {}, stage -> {}, checkpoint -> {}, promoted -> {
                // This callback is invoked AFTER Files.move ATOMIC_MOVE.
                // An external force-stop, not an exception in-process,
                // interrupts the writer AFTER fsync of the vault directory.
                if (!promoted.isFile() || promoted.length() < 33)
                    throw new IOException("F140 atomic promotion did not complete");
                File[] pending = folder().listFiles((d, name) ->
                    name.startsWith("checkpoint-") && name.endsWith(".tmp"));
                if (pending == null || pending.length != 0)
                    throw new IOException("F140 staged files survived rename");
                String sha = ApkIntegrity.sha256(promoted);
                if (sha.equals(read(new File(dir(), "accepted.sha256"))))
                    throw new IOException("F140 callback still sees old ciphertext");
                Files.write(new File(dir(), "promoted.sha256").toPath(),
                    sha.getBytes(StandardCharsets.US_ASCII));
                // Last marker: host only kills after new ciphertext AND SHA
                // are observable. This runs only after vault directory fsync.
                status(marker);
                try {
                    Thread.sleep(60000);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new java.io.InterruptedIOException(
                        "F140 waiting for host force-stop was interrupted");
                }
                throw new IOException("F140 host failed to kill post-rename writer");
            });
        held.save(source(), edits(revision));
    }

    private void commitD() throws Exception {
        if (!"C".equals(read(new File(dir(), "accepted.version"))))
            throw new IOException("F140 committed D requires observed C");
        new RecoveryVault(folder(), ALIAS).save(source(), edits(REV_D));
        Files.write(new File(dir(), "accepted.sha256").toPath(),
            ApkIntegrity.sha256(checkpoint()).getBytes(StandardCharsets.US_ASCII));
        Files.write(new File(dir(), "accepted.version").toPath(),
            "D".getBytes(StandardCharsets.US_ASCII));
        status("COMMITTED_D");
    }

    private void execute(String phase) {
        try {
            if ("seed".equals(phase)) seed();
            else if ("promote_b".equals(phase))
                promote(phase, "A", REV_B, "PROMOTED_B_POST_SYNC");
            else if ("promote_c".equals(phase))
                promote(phase, "B", REV_C, "PROMOTED_C_POST_SYNC");
            else commitD();
        } catch (Exception failure) {
            try { if (dir().isDirectory()) status("FAIL_" + phase); }
            catch (IOException ignored) { }
        }
    }
}
