package com.readroid.app;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;

/** Validates a rebuilt archive against the edit plan; does not assert installability. */
public final class RebuildVerifier {
    private RebuildVerifier() {}

    public static String verify(File apk, Map<String, String> edits) throws IOException {
        return verify(apk, edits, null);
    }

    static String verify(File apk, Map<String, String> edits,
            ExportSessionGuard.Token token) throws IOException {
        ExportSessionGuard.check(token);
        if (apk == null || !apk.isFile()) throw new IOException("Arquivo reconstruído não encontrado");
        if (edits == null || edits.isEmpty()) throw new IOException("Plano vazio");
        Set<String> matched = new HashSet<>();
        Set<String> names = new HashSet<>();
        boolean manifest = false, dex = false;
        int count = 0;
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ExportSessionGuard.check(token);
                ZipEntry entry = entries.nextElement();
                if (++count > 150000) throw new IOException("Entradas demais");
                String name = entry.getName();
                ApkDiskIndex.validatePath(name);
                if (!names.add(name)) throw new IOException("Entrada duplicada: " + name);
                if (name.equals("AndroidManifest.xml")) manifest = true;
                if (name.matches("classes([0-9]+)?\\.dex")) dex = true;
                String expected = edits.get(name);
                if (expected != null) {
                    byte[] expectedBytes = expected.getBytes(StandardCharsets.UTF_8);
                    if (expectedBytes.length > 131072) throw new IOException("Alteração grande demais");
                    try (InputStream in = zip.getInputStream(entry)) {
                        for (int i = 0; i < expectedBytes.length; i++) {
                            if ((i & 4095) == 0) ExportSessionGuard.check(token);
                            int actual = in.read();
                            if (actual != (expectedBytes[i] & 255))
                                throw new IOException("Alteração não confere: " + name);
                        }
                        ExportSessionGuard.check(token);
                        if (in.read() != -1)
                            throw new IOException("Tamanho da alteração não confere: " + name);
                    }
                    matched.add(name);
                }
            }
        }
        ExportSessionGuard.check(token);
        if (!manifest || !dex) throw new IOException("Manifesto ou código DEX ausente");
        if (matched.size() != edits.size()) throw new IOException("Alterações não encontradas no resultado");
        return "ZIP validado; " + matched.size() + " alteração(ões) conferida(s). APK ainda não assinado nem validado para instalação.";
    }

    /**
     * Compares every unedited entry byte-for-byte by SHA-256 against the source.
     * Edited entries are checked by verify() and old v1 signing metadata must
     * be absent. Also refuses added or omitted unrelated archive entries.
     * This checks ZIP contents, not APK installability or binary equivalence.
     */
    public static String verifyAgainstOriginal(File original, File rebuilt,
            Map<String, String> edits) throws IOException {
        return verifyAgainstOriginal(original, rebuilt, edits, null);
    }

    static String verifyAgainstOriginal(File original, File rebuilt,
            Map<String, String> edits, ExportSessionGuard.Token token) throws IOException {
        ExportSessionGuard.check(token);
        if (original == null || !original.isFile())
            throw new IOException("APK original não encontrado");
        String baseResult = verify(rebuilt, edits, token);
        int untouched = 0;
        Set<String> expectedPaths = new HashSet<>();
        Set<String> originalPaths = new HashSet<>();
        try (ZipFile source = new ZipFile(original); ZipFile output = new ZipFile(rebuilt)) {
            Enumeration<? extends ZipEntry> entries = source.entries();
            int count = 0;
            while (entries.hasMoreElements()) {
                ExportSessionGuard.check(token);
                if (++count > 150000) throw new IOException("Entradas demais na origem");
                ZipEntry entry = entries.nextElement();
                String name = entry.getName();
                ApkDiskIndex.validatePath(name);
                if (!originalPaths.add(name)) throw new IOException("Entrada duplicada na origem");
                if (isOldSignature(name)) {
                    if (output.getEntry(name) != null)
                        throw new IOException("Metadados de assinatura antiga preservados: " + name);
                    continue;
                }
                if (!expectedPaths.add(name))
                    throw new IOException("Entrada repetida na origem: " + name);
                ZipEntry exported = output.getEntry(name);
                if (exported == null || exported.isDirectory() != entry.isDirectory())
                    throw new IOException("Estrutura divergente: " + name);
                if (entry.isDirectory()) continue;
                if (edits.containsKey(name)) continue; // verify() checked exact edited content.
                if (!Arrays.equals(entryDigest(source, entry, token), entryDigest(output, exported, token)))
                    throw new IOException("Arquivo não editado foi alterado: " + name);
                untouched++;
            }
            Enumeration<? extends ZipEntry> rebuiltEntries = output.entries();
            int rebuiltCount = 0;
            while (rebuiltEntries.hasMoreElements()) {
                ExportSessionGuard.check(token);
                if (++rebuiltCount > 150000)
                    throw new IOException("Entradas demais no resultado");
                String name = rebuiltEntries.nextElement().getName();
                ApkDiskIndex.validatePath(name);
                if (!expectedPaths.remove(name))
                    throw new IOException("Arquivo inesperado no resultado: " + name);
            }
            if (!expectedPaths.isEmpty())
                throw new IOException("O resultado perdeu arquivos da origem");
        }
        ExportSessionGuard.check(token);
        return baseResult + "\n" + untouched
            + " arquivo(s) não editado(s) conferido(s) por SHA-256 contra o original.";
    }

    private static boolean isOldSignature(String name) {
        String upper = name.toUpperCase(Locale.ROOT);
        return upper.startsWith("META-INF/")
            && (upper.endsWith(".RSA") || upper.endsWith(".DSA")
                || upper.endsWith(".EC") || upper.endsWith(".SF")
                || upper.equals("META-INF/MANIFEST.MF"));
    }

    private static byte[] entryDigest(ZipFile zip, ZipEntry entry,
            ExportSessionGuard.Token token) throws IOException {
        final java.security.MessageDigest hash;
        try {
            hash = java.security.MessageDigest.getInstance("SHA-256");
        } catch (java.security.NoSuchAlgorithmException unavailable) {
            throw new IOException("SHA-256 indisponível", unavailable);
        }
        byte[] buffer = new byte[65536];
        long total = 0;
        try (InputStream in = zip.getInputStream(entry)) {
            int n;
            while (true) {
                ExportSessionGuard.check(token);
                n = in.read(buffer);
                ExportSessionGuard.check(token);
                if (n == -1) break;
                ExportSessionGuard.check(token);
                total += n;
                if (total > 1073741824L)
                    throw new IOException("Entrada acima do limite: " + entry.getName());
                hash.update(buffer, 0, n);
            }
        }
        ExportSessionGuard.check(token);
        return hash.digest();
    }
}
