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
 * F1.32: DEBUG-ONLY crash laboratory for RecoveryVault.
 * Host kills this app PROCESS while BeforeCommit holds an fsynced encrypted
 * stage, BEFORE the original checkpoint can be atomically replaced.
 * Paths, editing identity and Keystore alias are hard-coded CI fixtures.
 */
public final class F132CheckpointHarnessActivity extends Activity {
    static final String FOLDER = "f132_ci_checkpoint_lab";
    static final String ALIAS = "negrescodroid.f132.ci.checkpoint.v1";
    static final String SOURCE = "accepted_source.apk";
    static final String STATUS = "status";
    static final String EXPECTED_HASH = "expected_checkpoint.sha256";
    static final String CURRENT_VERSION = "accepted_version";
    static final String PATH = "assets/f132-recovery.txt";
    static final String REV_A = "F132 revision A - original accepted edits";
    static final String REV_B = "F132 revision B - later accepted edits";
    static final String REV_C = "F132 revision C - MUST NOT commit";

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        final String operation = getIntent().getStringExtra("phase");
        if (!"seed".equals(operation) && !"stage_b".equals(operation)
                && !"commit_b".equals(operation) && !"stage_c".equals(operation)) {
            finish();
            return;
        }
        new Thread(() -> execute(operation), "F132-test-only-vault-writer").start();
    }

    private File folder() { return new File(getFilesDir(), FOLDER); }
    private File source(File dir) { return new File(dir, SOURCE); }
    private File vaultFolder(File dir) { return new File(dir, "vault"); }
    private File checkpoint(File dir) {
        return new File(vaultFolder(dir), "edit-plan-checkpoint.v1");
    }
    private Map<String, String> edits(String revision) {
        return Collections.singletonMap(PATH, revision);
    }

    private void mark(File dir, String status) throws IOException {
        File state = new File(dir, STATUS);
        File staging = new File(dir, STATUS + ".new");
        Files.write(staging.toPath(), status.getBytes(StandardCharsets.US_ASCII));
        Files.move(staging.toPath(), state.toPath(),
            StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }

    private void setAcceptedVersion(File dir, String revision) throws IOException {
        String digest = ApkIntegrity.sha256(checkpoint(dir));
        Files.write(new File(dir, EXPECTED_HASH).toPath(),
            digest.getBytes(StandardCharsets.US_ASCII));
        Files.write(new File(dir, CURRENT_VERSION).toPath(),
            revision.getBytes(StandardCharsets.US_ASCII));
    }

    private static byte[] validZipFixture() throws IOException {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(buffer)) {
            zip.putNextEntry(new ZipEntry("AndroidManifest.xml"));
            zip.write("F132 disposable test manifest".getBytes(StandardCharsets.UTF_8));
            zip.closeEntry();
            zip.putNextEntry(new ZipEntry(PATH));
            zip.write("untouched source bytes".getBytes(StandardCharsets.UTF_8));
            zip.closeEntry();
        }
        return buffer.toByteArray();
    }

    private static String read(File file) throws IOException {
        return new String(Files.readAllBytes(file.toPath()), StandardCharsets.US_ASCII);
    }

    private void seed(File dir) throws Exception {
        if (!dir.mkdir())
            throw new IOException("F132 sandbox already exists; refuse overwrite");
        Files.write(source(dir).toPath(), validZipFixture(),
            StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        ApkZipIntegrity.verify(source(dir));
        RecoveryVault vault = new RecoveryVault(vaultFolder(dir), ALIAS);
        vault.save(source(dir), edits(REV_A));
        setAcceptedVersion(dir, "A");
        mark(dir, "SEEDED_A");
    }

    private void commitB(File dir) throws Exception {
        if (!"A".equals(read(new File(dir, CURRENT_VERSION))))
            throw new IOException("F132 refusing non-A checkpoint replacement");
        RecoveryVault vault = new RecoveryVault(vaultFolder(dir), ALIAS);
        vault.save(source(dir), edits(REV_B));
        setAcceptedVersion(dir, "B");
        mark(dir, "COMMITTED_B");
    }

    private void stageAndBlock(File dir, String version, String replacement)
            throws Exception {
        if (!version.equals(read(new File(dir, CURRENT_VERSION))))
            throw new IOException("F132 wrong accepted revision before crash");
        String marker = "A".equals(version) ? "STAGED_B" : "STAGED_C";
        RecoveryVault interrupted = new RecoveryVault(vaultFolder(dir), ALIAS,
            staged -> {
                if (!staged.isFile() || staged.length() < 33)
                    throw new IOException("F132 encrypted stage not synced");
                // Hook runs after fd.sync() but before atomic file move.
                mark(dir, marker);
                try {
                    Thread.sleep(60000);
                } catch (InterruptedException interruptedThread) {
                    Thread.currentThread().interrupt();
                    throw new java.io.InterruptedIOException(
                        "F132 interrupted before commit");
                }
                throw new IOException("F132 host failed to kill blocked writer");
            });
        interrupted.save(source(dir), edits(replacement));
    }

    private void execute(String operation) {
        File dir = folder();
        try {
            if ("seed".equals(operation)) seed(dir);
            else if ("stage_b".equals(operation)) stageAndBlock(dir, "A", REV_B);
            else if ("commit_b".equals(operation)) commitB(dir);
            else if ("stage_c".equals(operation)) stageAndBlock(dir, "B", REV_C);
        } catch (Exception error) {
            try {
                if (dir.isDirectory()) mark(dir, "FAIL_" + operation);
            } catch (IOException ignored) { }
        }
    }
}
