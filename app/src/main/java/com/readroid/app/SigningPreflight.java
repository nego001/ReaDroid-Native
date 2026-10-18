package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Conservative structural preflight, not a replacement for apksigner verify. */
public final class SigningPreflight {
    private SigningPreflight() {}

    public static String inspect(File apk) throws IOException {
        if (apk == null || !apk.isFile()) throw new IOException("APK não encontrado");
        int count = 0;
        int dex = 0;
        int nativeLibs = 0;
        int stored = 0;
        int signatureFiles = 0;
        boolean manifest = false;
        Set<String> seen = new HashSet<>();
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> items = zip.entries();
            while (items.hasMoreElements()) {
                ZipEntry e = items.nextElement();
                String name = e.getName();
                if (++count > 150000) throw new IOException("Limite de entradas excedido");
                if (name.startsWith("/") || name.contains("../") || name.contains("\\") || !seen.add(name))
                    throw new IOException("Entrada insegura ou duplicada: " + name);
                if (name.equals("AndroidManifest.xml")) manifest = true;
                if (name.matches("classes([0-9]+)?\\.dex")) dex++;
                if (name.startsWith("lib/") && name.endsWith(".so")) nativeLibs++;
                if (e.getMethod() == ZipEntry.STORED) stored++;
                String upper = name.toUpperCase(java.util.Locale.ROOT);
                if (upper.startsWith("META-INF/") && (upper.endsWith(".RSA") || upper.endsWith(".DSA") || upper.endsWith(".EC") || upper.endsWith(".SF")))
                    signatureFiles++;
            }
        }
        if (!manifest || dex == 0) throw new IOException("APK sem manifesto ou DEX");
        if (signatureFiles != 0) throw new IOException("Metadados de assinatura antiga ainda presentes");
        return "Pré-verificação estrutural aprovada.\nEntradas: " + count
            + "\nDEX: " + dex + "\nBibliotecas nativas: " + nativeLibs
            + "\nEntradas sem compressão: " + stored
            + "\n\nATENÇÃO: o ZIP foi reconstruído e pode ter perdido alinhamento e modo de compressão. "
            + "Ainda são obrigatórios zipalign, assinatura APK v2/v3 e apksigner verify. "
            + "Não instalar nem distribuir como APK final.";
    }
}
