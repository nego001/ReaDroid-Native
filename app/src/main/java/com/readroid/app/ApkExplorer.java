package com.readroid.app;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import java.util.HashSet;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Read-only, bounded ZIP explorer. Never extracts untrusted paths to disk. */
public final class ApkExplorer {
    private ApkExplorer() {}

    public static JSONObject inspect(File apk) throws Exception {
        JSONArray files = new JSONArray();
        int directories = 0;
        long totalUncompressed = 0;
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            int count = 0;
            Set<String> seen = new HashSet<>();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                if (++count > ApkZipAdmission.MAX_ENTRIES)
                    throw new IOException("APK com entradas demais");
                // Apply the SAME rules as the paginated SQLite index.
                // Reject unknown or suspicious declared expansion BEFORE JSON.
                totalUncompressed = ApkZipAdmission.cumulativeBytes(
                    totalUncompressed, entry);
                String name = entry.getName();
                if (!seen.add(name))
                    throw new IOException("Entrada ZIP duplicada: " + name);
                if (entry.isDirectory()) { directories++; continue; }
                long size = entry.getSize();
                JSONObject item = new JSONObject();
                item.put("path", name);
                item.put("sizeBytes", size);
                item.put("category", category(name));
                files.put(item);
            }
        }
        JSONObject result = new JSONObject();
        result.put("files", files);
        result.put("fileCount", files.length());
        result.put("directoryCount", directories);
        result.put("uncompressedBytes", totalUncompressed);
        result.put("readOnly", true);
        return result;
    }

    public static String category(String path) {
        if (path.endsWith(".dex")) return "Código DEX";
        if (path.startsWith("lib/")) return "Bibliotecas";
        if (path.startsWith("res/")) return "Recursos";
        if (path.startsWith("assets/")) return "Assets";
        if (path.startsWith("META-INF/")) return "Assinaturas/metadados";
        if (path.equals("AndroidManifest.xml")) return "Manifesto";
        return "Outros";
    }
}
