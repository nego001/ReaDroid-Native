package com.readroid.app;

import android.os.StatFs;
import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;

/**
 * F1.33: conservative free-space probe for encrypted checkpoint staging.
 *
 * This is a best-effort reserve, not a guarantee against ENOSPC or a power
 * failure. The production RecoveryVault still preserves the previous version
 * by writing an independent temp file and promoting it via ATOMIC_MOVE.
 *
 * FreeSpace is a package-private deterministic test seam: CI can emulate
 * shrinking storage without exhausting emulator storage or touching users.
 */
final class RecoveryStorageBudget {
    static final long SAFETY_RESERVE = 8L * 1024 * 1024;
    static final long MAX_ENCRYPTED_STAGE = 512L * 1024 + 256;

    interface FreeSpace {
        long availableBytes() throws IOException;
    }

    private RecoveryStorageBudget() {}

    static FreeSpace forDirectory(File directory) {
        return () -> {
            if (directory == null || !directory.isDirectory())
                throw new IOException("Diretório privado de recuperação indisponível");
            try {
                return new StatFs(directory.getAbsolutePath()).getAvailableBytes();
            } catch (IllegalArgumentException | SecurityException unavailable) {
                throw new IOException("Espaço livre da recuperação indisponível",
                    unavailable);
            }
        };
    }

    static void requireStagingRoom(FreeSpace space, long encodedBytes)
            throws IOException {
        if (Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Gravação da recuperação interrompida");
        if (space == null || encodedBytes <= 0
                || encodedBytes > MAX_ENCRYPTED_STAGE)
            throw new IOException("Orçamento de recuperação inválido");
        long free = space.availableBytes();
        // Fail closed on zero, negative, overflow-like, or insufficient space.
        // Subtraction avoids reserve+encodedBytes overflowing long.
        if (free < SAFETY_RESERVE
                || encodedBytes > free - SAFETY_RESERVE)
            throw new IOException("Espaço insuficiente para salvar recuperação");
    }
}
