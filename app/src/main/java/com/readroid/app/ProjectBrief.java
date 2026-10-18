package com.readroid.app;

import android.app.Activity;
import android.content.Intent;
import android.widget.EditText;
import android.widget.LinearLayout;
import org.json.JSONObject;

/** Generates a user-reviewed project brief. Does not patch or distribute APKs. */
public final class ProjectBrief {
    private ProjectBrief() {}

    public static void create(Activity activity, JSONObject report) {
        if (report == null) return;
        LinearLayout fields = new LinearLayout(activity);
        fields.setOrientation(LinearLayout.VERTICAL);
        fields.setPadding(28, 12, 28, 8);
        EditText name = new EditText(activity);
        name.setHint("Nome da sua versão");
        fields.addView(name);
        EditText changes = new EditText(activity);
        changes.setHint("O que você quer modificar?");
        changes.setMinLines(3);
        changes.setMaxLines(6);
        fields.addView(changes);
        new android.app.AlertDialog.Builder(activity)
            .setTitle("Criar minha versão")
            .setMessage("Planejamento somente. Confirme que possui autorização para modificar o aplicativo.")
            .setView(fields)
            .setNegativeButton("Cancelar", null)
            .setPositiveButton("Preparar projeto", (dialog, which) -> {
                JSONObject manifest = report.optJSONObject("manifestAnalysis");
                String text = "# Projeto ReaDroid Native\n\n"
                    + "Nome: " + name.getText().toString().trim() + "\n"
                    + "APK original (pacote): " + (manifest == null ? "desconhecido" : manifest.optString("packageName")) + "\n"
                    + "Versão original: " + (manifest == null ? "desconhecida" : manifest.optString("versionName")) + "\n"
                    + "SHA-256 original: " + report.optString("sha256") + "\n"
                    + "Alterações pretendidas:\n" + changes.getText().toString().trim() + "\n\n"
                    + "Status: planejamento. Nenhum APK foi alterado.\n"
                    + "Próximos passos: verificar autorização, avaliar viabilidade e desenvolver com testes.";
                Intent send = new Intent(Intent.ACTION_SEND);
                send.setType("text/plain");
                send.putExtra(Intent.EXTRA_TEXT, text);
                activity.startActivity(Intent.createChooser(send, "Compartilhar projeto"));
            }).show();
    }
}
