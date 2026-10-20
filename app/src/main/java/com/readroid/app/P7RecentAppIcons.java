package com.readroid.app;

import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import android.net.Uri;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Safe, small previews extracted from the actual user-selected APK.
 * The app never installs/executes the archive and never assumes a brand icon.
 * Only APKs with a persisted SAF READ grant receive a private cached thumbnail.
 */
public final class P7RecentAppIcons {
    private static final String DIRECTORY = "p7_recent_icons";
    private static final int ICON_SIZE = 64;
    private static final long MAX_CACHED_BYTES = 96 * 1024;

    private P7RecentAppIcons() {}

    private static File directory(Context context) {
        return new File(context.getFilesDir(), DIRECTORY);
    }

    private static String filename(Uri uri) {
        if (uri == null || !"content".equals(uri.getScheme())) return null;
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                .digest(uri.toString().getBytes(StandardCharsets.UTF_8));
            StringBuilder name = new StringBuilder(68);
            for (byte b : digest)
                name.append(Character.forDigit((b >>> 4) & 15, 16))
                    .append(Character.forDigit(b & 15, 16));
            return name.append(".png").toString();
        } catch (Exception unexpected) {
            return null;
        }
    }

    /** PackageManager reads resource metadata in the archive, not executable code. */
    static Bitmap extract(Context context, File copiedApk) {
        if (copiedApk == null || !copiedApk.isFile()) return null;
        try {
            PackageManager pm = context.getPackageManager();
            PackageInfo info = pm.getPackageArchiveInfo(copiedApk.getAbsolutePath(), 0);
            if (info == null || info.applicationInfo == null
                    || info.applicationInfo.icon == 0) return null;
            ApplicationInfo app = info.applicationInfo;
            app.sourceDir = copiedApk.getAbsolutePath();
            app.publicSourceDir = copiedApk.getAbsolutePath();
            Drawable drawable = pm.getApplicationIcon(app);
            if (drawable == null) return null;
            Bitmap bitmap = Bitmap.createBitmap(ICON_SIZE, ICON_SIZE,
                Bitmap.Config.ARGB_8888);
            Canvas canvas = new Canvas(bitmap);
            drawable.setBounds(0, 0, ICON_SIZE, ICON_SIZE);
            drawable.draw(canvas);
            return bitmap;
        } catch (RuntimeException invalidArchive) {
            // ZIP resources and XML from the APK are untrusted.
            return null;
        }
    }

    /**
     * Called on the worker thread only after a successful analysis and the
     * history record. Permission is checked again at the point of writing.
     */
    public static boolean capture(Context context, Uri uri, File copiedApk) {
        String name = filename(uri);
        if (name == null || !P7ProjectHistory.hasPermission(context, uri))
            return false;
        Bitmap icon = extract(context, copiedApk);
        if (icon == null) return false;
        File temp = null;
        try {
            File dir = directory(context);
            if (!dir.isDirectory() && !dir.mkdirs()) return false;
            temp = File.createTempFile("thumb_", ".tmp", dir);
            try (FileOutputStream out = new FileOutputStream(temp)) {
                if (!icon.compress(Bitmap.CompressFormat.PNG, 100, out)) return false;
                out.getFD().sync();
            }
            if (temp.length() == 0 || temp.length() > MAX_CACHED_BYTES)
                return false;
            File target = new File(dir, name);
            if (target.exists() && !target.delete()) return false;
            return temp.renameTo(target);
        } catch (IOException ignored) {
            return false;
        } finally {
            icon.recycle();
            if (temp != null) temp.delete();
        }
    }

    /** Only decode files named by an authorized SAF URI. */
    public static Bitmap load(Context context, Uri uri) {
        String name = filename(uri);
        if (name == null || !P7ProjectHistory.hasPermission(context, uri))
            return null;
        File icon = new File(directory(context), name);
        if (!icon.isFile() || icon.length() <= 0 ||
                icon.length() > MAX_CACHED_BYTES) return null;
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(icon.getAbsolutePath(), options);
        if (options.outWidth <= 0 || options.outHeight <= 0 ||
                options.outWidth > 128 || options.outHeight > 128) return null;
        options.inJustDecodeBounds = false;
        return BitmapFactory.decodeFile(icon.getAbsolutePath(), options);
    }

    /** Called off the UI thread after a successful insert or explicit clear. */
    public static void prune(Context context, List<P7ProjectHistory.Entry> entries) {
        File[] files = directory(context).listFiles();
        if (files == null) return;
        Set<String> keep = new HashSet<>();
        for (P7ProjectHistory.Entry item : entries) {
            String name = filename(item.uri);
            if (name != null && P7ProjectHistory.hasPermission(context, item.uri))
                keep.add(name);
        }
        for (File file : files) {
            if (file.isFile() && !keep.contains(file.getName())) file.delete();
        }
    }
}
