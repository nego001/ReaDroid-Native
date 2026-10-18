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
    private Button ai;
    private Button project;
    private Button editExport;
    private Button rebuild;
    private Button signatureInfo;
    private Button signingGuide;
    private Button localIdentity;
    private Button signingTest;
    private static final int REQUEST_EXPORT_APK = 2;
    private JSONObject report;
    private File currentApk;
    private ExplorerView explorerView;
    private LinearLayout homeSection;
    private LinearLayout filesSection;
    private LinearLayout securitySection;
    private LinearLayout buildSection;
    private LinearLayout aiSection;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(NegrescoTheme.dp(this, 20), NegrescoTheme.dp(this, 34), NegrescoTheme.dp(this, 20), NegrescoTheme.dp(this, 24));
        root.setBackgroundColor(NegrescoTheme.BACKGROUND);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(root);
        setContentView(scroll);

        TextView title = new TextView(this);
        title.setText("NEGRESCODROID\nAPK ENGINEERING STUDIO");
        title.setTextSize(25);
        title.setTextColor(NegrescoTheme.TEXT);
        root.addView(title);

        LinearLayout nav = new LinearLayout(this);
        nav.setOrientation(LinearLayout.HORIZONTAL);
        root.addView(nav);
        String[] tabs = {"Início", "Arquivos", "Construir", "Segurança", "IA"};
        for (int index = 0; index < tabs.length; index++) {
            final int target = index;
            Button tab = NegrescoTheme.action(this, tabs[index], false);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, NegrescoTheme.dp(this, 52), 1f);
            lp.setMargins(0, 0, NegrescoTheme.dp(this, 3), NegrescoTheme.dp(this, 12));
            tab.setLayoutParams(lp);
            tab.setTextSize(10);
            nav.addView(tab);
            tab.setOnClickListener(v -> showSection(target));
        }
        homeSection = section(root);
        filesSection = section(root);
        buildSection = section(root);
        securitySection = section(root);
        aiSection = section(root);

        Button choose = NegrescoTheme.action(this, "ABRIR APK", true);
        choose.setText("Selecionar APK");
        homeSection.addView(choose);
        choose.setOnClickListener(v -> {
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("*/*");
            startActivityForResult(intent, 1);
        });

        output = new TextView(this);
        output.setText("Selecione um APK para começar.");
        output.setTextColor(NegrescoTheme.MUTED);
        output.setTextSize(15);
        output.setTextIsSelectable(true);
        output.setPadding(NegrescoTheme.dp(this, 12), NegrescoTheme.dp(this, 16), NegrescoTheme.dp(this, 12), NegrescoTheme.dp(this, 16));
        output.setBackground(NegrescoTheme.panel(this));
        homeSection.addView(output);

        explorerView = new ExplorerView(this, filesSection);

        ai = NegrescoTheme.action(this, "", false);
        ai.setText("Analisar com ChatGPT / IA");
        ai.setEnabled(false);
        aiSection.addView(ai);
        ai.setOnClickListener(v -> AiBridge.shareReport(this, report));

        project = NegrescoTheme.action(this, "", false);
        project.setText("Criar minha versão");
        project.setEnabled(false);
        homeSection.addView(project);
        project.setOnClickListener(v -> ProjectBrief.create(this, report));

        editExport = NegrescoTheme.action(this, "", false);
        editExport.setText("Compartilhar plano de alterações");
        buildSection.addView(editExport);
        editExport.setOnClickListener(v -> {
            try {
                String content = explorerView.getEditPlan().toJson().toString(2);
                Intent send = new Intent(Intent.ACTION_SEND);
                send.setType("text/plain");
                send.putExtra(Intent.EXTRA_TEXT, content);
                startActivity(Intent.createChooser(send, "Compartilhar plano"));
            } catch (Exception error) {
                output.setText("Erro ao preparar plano: " + error.getMessage());
            }
        });

        signatureInfo = NegrescoTheme.action(this, "", false);
        signatureInfo.setText("Ver certificado de assinatura");
        signatureInfo.setEnabled(false);
        securitySection.addView(signatureInfo);
        signatureInfo.setOnClickListener(v -> {
            if (currentApk == null) return;
            final File file = currentApk;
            executor.execute(() -> {
                final String details = ApkSignatureInspector.inspect(this, file);
                runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                    .setTitle("Certificado do APK")
                    .setMessage(details)
                    .setPositiveButton("OK", null).show());
            });
        });

        signingGuide = NegrescoTheme.action(this, "", false);
        signingGuide.setText("Assinatura: requisitos e segurança");
        securitySection.addView(signingGuide);
        signingGuide.setOnClickListener(v -> new android.app.AlertDialog.Builder(this)
            .setTitle("Assinatura de APK modificado")
            .setMessage("O APK exportado ainda não pode ser considerado instalável. Para assinar corretamente, precisamos de alinhamento ZIP, assinatura APK Signature Scheme v2/v3 e verificação criptográfica.\\n\\nUma chave própria deve ser gerada e protegida, nunca enviada ao ChatGPT ou ao GitHub. A nova assinatura não substitui a identidade do desenvolvedor original e pode exigir desinstalar a versão anterior.\\n\\nO ReaDroid ainda NÃO assina APKs modificados.")
            .setPositiveButton("Entendi", null).show());

        localIdentity = NegrescoTheme.action(this, "", false);
        localIdentity.setText("Minha chave de assinatura local");
        securitySection.addView(localIdentity);
        localIdentity.setOnClickListener(v -> executor.execute(() -> {
            String status;
            try { status = LocalSigningIdentity.describe(); }
            catch (Exception error) { status = "Erro: " + error.getMessage(); }
            final String result = status;
            runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                .setTitle("Identidade local")
                .setMessage(result + "\n\nA chave pode ser perdida ao desinstalar o ReaDroid ou limpar seus dados. Faça isso somente se compreender que atualizações assinadas por outra chave não são compatíveis.")
                .setNegativeButton("Fechar", null)
                .setPositiveButton("Criar se necessário", (dialog, which) ->
                    new android.app.AlertDialog.Builder(this)
                        .setTitle("Criar identidade?")
                        .setMessage("A chave privada ficará no Android Keystore. Ela não será enviada nem exportada. Criar?")
                        .setNegativeButton("Cancelar", null)
                        .setPositiveButton("Criar", (d, w) -> executor.execute(() -> {
                            String detail;
                            try { detail = LocalSigningIdentity.create(); }
                            catch (Exception error) { detail = "Falha: " + error.getMessage(); }
                            final String message = detail;
                            runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                                .setTitle("Identidade de assinatura")
                                .setMessage(message).setPositiveButton("OK", null).show());
                        })).show())
                .show());
        }));

        signingTest = NegrescoTheme.action(this, "", false);
        signingTest.setText("Testar assinatura da chave local");
        securitySection.addView(signingTest);
        signingTest.setOnClickListener(v -> {
            signingTest.setEnabled(false);
            executor.execute(() -> {
                String message;
                try { message = SigningSelfTest.run(); }
                catch (Exception error) { message = "Teste falhou: " + error.getMessage(); }
                final String result = message;
                runOnUiThread(() -> {
                    signingTest.setEnabled(true);
                    new android.app.AlertDialog.Builder(this).setTitle("Autoteste criptográfico")
                        .setMessage(result).setPositiveButton("OK", null).show();
                });
            });
        });

        rebuild = NegrescoTheme.action(this, "", false);
        rebuild.setText("Exportar APK modificado (sem assinatura)");
        rebuild.setEnabled(false);
        buildSection.addView(rebuild);
        rebuild.setOnClickListener(v -> {
            if (currentApk == null || explorerView.getEditPlan().size() == 0) {
                new android.app.AlertDialog.Builder(this).setMessage("Primeiro registre uma alteração textual no explorador.").setPositiveButton("OK", null).show();
                return;
            }
            new android.app.AlertDialog.Builder(this)
                .setTitle("Reconstrução experimental")
                .setMessage("O resultado NÃO estará assinado e pode não instalar ou funcionar. O APK original será preservado. Continuar?")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Escolher destino", (dialog, which) -> {
                    Intent create = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    create.addCategory(Intent.CATEGORY_OPENABLE);
                    create.setType("application/vnd.android.package-archive");
                    create.putExtra(Intent.EXTRA_TITLE, "negrescodroid-modificado-unsigned.apk");
                    startActivityForResult(create, REQUEST_EXPORT_APK);
                }).show();
        });

        share = NegrescoTheme.action(this, "", false);
        share.setText("Compartilhar relatório JSON");
        share.setEnabled(false);
        aiSection.addView(share);
        share.setOnClickListener(v -> {
            if (report == null) return;
            Intent intent = new Intent(Intent.ACTION_SEND);
            intent.setType("application/json");
            intent.putExtra(Intent.EXTRA_TEXT, report.toString());
            startActivity(Intent.createChooser(intent, "Compartilhar relatório"));
        });
        showSection(0);
    }

    private LinearLayout section(LinearLayout parent) {
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        parent.addView(content);
        return content;
    }

    private void showSection(int index) {
        LinearLayout[] sections = {homeSection, filesSection, buildSection, securitySection, aiSection};
        for (int i = 0; i < sections.length; i++) sections[i].setVisibility(i == index ? View.VISIBLE : View.GONE);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (result != RESULT_OK || data == null || data.getData() == null) return;
        if (request == REQUEST_EXPORT_APK) { exportRebuilt(data.getData()); return; }
        if (request != 1) return;
        Uri uri = data.getData();
        report = null;
        if (currentApk != null) { currentApk.delete(); currentApk = null; }
        output.setText("Analisando...");
        share.setEnabled(false);
        ai.setEnabled(false);
        project.setEnabled(false);
        rebuild.setEnabled(false);
        signatureInfo.setEnabled(false);
        explorerView.getEditPlan().clear();
        executor.execute(() -> {
            try {
                JSONObject resultJson = analyze(uri);
                runOnUiThread(() -> {
                    report = resultJson;
                    output.setText(formatReport(resultJson));
                    JSONObject tree = resultJson.optJSONObject("explorer");
                    explorerView.setFiles(tree == null ? null : tree.optJSONArray("files"), currentApk);
                    share.setEnabled(true);
                    ai.setEnabled(true);
                    project.setEnabled(true);
                    rebuild.setEnabled(true);
                    signatureInfo.setEnabled(true);
                });
            } catch (Exception error) {
                runOnUiThread(() -> output.setText("Erro: " + error.getMessage()));
            }
        });
    }

    private void exportRebuilt(Uri destination) {
        if (currentApk == null) return;
        final File source = currentApk;
        final Map<String, String> changes = explorerView.getEditPlan().snapshot();
        if (changes.isEmpty()) return;
        rebuild.setEnabled(false);
        executor.execute(() -> {
            File temp = null;
            try {
                temp = File.createTempFile("readroid_unsigned_", ".apk", getCacheDir());
                ApkRebuilder.rebuild(source, temp, changes);
                final String verification = RebuildVerifier.verify(temp, changes);
                final String preflight = SigningPreflight.inspect(temp);
                try (InputStream in = new FileInputStream(temp);
                     OutputStream out = getContentResolver().openOutputStream(destination, "w")) {
                    if (out == null) throw new IOException("Destino inacessível");
                    byte[] buffer = new byte[65536];
                    int n;
                    while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
                }
                runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                    .setTitle("APK não assinado exportado")
                    .setMessage(verification + "\\n\\nO arquivo original foi preservado.")
                    .setPositiveButton("OK", null).show());
            } catch (Exception error) {
                runOnUiThread(() -> new android.app.AlertDialog.Builder(this)
                    .setTitle("Falha na reconstrução").setMessage(error.getMessage())
                    .setPositiveButton("OK", null).show());
            } finally {
                if (temp != null) temp.delete();
                runOnUiThread(() -> rebuild.setEnabled(true));
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
            currentApk = file;
            return json;
        } catch (Exception error) {
            file.delete();
            throw error;
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
        if (currentApk != null) currentApk.delete();
        super.onDestroy();
    }
}
