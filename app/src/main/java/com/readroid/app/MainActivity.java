package com.readroid.app;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.net.Uri;
import android.graphics.Color;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

public class MainActivity extends Activity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private TextView output;
    private Button share;
    private JSONObject report;
    private ExplorerView explorerView;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(28, 48, 28, 28);
        root.setBackgroundColor(0xff080b12);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(root);
        setContentView(scroll);

        TextView title = new TextView(this);
        title.setText("ReaDroid Native\nAnálise de APK sem Termux");
        title.setTextSize(26);
        title.setTextColor(Color.WHITE);
        root.addView(title);

        Button choose = new Button(this);
        choose.setText("Selecionar APK");
        root.addView(choose);
        choose.setOnClickListener(v -> {
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("*/*");
            startActivityForResult(intent, 1);
        });

        output = new TextView(this);
        output.setText("Selecione um APK para começar.");
        output.setTextColor(0xffc3d5ee);
        output.setTextSize(15);
        output.setTextIsSelectable(true);
        output.setPadding(0, 25, 0, 25);
        root.addView(output);

        explorerView = new ExplorerView(this, root);

        share = new Button(this);
        share.setText("Compartilhar relatório JSON");
        share.setEnabled(false);
        root.addView(share);
        share.setOnClickListener(v -> {
            if (report == null) return;
            Intent intent = new Intent(Intent.ACTION_SEND);
            intent.setType("application/json");
            intent.putExtra(Intent.EXTRA_TEXT, report.toString());
            startActivity(Intent.createChooser(intent, "Compartilhar relatório"));
        });
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != 1 || result != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        output.setText("Analisando...");
        share.setEnabled(false);
        executor.execute(() -> {
            try {
                JSONObject resultJson = analyze(uri);
                runOnUiThread(() -> {
                    report = resultJson;
                    output.setText(formatReport(resultJson));
                    JSONObject tree = resultJson.optJSONObject("explorer");
                    explorerView.setFiles(tree == null ? null : tree.optJSONArray("files"));
                    share.setEnabled(true);
                });
            } catch (Exception error) {
                runOnUiThread(() -> output.setText("Erro: " + error.getMessage()));
            }
        });
    }

    private JSONObject analyze(Uri uri) throws Exception {
        File file = File.createTempFile("readroid_", ".apk", getCacheDir());
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            long size = 0;
            try (InputStream in = getContentResolver().openInputStream(uri);
                 OutputStream out = new FileOutputStream(file)) {
                if (in == null) throw new IOException("Arquivo inacessível");
                byte[] buffer = new byte[65536];
                int count;
                while ((count = in.read(buffer)) != -1) {
                    size += count;
                    if (size > 1073741824L) throw new IOException("Limite de 1 GB excedido");
                    digest.update(buffer, 0, count);
                    out.write(buffer, 0, count);
                }
            }
            StringBuilder hash = new StringBuilder();
            for (byte b : digest.digest()) hash.append(String.format(Locale.ROOT, "%02x", b & 255));
            JSONArray dex = new JSONArray();
            JSONArray libraries = new JSONArray();
            int entries = 0, assets = 0;
            boolean manifest = false;
            try (ZipFile zip = new ZipFile(file)) {
                Enumeration<? extends ZipEntry> items = zip.entries();
                while (items.hasMoreElements()) {
                    ZipEntry entry = items.nextElement();
                    String name = entry.getName();
                    if (++entries > 150000) throw new IOException("Entradas demais");
                    if (name.matches("classes([0-9]+)?\\.dex")) dex.put(name);
                    if (name.startsWith("lib/") && name.endsWith(".so")) libraries.put(name);
                    if (name.startsWith("assets/") && !entry.isDirectory()) assets++;
                    if (name.equals("AndroidManifest.xml")) manifest = true;
                }
            }
            JSONObject json = new JSONObject();
            json.put("manifestAnalysis", ManifestInspector.inspect(this, file));
            json.put("explorer", ApkExplorer.inspect(file));
            json.put("sizeBytes", size);
            json.put("sha256", hash.toString());
            json.put("entries", entries);
            json.put("dexFiles", dex);
            json.put("nativeLibraries", libraries);
            json.put("assets", assets);
            json.put("hasManifest", manifest);
            try (ZipFile securityZip = new ZipFile(file)) { json.put("security", SecurityScanner.scan(securityZip)); }
            json.put("note", "Análise estática preliminar: não decodifica manifesto binário nem valida assinatura.");
            return json;
        } finally {
            file.delete();
        }
    }

    private String formatReport(JSONObject data) {
        StringBuilder out = new StringBuilder();
        JSONObject manifest = data.optJSONObject("manifestAnalysis");
        out.append("VISÃO GERAL\\n\\n");
        if (manifest != null) {
            out.append("Pacote: ").append(manifest.optString("packageName", "Desconhecido")).append("\\n");
            out.append("Versão: ").append(manifest.optString("versionName", "Desconhecida")).append("\\n");
            out.append("Android mínimo (API): ").append(manifest.optString("minSdk", "?")).append("\\n");
            out.append("Android alvo (API): ").append(manifest.optString("targetSdk", "?")).append("\\n");
            out.append("Permissões: ").append(manifest.optJSONArray("requestedPermissions") == null ? 0 : manifest.optJSONArray("requestedPermissions").length()).append("\\n");
        }
        out.append("Tamanho: ").append(data.optLong("sizeBytes") / 1024).append(" KB\\n");
        out.append("SHA-256: ").append(data.optString("sha256")).append("\\n\\n");
        JSONObject explorer = data.optJSONObject("explorer");
        if (explorer != null) out.append("Arquivos no APK: ").append(explorer.optInt("fileCount")).append("\\n");
        out.append("\\nNavegue pelas pastas e pesquise os arquivos abaixo.\\n");
        out.append("\\nRelatório completo disponível em Compartilhar JSON.");
        return out.toString();
    }

    @Override protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }
}
