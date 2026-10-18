package com.readroid.app;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Safely preview small UTF-8 text entries without extracting APK content. */
public final class ApkPreview {
    private static final int MAX_BYTES = 128 * 1024;
    private ApkPreview() {}

    public static String readText(File apk, String path) throws IOException {
        if (path == null || path.isEmpty() || path.startsWith("/") || path.contains("\\") || path.contains("../"))
            throw new IOException("Caminho inválido");
        try (ZipFile zip = new ZipFile(apk)) {
            ZipEntry entry = zip.getEntry(path);
            if (entry == null || entry.isDirectory()) throw new IOException("Arquivo não encontrado");
            if (entry.getSize() > MAX_BYTES) throw new IOException("Arquivo grande demais para pré-visualização (128 KB)");
            try (InputStream in = zip.getInputStream(entry);
                 ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                int n;
                while ((n = in.read(buffer)) != -1) {
                    if (out.size() + n > MAX_BYTES) throw new IOException("Pré-visualização limitada a 128 KB");
                    out.write(buffer, 0, n);
                }
                byte[] bytes = out.toByteArray();
                for (byte b : bytes) if (b == 0) throw new IOException("Arquivo binário: pré-visualização textual indisponível");
                try {
                    return StandardCharsets.UTF_8.newDecoder()
                        .onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT)
                        .decode(ByteBuffer.wrap(bytes)).toString();
                } catch (CharacterCodingException e) {
                    throw new IOException("Arquivo não contém texto UTF-8 válido");
                }
            }
        }
    }
}
