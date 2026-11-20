package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;

/**
 * F1.26: cold-start removal of unmistakably unfinished SAF copy files.
 *
 * Invoked exactly ONCE per Android process before any new import can start;
 * never on ordinary Activity recreation. Only our private cache's immediate
 * regular readroid_<random>.apk.pending entries qualify. Completed .apk,
 * SQLite, recovery, links, directories, nested paths and SAF source documents
 * are never candidates. A bounded scan cannot recursively prune user data.
 */
final class ImportCrashJanitor {
    static final int MAX_SCANNED = 1024;

    static final class Report {
        final int scanned;
        final int deleted;
        final int errors;
        final boolean incomplete;

        Report(int scanned, int deleted, int errors, boolean incomplete) {
            this.scanned = scanned;
            this.deleted = deleted;
            this.errors = errors;
            this.incomplete = incomplete;
        }
    }

    private ImportCrashJanitor() {}

    static boolean pendingName(String name) {
        if (name == null || !name.startsWith("readroid_")
                || !name.endsWith(".apk.pending")) return false;
        String id = name.substring("readroid_".length(),
            name.length() - ".apk.pending".length());
        if (id.length() < 6 || id.length() > 64) return false;
        for (int i = 0; i < id.length(); i++) {
            char c = id.charAt(i);
            if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
                    || (c >= '0' && c <= '9') || c == '-')) return false;
        }
        return true;
    }

    static Report sweep(File privateCache) {
        if (privateCache == null) return new Report(0, 0, 1, true);
        Path root = privateCache.toPath().toAbsolutePath().normalize();
        if (!Files.isDirectory(root, LinkOption.NOFOLLOW_LINKS))
            return new Report(0, 0, 1, true);
        int scanned = 0, deleted = 0, errors = 0;
        boolean incomplete = false;
        try (DirectoryStream<Path> children = Files.newDirectoryStream(root)) {
            for (Path path : children) {
                if (scanned >= MAX_SCANNED) { incomplete = true; break; }
                scanned++;
                if (!pendingName(path.getFileName().toString())) continue;
                try {
                    if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS))
                        continue;
                    if (Files.deleteIfExists(path)) deleted++;
                } catch (IOException | SecurityException error) {
                    errors++;
                    incomplete = true;
                }
            }
        } catch (IOException | SecurityException error) {
            errors++;
            incomplete = true;
        }
        return new Report(scanned, deleted, errors, incomplete);
    }
}
