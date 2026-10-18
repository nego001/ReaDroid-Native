package com.readroid.app;

import android.content.Context;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.ProviderInfo;
import android.content.pm.ServiceInfo;
import android.os.Build;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;

/** Decodes Android's binary manifest through the platform PackageManager. */
public final class ManifestInspector {
    private ManifestInspector() {}

    public static JSONObject inspect(Context context, File apk) throws Exception {
        PackageManager pm = context.getPackageManager();
        int flags = PackageManager.GET_PERMISSIONS | PackageManager.GET_ACTIVITIES
                | PackageManager.GET_SERVICES | PackageManager.GET_RECEIVERS
                | PackageManager.GET_PROVIDERS;
        PackageInfo info;
        if (Build.VERSION.SDK_INT >= 33) {
            info = pm.getPackageArchiveInfo(apk.getAbsolutePath(),
                    PackageManager.PackageInfoFlags.of(flags));
        } else {
            info = pm.getPackageArchiveInfo(apk.getAbsolutePath(), flags);
        }
        if (info == null) throw new IllegalArgumentException("Manifesto inválido ou não reconhecido pelo Android");
        JSONObject result = new JSONObject();
        result.put("packageName", info.packageName);
        result.put("versionName", info.versionName == null ? JSONObject.NULL : info.versionName);
        result.put("versionCode", Build.VERSION.SDK_INT >= 28 ? info.getLongVersionCode() : info.versionCode);
        if (info.applicationInfo != null) {
            result.put("minSdk", info.applicationInfo.minSdkVersion);
            result.put("targetSdk", info.applicationInfo.targetSdkVersion);
            result.put("debuggable", (info.applicationInfo.flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0);
            result.put("allowBackup", (info.applicationInfo.flags & android.content.pm.ApplicationInfo.FLAG_ALLOW_BACKUP) != 0);
        }
        JSONArray permissions = new JSONArray();
        if (info.requestedPermissions != null) for (String permission : info.requestedPermissions) permissions.put(permission);
        result.put("requestedPermissions", permissions);
        JSONArray components = new JSONArray();
        if (info.activities != null) for (ActivityInfo item : info.activities) components.put(component("activity", item.name, item.exported, item.permission));
        if (info.receivers != null) for (ActivityInfo item : info.receivers) components.put(component("receiver", item.name, item.exported, item.permission));
        if (info.services != null) for (ServiceInfo item : info.services) components.put(component("service", item.name, item.exported, item.permission));
        if (info.providers != null) for (ProviderInfo item : info.providers) components.put(component("provider", item.name, item.exported, item.readPermission == null ? item.writePermission : item.readPermission));
        result.put("components", components);
        JSONArray findings = new JSONArray();
        if (result.optBoolean("debuggable")) findings.put(finding("high", "Aplicativo depurável", "android:debuggable está habilitado."));
        if (result.optBoolean("allowBackup")) findings.put(finding("warning", "Backup permitido", "Verifique as regras de backup e os dados incluídos."));
        for (int i=0; i<components.length(); i++) {
            JSONObject c = components.getJSONObject(i);
            if (c.getBoolean("exported") && c.isNull("permission")) {
                findings.put(finding("review", "Componente exportado sem permissão", c.getString("type") + ": " + c.getString("name") + ". Pode ser intencional; revise os intent-filters e controles internos."));
            }
        }
        result.put("findings", findings);
        result.put("limitations", "O PackageManager pode omitir detalhes do XML, como intent-filters e networkSecurityConfig; os alertas precisam de revisão contextual.");
        return result;
    }

    private static JSONObject component(String type, String name, boolean exported, String permission) throws Exception {
        JSONObject o = new JSONObject();
        o.put("type", type); o.put("name", name); o.put("exported", exported);
        o.put("permission", permission == null ? JSONObject.NULL : permission);
        return o;
    }

    private static JSONObject finding(String severity, String title, String detail) throws Exception {
        JSONObject o = new JSONObject();
        o.put("severity", severity); o.put("title", title); o.put("explanation", detail);
        return o;
    }
}
