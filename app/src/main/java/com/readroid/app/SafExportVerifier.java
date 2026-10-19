package com.readroid.app;

import android.content.ContentResolver;
import android.net.Uri;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;

/**
 * Confirm that the exported file really contains the complete rebuilt ZIP.
 * SAF providers are allowed to acknowledge a write without necessarily
 * preserving every byte; only a full readback can confirm success.
 */
public final class SafExportVerifier {
    private SafExportVerifier() {}

    public static long copyAndVerify(ContentResolver resolver, File source, Uri destination)
            throws IOException {
        if (source == null || !source.isFile() || destination == null)
            throw new IOException("Arquivo ou destino inválido");
        byte[] expected;
        long sourceLength = 0;
        MessageDigest expectedDigest = sha256();
        byte[] buffer = new byte[65536];
        try (InputStream in = new FileInputStream(source)) {
            int n;
            while ((n = in.read(buffer)) != -1) {
                if (Thread.currentThread().isInterrupted())
                    throw new java.io.InterruptedIOException("Exportação interrompida");
                expectedDigest.update(buffer, 0, n);
                sourceLength += n;
            }
        }
        expected = expectedDigest.digest();
        try (InputStream input = new FileInputStream(source);
             OutputStream output = resolver.openOutputStream(destination, "w")) {
            if (output == null) throw new IOException("O Android não abriu o destino para gravação");
            int n;
            while ((n = input.read(buffer)) != -1) {
                if (Thread.currentThread().isInterrupted())
                    throw new java.io.InterruptedIOException("Exportação interrompida");
                output.write(buffer, 0, n);
            }
            output.flush();
        }
        long exportedLength = 0;
        MessageDigest actualDigest = sha256();
        try (InputStream verify = resolver.openInputStream(destination)) {
            if (verify == null)
                throw new IOException("Não foi possível reler o arquivo exportado");
            int n;
            while ((n = verify.read(buffer)) != -1) {
                if (Thread.currentThread().isInterrupted())
                    throw new java.io.InterruptedIOException("Verificação interrompida");
                actualDigest.update(buffer, 0, n);
                exportedLength += n;
                if (exportedLength > sourceLength)
                    throw new IOException("O destino contém bytes extras");
            }
        }
        if (sourceLength != exportedLength || !Arrays.equals(expected, actualDigest.digest()))
            throw new IOException("O arquivo exportado não confere com o APK verificado (SHA-256)");
        return exportedLength;
    }

    private static MessageDigest sha256() throws IOException {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException unavailable) {
            throw new IOException("SHA-256 indisponível", unavailable);
        }
    }
}
