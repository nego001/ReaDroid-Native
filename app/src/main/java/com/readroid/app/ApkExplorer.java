package com.readroid.app;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.util.Enumeration;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * M2.3 bounded metadata preview. The complete archive is browsed through
 * ApkDiskIndex when the entry count exceeds the preview budget.
 * No file content is extracted and no unbounded JSON path list is retained.
 */
public final class ApkExplorer {
    public static final int PREVIEW_LIMIT = 120;
    private static final int MAX_ENTRIES = 150000;
    private static final long MAX_ENTRY_BYTES = 1073741824L;
    private static final long MAX_TOTAL_BYTES = 2147483648L;

    private ApkExplorer() {}

    /**
     * Public standalone entrypoint always verifies the untrusted ZIP first.
     * MainActivity calls inspectVerified only after ApkArchiveSafety.verify.
     */
    public static JSONObject inspect(File apk) throws Exception {
        ApkArchiveSafety.verify(apk);
        return inspectVerified(apk);
    }

    /** Caller must have admitted the same private cache file via ApkArchiveSafety. */
    static JSONObject inspectVerified(File apk) throws Exception {
        JSONArray preview = new JSONArray();
        int directories = 0;
        int fileCount = 0;
        int entryCount = 0;
        long totalUncompressed = 0;
        boolean[] engineSignals = new boolean[4];
        try (ZipFile zip = new ZipFile(apk)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                if (Thread.currentThread().isInterrupted())
                    throw new InterruptedIOException("Prévia de APK cancelada");
                ZipEntry entry = entries.nextElement();
                if (++entryCount > MAX_ENTRIES)
                    throw new IOException("APK com entradas demais");
                String name = entry.getName();
                ApkDiskIndex.validatePath(name);
                if (entry.isDirectory()) {
                    directories++;
                    continue;
                }
                fileCount++;
                ApkIntelligence.mark(name, engineSignals);
                long size = entry.getSize();
                if (size < 0 || size > MAX_ENTRY_BYTES)
                    throw new IOException("Entrada ZIP com tamanho inválido: " + name);
                if (totalUncompressed > MAX_TOTAL_BYTES - size)
                    throw new IOException("APK excede 2 GiB descomprimidos");
                totalUncompressed += size;
                if (preview.length() < PREVIEW_LIMIT) {
                    JSONObject item = new JSONObject();
                    item.put("path", name);
                    item.put("sizeBytes", size);
                    item.put("category", category(name));
                    preview.put(item);
                }
            }
        }
        JSONArray hints = new JSONArray();
        for (boolean signal : engineSignals) hints.put(signal);
        JSONObject result = new JSONObject();
        result.put("files", preview);
        result.put("fileCount", fileCount);
        result.put("entryCount", entryCount);
        result.put("previewCount", preview.length());
        result.put("previewTruncated", fileCount > preview.length());
        result.put("engineSignals", hints);
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
