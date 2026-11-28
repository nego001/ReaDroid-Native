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
import java.util.Arrays;
import java.util.Collections;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Emulator-only F1.41. No production APK, aliases, files or physical devices. */
public final class F141FinalReadCrashHarnessActivity extends Activity {
    static final String LAB = "f141_ci_final_read_lab";
    static final String ALIAS = "negrescodroid.f141.ci.finalread.v1";
    static final String ENTRY = "assets/f141-final.txt";
    static final String FILE = "edit-plan-checkpoint.v1";
    static String revision(char c) {
        char[] chars = new char[24000];
        Arrays.fill(chars, c);
        return "F141:" + c + ":" + new String(chars);
    }
    private File root() { return new File(getFilesDir(), LAB); }
    private File source() { return new File(root(), "accepted_source.apk"); }
    private File folder() { return new File(root(), "vault"); }
    private File checkpoint() { return new File(folder(), FILE); }
    private Map<String, String> edits(char c) {
        return Collections.singletonMap(ENTRY, revision(c));
    }
    private static String read(File file) throws IOException {
        return new String(Files.readAllBytes(file.toPath()), StandardCharsets.US_ASCII);
    }
    private void status(String marker) throws IOException {
        File temp = new File(root(), "status.new");
        Files.write(temp.toPath(), marker.getBytes(StandardCharsets.US_ASCII));
        Files.move(temp.toPath(), new File(root(), "status").toPath(),
            StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }
    private static byte[] testZip() throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ZipOutputStream out = new ZipOutputStream(bytes)) {
            out.putNextEntry(new ZipEntry("AndroidManifest.xml"));
            out.write("F141 disposable manifest".getBytes(StandardCharsets.UTF_8));
            out.closeEntry();
            out.putNextEntry(new ZipEntry(ENTRY));
            out.write("F141 immutable original entry".getBytes(StandardCharsets.UTF_8));
            out.closeEntry();
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
        new Thread(() -> execute(phase), "F141-final-read").start();
    }
    private void seed() throws Exception {
        if (!root().mkdir())
            throw new IOException("F141 isolated sandbox already exists");
        Files.write(source().toPath(), testZip(), StandardOpenOption.CREATE_NEW);
        ApkZipIntegrity.verify(source());
        new RecoveryVault(folder(), ALIAS).save(source(), edits('A'));
        Files.write(new File(root(), "accepted.sha256").toPath(),
            ApkIntegrity.sha256(checkpoint()).getBytes(StandardCharsets.US_ASCII));
        Files.write(new File(root(), "accepted.version").toPath(),
            "A".getBytes(StandardCharsets.US_ASCII));
        status("SEEDED_A");
    }
    private void promote(char expected, char next) throws Exception {
        if (!String.valueOf(expected).equals(read(
                new File(root(), "accepted.version"))))
            throw new IOException("F141 phase rejected: wrong predecessor");
        if (!ApkIntegrity.sha256(checkpoint()).equals(
                read(new File(root(), "accepted.sha256"))))
            throw new IOException("F141 previously accepted SHA has changed");
        RecoveryVault held = new RecoveryVault(folder(), ALIAS,
            stage -> {}, RecoveryStorageBudget.forDirectory(folder()),
            (verified, total) -> {}, stage -> {}, promoted -> {},
            promoted -> {}, (verified, total) -> {
                // This callback belongs ONLY to final post-fsync reread.
                // A first 8 KiB chunk has been read; more ciphertext remains.
                if (!(verified == 8192 && total > verified))
                    throw new IOException("F141 first final chunk boundary invalid");
                File[] stages = folder().listFiles((d, name) ->
                    name.startsWith("checkpoint-") && name.endsWith(".tmp"));
                if (stages == null || stages.length != 0)
                    throw new IOException("F141 unfinished staging after move");
                String sha = ApkIntegrity.sha256(checkpoint());
                if (sha.equals(read(new File(root(), "accepted.sha256"))))
                    throw new IOException("F141 final observer still sees old file");
                Files.write(new File(root(), "promoted.sha256").toPath(),
                    sha.getBytes(StandardCharsets.US_ASCII));
                status("READING_" + next);
                // ADB force-stop is external. A timeout is a failure, not pass.
                try { Thread.sleep(60000); }
                catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new java.io.InterruptedIOException(
                        "F141 final-read writer was interrupted");
                }
                throw new IOException("F141 host did not terminate writer");
            });
        held.save(source(), edits(next));
    }
    private void commitD() throws Exception {
        if (!"C".equals(read(new File(root(), "accepted.version"))))
            throw new IOException("F141 normal D requires recovered C");
        new RecoveryVault(folder(), ALIAS).save(source(), edits('D'));
        Files.write(new File(root(), "accepted.sha256").toPath(),
            ApkIntegrity.sha256(checkpoint()).getBytes(StandardCharsets.US_ASCII));
        Files.write(new File(root(), "accepted.version").toPath(),
            "D".getBytes(StandardCharsets.US_ASCII));
        status("COMMITTED_D");
    }
    private void execute(String phase) {
        try {
            if ("seed".equals(phase)) seed();
            else if ("promote_b".equals(phase)) promote('A', 'B');
            else if ("promote_c".equals(phase)) promote('B', 'C');
            else commitD();
        } catch (Exception failure) {
            try { if (root().isDirectory()) status("FAIL_" + phase); }
            catch (IOException ignored) { }
        }
    }
}
