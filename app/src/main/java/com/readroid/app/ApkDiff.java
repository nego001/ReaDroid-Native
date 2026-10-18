package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.Enumeration;

/** Compares ZIP entry metadata without extracting or executing APK code. */
public final class ApkDiff {
    private ApkDiff() {}

    public static String compare(File first, File second) throws IOException {
        Map<String, String> left = entries(first);
        Map<String, String> right = entries(second);
        int added = 0, removed = 0, changed = 0, identical = 0;
        StringBuilder details = new StringBuilder();
        for (String name : right.keySet()) {
            if (!left.containsKey(name)) { added++; append(details, "+ ", name); }
            else if (!left.get(name).equals(right.get(name))) { changed++; append(details, "~ ", name); }
            else identical++;
        }
        for (String name : left.keySet()) {
            if (!right.containsKey(name)) { removed++; append(details, "- ", name); }
        }
        return "COMPARAÇÃO DE ESTRUTURA ZIP\n\nAdicionados: " + added
            + "\nRemovidos: " + removed + "\nModificados (CRC/tamanho): " + changed
            + "\nSem diferenças de metadados: " + identical
            + "\n\n" + details
            + "\nNota: CRC e tamanho não são uma prova criptográfica de igualdade.";
    }

    private static void append(StringBuilder out, String prefix, String name) {
        if (out.length() < 12000) out.append(prefix).append(name).append('\n');
    }

    private static Map<String, String> entries(File apk) throws IOException {
        if (apk == null || !apk.isFile()) throw new IOException("APK indisponível");
        Map<String, String> result = new HashMap<>();
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> it = zip.entries();
            int count = 0;
            while (it.hasMoreElements()) {
                ZipEntry entry = it.nextElement();
                if (++count > 150000) throw new IOException("Entradas demais");
                String name = entry.getName();
                if (name.startsWith("/") || name.contains("\\") || name.contains("../") || name.equals(".."))
                    throw new IOException("Caminho ZIP inseguro");
                if (result.put(name, entry.getCrc() + ":" + entry.getSize()) != null)
                    throw new IOException("Entrada ZIP duplicada");
            }
        }
        return result;
    }
}
