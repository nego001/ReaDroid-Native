package com.readroid.app;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import android.system.StructStat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileDescriptor;
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
    private final RecoveryStorageBudget.FreeSpace freeSpace;
    private final StageReadObserver stageReadObserver;
    private final BeforeMove beforeMove;
    private final AfterAtomicMove afterAtomicMove;
    private final AfterDirectorySync afterDirectorySync;

    /** Failure injection for Android instrumented tests, never user-controlled. */
    interface BeforeCommit {
        void run(File staged) throws IOException;
    }

    /** Package-private CI seam: observe a verified chunk, no user callback. */
    interface StageReadObserver {
        void onChunk(int bytesVerified, int totalBytes) throws IOException;
    }

    /** F1.36 pre-move fault injection: only package-private instrumentation. */
    interface BeforeMove {
        void run(File verifiedStage) throws IOException;
    }

    /**
     * F1.39 CI-only seam, called AFTER successful ATOMIC_MOVE and BEFORE
     * directory fsync. Production installs a no-op; never user controlled.
     * The previous checkpoint is already replaced at this boundary.
     */
    interface AfterAtomicMove {
        void run(File promotedCheckpoint) throws IOException;
    }

    /**
     * F1.40 package-private CI probe. Fires only AFTER directory fsync
     * returns, and BEFORE final content/inode verification. Production
     * installs a no-op observer; never exposed to user input.
     */
    interface AfterDirectorySync {
        void run(File promotedCheckpoint) throws IOException;
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
        this(storage, alias, beforeCommit,
            RecoveryStorageBudget.forDirectory(storage));
    }

    /** Deterministic free-space changes are injected only by instrumentation. */
    RecoveryVault(File storage, String alias, BeforeCommit beforeCommit,
            RecoveryStorageBudget.FreeSpace freeSpace) {
        this(storage, alias, beforeCommit, freeSpace,
            (verified, total) -> {});
    }

    /**
     * Package-private seam for deterministic stage-verification interruption
     * in isolated Android tests. Production always uses the no-op observer.
     */
    RecoveryVault(File storage, String alias, BeforeCommit beforeCommit,
            RecoveryStorageBudget.FreeSpace freeSpace,
            StageReadObserver stageReadObserver) {
        this(storage, alias, beforeCommit, freeSpace, stageReadObserver,
            stage -> {});
    }

    /** F1.36 test seam; production has a no-op before-move observer. */
    RecoveryVault(File storage, String alias, BeforeCommit beforeCommit,
            RecoveryStorageBudget.FreeSpace freeSpace,
            StageReadObserver stageReadObserver, BeforeMove beforeMove) {
        this(storage, alias, beforeCommit, freeSpace, stageReadObserver,
            beforeMove, checkpoint -> {});
    }

    /** Isolated F1.39 fault injection; all production constructors use no-op. */
    RecoveryVault(File storage, String alias, BeforeCommit beforeCommit,
            RecoveryStorageBudget.FreeSpace freeSpace,
            StageReadObserver stageReadObserver, BeforeMove beforeMove,
            AfterAtomicMove afterAtomicMove) {
        this(storage, alias, beforeCommit, freeSpace, stageReadObserver,
            beforeMove, afterAtomicMove, checkpoint -> {});
    }

    /** F1.40 isolated post-fsync injection. Not used by production callers. */
    RecoveryVault(File storage, String alias, BeforeCommit beforeCommit,
            RecoveryStorageBudget.FreeSpace freeSpace,
            StageReadObserver stageReadObserver, BeforeMove beforeMove,
            AfterAtomicMove afterAtomicMove, AfterDirectorySync afterDirectorySync) {
        if (storage == null || alias == null || alias.isEmpty()
                || beforeCommit == null || freeSpace == null
                || stageReadObserver == null || beforeMove == null
                || afterAtomicMove == null || afterDirectorySync == null)
            throw new IllegalArgumentException("Armazenamento de recuperação inválido");
        this.storage = storage;
        this.alias = alias;
        this.beforeCommit = beforeCommit;
        this.freeSpace = freeSpace;
        this.stageReadObserver = stageReadObserver;
        this.beforeMove = beforeMove;
        this.afterAtomicMove = afterAtomicMove;
        this.afterDirectorySync = afterDirectorySync;
    }

    public boolean hasCheckpoint() {
        synchronized (IN_PROCESS_LOCK) {
            return new File(storage, FILE_NAME).isFile();
        }
    }

    public void clear() throws IOException {
        synchronized (IN_PROCESS_LOCK) {
            // Explicit user deletion also removes encrypted, possibly recent
            // staging files. Never report success if cleanup is incomplete.
            // The old checkpoint remains available if cleanup fails.
            clearEncryptedStages(storage);
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
        RecoveryDirectoryGuard pinnedDirectory = null;
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
            // Pin THIS directory before staging bytes, refuse symlink roots.
            // The final path may not be rebound during the transaction.
            pinnedDirectory = RecoveryDirectoryGuard.open(storage);
            // Refuse low-space saves BEFORE staging new ciphertext. Never
            // touch an already committed checkpoint on budget failure.
            RecoveryStorageBudget.requireStagingRoom(freeSpace, encoded.length);
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
            // Recheck AFTER fsync and callback, just before atomic promotion:
            // free space may have vanished while the encrypted file was saved.
            RecoveryStorageBudget.requireStagingRoom(freeSpace, encoded.length);
            // F1.34: a synced temporary is not necessarily an intact one.
            // Re-read the exact encrypted bytes before replacing the last
            // usable recovery checkpoint, and refuse swapped symlinks.
            verifyStagedCiphertext(temporary, encoded, stageReadObserver);
            // F1.36: remember the actual inode, not just the path's bytes.
            // An identical-byte replacement must not silently inherit the
            // permission to become the new recovery checkpoint.
            final StageIdentity verifiedIdentity = stageIdentity(temporary);
            beforeMove.run(temporary);
            if (Thread.currentThread().isInterrupted())
                throw new InterruptedIOException("Confirmação da recuperação interrompida");
            pinnedDirectory.requireSameDirectory();
            // Recheck AFTER any intervening work and directly BEFORE rename.
            // No untrusted callback may run between this second read and move.
            verifyStagedCiphertext(temporary, encoded, (verified, total) -> {});
            if (!verifiedIdentity.sameFile(stageIdentity(temporary)))
                throw new IOException("Arquivo temporário substituído antes da confirmação");
            pinnedDirectory.requireSameDirectory();
            if (Thread.currentThread().isInterrupted())
                throw new InterruptedIOException("Confirmação da recuperação interrompida");
            try {
                Files.move(temporary.toPath(), new File(storage, FILE_NAME).toPath(),
                    StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            } catch (AtomicMoveNotSupportedException unavailable) {
                throw new IOException("Armazenamento sem troca atômica segura", unavailable);
            }
            // An atomic move is the commit boundary: never automatically
            // roll back or delete the new checkpoint on post-move errors.
            committed = true;
            // F1.39: deliberately terminate a disposable CI process HERE:
            // the new ciphertext is already promoted, but directory fsync
            // has not been invoked. An exception cannot roll back this move.
            afterAtomicMove.run(new File(storage, FILE_NAME));
            pinnedDirectory.syncAfterRename();
            // F1.40: a force-stop at this test-only callback occurs AFTER
            // the directory fsync, not at the F1.39 pre-sync boundary.
            File promotedCheckpoint = new File(storage, FILE_NAME);
            afterDirectorySync.run(promotedCheckpoint);
            pinnedDirectory.requireSameDirectory();
            StageIdentity promoted = stageIdentity(promotedCheckpoint);
            if (!verifiedIdentity.sameFile(promoted)
                    || promoted.size != encoded.length)
                throw new IOException("Identidade do checkpoint promovido divergiu");
            // Inode and length alone cannot detect a same-size bit flip
            // after fsync. Reopen with O_NOFOLLOW and attest all ciphertext.
            // A failure here is POST-commit: it must never claim rollback.
            verifyStagedCiphertext(promotedCheckpoint, encoded,
                (verified, total) -> {});
        } finally {
            if (!committed && temporary != null) temporary.delete();
            try {
                if (pinnedDirectory != null) pinnedDirectory.close();
            } finally {
                Arrays.fill(plaintext, (byte) 0);
                if (encrypted != null) Arrays.fill(encrypted, (byte) 0);
                if (encoded != null) Arrays.fill(encoded, (byte) 0);
            }
        }
    }

    /**
     * F1.34: verify staged encrypted bytes against those actually produced by
     * AES-GCM, before the atomic rename. This covers truncated / tampered /
     * vanished temporary files, and does not follow symlinks even if the
     * symlink points to matching bytes.
     *
     * A process-local transaction lock still guards concurrent vault calls.
     * This is not a power-loss proof or a defense against processes with
     * filesystem write access racing the final rename.
     */
    private static void verifyStagedCiphertext(File stage, byte[] expected,
            StageReadObserver observer) throws IOException {
        if (stage == null || expected == null || expected.length < 33)
            throw new IOException("Estágio criptografado inválido");
        Path path = stage.toPath();
        if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)
                || Files.size(path) != expected.length)
            throw new IOException("Estágio criptografado incompleto ou substituído");
        byte[] chunk = new byte[8192];
        int mismatch = 0;
        int offset = 0;
        // F1.37: O_NOFOLLOW binds the read to ONE inode. Merely testing
        // Files.isRegularFile(path) before Files.newInputStream(path) leaves
        // a gap in which an identical-byte replacement could become the
        // stream source without being noticed by the path-only checks.
        try (FileInputStream in = new FileInputStream(Os.open(
                stage.getAbsolutePath(),
                OsConstants.O_RDONLY | OsConstants.O_CLOEXEC
                    | OsConstants.O_NOFOLLOW, 0))) {
            StageIdentity opened = stageIdentity(in.getFD());
            if (!opened.sameFile(stageIdentity(stage))
                    || opened.size != expected.length)
                throw new IOException("Arquivo de estágio substituído na abertura");
            while (offset < expected.length) {
                if (Thread.currentThread().isInterrupted())
                    throw new InterruptedIOException("Verificação do estágio interrompida");
                int n = in.read(chunk, 0, Math.min(chunk.length,
                    expected.length - offset));
                if (n <= 0)
                    throw new IOException("Leitura incompleta do estágio criptografado");
                for (int i = 0; i < n; i++)
                    mismatch |= chunk[i] ^ expected[offset + i];
                offset += n;
                // F1.35 still observes real first-block reads. F1.37
                // additionally catches path swaps AND new hardlinks made
                // while this pinned descriptor is held open.
                observer.onChunk(offset, expected.length);
                if (Thread.currentThread().isInterrupted())
                    throw new InterruptedIOException(
                        "Verificação do estágio interrompida");
            }
            if (in.read() != -1)
                throw new IOException("Estágio criptografado cresceu durante a leitura");
            if (!opened.sameFile(stageIdentity(in.getFD()))
                    || !opened.sameFile(stageIdentity(stage)))
                throw new IOException("Identidade do estágio mudou durante a leitura");
        } catch (ErrnoException unreadable) {
            throw new IOException("Não foi possível abrir estágio sem seguir links",
                unreadable);
        } finally {
            Arrays.fill(chunk, (byte) 0);
        }
        if (mismatch != 0
                || !Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)
                || Files.size(path) != expected.length)
            throw new IOException("Conteúdo do estágio criptografado foi alterado");
    }

    /**
     * Linux device/inode identity is reliable on Android's private filesystems.
     * Requiring it supplements byte equality: a newly renamed file containing
     * identical bytes must still be rejected after initial verification.
     * A fully hostile same-UID actor racing between final stat and rename
     * remains outside this guarantee.
     */
    private static StageIdentity stageIdentity(File staged) throws IOException {
        try {
            StructStat stat = Os.lstat(staged.getAbsolutePath());
            if (!Files.isRegularFile(staged.toPath(), LinkOption.NOFOLLOW_LINKS))
                throw new IOException("Estágio deixou de ser arquivo regular");
            return checkedStageIdentity(stat);
        } catch (ErrnoException badStage) {
            throw new IOException("Não foi possível conferir identidade do estágio",
                badStage);
        }
    }

    private static StageIdentity stageIdentity(FileDescriptor openDescriptor)
            throws IOException {
        try {
            return checkedStageIdentity(Os.fstat(openDescriptor));
        } catch (ErrnoException badStage) {
            throw new IOException("Não foi possível conferir descritor do estágio",
                badStage);
        }
    }

    private static StageIdentity checkedStageIdentity(StructStat stat)
            throws IOException {
        // A second hardlink aliases this ciphertext under another path.
        // A same-UID writer could mutate that alias AFTER the move and
        // destroy the user's last recoverable checkpoint. Fail closed.
        if (!OsConstants.S_ISREG(stat.st_mode))
            throw new IOException("Estágio criptografado não é arquivo regular");
        requireSingleStageLinkCount(stat.st_nlink);
        return new StageIdentity(stat.st_dev, stat.st_ino, stat.st_size);
    }

    /** Pure link-count policy, exercised even if an emulator forbids hardlink(). */
    static void requireSingleStageLinkCount(long count) throws IOException {
        if (count != 1L)
            throw new IOException("Estágio não regular ou com múltiplos links");
    }

    private static final class StageIdentity {
        final long device;
        final long inode;
        final long size;
        StageIdentity(long device, long inode, long size) {
            this.device = device;
            this.inode = inode;
            this.size = size;
        }
        boolean sameFile(StageIdentity other) {
            return other != null && device == other.device && inode == other.inode;
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
     * Explicit removal of encrypted staging files, including recent leftovers
     * after a process crash. IN_PROCESS_LOCK must be held by the caller.
     * Refuse overly large directories instead of claiming a complete clear.
     * Preserve directories, symlinks and non-matching private files.
     */
    private static void clearEncryptedStages(File directory) throws IOException {
        if (!Files.isDirectory(directory.toPath(), LinkOption.NOFOLLOW_LINKS))
            return;
        // Preflight the number of matching names without modifying anything.
        // Previously the 257th candidate was detected only after up to 256
        // earlier stages had already been deleted.
        int inspected = 0;
        try (DirectoryStream<Path> entries =
                Files.newDirectoryStream(directory.toPath(), "checkpoint-*.tmp")) {
            for (Path ignored : entries) {
                if (Thread.currentThread().isInterrupted())
                    throw new InterruptedIOException("Exclusão da recuperação interrompida");
                if (++inspected > MAX_STAGE_SCAN)
                    throw new IOException("Arquivos temporários demais para exclusão segura");
            }
        } catch (DirectoryIteratorException failed) {
            throw new IOException("Não foi possível contar os arquivos temporários", failed);
        }
        try (DirectoryStream<Path> entries =
                Files.newDirectoryStream(directory.toPath(), "checkpoint-*.tmp")) {
            for (Path candidate : entries) {
                if (Thread.currentThread().isInterrupted())
                    throw new InterruptedIOException("Exclusão da recuperação interrompida");
                if (!Files.isRegularFile(candidate, LinkOption.NOFOLLOW_LINKS))
                    continue;
                Files.deleteIfExists(candidate);
            }
        } catch (DirectoryIteratorException failed) {
            throw new IOException("Não foi possível limpar os arquivos temporários", failed);
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
