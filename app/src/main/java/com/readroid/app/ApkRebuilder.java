package com.readroid.app;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;

/** Experimental unsigned APK ZIP rebuild. Never changes the original input. */
public final class ApkRebuilder {
    private ApkRebuilder() {}

    /** Package-private seam: tests can revoke export session mid-ZIP. */
    interface CopiedChunkObserver {
        void onCopied(String path, long bytes) throws IOException;
    }

    /** Test-only injection point, never passed by production UI callers. */
    interface BeforeStageVerification {
        void run(File staged) throws IOException;
    }

    public static void rebuild(File original, File destination, Map<String, String> edits)
            throws IOException {
        rebuild(original, destination, edits, (ExportSessionGuard.Token) null);
    }

    static void rebuild(File original, File destination, Map<String, String> edits,
            ExportSessionGuard.Token token) throws IOException {
        rebuild(original, destination, edits, staged -> {},
            RebuildStorageBudget.forDirectory(destination == null
                ? null : destination.getAbsoluteFile().getParentFile()),
            token, (path, bytes) -> {});
    }

    // F1.10 tests can simulate a damaged staging archive before final commit.
    static void rebuild(File original, File destination, Map<String, String> edits,
            BeforeStageVerification beforeVerify) throws IOException {
        rebuild(original, destination, edits, beforeVerify,
            RebuildStorageBudget.forDirectory(destination == null
                ? null : destination.getAbsoluteFile().getParentFile()),
            null, (path, bytes) -> {});
    }

    // F1.11: deterministic free-space seam for instrumented low-storage tests.
    static void rebuild(File original, File destination, Map<String, String> edits,
            BeforeStageVerification beforeVerify, RebuildStorageBudget.FreeSpace space)
            throws IOException {
        rebuild(original, destination, edits, beforeVerify, space,
            null, (path, bytes) -> {});
    }

    // F1.15: propagate cancellation to CRC, SHA, and each copied ZIP chunk.
    static void rebuild(File original, File destination, Map<String, String> edits,
            BeforeStageVerification beforeVerify, RebuildStorageBudget.FreeSpace space,
            ExportSessionGuard.Token token, CopiedChunkObserver observer)
            throws IOException {
        if (beforeVerify == null || space == null || observer == null)
            throw new IOException("Validador ou orçamento de armazenamento indisponível");
        ExportSessionGuard.check(token);
        if (original == null || !original.isFile() || destination == null || edits == null || edits.isEmpty())
            throw new IOException("APK e alterações são obrigatórios");
        if (original.getCanonicalPath().equals(destination.getCanonicalPath()))
            throw new IOException("Destino não pode ser o APK original");
        // A validated snapshot, not the caller's possibly mutable Map, drives
        // the entire write. Direct callers cannot race post-validation edits.
        final Map<String, String> safeEdits;
        try {
            EditPlan verified = new EditPlan();
            for (Map.Entry<String, String> change : edits.entrySet())
                verified.addTextReplacement(change.getKey(), change.getValue());
            safeEdits = verified.snapshot();
        } catch (IllegalArgumentException invalid) {
            throw new IOException("Plano de edição inválido", invalid);
        }
        ExportSessionGuard.check(token);
        // Validate direct callers as rigorously as the SAF importer. An intact
        // central directory alone does not prove every payload can inflate.
        final String sourceSha256 = ApkIntegrity.sha256(original, token);
        ApkZipIntegrity.verify(original, token);
        ApkIntegrity.confirmExpected(original, sourceSha256, token);
        ExportSessionGuard.check(token);
        // Reserve 64 MiB of free storage before creating staging. The quota
        // counts actual compressed ZIP bytes, including headers and trailers.
        RebuildStorageBudget.preflight(space);
        ExportSessionGuard.check(token);
        // Build beside the target, never directly over an existing export.
        // A failed rebuild leaves both original APK and previous result intact.
        File staged = File.createTempFile("readroid-rebuild-", ".tmp",
            destination.getAbsoluteFile().getParentFile());
        RebuildTempJanitor.track(staged);
        boolean committed = false;
        Set<String> applied = new HashSet<>();
        byte[] buffer = new byte[65536];
        try {
          RebuildStorageBudget.CheckedOutputStream budget =
              RebuildStorageBudget.open(staged, space);
          // First resource owns the file descriptor even if opening ZipFile
          // fails. ZipOutputStream may close it first; close() is idempotent.
          try (RebuildStorageBudget.CheckedOutputStream managedBudget = budget;
               ZipFile input = new ZipFile(original);
               ZipOutputStream output = new ZipOutputStream(
                   new BufferedOutputStream(managedBudget))) {
            Enumeration<? extends ZipEntry> entries = input.entries();
            Set<String> seen = new HashSet<>();
            int count = 0;
            while (entries.hasMoreElements()) {
                ExportSessionGuard.check(token);
                ZipEntry entry = entries.nextElement();
                if (++count > 150000) throw new IOException("Número excessivo de entradas");
                String name = entry.getName();
                // F1.9: same strict archive-path policy used by admission and
                // the read-only SQLite index, including direct rebuild callers.
                ApkDiskIndex.validatePath(name);
                if (!seen.add(name)) throw new IOException("Entrada duplicada: " + name);
                // Signing metadata cannot be reused after modifications.
                String upper = name.toUpperCase(Locale.ROOT);
                if (upper.startsWith("META-INF/") &&
                    (upper.endsWith(".RSA") || upper.endsWith(".DSA") || upper.endsWith(".EC")
                        || upper.endsWith(".SF") || upper.equals("META-INF/MANIFEST.MF"))) continue;
                if (entry.isDirectory() && safeEdits.containsKey(name))
                    throw new IOException("Não é possível editar diretório: " + name);
                ZipEntry copy = new ZipEntry(name);
                copy.setTime(entry.getTime());
                output.putNextEntry(copy);
                if (!entry.isDirectory()) {
                    String replacement = safeEdits.get(name);
                    if (replacement != null) {
                        if (!EditPlan.isEditable(name)) throw new IOException("Edição não permitida: " + name);
                        ExportSessionGuard.check(token);
                        output.write(replacement.getBytes(StandardCharsets.UTF_8));
                        ExportSessionGuard.check(token);
                        applied.add(name);
                    } else {
                        try (InputStream in = input.getInputStream(entry)) {
                            int n;
                            long total = 0;
                            while (true) {
                                ExportSessionGuard.check(token);
                                n = in.read(buffer);
                                ExportSessionGuard.check(token);
                                if (n == -1) break;
                                total += n;
                                if (total > 1073741824L) throw new IOException("Entrada excede 1 GB");
                                output.write(buffer, 0, n);
                                ExportSessionGuard.check(token);
                                observer.onCopied(name, total);
                                ExportSessionGuard.check(token);
                            }
                        }
                    }
                }
                output.closeEntry();
                ExportSessionGuard.check(token);
            }
            if (applied.size() != safeEdits.size())
                throw new IOException("Alguns arquivos editados não existem no APK");
          }
          ExportSessionGuard.check(token);
          // A short final ZIP or central-directory trailer still needs a
          // post-close reserve check, even below the periodic 8 MiB interval.
          budget.verifyFinal();
          // Complete and close staged ZIP first. Do not replace an existing
          // export until CRC, paths, expected edits, and every untouched member
          // match the original. The test seam injects damage at this boundary.
          ExportSessionGuard.check(token);
          beforeVerify.run(staged);
          ExportSessionGuard.check(token);
          ApkZipIntegrity.verify(staged, token);
          RebuildVerifier.verifyAgainstOriginal(original, staged, safeEdits, token);
          ApkIntegrity.confirmExpected(original, sourceSha256, token);
          ExportSessionGuard.check(token);
          ExportSessionGuard.check(token);
          // Fail closed on filesystems without atomic replacement. Never
          // delete or truncate an existing destination on an error.
          try {
              java.nio.file.Files.move(staged.toPath(), destination.toPath(),
                  java.nio.file.StandardCopyOption.ATOMIC_MOVE,
                  java.nio.file.StandardCopyOption.REPLACE_EXISTING);
          } catch (java.nio.file.AtomicMoveNotSupportedException unavailable) {
              throw new IOException("Destino não aceita troca atômica segura", unavailable);
          }
          committed = true;
        } finally {
            try {
                if (!committed) staged.delete();
            } finally {
                RebuildTempJanitor.release(staged);
            }
        }
    }
}
