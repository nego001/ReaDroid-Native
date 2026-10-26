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
        JSONArray dexMaps = new JSONArray();
        JSONArray dexClasses = new JSONArray();
        JSONArray dexNames = new JSONArray();
        JSONArray dexMethods = new JSONArray();
        JSONArray dexPrototypes = new JSONArray();
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
                // M3.2: only four maps; at most 16 MiB stream-read each.
                // Header preview remains independent if map data is unsupported.
                if (dexMaps.length() < 4) {
                    JSONObject mapPreview = new JSONObject();
                    mapPreview.put("name", name);
                    try (InputStream mapInput = zip.getInputStream(e)) {
                        DexMapProbe.Result map = DexMapProbe.inspect(mapInput, e.getSize());
                        mapPreview.put("status", "map-only");
                        mapPreview.put("version", map.version);
                        mapPreview.put("mapOffset", map.mapOffset);
                        mapPreview.put("declaredSections", map.items.size());
                        JSONArray sections = new JSONArray();
                        for (DexMapProbe.Item item : map.items) {
                            JSONObject section = new JSONObject();
                            section.put("type", item.label);
                            section.put("count", item.count);
                            section.put("offset", item.offset);
                            sections.put(section);
                        }
                        mapPreview.put("sections", sections);
                    } catch (java.io.InterruptedIOException cancelled) {
                        throw cancelled;
                    } catch (IOException invalid) {
                        mapPreview.put("status", "unreadable-map");
                        mapPreview.put("reason", "Mapa DEX inválido ou não suportado");
                    }
                    dexMaps.put(mapPreview);
                }
                // M3.3: only numeric class_def indices; no strings or bytecode.
                // Maximum four DEX files and 24 class records per file.
                if (dexClasses.length() < 4) {
                    JSONObject classPreview = new JSONObject();
                    classPreview.put("name", name);
                    try (InputStream classInput = zip.getInputStream(e)) {
                        DexClassDefProbe.Result classes =
                            DexClassDefProbe.inspect(classInput, e.getSize());
                        classPreview.put("status", "class-index-only");
                        classPreview.put("version", classes.version);
                        classPreview.put("declaredClasses", classes.declaredClasses);
                        classPreview.put("previewTruncated", classes.previewTruncated);
                        JSONArray sampled = new JSONArray();
                        for (DexClassDefProbe.Item item : classes.items) {
                            JSONObject row = new JSONObject();
                            row.put("classTypeIdx", item.classTypeIdx);
                            row.put("accessFlags", item.accessFlags);
                            row.put("superclassTypeIdx", item.superclassTypeIdx);
                            row.put("interfacesOff", item.interfacesOff);
                            row.put("sourceFileStringIdx", item.sourceFileStringIdx);
                            row.put("annotationsOff", item.annotationsOff);
                            row.put("classDataOff", item.classDataOff);
                            row.put("staticValuesOff", item.staticValuesOff);
                            sampled.put(row);
                        }
                        classPreview.put("classDefinitions", sampled);
                    } catch (java.io.InterruptedIOException cancelled) {
                        throw cancelled;
                    } catch (IOException invalid) {
                        classPreview.put("status", "unreadable-class-index");
                        classPreview.put("reason", "Índices class_def inválidos ou não suportados");
                    }
                    dexClasses.put(classPreview);
                }
                // M3.4: do not expose raw DEX contents. Resolve at most six
                // descriptor strings from each of the first two DEX entries.
                if (dexNames.length() < 2) {
                    JSONObject namePreview = new JSONObject();
                    namePreview.put("name", name);
                    try {
                        DexClassNameProbe.Result names = DexClassNameProbe.inspect(
                            () -> zip.getInputStream(e), e.getSize());
                        namePreview.put("status", "class-names-preview");
                        namePreview.put("declaredClasses", names.declaredClasses);
                        namePreview.put("previewTruncated", names.truncated);
                        JSONArray listed = new JSONArray();
                        for (DexClassNameProbe.Item item : names.items) {
                            JSONObject record = new JSONObject();
                            record.put("classTypeIdx", item.classTypeIdx);
                            record.put("descriptor", item.descriptor);
                            record.put("name", item.name);
                            listed.put(record);
                        }
                        namePreview.put("resolvedClasses", listed);
                    } catch (java.io.InterruptedIOException cancelled) {
                        throw cancelled;
                    } catch (IOException invalid) {
                        namePreview.put("status", "unreadable-class-names");
                        namePreview.put("reason", "Descritores de classes DEX inválidos ou não suportados");
                    }
                    dexNames.put(namePreview);
                }
                // M3.5: method_ids contain references AND definitions. Never
                // claim these are methods implemented by this APK.
                if (dexMethods.length() < 2) {
                    JSONObject methodPreview = new JSONObject();
                    methodPreview.put("name", name);
                    try {
                        DexMethodProbe.Result methods = DexMethodProbe.inspect(
                            () -> zip.getInputStream(e), e.getSize());
                        methodPreview.put("status", "method-ids-preview");
                        methodPreview.put("version", methods.version);
                        methodPreview.put("totalMethodIds", methods.totalMethodIds);
                        methodPreview.put("previewTruncated", methods.truncated);
                        JSONArray items = new JSONArray();
                        for (DexMethodProbe.Item method : methods.methods) {
                            JSONObject item = new JSONObject();
                            item.put("methodIndex", method.methodIndex);
                            item.put("classTypeIdx", method.declaringTypeIdx);
                            item.put("protoIdx", method.prototypeIdx);
                            item.put("nameStringIdx", method.nameStringIdx);
                            item.put("methodName", method.name);
                            items.put(item);
                        }
                        methodPreview.put("methodIds", items);
                    } catch (java.io.InterruptedIOException cancelled) {
                        throw cancelled;
                    } catch (IOException invalid) {
                        methodPreview.put("status", "unreadable-method-ids");
                        methodPreview.put("reason",
                            "Tabela method_ids ou nomes inválidos/não suportados");
                    }
                    dexMethods.put(methodPreview);
                }
                // M3.6: a method_id can be an EXTERNAL reference. Signatures
                // describe its declared proto, never a local method body.
                if (dexPrototypes.length() < 2) {
                    JSONObject protoPreview = new JSONObject();
                    protoPreview.put("name", name);
                    try {
                        DexPrototypeProbe.Result protos = DexPrototypeProbe.inspect(
                            () -> zip.getInputStream(e), e.getSize());
                        protoPreview.put("status", "prototype-signatures-preview");
                        protoPreview.put("totalMethodIds", protos.totalMethodIds);
                        protoPreview.put("previewTruncated", protos.truncated);
                        JSONArray entriesPreview = new JSONArray();
                        for (DexPrototypeProbe.MethodSignature item : protos.signatures) {
                            JSONObject entryPreview = new JSONObject();
                            entryPreview.put("methodIndex", item.methodIndex);
                            entryPreview.put("methodName", item.methodName);
                            entryPreview.put("protoIdx", item.prototypeIndex);
                            entryPreview.put("returnType", item.returnType);
                            JSONArray parameters = new JSONArray();
                            for (String type : item.parameterTypes) parameters.put(type);
                            entryPreview.put("parameters", parameters);
                            entryPreview.put("signature", item.descriptor);
                            entriesPreview.put(entryPreview);
                        }
                        protoPreview.put("methodSignatures", entriesPreview);
                    } catch (java.io.InterruptedIOException cancelled) {
                        throw cancelled;
                    } catch (IOException invalid) {
                        protoPreview.put("status", "unreadable-prototypes");
                        protoPreview.put("reason",
                            "Protótipos ou assinaturas DEX inválidos/não suportados");
                    }
                    dexPrototypes.put(protoPreview);
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
        report.put("dexMapPreview", dexMaps);
        report.put("dexMapPreviewTruncated", dexCount > dexMaps.length());
        report.put("dexClassPreview", dexClasses);
        report.put("dexClassPreviewTruncated", dexCount > dexClasses.length());
        report.put("dexClassNamePreview", dexNames);
        report.put("dexClassNamePreviewTruncated", dexCount > dexNames.length());
        report.put("dexMethodPreview", dexMethods);
        report.put("dexMethodPreviewTruncated", dexCount > dexMethods.length());
        report.put("dexPrototypePreview", dexPrototypes);
        report.put("dexPrototypePreviewTruncated", dexCount > dexPrototypes.length());
        report.put("nativeLibraryCount", nativeLibraryCount);
        report.put("manifestPresent", manifest);
        report.put("dexFiles", dex);
        report.put("nativeLibraries", nativeLibraries);
        report.put("fileExplorerPreview", files);
        report.put("findings", findings);
        report.put("limitations", "Prévia limitada de cabeçalho, mapa, nomes, method_ids e protótipos DEX v035-v040. method_ids podem referenciar métodos externos; não decodifica corpos de métodos, recursos compilados ou assinaturas APK.");
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
