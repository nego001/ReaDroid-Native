package com.readroid.app;

import android.app.Activity;
import android.content.Intent;
import org.json.JSONObject;

public final class AiBridge {
    private AiBridge() {}

    public static void shareReport(Activity activity, JSONObject report) {
        if (report == null) return;
        JSONObject manifest = report.optJSONObject("manifestAnalysis");
        String prompt = "Explique este resumo de análise estática de APK do ReaDroid Native:\n"
            + "Pacote: " + (manifest == null ? "desconhecido" : manifest.optString("packageName")) + "\n"
            + "Versão: " + (manifest == null ? "desconhecida" : manifest.optString("versionName")) + "\n"
            + "SHA-256: " + report.optString("sha256") + "\n"
            + "Tamanho: " + report.optLong("sizeBytes") + " bytes\n"
            + "DEX: " + report.optJSONArray("dexFiles");
        share(activity, prompt);
    }

    public static void shareFile(Activity activity, String path, String category) {
        share(activity, "Explique a função deste arquivo em um APK e possíveis alterações autorizadas:\nCaminho: " + path + "\nTipo: " + category);
    }

    private static void share(Activity activity, String text) {
        new android.app.AlertDialog.Builder(activity)
            .setTitle("ReaDroid AI Bridge")
            .setMessage("Revise os dados antes de compartilhar. Nada será enviado automaticamente.\n\n" + text)
            .setNegativeButton("Cancelar", null)
            .setPositiveButton("Compartilhar", (dialog, which) -> {
                Intent intent = new Intent(Intent.ACTION_SEND);
                intent.setType("text/plain");
                intent.putExtra(Intent.EXTRA_TEXT, text);
                activity.startActivity(Intent.createChooser(intent, "Compartilhar com assistente"));
            }).show();
    }
}
