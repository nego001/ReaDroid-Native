package com.readroid.app;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.DirectoryStream;
import java.nio.file.DirectoryIteratorException;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Map;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * Explicit, single-slot encrypted recovery checkpoint. No auto-save, APK
 * copies, Android Backup or credentials leave application-private storage.
 * The matching original APK must be reopened before applying a recovery.
 */
public final class RecoveryVault {
    private static final String FILE_NAME = "edit-plan-checkpoint.v1";
    private static final String KEY_ALIAS = "negrescodroid.v3.recovery.v1";
    private static final byte[] MAGIC = {'N', 'G', 'R', '3'};
    private static final byte VERSION = 1;
    private static final int MAX_PLAINTEXT = 512 * 1024;
    private static final int MAX_FILE = MAX_PLAINTEXT + 256;
    private static final int MAX_CHANGES = 100;
    // Never delete a potentially active save; only encrypted stages older
    // than 24 hours qualify for bounded, best-effort cleanup.
    private static final long STALE_STAGE_MILLIS = 24L * 60 * 60 * 1000;
    private static final int MAX_STAGE_SCAN = 256;
    // All vault instances share one application process and Keystore identity.
    // Serialize full save/load/clear transactions, not just their file moves.
    private static final Object IN_PROCESS_LOCK = new Object();
    private static final byte[] AAD = "NegrescoDroid:recovery:v1"
        .getBytes(StandardCharsets.US_ASCII);

    private final File storage;
    private final String alias;
    private final BeforeCommit beforeCommit;

    /** Failure injection for Android instrumented tests, never user-controlled. */
    interface BeforeCommit {
        void run(File staged) throws IOException;
    }

    public RecoveryVault(Context context) {
        this(new File(context.getFilesDir(), "v3-private-recovery"), KEY_ALIAS);
    }

    /** Isolated folder and key alias for instrumentation only. */
    RecoveryVault(File storage, String alias) {
        this(storage, alias, staged -> {});
    }

    /** Test-only seam to simulate failure after durable write and before commit. */
    RecoveryVault(File storage, String alias, BeforeCommit beforeCommit) {
        if (storage == null || alias == null || alias.isEmpty() || beforeCommit == null)
            throw new IllegalArgumentException("Armazenamento de recuperação inválido");
        this.storage = storage;
        this.alias = alias;
        this.beforeCommit = beforeCommit;
    }

    public boolean hasCheckpoint() {
        synchronized (IN_PROCESS_LOCK) {
            return new File(storage, FILE_NAME).isFile();
        }
    }

    public void clear() throws IOException {
        synchronized (IN_PROCESS_LOCK) {
            File backup = new File(storage, FILE_NAME);
            if (backup.exists() && !backup.delete())
                throw new IOException("Não foi possível remover a cópia de recuperação");
        }
    }

    public void save(File sourceApk, Map<String, String> changes) throws Exception {
        synchronized (IN_PROCESS_LOCK) {
            saveSerialized(sourceApk, changes);
        }
    }

    private void saveSerialized(File sourceApk, Map<String, String> changes)
            throws Exception {
        String fingerprint = sha256(sourceApk);
        if (changes == null || changes.isEmpty() || changes.size() > MAX_CHANGES)
            throw new IllegalArgumentException("O plano deve ter de 1 a 100 alterações");
        EditPlan plan = new EditPlan();
        for (Map.Entry<String, String> entry : changes.entrySet()) {
            plan.addTextReplacement(entry.getKey(), entry.getValue());
            // Do not trust a custom Map's size(): count validated entries.
            if (plan.size() > MAX_CHANGES)
                throw new IllegalArgumentException("O plano deve ter de 1 a 100 alterações");
        }
        if (plan.size() == 0)
            throw new IllegalArgumentException("O plano não contém alterações");
        JSONObject payload = plan.toJson();
        payload.put("sourceSha256", fingerprint);
        byte[] plaintext = payload.toString().getBytes(StandardCharsets.UTF_8);
        byte[] encrypted = null;
        byte[] encoded = null;
        File temporary = null;
        boolean committed = false;
        // This finally must cover oversize, Keystore/crypto, folder creation
        // and atomic-move errors, not only the final file write.
        try {
            if (plaintext.length > MAX_PLAINTEXT)
                throw new IllegalArgumentException("Plano excede o limite de 512 KiB");
            SecretKey key = obtainKey(true);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, key);
            cipher.updateAAD(AAD);
            byte[] iv = cipher.getIV();
            if (iv == null || iv.length != 12)
                throw new IOException("Vetor criptográfico inesperado");
            encrypted = cipher.doFinal(plaintext);
            ByteBuffer buffer = ByteBuffer.allocate(MAGIC.length + 1 + iv.length + encrypted.length);
            buffer.put(MAGIC).put(VERSION).put(iv).put(encrypted);
            encoded = buffer.array();
            if (!storage.isDirectory() && !storage.mkdirs())
                throw new IOException("Não foi possível criar o diretório privado");
            pruneAbandonedStages(storage, System.currentTimeMillis());
            temporary = File.createTempFile("checkpoint-", ".tmp", storage);
            try (FileOutputStream out = new FileOutputStream(temporary)) {
                out.write(encoded);
                out.getFD().sync();
            }
            // Once bytes are synced, a cancellation must not replace the
            // previous checkpoint. The temporary is cleaned by finally.
            if (Thread.currentThread().isInterrupted())
                throw new InterruptedIOException("Gravação da recuperação interrompida");
            beforeCommit.run(temporary);
            if (Thread.currentThread().isInterrupted())
                throw new InterruptedIOException("Gravação da recuperação interrompida");
            try {
                Files.move(temporary.toPath(), new File(storage, FILE_NAME).toPath(),
                    StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            } catch (AtomicMoveNotSupportedException unavailable) {
                throw new IOException("Armazenamento sem troca atômica segura", unavailable);
            }
            committed = true;
        } finally {
            if (!committed && temporary != null) temporary.delete();
            Arrays.fill(plaintext, (byte) 0);
            if (encrypted != null) Arrays.fill(encrypted, (byte) 0);
            if (encoded != null) Arrays.fill(encoded, (byte) 0);
        }
    }

    /** Pure read/verification: caller must get consent before modifying live EditPlan. */
    public Map<String, String> loadForSource(File sourceApk) throws Exception {
        synchronized (IN_PROCESS_LOCK) {
            return loadSerialized(sourceApk);
        }
    }

    private Map<String, String> loadSerialized(File sourceApk) throws Exception {
        String fingerprint = sha256(sourceApk);
        File file = new File(storage, FILE_NAME);
        if (!file.isFile() || file.length() < 4 + 1 + 12 + 16
            || file.length() > MAX_FILE)
            throw new IOException("Cópia de recuperação ausente ou inválida");
        final byte[] encoded;
        try (FileInputStream input = new FileInputStream(file)) {
            // Never trust an earlier File.length() observation. The file
            // might grow or be replaced while an untrusted checkpoint is read.
            encoded = readBounded(input);
        }
        byte[] iv = null;
        byte[] ciphertext = null;
        byte[] plaintext = null;
        try {
            // Recheck after reading in case the file changed since length().
            if (encoded.length < MAGIC.length + 1 + 12 + 16
                || encoded.length > MAX_FILE)
                throw new IOException("Tamanho da cópia de recuperação inválido");
            ByteBuffer input = ByteBuffer.wrap(encoded);
            for (byte b : MAGIC) {
                if (input.get() != b) throw new IOException("Formato de cópia incompatível");
            }
            if (input.get() != VERSION) throw new IOException("Versão de cópia incompatível");
            iv = new byte[12];
            input.get(iv);
            ciphertext = new byte[input.remaining()];
            input.get(ciphertext);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            // Reading a backup must never generate a replacement Keystore key.
            // If the original key was lost, fail without rewriting its identity.
            cipher.init(Cipher.DECRYPT_MODE, obtainKey(false), new GCMParameterSpec(128, iv));
            cipher.updateAAD(AAD);
            plaintext = cipher.doFinal(ciphertext); // authenticates before JSON parsing
            if (plaintext.length > MAX_PLAINTEXT)
                throw new IOException("Cópia excede limite de segurança");
            JSONObject payload = new JSONObject(new String(plaintext, StandardCharsets.UTF_8));
            if (!"readroid-edit-plan-v1".equals(payload.optString("format"))
                || !(payload.opt("applied") instanceof Boolean)
                || payload.getBoolean("applied")
                || !(payload.opt("sourceSha256") instanceof String))
                throw new IOException("Metadados de recuperação inválidos");
            if (!MessageDigest.isEqual(
                    fingerprint.getBytes(StandardCharsets.US_ASCII),
                    payload.getString("sourceSha256").getBytes(StandardCharsets.US_ASCII)))
                throw new SecurityException("Esta cópia pertence a outro APK");
            JSONArray changes = payload.optJSONArray("changes");
            if (changes == null || changes.length() < 1 || changes.length() > MAX_CHANGES)
                throw new IOException("Quantidade de alterações inválida");
            EditPlan parsed = new EditPlan();
            for (int i = 0; i < changes.length(); i++) {
                JSONObject entry = changes.optJSONObject(i);
                if (entry == null || !(entry.opt("path") instanceof String)
                    || !(entry.opt("replacementText") instanceof String))
                    throw new IOException("Alteração inválida na cópia");
                String path = entry.getString("path");
                if (parsed.contains(path)) throw new IOException("Caminho duplicado");
                parsed.addTextReplacement(path, entry.getString("replacementText"));
            }
            return parsed.snapshot();
        } finally {
            if (plaintext != null) Arrays.fill(plaintext, (byte) 0);
            if (ciphertext != null) Arrays.fill(ciphertext, (byte) 0);
            if (iv != null) Arrays.fill(iv, (byte) 0);
            Arrays.fill(encoded, (byte) 0);
        }
    }

    /**
     * Remove only app-created encrypted staging files older than one day.
     * Do not traverse subdirectories, follow symlinks, or touch the actual
     * checkpoint. Cleanup is best-effort and cannot prevent a valid save.
     * Package-private for deterministic Android regression coverage.
     */
    static int pruneAbandonedStages(File directory, long nowMillis) {
        if (directory == null
            || !Files.isDirectory(directory.toPath(), LinkOption.NOFOLLOW_LINKS))
            return 0;
        int removed = 0;
        int visited = 0;
        try (DirectoryStream<Path> entries =
                Files.newDirectoryStream(directory.toPath(), "checkpoint-*.tmp")) {
            for (Path candidate : entries) {
                if (++visited > MAX_STAGE_SCAN) break;
                if (!Files.isRegularFile(candidate, LinkOption.NOFOLLOW_LINKS))
                    continue;
                FileTime modified = Files.getLastModifiedTime(
                    candidate, LinkOption.NOFOLLOW_LINKS);
                long ageMillis = nowMillis - modified.toMillis();
                if (ageMillis < STALE_STAGE_MILLIS || ageMillis < 0)
                    continue;
                if (Files.deleteIfExists(candidate)) removed++;
            }
        } catch (IOException | DirectoryIteratorException | SecurityException failure) {
            // Cleanup never invalidates a checkpoint or blocks a new save.
        }
        return removed;
    }

    /**
     * Read a checkpoint with a hard allocation ceiling, including if it grows
     * after the initial length check. Package-private for stream regressions.
     * Wipe the staging array on both success and failure.
     */
    static byte[] readBounded(InputStream input) throws IOException {
        byte[] staging = new byte[MAX_FILE + 1];
        int count = 0;
        try {
            while (count < staging.length) {
                if (Thread.currentThread().isInterrupted())
                    throw new InterruptedIOException("Leitura da recuperação interrompida");
                int n = input.read(staging, count, staging.length - count);
                if (n < 0) break;
                if (n == 0) {
                    int one = input.read();
                    if (one < 0) break;
                    staging[count++] = (byte) one;
                } else {
                    count += n;
                }
                if (count > MAX_FILE)
                    throw new IOException("Cópia excede o limite de tamanho");
            }
            if (count > MAX_FILE)
                throw new IOException("Cópia excede o limite de tamanho");
            return Arrays.copyOf(staging, count);
        } finally {
            Arrays.fill(staging, (byte) 0);
        }
    }

    private SecretKey obtainKey(boolean createIfMissing) throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        java.security.Key existing = store.getKey(alias, null);
        if (existing != null) {
            if (!(existing instanceof SecretKey))
                throw new SecurityException("Identidade criptográfica incompatível");
            return (SecretKey) existing;
        }
        if (!createIfMissing)
            throw new SecurityException("Chave de recuperação indisponível no Android Keystore");
        // A stored checkpoint may still be recoverable if its Keystore identity
        // comes back (for example during device state repair). Do not silently
        // replace it with a new key merely because saving was requested.
        // Users must explicitly clear the obsolete checkpoint first.
        if (new File(storage, FILE_NAME).exists())
            throw new SecurityException(
                "Cópia existente sem chave de recuperação; remova a cópia explicitamente antes de criar outra");
        KeyGenerator generator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(alias,
            KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .setRandomizedEncryptionRequired(true)
            .build());
        return generator.generateKey();
    }

    private static String sha256(File source) throws Exception {
        if (source == null || !source.isFile() || source.length() > 1073741824L)
            throw new IOException("APK de origem ausente ou grande demais");
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[65536];
        long total = 0;
        try (FileInputStream in = new FileInputStream(source)) {
            int n;
            while ((n = in.read(buffer)) != -1) {
                if (Thread.currentThread().isInterrupted())
                    throw new java.io.InterruptedIOException("Verificação interrompida");
                total += n;
                if (total > 1073741824L)
                    throw new IOException("APK ultrapassa 1 GiB");
                digest.update(buffer, 0, n);
            }
        }
        StringBuilder hex = new StringBuilder(64);
        for (byte b : digest.digest())
            hex.append(String.format(java.util.Locale.ROOT, "%02x", b & 0xff));
        return hex.toString();
    }
}
