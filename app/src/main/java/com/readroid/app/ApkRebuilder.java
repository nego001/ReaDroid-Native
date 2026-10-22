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
        // Revalidate untrusted direct Map callers before opening any output
        // file. Never let a raw map bypass EditPlan's UTF-8/path constraints.
        try {
            EditPlan verified = new EditPlan();
            for (Map.Entry<String, String> change : edits.entrySet())
                verified.addTextReplacement(change.getKey(), change.getValue());
        } catch (IllegalArgumentException invalid) {
            throw new IOException("Plano de edição inválido", invalid);
        }
        Set<String> applied = new HashSet<>();
        byte[] buffer = new byte[65536];
        boolean success = false;
        try (ZipFile input = new ZipFile(original);
             ZipOutputStream output = new ZipOutputStream(new BufferedOutputStream(new FileOutputStream(destination)))) {
            Enumeration<? extends ZipEntry> entries = input.entries();
            Set<String> seen = new HashSet<>();
            int count = 0;
            while (entries.hasMoreElements()) {
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
                if (entry.isDirectory() && edits.containsKey(name))
                    throw new IOException("Não é possível editar diretório: " + name);
                ZipEntry copy = new ZipEntry(name);
                copy.setTime(entry.getTime());
                output.putNextEntry(copy);
                if (!entry.isDirectory()) {
                    String replacement = edits.get(name);
                    if (replacement != null) {
                        if (!EditPlan.isEditable(name)) throw new IOException("Edição não permitida: " + name);
                        output.write(replacement.getBytes(StandardCharsets.UTF_8));
                        applied.add(name);
                    } else {
                        try (InputStream in = input.getInputStream(entry)) {
                            int n;
                            long total = 0;
                            while ((n = in.read(buffer)) != -1) {
                                total += n;
                                if (total > 1073741824L) throw new IOException("Entrada excede 1 GB");
                                output.write(buffer, 0, n);
                            }
                        }
                    }
                }
                output.closeEntry();
            }
            if (applied.size() != edits.size()) throw new IOException("Alguns arquivos editados não existem no APK");
            success = true;
        } finally {
            if (!success) destination.delete();
        }
    }
}
