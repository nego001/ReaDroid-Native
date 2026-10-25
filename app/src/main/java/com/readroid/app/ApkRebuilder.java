package com.readroid.app;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;

/** Experimental unsigned APK ZIP rebuild. Never changes the original input. */
public final class ApkRebuilder {
    private ApkRebuilder() {}

    public static void rebuild(File original, File destination, Map<String, String> edits) throws IOException {
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
        if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Reconstrução interrompida");
        // Build beside the target, never directly over an existing export.
        // A failed rebuild leaves both original APK and previous result intact.
        File staged = File.createTempFile("readroid-rebuild-", ".tmp",
            destination.getAbsoluteFile().getParentFile());
        boolean committed = false;
        Set<String> applied = new HashSet<>();
        byte[] buffer = new byte[65536];
        try {
          try (ZipFile input = new ZipFile(original);
               ZipOutputStream output = new ZipOutputStream(
                   new BufferedOutputStream(new FileOutputStream(staged)))) {
            Enumeration<? extends ZipEntry> entries = input.entries();
            Set<String> seen = new HashSet<>();
            int count = 0;
            while (entries.hasMoreElements()) {
                if (Thread.currentThread().isInterrupted())
                    throw new InterruptedIOException("Reconstrução interrompida");
                ZipEntry entry = entries.nextElement();
                if (++count > 150000) throw new IOException("Número excessivo de entradas");
                String name = entry.getName();
                if (name.startsWith("/") || name.contains("\\") || name.contains("../") || name.equals(".."))
                    throw new IOException("Caminho inseguro: " + name);
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
                        output.write(replacement.getBytes(StandardCharsets.UTF_8));
                        applied.add(name);
                    } else {
                        try (InputStream in = input.getInputStream(entry)) {
                            int n;
                            long total = 0;
                            while ((n = in.read(buffer)) != -1) {
                                if (Thread.currentThread().isInterrupted())
                                    throw new InterruptedIOException("Reconstrução interrompida");
                                total += n;
                                if (total > 1073741824L) throw new IOException("Entrada excede 1 GB");
                                output.write(buffer, 0, n);
                            }
                        }
                    }
                }
                output.closeEntry();
            }
            if (applied.size() != safeEdits.size())
                throw new IOException("Alguns arquivos editados não existem no APK");
          }
          if (Thread.currentThread().isInterrupted())
              throw new InterruptedIOException("Reconstrução interrompida");
          // The staged ZIP must pass ALL archive, edit and untouched-content
          // verification BEFORE replacing the last known-good export.
          // This also rejects ZIPs with no AndroidManifest.xml/classes.dex.
          // The verifier checks original ZIP entry CRCs as well as SHA-256.
          RebuildVerifier.verifyAgainstOriginal(original, staged, safeEdits);
          if (Thread.currentThread().isInterrupted())
              throw new InterruptedIOException("Reconstrução interrompida");
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
            if (!committed) staged.delete();
        }
    }
}
