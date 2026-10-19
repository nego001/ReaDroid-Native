package com.readroid.app;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Read-only, offline APK structural advisor. It detects file-name indicators,
 * not engine provenance, decompilation support or vulnerability. Never executes
 * untrusted APK code or sends project data to external services.
 */
public final class ApkIntelligence {
    private ApkIntelligence() {}

    public static JSONObject inspect(JSONObject analysis) throws Exception {
        if (analysis == null) throw new IllegalArgumentException("Relatório ausente");
        // Scan the existing report once using fixed-size flags. In particular,
        // never allocate another 150k-path set while loading a large APK.
        boolean[] signals = new boolean[4]; // Unity, Unreal, Flutter, React Native
        JSONObject explorer = analysis.optJSONObject("explorer");
        JSONArray files = explorer == null ? null : explorer.optJSONArray("files");
        if (files != null) {
            for (int i = 0; i < files.length(); i++) {
                JSONObject file = files.optJSONObject(i);
                if (file != null) mark(file.optString("path", ""), signals);
            }
        }
        JSONArray libs = analysis.optJSONArray("nativeLibraries");
        if (libs != null) for (int i = 0; i < libs.length(); i++)
            mark(libs.optString(i, ""), signals);

        List<String> engines = new ArrayList<>();
        JSONArray evidence = new JSONArray();
        boolean unity = signals[0];
        boolean unreal = signals[1];
        boolean flutter = signals[2];
        boolean react = signals[3];

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

    private static void mark(String value, boolean[] flags) {
        String path = value.toLowerCase(Locale.ROOT);
        if (path.endsWith("/libunity.so") || path.endsWith("/libil2cpp.so")
                || path.startsWith("assets/bin/data/")) flags[0] = true;
        if (path.endsWith("/libue4.so") || path.endsWith("/libunreal.so")
                || path.startsWith("assets/ue4game/")) flags[1] = true;
        if (path.endsWith("/libflutter.so") || path.startsWith("assets/flutter_assets/"))
            flags[2] = true;
        if (path.equals("assets/index.android.bundle")
                || path.equals("assets/index.android.hermes")
                || path.endsWith("/libreactnativejni.so")) flags[3] = true;
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
