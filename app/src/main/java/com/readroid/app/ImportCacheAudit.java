package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * F1.17: read-only audit of private imported APK caches and their SQLite indexes.
 *
 * An import without an index can be VALID (small APKs use no SQLite index).
 * An older import can still be recoverable. Therefore this class NEVER
 * deletes, moves, opens SQLite for writing, or mutates a user/project file.
 * It only emits aggregate counters, with no user-specific paths or names.
 */
final class ImportCacheAudit {
    static final long REVIEW_AGE_MS = 7L * 24 * 60 * 60 * 1000;
    static final int MAX_SCANNED = 4096;
    private static final String APK_PREFIX = "readroid_";
    private static final String APK_SUFFIX = ".apk";
    private static final String INDEX_SUFFIX = ".apk.idx.db";
    private static final Set<Path> ACTIVE = ConcurrentHashMap.newKeySet();

    private ImportCacheAudit() {}

    static void track(File file) {
        if (file != null) ACTIVE.add(file.toPath().toAbsolutePath().normalize());
    }

    static void release(File file) {
        if (file != null) ACTIVE.remove(file.toPath().toAbsolutePath().normalize());
    }

    static final class Report {
        final int scanned;
        final int importedApks;
        final int sqliteIndexes;
        final int indexWithoutApk;
        final int importsWithoutIndex;
        final int activeOrRetained;
        final int oldCandidates;
        final int errors;
        final long countedBytes;
        final boolean incomplete;

        Report(int scanned, int importedApks, int sqliteIndexes,
                int indexWithoutApk, int importsWithoutIndex,
                int activeOrRetained, int oldCandidates, int errors,
                long countedBytes, boolean incomplete) {
            this.scanned = scanned;
            this.importedApks = importedApks;
            this.sqliteIndexes = sqliteIndexes;
            this.indexWithoutApk = indexWithoutApk;
            this.importsWithoutIndex = importsWithoutIndex;
            this.activeOrRetained = activeOrRetained;
            this.oldCandidates = oldCandidates;
            this.errors = errors;
            this.countedBytes = countedBytes;
            this.incomplete = incomplete;
        }
    }

    static Report inspect(File privateCache, File retainedApk, File retainedIndex) {
        return inspect(privateCache, retainedApk, retainedIndex, System.currentTimeMillis());
    }

    // Deterministic time seam for Android instrumentation (no destructive scan).
    static Report inspect(File privateCache, File retainedApk, File retainedIndex,
            long nowMillis) {
        if (privateCache == null || nowMillis <= 0)
            return new Report(0,0,0,0,0,0,0,1,0,true);
        Path root = privateCache.toPath().toAbsolutePath().normalize();
        if (!Files.isDirectory(root, LinkOption.NOFOLLOW_LINKS))
            return new Report(0,0,0,0,0,0,0,1,0,true);
        Path retainedApkPath = normalize(retainedApk);
        Path retainedIndexPath = normalize(retainedIndex);
        int scanned = 0, imports = 0, indexes = 0, indexWithout = 0,
            importsWithout = 0, retained = 0, old = 0, errors = 0;
        long bytes = 0;
        boolean incomplete = false;
        try (DirectoryStream<Path> children = Files.newDirectoryStream(root)) {
            for (Path child : children) {
                if (scanned >= MAX_SCANNED) { incomplete = true; break; }
                scanned++;
                String name = child.getFileName().toString();
                boolean apk = importedApkName(name);
                boolean index = importedIndexName(name);
                if (!apk && !index) continue;
                try {
                    // Never follow a symlink, including an apparent SQLite file.
                    if (!Files.isRegularFile(child, LinkOption.NOFOLLOW_LINKS)) continue;
                    Path canonical = child.toAbsolutePath().normalize();
                    long size = Files.size(child);
                    bytes = size > Long.MAX_VALUE - bytes ? Long.MAX_VALUE : bytes + size;
                    boolean active = canonical.equals(retainedApkPath)
                        || canonical.equals(retainedIndexPath) || ACTIVE.contains(canonical);
                    if (active) retained++;
                    long modified = Files.getLastModifiedTime(child,
                        LinkOption.NOFOLLOW_LINKS).toMillis();
                    if (!active && modified > 0 && modified <= nowMillis
                            && nowMillis - modified >= REVIEW_AGE_MS) old++;
                    if (apk) {
                        imports++;
                        // Missing index is NORMAL for small APKs; never call it orphaned.
                        if (!Files.isRegularFile(
                                root.resolve(name + ".idx.db"), LinkOption.NOFOLLOW_LINKS))
                            importsWithout++;
                    } else {
                        indexes++;
                        String importedName = name.substring(0,
                            name.length() - ".idx.db".length());
                        if (!Files.isRegularFile(root.resolve(importedName),
                                LinkOption.NOFOLLOW_LINKS)) indexWithout++;
                    }
                } catch (IOException | SecurityException unavailable) {
                    errors++;
                    incomplete = true;
                }
            }
        } catch (IOException | SecurityException unavailable) {
            errors++;
            incomplete = true;
        }
        return new Report(scanned, imports, indexes, indexWithout, importsWithout,
            retained, old, errors, bytes, incomplete);
    }

    private static Path normalize(File f) {
        return f == null ? null : f.toPath().toAbsolutePath().normalize();
    }

    private static boolean importedIndexName(String name) {
        if (!name.endsWith(INDEX_SUFFIX)) return false;
        return importedApkName(name.substring(0, name.length() - ".idx.db".length()));
    }

    private static boolean importedApkName(String name) {
        if (!name.startsWith(APK_PREFIX) || !name.endsWith(APK_SUFFIX))
            return false;
        // Distinguish imported cache names from export staging and test names.
        String token = name.substring(APK_PREFIX.length(),
            name.length() - APK_SUFFIX.length());
        if (token.length() < 6 || token.length() > 64) return false;
        for (int i = 0; i < token.length(); i++) {
            char c = token.charAt(i);
            if ((c < '0' || c > '9') && (c < 'A' || c > 'Z')
                    && (c < 'a' || c > 'z') && c != '-') return false;
        }
        return true;
    }
}
