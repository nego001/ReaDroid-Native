package com.readroid.app;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Read-only, offline APK structural advisor. It detects file-name indicators,
 * not engine provenance, decompilation support or vulnerability. Never executes
 * untrusted APK code or sends project data to external services.
 */
public final class ApkIntelligence {
    private ApkIntelligence() {}

    public static JSONObject inspect(JSONObject analysis) throws Exception {
        if (analysis == null) throw new IllegalArgumentException("Relatório ausente");
        Set<String> paths = new LinkedHashSet<>();
        JSONObject explorer = analysis.optJSONObject("explorer");
        JSONArray files = explorer == null ? null : explorer.optJSONArray("files");
        if (files != null) {
            for (int i = 0; i < files.length(); i++) {
                JSONObject file = files.optJSONObject(i);
                if (file != null) paths.add(file.optString("path", "").toLowerCase(Locale.ROOT));
            }
        }
        // Some callers only provide the older partial analysis fields.
        JSONArray libs = analysis.optJSONArray("nativeLibraries");
        if (libs != null) for (int i = 0; i < libs.length(); i++)
            paths.add(libs.optString(i, "").toLowerCase(Locale.ROOT));

        List<String> engines = new ArrayList<>();
        JSONArray evidence = new JSONArray();
        boolean unity = matchSuffix(paths, "/libunity.so") || matchSuffix(paths, "/libil2cpp.so")
            || matchPrefix(paths, "assets/bin/data/");
        boolean unreal = matchSuffix(paths, "/libue4.so") || matchSuffix(paths, "/libunreal.so")
            || matchPrefix(paths, "assets/ue4game/");
        boolean flutter = matchSuffix(paths, "/libflutter.so")
            || matchPrefix(paths, "assets/flutter_assets/");
        boolean react = paths.contains("assets/index.android.bundle")
            || paths.contains("assets/index.android.hermes")
            || matchSuffix(paths, "/libreactnativejni.so");

        if (unity) {
            engines.add("Unity");
            evidence.put("libunity/libil2cpp ou assets/bin/Data");
        }
        if (unreal) {
            engines.add("Unreal Engine");
            evidence.put("libUE4/libUnreal ou assets/UE4Game");
        }
        if (flutter) {
            engines.add("Flutter");
            evidence.put("libflutter ou flutter_assets");
        }
        if (react) {
            engines.add("React Native");
            evidence.put("index.android.bundle/Hermes ou libreactnativejni");
        }

        String platform = engines.size() == 0 ? "Android/ZIP"
            : engines.size() == 1 ? engines.get(0) : "Sinais mistos";
        JSONArray tools = new JSONArray();
        tools.put("Explorar pastas, pesquisar e filtrar entradas ZIP");
        tools.put("Analisar manifesto e componentes reconhecidos pelo Android");
        tools.put("Inspecionar metadados e SHA-256 de entradas");
        tools.put("Comparar APKs e examinar certificados");
        tools.put("Planejar edição de texto UTF-8 pequeno e exportar ZIP sem assinatura");

        JSONArray limitations = new JSONArray();
        limitations.put("A detecção é por indícios de nomes de arquivos, não por execução ou decompilação.");
        limitations.put("Limite atual: APK de até 1 GiB; máximo de 150 mil entradas.");
        limitations.put("Não decodifica nem modifica DEX, resources.arsc ou recursos binários avançados.");
        limitations.put("Não edita assets Unity/Unreal, dados OBB nem contêineres split APKS/XAPK.");
        limitations.put("A exportação de alterações ainda não produz um APK assinado/instalável.");
        JSONObject profile = new JSONObject();
        profile.put("platformHint", platform);
        profile.put("confidence", engines.size() == 1 ? "indício estrutural"
            : engines.size() > 1 ? "ambíguo" : "não identificada");
        profile.put("evidence", evidence);
        profile.put("availableTools", tools);
        profile.put("limitations", limitations);
        profile.put("localOnly", true);
        return profile;
    }

    private static boolean matchSuffix(Set<String> paths, String suffix) {
        for (String path : paths) if (path.endsWith(suffix)) return true;
        return false;
    }

    private static boolean matchPrefix(Set<String> paths, String prefix) {
        for (String path : paths) if (path.startsWith(prefix)) return true;
        return false;
    }

    public static String describe(JSONObject profile) {
        if (profile == null) return "Selecione e analise um APK primeiro.";
        StringBuilder result = new StringBuilder();
        result.append("PERFIL DETECTADO\n").append(profile.optString("platformHint", "Indefinido"))
            .append("\nNível: ").append(profile.optString("confidence", "não verificado"));
        appendList(result, "\n\nINDÍCIOS", profile.optJSONArray("evidence"));
        appendList(result, "\n\nFERRAMENTAS DISPONÍVEIS AGORA", profile.optJSONArray("availableTools"));
        appendList(result, "\n\nAINDA NÃO SUPORTADO", profile.optJSONArray("limitations"));
        result.append("\n\nAnálise feita no aparelho, sem executar código do APK. ")
            .append("Nenhuma modificação automática é aplicada.");
        return result.toString();
    }

    private static void appendList(StringBuilder result, String heading, JSONArray items) {
        if (items == null || items.length() == 0) return;
        result.append(heading);
        for (int i = 0; i < items.length(); i++)
            result.append("\n• ").append(items.optString(i));
    }
}
