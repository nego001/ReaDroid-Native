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
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.nio.file.AtomicMoveNotSupportedException;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.LinkedHashMap;
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
    private static final byte[] AAD = "NegrescoDroid:recovery:v1"
        .getBytes(StandardCharsets.US_ASCII);

    private final File storage;
    private final String alias;

    public RecoveryVault(Context context) {
        this(new File(context.getFilesDir(), "v3-private-recovery"), KEY_ALIAS);
    }

    /** Isolated folder and key alias for instrumentation only. */
    RecoveryVault(File storage, String alias) {
        if (storage == null || alias == null || alias.isEmpty())
            throw new IllegalArgumentException("Armazenamento de recuperação inválido");
        this.storage = storage;
        this.alias = alias;
    }

    public boolean hasCheckpoint() {
        return new File(storage, FILE_NAME).isFile();
    }

    public void clear() throws IOException {
        File backup = new File(storage, FILE_NAME);
        if (backup.exists() && !backup.delete())
            throw new IOException("Não foi possível remover a cópia de recuperação");
    }

    public void save(File sourceApk, Map<String, String> changes) throws Exception {
        String fingerprint = sha256(sourceApk);
        if (changes == null || changes.isEmpty() || changes.size() > MAX_CHANGES)
            throw new IllegalArgumentException("O plano deve ter de 1 a 100 alterações");
        EditPlan plan = new EditPlan();
        for (Map.Entry<String, String> entry : changes.entrySet())
            plan.addTextReplacement(entry.getKey(), entry.getValue());
        JSONObject payload = plan.toJson();
        payload.put("sourceSha256", fingerprint);
        byte[] plaintext = payload.toString().getBytes(StandardCharsets.UTF_8);
        if (plaintext.length > MAX_PLAINTEXT)
            throw new IllegalArgumentException("Plano excede o limite de 512 KiB");
        SecretKey key = obtainKey();
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key);
        cipher.updateAAD(AAD);
        byte[] iv = cipher.getIV();
        if (iv == null || iv.length != 12)
            throw new IOException("Vetor criptográfico inesperado");
        byte[] encrypted = cipher.doFinal(plaintext);
        ByteBuffer buffer = ByteBuffer.allocate(MAGIC.length + 1 + iv.length + encrypted.length);
        buffer.put(MAGIC).put(VERSION).put(iv).put(encrypted);
        if (!storage.isDirectory() && !storage.mkdirs())
            throw new IOException("Não foi possível criar o diretório privado");
        File temporary = File.createTempFile("checkpoint-", ".tmp", storage);
        boolean committed = false;
        try {
            try (FileOutputStream out = new FileOutputStream(temporary)) {
                out.write(buffer.array());
                out.getFD().sync();
            }
            try {
                Files.move(temporary.toPath(), new File(storage, FILE_NAME).toPath(),
                    StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            } catch (AtomicMoveNotSupportedException unavailable) {
                throw new IOException("Armazenamento sem troca atômica segura", unavailable);
            }
            committed = true;
        } finally {
            if (!committed) temporary.delete();
            Arrays.fill(plaintext, (byte) 0);
        }
    }

    /** Pure read/verification: caller must get consent before modifying live EditPlan. */
    public Map<String, String> loadForSource(File sourceApk) throws Exception {
        String fingerprint = sha256(sourceApk);
        File file = new File(storage, FILE_NAME);
        if (!file.isFile() || file.length() < 4 + 1 + 12 + 16
            || file.length() > MAX_FILE)
            throw new IOException("Cópia de recuperação ausente ou inválida");
        byte[] encoded = Files.readAllBytes(file.toPath());
        ByteBuffer input = ByteBuffer.wrap(encoded);
        for (byte b : MAGIC) {
            if (input.get() != b) throw new IOException("Formato de cópia incompatível");
        }
        if (input.get() != VERSION) throw new IOException("Versão de cópia incompatível");
        byte[] iv = new byte[12];
        input.get(iv);
        byte[] ciphertext = new byte[input.remaining()];
        input.get(ciphertext);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, obtainKey(), new GCMParameterSpec(128, iv));
        cipher.updateAAD(AAD);
        byte[] plaintext = cipher.doFinal(ciphertext); // rejects tampering before JSON parsing
        try {
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
            Arrays.fill(plaintext, (byte) 0);
        }
    }

    private SecretKey obtainKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        java.security.Key existing = store.getKey(alias, null);
        if (existing != null) {
            if (!(existing instanceof SecretKey))
                throw new SecurityException("Identidade criptográfica incompatível");
            return (SecretKey) existing;
        }
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
