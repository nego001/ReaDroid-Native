package com.readroid.app;

import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import android.system.StructStat;

import java.io.File;
import java.io.FileDescriptor;
import java.io.IOException;

/**
 * F1.38: pin the private recovery DIRECTORY across staged verification and
 * atomic replacement. Do not follow a symlink at the directory's last
 * component; reject a pathname rebound to a different directory inode.
 *
 * The directory fd is fsynced AFTER atomic promotion. This is an additional
 * durability step, not a power-loss / malicious-same-UID guarantee.
 */
final class RecoveryDirectoryGuard implements AutoCloseable {
    private final File root;
    private final FileDescriptor descriptor;
    private final long device;
    private final long inode;
    private boolean closed;

    private RecoveryDirectoryGuard(File root, FileDescriptor descriptor,
            long device, long inode) {
        this.root = root;
        this.descriptor = descriptor;
        this.device = device;
        this.inode = inode;
    }

    static RecoveryDirectoryGuard open(File directory) throws IOException {
        if (directory == null)
            throw new IOException("Diretório privado de recuperação ausente");
        FileDescriptor fd = null;
        boolean returned = false;
        try {
            fd = Os.open(directory.getAbsolutePath(),
                OsConstants.O_RDONLY | OsConstants.O_DIRECTORY
                    | OsConstants.O_NOFOLLOW | OsConstants.O_CLOEXEC, 0);
            StructStat stat = Os.fstat(fd);
            if (!OsConstants.S_ISDIR(stat.st_mode))
                throw new IOException("Recuperação exige diretório privado real");
            RecoveryDirectoryGuard guard = new RecoveryDirectoryGuard(directory,
                fd, stat.st_dev, stat.st_ino);
            guard.requireSameDirectory();
            returned = true;
            return guard;
        } catch (ErrnoException error) {
            throw new IOException("Diretório de recuperação indisponível ou symlink",
                error);
        } finally {
            // The returned guard owns fd; close only on unsuccessful opening.
            if (!returned && fd != null) {
                try { Os.close(fd); }
                catch (ErrnoException ignored) { /* original failure wins */ }
            }
        }
    }

    void requireSameDirectory() throws IOException {
        if (closed) throw new IOException("Descritor do cofre já fechado");
        try {
            StructStat held = Os.fstat(descriptor);
            StructStat path = Os.lstat(root.getAbsolutePath());
            if (!OsConstants.S_ISDIR(held.st_mode)
                    || !OsConstants.S_ISDIR(path.st_mode)
                    || held.st_dev != device || held.st_ino != inode
                    || path.st_dev != device || path.st_ino != inode)
                throw new IOException("Diretório privado alterado durante gravação");
        } catch (ErrnoException error) {
            throw new IOException("Não foi possível validar diretório privado",
                error);
        }
    }

    void syncAfterRename() throws IOException {
        requireSameDirectory();
        try {
            Os.fsync(descriptor);
        } catch (ErrnoException error) {
            // Atomic rename has ALREADY completed; the caller must not pretend
            // it can restore the old version. Report uncertain durability.
            throw new IOException("Checkpoint promovido; sync do diretório falhou",
                error);
        }
        requireSameDirectory();
    }

    @Override public void close() throws IOException {
        if (closed) return;
        closed = true;
        try {
            Os.close(descriptor);
        } catch (ErrnoException error) {
            throw new IOException("Não foi possível fechar descritor privado",
                error);
        }
    }
}
