package com.readroid.app;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.util.zip.CRC32;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Read-only prefix of an uncompressed ZIP entry; offsets are entry-relative. */
final class ApkHexPreview {
    static final int MAX_BYTES = 4096;
    private static final char[] HEX = "0123456789ABCDEF".toCharArray();

    static final class Result {
        final long size;
        final int shown;
        final boolean truncated;
        final String dump;
        final boolean nativeUsed;
        Result(long size, int shown, String dump, boolean nativeUsed) {
            this.size = size;
            this.shown = shown;
            this.truncated = size > shown;
            this.dump = dump;
            this.nativeUsed = nativeUsed;
        }
    }

    private ApkHexPreview() {}

    static Result read(File apk, String path) throws IOException {
        if (apk == null || path == null || path.isEmpty() || path.startsWith("/")
                || path.contains("\\") || path.contains("../") || path.equals("..")
                || path.endsWith("/.."))
            throw new IOException("Caminho inválido");
        try (ZipFile zip = new ZipFile(apk)) {
            ZipEntry entry = zip.getEntry(path);
            if (entry == null || entry.isDirectory())
                throw new IOException("Arquivo não encontrado");
            long size = entry.getSize();
            if (size < 0) throw new IOException("Tamanho desconhecido");
            byte[] bytes = new byte[(int) Math.min(size, MAX_BYTES)];
            try (InputStream in = zip.getInputStream(entry)) {
                int pos = 0;
                while (pos < bytes.length) {
                    if (Thread.currentThread().isInterrupted())
                        throw new java.io.InterruptedIOException("Prévia interrompida");
                    int n = in.read(bytes, pos, bytes.length - pos);
                    if (n <= 0) throw new IOException("Entrada ZIP incompleta");
                    pos += n;
                }
                if (size <= MAX_BYTES) {
                    CRC32 crc = new CRC32();
                    crc.update(bytes);
                    if (in.read() != -1 || crc.getValue() != entry.getCrc())
                        throw new IOException("Integridade da entrada ZIP inválida");
                }
            }
            if (Thread.currentThread().isInterrupted())
                throw new java.io.InterruptedIOException("Prévia interrompida");
            NativeHexBackend.Selection selected;
            try (NativeHexSession session = NativeHexSession.open()) {
                selected = session.format(bytes, format(bytes), BuildConfig.NATIVE_HEX_ENABLED);
            }
            if (Thread.currentThread().isInterrupted())
                throw new java.io.InterruptedIOException("Prévia interrompida");
            return new Result(size, bytes.length, selected.dump, selected.nativeUsed);
        }
    }

    private static void appendHex(StringBuilder out, int value, int digits) {
        for (int shift = (digits - 1) * 4; shift >= 0; shift -= 4)
            out.append(HEX[(value >>> shift) & 15]);
    }

    private static String format(byte[] bytes) {
        StringBuilder out = new StringBuilder(bytes.length * 5 + 32);
        for (int offset = 0; offset < bytes.length; offset += 16) {
            appendHex(out, offset, 8);
            out.append("  ");
            for (int col = 0; col < 16; col++) {
                if (offset + col < bytes.length)
                    appendHex(out, bytes[offset + col] & 255, 2);
                else out.append("  ");
                out.append(' ');
            }
            out.append(" |");
            for (int col = 0; col < 16 && offset + col < bytes.length; col++) {
                int value = bytes[offset + col] & 255;
                out.append(value >= 32 && value <= 126 ? (char) value : '.');
            }
            out.append("|\n");
        }
        return out.toString();
    }
}
