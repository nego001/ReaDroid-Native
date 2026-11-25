package com.readroid.app;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.util.Locale;
import java.util.zip.CRC32;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Bounded, read-only raster preview. No extraction, animation or editing. */
final class ApkImagePreview {
    static final int MAX_ENCODED_BYTES = 8 * 1024 * 1024;
    static final int MAX_SOURCE_EDGE = 8192;
    static final long MAX_SOURCE_PIXELS = 32L * 1024 * 1024;
    static final int MAX_PREVIEW_EDGE = 1024;

    static final class Result {
        final Bitmap bitmap;
        final int width, height;
        final String mime;
        Result(Bitmap bitmap, int width, int height, String mime) {
            this.bitmap = bitmap;
            this.width = width;
            this.height = height;
            this.mime = mime;
        }
    }

    private ApkImagePreview() {}

    private static String expectedMime(String path) {
        if (path == null) return null;
        String p = path.toLowerCase(Locale.ROOT);
        if (p.endsWith(".png")) return "image/png";
        if (p.endsWith(".jpg") || p.endsWith(".jpeg")) return "image/jpeg";
        if (p.endsWith(".webp")) return "image/webp";
        return null;
    }

    static boolean supports(String path) { return expectedMime(path) != null; }

    static Result read(File apk, String path) throws IOException {
        String mime = expectedMime(path);
        if (mime == null || path.startsWith("/") || path.contains("\\")
                || path.contains("../") || path.contains("/..") || apk == null)
            throw new IOException("Formato ou caminho de imagem não suportado");
        byte[] data;
        try (ZipFile zip = new ZipFile(apk)) {
            ZipEntry entry = zip.getEntry(path);
            if (entry == null || entry.isDirectory()) throw new IOException("Imagem não encontrada");
            long size = entry.getSize();
            if (size <= 0 || size > MAX_ENCODED_BYTES)
                throw new IOException("Imagem acima do limite de 8 MiB ou vazia");
            data = new byte[(int) size];
            CRC32 crc = new CRC32();
            try (InputStream in = zip.getInputStream(entry)) {
                int pos = 0;
                while (pos < data.length) {
                    int n = in.read(data, pos, Math.min(65536, data.length - pos));
                    if (n <= 0) throw new IOException("Imagem ZIP incompleta");
                    crc.update(data, pos, n);
                    pos += n;
                }
                if (in.read() != -1 || crc.getValue() != entry.getCrc())
                    throw new IOException("Integridade da imagem ZIP inválida");
            }
        }
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(data, 0, data.length, bounds);
        int w = bounds.outWidth, h = bounds.outHeight;
        if (!mime.equals(bounds.outMimeType) || w <= 0 || h <= 0)
            throw new IOException("Imagem inválida ou formato diferente da extensão");
        if (w > MAX_SOURCE_EDGE || h > MAX_SOURCE_EDGE
                || (long) w * h > MAX_SOURCE_PIXELS)
            throw new IOException("Dimensões da imagem acima do limite de prévia");
        int sample = 1;
        while ((Math.max(w, h) + sample - 1) / sample > MAX_PREVIEW_EDGE)
            sample *= 2;
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = sample;
        options.inScaled = false;
        options.inPreferredConfig = Bitmap.Config.ARGB_8888;
        Bitmap bitmap = BitmapFactory.decodeByteArray(data, 0, data.length, options);
        if (bitmap == null) throw new IOException("Não foi possível decodificar a imagem");
        if (bitmap.getWidth() > MAX_PREVIEW_EDGE || bitmap.getHeight() > MAX_PREVIEW_EDGE) {
            bitmap.recycle();
            throw new IOException("Prévia decodificada acima do limite");
        }
        return new Result(bitmap, w, h, mime);
    }
}
