package com.readroid.app;

import android.app.Activity;
import android.os.Bundle;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.Collections;
import java.util.Map;

/**
 * F1.35 debug-only, fixed-identity checkpoint verifier crash probe.
 * ADB force-stop happens AFTER the first 8192 encrypted bytes are read
 * but BEFORE remaining ciphertext is verified or the atomic move occurs.
 * This cannot run against any production user document or Keystore alias.
 */
public final class F135VerifierCrashHarnessActivity extends Activity {
    static final String DIR = "f135_ci_verify_lab";
    static final String KEY = "negrescodroid.f135.ci.verification.v1";
    static final String ENTRY = "assets/f135-verified.txt";
    static final String A = "F135 accepted revision A";
    static final String B = "F135 accepted revision B";
    static final String SOURCE = "source.apk";

    private File root() { return new File(getFilesDir(), DIR); }
    private File folder() { return new File(root(), "vault"); }
    private File source() { return new File(root(), SOURCE); }
    private File checkpoint() { return new File(folder(), "edit-plan-checkpoint.v1"); }
    private Map<String, String> edits(String s) {
        return Collections.singletonMap(ENTRY, s);
    }
    private static String large(String marker) {
        StringBuilder text = new StringBuilder(marker);
        while (text.length() < 64000)
            text.append(" encrypted verification payload 0123456789 ");
        return text.toString();
    }
    private static String read(File f) throws IOException {
        return new String(Files.readAllBytes(f.toPath()), StandardCharsets.US_ASCII);
    }
    private void status(String value) throws IOException {
        File dest = new File(root(), "status");
        File tmp = new File(root(), "status.new");
        Files.write(tmp.toPath(), value.getBytes(StandardCharsets.US_ASCII));
        Files.move(tmp.toPath(), dest.toPath(), StandardCopyOption.ATOMIC_MOVE,
            StandardCopyOption.REPLACE_EXISTING);
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String phase = getIntent().getStringExtra("phase");
        if (!"seed".equals(phase) && !"verify_1".equals(phase)
                && !"verify_2".equals(phase) && !"commit_b".equals(phase)) {
            finish();
            return;
        }
        new Thread(() -> execute(phase), "F135-verifier").start();
    }

    private void seed() throws Exception {
        if (!root().mkdir())
            throw new IOException("F135 sandbox already exists");
        Files.write(source().toPath(),
            "F135 accepted source file".getBytes(StandardCharsets.UTF_8),
            StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        RecoveryVault vault = new RecoveryVault(folder(), KEY);
        vault.save(source(), edits(A));
        Files.write(new File(root(), "accepted.sha256").toPath(),
            ApkIntegrity.sha256(checkpoint()).getBytes(StandardCharsets.US_ASCII));
        Files.write(new File(root(), "accepted.version").toPath(),
            "SEEDED".getBytes(StandardCharsets.US_ASCII));
        // Expose READY only once every precondition has reached disk.
        status("SEEDED");
    }

    private void interruptedVerification(String phase) throws Exception {
        if (!"SEEDED".equals(read(new File(root(), "accepted.version")))) {
            // Version set once by seed below; protects fixed-order CI stages.
            throw new IOException("F135 accepted version not A");
        }
        final String marker = "verify_1".equals(phase)
            ? "READING_1" : "READING_2";
        RecoveryVault held = new RecoveryVault(folder(), KEY,
            staged -> {},
            RecoveryStorageBudget.forDirectory(folder()),
            (verified, total) -> {
                if (verified < 8192 || verified >= total)
                    throw new IOException("F135 test must block on first chunk");
                status(marker);
                try { Thread.sleep(60000); }
                catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw new java.io.InterruptedIOException(
                        "F135 blocked verifier interrupted");
                }
                throw new IOException("F135 ADB host failed to terminate verifier");
            });
        held.save(source(), edits(large("F135 never commit " + phase)));
    }

    private void commitB() throws Exception {
        if (!"SEEDED".equals(read(new File(root(), "accepted.version"))))
            throw new IOException("F135 version unexpectedly mutated");
        RecoveryVault vault = new RecoveryVault(folder(), KEY);
        vault.save(source(), edits(B));
        Files.write(new File(root(), "accepted.version").toPath(),
            "B".getBytes(StandardCharsets.US_ASCII));
        Files.write(new File(root(), "accepted.sha256").toPath(),
            ApkIntegrity.sha256(checkpoint()).getBytes(StandardCharsets.US_ASCII));
        status("COMMITTED_B");
    }

    private void execute(String phase) {
        try {
            if ("seed".equals(phase)) seed();
            else if ("commit_b".equals(phase)) commitB();
            else interruptedVerification(phase);
        } catch (Exception e) {
            try { if (root().isDirectory()) status("FAIL_" + phase); }
            catch (IOException ignored) {}
        }
    }
}
