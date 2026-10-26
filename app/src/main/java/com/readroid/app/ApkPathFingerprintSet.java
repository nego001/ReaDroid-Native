package com.readroid.app;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * M2.7: fixed-width SHA-256/128 path identifiers in a bounded, primitive
 * open-addressed table. Never retains the attacker-controlled path Strings.
 *
 * Two distinct names with an identical 128-bit digest are rejected rather
 * than silently admitted. Slot hash collisions are resolved by probing and
 * comparing BOTH 64-bit words, not by rejecting different identifiers.
 * The table does not execute or extract anything from an APK.
 */
final class ApkPathFingerprintSet {
    private static final int INITIAL_CAPACITY = 256;
    private static final int MAX_ENTRIES = 150000;
    private static final int DIGEST_BYTES = 32;
    private final MessageDigest sha256;
    private final byte[] digestBuffer = new byte[DIGEST_BYTES];
    private long[] high = new long[INITIAL_CAPACITY];
    private long[] low = new long[INITIAL_CAPACITY];
    private byte[] occupied = new byte[INITIAL_CAPACITY];
    private int count;

    ApkPathFingerprintSet() throws IOException {
        try {
            sha256 = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException unavailable) {
            throw new IOException("SHA-256 indisponível para validar caminhos ZIP", unavailable);
        }
    }

    int size() {
        return count;
    }

    /** Visible to package-scoped tests; slots remain private and non-editable. */
    int capacity() {
        return occupied.length;
    }

    void requireUnique(String path) throws IOException {
        if (path == null)
            throw new IOException("Caminho ZIP ausente");
        if (count >= MAX_ENTRIES)
            throw new IOException("APK excede 150 mil caminhos verificados");
        sha256.update(path.getBytes(StandardCharsets.UTF_8));
        try {
            if (sha256.digest(digestBuffer, 0, DIGEST_BYTES) != DIGEST_BYTES)
                throw new IOException("Digest SHA-256 incompleto");
        } catch (java.security.DigestException invalid) {
            throw new IOException("Falha ao calcular hash de caminho ZIP", invalid);
        }
        long first = readLong(digestBuffer, 0);
        long second = readLong(digestBuffer, 8);
        // Keep load below 70% so hostile inputs cannot force an unbounded
        // probe chain in an almost-full table. Maximum growth is 262144 slots
        // for the 150000 permitted paths.
        if ((count + 1L) * 10 > occupied.length * 7L)
            grow();
        insert(first, second, path);
    }

    private void insert(long first, long second, String path) throws IOException {
        int index = bucket(first, second, occupied.length);
        while (occupied[index] != 0) {
            if (high[index] == first && low[index] == second)
                throw new IOException(
                    "Entrada ZIP duplicada ou impressão digital colidiu: " + path);
            index = (index + 1) & (occupied.length - 1);
        }
        occupied[index] = 1;
        high[index] = first;
        low[index] = second;
        count++;
    }

    private void grow() throws IOException {
        if (occupied.length >= (1 << 18))
            throw new IOException("Orçamento máximo de índices ZIP excedido");
        long[] oldHigh = high;
        long[] oldLow = low;
        byte[] oldOccupied = occupied;
        int enlarged = oldOccupied.length << 1;
        high = new long[enlarged];
        low = new long[enlarged];
        occupied = new byte[enlarged];
        for (int i = 0; i < oldOccupied.length; i++) {
            if (oldOccupied[i] == 0) continue;
            int index = bucket(oldHigh[i], oldLow[i], enlarged);
            while (occupied[index] != 0)
                index = (index + 1) & (enlarged - 1);
            occupied[index] = 1;
            high[index] = oldHigh[i];
            low[index] = oldLow[i];
        }
        // Count is unchanged: rehashing never creates new source entries.
    }

    /** Avalanche both words to spread low-order bits across table buckets. */
    private static int bucket(long first, long second, int capacity) {
        long value = first ^ Long.rotateLeft(second, 27);
        value ^= value >>> 33;
        value *= 0xff51afd7ed558ccdL;
        value ^= value >>> 33;
        value *= 0xc4ceb9fe1a85ec53L;
        value ^= value >>> 33;
        return ((int) value) & (capacity - 1);
    }

    private static long readLong(byte[] bytes, int offset) {
        long result = 0;
        for (int i = 0; i < 8; i++)
            result = (result << 8) | (bytes[offset + i] & 255L);
        return result;
    }
}
