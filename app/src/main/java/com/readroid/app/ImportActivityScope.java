package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
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
        if (!name.startsWith("readroid_") || !name.endsWith(".apk"))
            return false;
        String random = name.substring("readroid_".length(), name.length() - ".apk".length());
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
