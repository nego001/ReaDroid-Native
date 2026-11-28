package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.HashSet;
import java.util.Set;

/**
 * F1.25: lifecycle ownership for uncommitted SAF-import APK staging files.
 *
 * A ContentProvider can block inside read() even after Activity.onDestroy().
 * Invalidating an import token alone cannot unlink its unfinished cache file
 * until that provider returns. This scope tracks ONLY files explicitly created
 * by the old Activity's staging operation in its PRIVATE cache root.
 *
 * On close, unlink owned temporary APK paths (never accepted projects,
 * directories, links, SQLite files, unrelated cache entries or SAF documents).
 * A blocked provider may still hold the inode via an open descriptor; on
 * Android/Linux the path disappears, and the token rejects the late return.
 * No recursion or glob cleanup.
 */
final class ImportActivityScope implements AutoCloseable {
    private static final int MAX_OWNED = 4;
    private final Path root;
    private final Set<Path> pending = new HashSet<>();
    private boolean closed;

    ImportActivityScope(File privateCache) {
        if (privateCache == null) throw new IllegalArgumentException("Private cache required");
        this.root = privateCache.toPath().toAbsolutePath().normalize();
    }

    synchronized void track(File candidate) throws IOException {
        Path path = requireOwnedCandidate(candidate);
        if (closed) {
            try {
                Files.deleteIfExists(path);
            } finally {
                ImportCacheAudit.release(candidate);
            }
            throw new InterruptedIOException("A Activity antiga já foi encerrada");
        }
        if (!pending.contains(path) && pending.size() >= MAX_OWNED)
            throw new IOException("Limite de arquivos temporários da importação atingido");
        pending.add(path);
    }

    /**
     * Open the already tracked inode before calling an untrusted SAF provider.
     * Both acquisition and onDestroy() cleanup hold this same monitor, so a
     * provider returning late from open() cannot recreate an unlinked path.
     * CREATE is intentionally omitted and links are not followed.
     */
    synchronized OutputStream openForWrite(File candidate) throws IOException {
        if (closed)
            throw new InterruptedIOException("A Activity antiga já foi encerrada");
        Path path = requireOwnedCandidate(candidate);
        if (!pending.contains(path))
            throw new IOException("Candidato SAF não pertence a esta Activity");
        return Files.newOutputStream(path, StandardOpenOption.WRITE,
            StandardOpenOption.TRUNCATE_EXISTING, LinkOption.NOFOLLOW_LINKS);
    }

    /**
     * Atomic handoff from partial copy to a fully copied private APK. This is
     * NOT project acceptance; the returned APK remains tracked and disposable
     * until MainActivity has validated ZIP, index and UI project commit.
     */
    synchronized File promote(File partial, ExportSessionGuard.Token token)
            throws IOException {
        if (closed)
            throw new InterruptedIOException("A Activity antiga já foi encerrada");
        Path source = requireOwnedCandidate(partial);
        String name = source.getFileName().toString();
        if (!name.endsWith(".apk.pending") || !pending.contains(source))
            throw new IOException("Arquivo parcial não pertence à importação atual");
        ExportSessionGuard.check(token);
        Path destination = root.resolve(name.substring(
            0, name.length() - ".pending".length()));
        if (Files.exists(destination, LinkOption.NOFOLLOW_LINKS))
            throw new IOException("APK privado já existe; substituição recusada");
        // Source and target are siblings in the same private cache filesystem.
        // Do not silently fall back to a potentially non-atomic move.
        Files.move(source, destination, StandardCopyOption.ATOMIC_MOVE);
        pending.remove(source);
        pending.add(destination);
        ImportCacheAudit.release(partial);
        ImportCacheAudit.track(destination.toFile());
        return destination.toFile();
    }

    synchronized void release(File candidate) {
        if (candidate != null)
            pending.remove(candidate.toPath().toAbsolutePath().normalize());
    }

    synchronized boolean isClosed() { return closed; }

    synchronized int pendingCount() { return pending.size(); }

    @Override public synchronized void close() {
        if (closed) return;
        closed = true;
        for (Path path : pending) {
            try {
                if (eligible(path))
                    Files.deleteIfExists(path);
            } catch (IOException | SecurityException ignored) {
                // A late worker's transactional finally can retry cleanup.
            } finally {
                ImportCacheAudit.release(path.toFile());
            }
        }
        pending.clear();
    }

    private Path requireOwnedCandidate(File candidate) throws IOException {
        if (candidate == null) throw new IOException("Candidato SAF ausente");
        Path path = candidate.toPath().toAbsolutePath().normalize();
        if (!eligible(path))
            throw new IOException("Candidato SAF fora do cache privado ou não é temporário");
        return path;
    }

    private boolean eligible(Path path) {
        if (!root.equals(path.getParent())
                || !Files.isDirectory(root, LinkOption.NOFOLLOW_LINKS)
                || !Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS))
            return false;
        String name = path.getFileName().toString();
        if (!name.startsWith("readroid_")) return false;
        String expected = name.endsWith(".apk.pending")
            ? name.substring(0, name.length() - ".pending".length()) : name;
        if (!expected.endsWith(".apk")) return false;
        String random = expected.substring("readroid_".length(),
            expected.length() - ".apk".length());
        if (random.length() < 6 || random.length() > 64) return false;
        for (int i = 0; i < random.length(); i++) {
            char c = random.charAt(i);
            if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
                    || (c >= '0' && c <= '9') || c == '-'))
                return false;
        }
        return true;
    }
}
