package com.readroid.app;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.IOException;
import java.io.InputStream;
import java.util.Enumeration;
import java.util.Locale;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Static, offline checks. Findings are indicators, not proof of a vulnerability. */
public final class SecurityScanner {
    private SecurityScanner() {}

    public static JSONObject scan(ZipFile zip) throws Exception {
        JSONArray findings = new JSONArray();
        JSONArray files = new JSONArray();
        JSONArray dex = new JSONArray();
        JSONArray dexHeaders = new JSONArray();
        JSONArray nativeLibraries = new JSONArray();
        int count = 0;
        int dexCount = 0;
        int nativeLibraryCount = 0;
        long expanded = 0;
        boolean manifest = false;
        boolean signature = false;
        Pattern signatureFile = Pattern.compile("META-INF/[^/]+\\.(RSA|DSA|EC|SF)", Pattern.CASE_INSENSITIVE);
        Enumeration<? extends ZipEntry> entries = zip.entries();
        while (entries.hasMoreElements()) {
            ZipEntry e = entries.nextElement();
            if (++count > 150000) throw new IllegalArgumentException("APK com entradas demais");
            String name = e.getName();
            if (files.length() < ApkExplorer.PREVIEW_LIMIT) files.put(name);
            if (e.getSize() > 0) {
                expanded += e.getSize();
                if (expanded > 4L * 1024 * 1024 * 1024) {
                    add(findings, "warning", "Arquivos descompactados muito grandes",
                        "O tamanho declarado supera 4 GB. Evite extrair sem limites.");
                    break;
                }
            }
            if (name.equals("AndroidManifest.xml")) manifest = true;
            if (name.matches("classes([0-9]+)?\\.dex")) {
                dexCount++;
                if (dex.length() < ApkExplorer.PREVIEW_LIMIT) dex.put(name);
                // M3.1: inspect at most 12 DEX headers; never read the DEX
                // body or turn malformed/unsupported DEX into a scan crash.
                if (dexHeaders.length() < 12) {
                    JSONObject preview = new JSONObject();
                    preview.put("name", name);
                    try (InputStream input = zip.getInputStream(e)) {
                        DexHeaderProbe.Header header = DexHeaderProbe.inspect(input, e.getSize());
                        preview.put("status", "header-only");
                        preview.put("version", header.version);
                        preview.put("sizeBytes", header.sizeBytes);
                        preview.put("strings", header.stringIds);
                        preview.put("types", header.typeIds);
                        preview.put("prototypes", header.protoIds);
                        preview.put("fields", header.fieldIds);
                        preview.put("methods", header.methodIds);
                        preview.put("classes", header.classDefs);
                    } catch (java.io.InterruptedIOException cancelled) {
                        throw cancelled;
                    } catch (IOException invalid) {
                        preview.put("status", "unreadable-header");
                        // Do not persist arbitrary ZIP paths or parser errors
                        // inside the diagnostic explanation.
                        preview.put("reason", "Cabeçalho DEX inválido ou não suportado");
                    }
                    dexHeaders.put(preview);
                }
            }
            if (name.startsWith("lib/") && name.endsWith(".so")) {
                nativeLibraryCount++;
                if (nativeLibraries.length() < ApkExplorer.PREVIEW_LIMIT)
                    nativeLibraries.put(name);
            }
            if (signatureFile.matcher(name).matches()) signature = true;
            if (name.contains("../") || name.startsWith("/") || name.contains("\\")) {
                add(findings, "high", "Caminho suspeito no arquivo", name);
            }
        }
        if (!manifest) add(findings, "high", "Manifesto ausente", "AndroidManifest.xml não encontrado.");
        if (dexCount == 0) add(findings, "info", "Sem DEX", "Pode ser um APK de recursos ou um pacote incompleto.");
        if (!signature) add(findings, "info", "Sem assinatura v1 detectada",
            "Isso não prova ausência de assinatura: v2/v3 usam o bloco de assinatura do APK.");
        JSONObject report = new JSONObject();
        report.put("entries", count);
        report.put("filePreviewTruncated", count > files.length());
        report.put("dexFileCount", dexCount);
        report.put("dexHeaderPreview", dexHeaders);
        report.put("dexHeaderPreviewTruncated", dexCount > dexHeaders.length());
        report.put("nativeLibraryCount", nativeLibraryCount);
        report.put("manifestPresent", manifest);
        report.put("dexFiles", dex);
        report.put("nativeLibraries", nativeLibraries);
        report.put("fileExplorerPreview", files);
        report.put("findings", findings);
        report.put("limitations", "Inspeção estática inicial; cabeçalho DEX v035-v040 é lido, mas classes, instruções e recursos compilados não são decodificados. Certificado v2/v3 requer análise própria.");
        return report;
    }

    private static void add(JSONArray findings, String severity, String title, String explanation) throws Exception {
        JSONObject item = new JSONObject();
        item.put("severity", severity);
        item.put("title", title);
        item.put("explanation", explanation);
        findings.put(item);
    }
}
