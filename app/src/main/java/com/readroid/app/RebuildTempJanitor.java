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
 * F1.16: bounded best-effort recovery of orphaned unsigned-export staging.
 * Only exact internal temporary-file name families are eligible, directly
 * inside the app's PRIVATE cache directory. No directory traversal, links,
 * user-selected SAF documents, imported APKs, or recovery vault files.
 *
 * A conservative age threshold protects fresh files left by a process death.
 * Active leases protect in-progress exports, including older long operations.
 * Failure to delete only defers cleanup until a future start.
 */
final class RebuildTempJanitor {
    static final long MIN_STALE_AGE_MS = 24L * 60 * 60 * 1000;
    static final int MAX_SCANNED = 4096;
    static final int MAX_DELETED = 64;

    private static final String EXPORT_PREFIX = "readroid_unsigned_";
    private static final String EXPORT_SUFFIX = ".apk";
    private static final String STAGING_PREFIX = "readroid-rebuild-";
    private static final String STAGING_SUFFIX = ".tmp";
    private static final Set<Path> ACTIVE = ConcurrentHashMap.newKeySet();

    private RebuildTempJanitor() {}

    static void track(File temporary) {
        if (temporary != null) ACTIVE.add(temporary.toPath().toAbsolutePath().normalize());
    }

    static void release(File temporary) {
        if (temporary != null) ACTIVE.remove(temporary.toPath().toAbsolutePath().normalize());
    }

    static final class Result {
        final int scanned;
        final int deleted;
        final int failed;

        Result(int scanned, int deleted, int failed) {
            this.scanned = scanned;
            this.deleted = deleted;
            this.failed = failed;
        }
    }

    static Result sweep(File privateCache) {
        return sweep(privateCache, System.currentTimeMillis(), MIN_STALE_AGE_MS);
    }

    // Deterministic test seam for age checks; production always uses 24 hours.
    static Result sweep(File privateCache, long nowMillis, long minAgeMillis) {
        if (privateCache == null || nowMillis <= 0 || minAgeMillis < MIN_STALE_AGE_MS)
            return new Result(0, 0, 1);
        Path root = privateCache.toPath();
        if (!Files.isDirectory(root, LinkOption.NOFOLLOW_LINKS))
            return new Result(0, 0, 1);

        int scanned = 0;
        int deleted = 0;
        int failed = 0;
        try (DirectoryStream<Path> children = Files.newDirectoryStream(root)) {
            for (Path child : children) {
                if (++scanned > MAX_SCANNED || deleted >= MAX_DELETED) break;
                if (!recognized(child.getFileName().toString())) continue;
                Path path = child.toAbsolutePath().normalize();
                if (ACTIVE.contains(path)) continue;
                try {
                    if (!Files.isRegularFile(child, LinkOption.NOFOLLOW_LINKS)) continue;
                    long modified = Files.getLastModifiedTime(child,
                        LinkOption.NOFOLLOW_LINKS).toMillis();
                    if (modified <= 0 || modified > nowMillis
                            || nowMillis - modified < minAgeMillis) continue;
                    // Delete only this direct child, never walk into directories.
                    if (Files.deleteIfExists(child)) deleted++;
                } catch (IOException | SecurityException inaccessible) {
                    failed++;
                }
            }
        } catch (IOException | SecurityException inaccessible) {
            failed++;
        }
        return new Result(Math.min(scanned, MAX_SCANNED), deleted, failed);
    }

    private static boolean recognized(String filename) {
        final String token;
        if (filename.startsWith(EXPORT_PREFIX) && filename.endsWith(EXPORT_SUFFIX)) {
            token = filename.substring(EXPORT_PREFIX.length(),
                filename.length() - EXPORT_SUFFIX.length());
        } else if (filename.startsWith(STAGING_PREFIX)
                && filename.endsWith(STAGING_SUFFIX)) {
            token = filename.substring(STAGING_PREFIX.length(),
                filename.length() - STAGING_SUFFIX.length());
        } else {
            return false;
        }
        // File.createTempFile generates a random suffix, not an empty name or
        // a user-provided label. Enforce a narrow ASCII token, not a glob.
        if (token.length() < 6 || token.length() > 64) return false;
        for (int i = 0; i < token.length(); i++) {
            char c = token.charAt(i);
            if ((c < '0' || c > '9') && (c < 'A' || c > 'Z')
                    && (c < 'a' || c > 'z') && c != '_' && c != '-')
                return false;
        }
        return true;
    }
}
