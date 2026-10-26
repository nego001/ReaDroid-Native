package com.readroid.app;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashSet;
import java.util.Set;

/**
 * M2.5: ZIP admission keeps fixed-width SHA-256/128 fingerprints of paths,
 * never the original untrusted path Strings.
 *
 * Equal paths always produce equal fingerprints. A digest collision between
 * different paths is deliberately rejected as a conservative false positive,
 * never accepted as a distinct path (fail closed). No path extraction occurs.
 * The 150k entry and aggregate path-char limits are enforced by the caller.
 */
final class ApkPathFingerprintSet {
    private static final int FINGERPRINT_BYTES = 16;
    private final MessageDigest sha256;
    private final Set<Fingerprint> seen = new HashSet<>();

    ApkPathFingerprintSet() throws IOException {
        try {
            sha256 = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException unavailable) {
            throw new IOException("SHA-256 indisponível para validar caminhos ZIP", unavailable);
        }
    }

    int size() {
        return seen.size();
    }

    void requireUnique(String path) throws IOException {
        if (path == null)
            throw new IOException("Caminho ZIP ausente");
        // Caller has validated path length and structure first. Keep only two
        // 64-bit digest words per path instead of retaining a potentially long
        // attacker-controlled Java String in the admission set.
        byte[] digest = sha256.digest(path.getBytes(StandardCharsets.UTF_8));
        Fingerprint fingerprint = new Fingerprint(readLong(digest, 0),
            readLong(digest, FINGERPRINT_BYTES / 2));
        if (!seen.add(fingerprint))
            throw new IOException("Entrada ZIP duplicada ou impressão digital colidiu: " + path);
    }

    private static long readLong(byte[] bytes, int offset) {
        long result = 0;
        for (int i = 0; i < 8; i++)
            result = (result << 8) | (bytes[offset + i] & 255L);
        return result;
    }

    private static final class Fingerprint {
        final long high;
        final long low;

        Fingerprint(long high, long low) {
            this.high = high;
            this.low = low;
        }

        @Override public boolean equals(Object other) {
            if (this == other) return true;
            if (!(other instanceof Fingerprint)) return false;
            Fingerprint that = (Fingerprint) other;
            return high == that.high && low == that.low;
        }

        @Override public int hashCode() {
            long mixed = high ^ Long.rotateLeft(low, 23);
            return (int) (mixed ^ (mixed >>> 32));
        }
    }
}
