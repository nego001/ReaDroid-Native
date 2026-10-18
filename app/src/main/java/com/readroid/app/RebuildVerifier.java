package com.readroid.app;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;

/** Validates a rebuilt archive against the edit plan; does not assert installability. */
public final class RebuildVerifier {
    private RebuildVerifier() {}

    public static String verify(File apk, Map<String, String> edits) throws IOException {
        if (apk == null || !apk.isFile()) throw new IOException("Arquivo reconstruído não encontrado");
        if (edits == null || edits.isEmpty()) throw new IOException("Plano vazio");
        Set<String> matched = new HashSet<>();
        Set<String> names = new HashSet<>();
        boolean manifest = false, dex = false;
        int count = 0;
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                if (++count > 150000) throw new IOException("Entradas demais");
                String name = entry.getName();
                if (!names.add(name)) throw new IOException("Entrada duplicada: " + name);
                if (name.equals("AndroidManifest.xml")) manifest = true;
                if (name.matches("classes([0-9]+)?\\.dex")) dex = true;
                String expected = edits.get(name);
                if (expected != null) {
                    byte[] expectedBytes = expected.getBytes(StandardCharsets.UTF_8);
                    if (expectedBytes.length > 131072) throw new IOException("Alteração grande demais");
                    try (InputStream in = zip.getInputStream(entry)) {
                        for (byte value : expectedBytes) {
                            int actual = in.read();
                            if (actual != (value & 255)) throw new IOException("Alteração não confere: " + name);
                        }
                        if (in.read() != -1) throw new IOException("Tamanho da alteração não confere: " + name);
                    }
                    matched.add(name);
                }
            }
        }
        if (!manifest || !dex) throw new IOException("Manifesto ou código DEX ausente");
        if (matched.size() != edits.size()) throw new IOException("Alterações não encontradas no resultado");
        return "ZIP validado; " + matched.size() + " alteração(ões) conferida(s). APK ainda não assinado nem validado para instalação.";
    }
}
