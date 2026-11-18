package com.readroid.app;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.OutputStream;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * F1.29: disposable AndroidTest-only ContentProvider, never in production APK.
 *
 * Pipe backed streams cross the actual Android ContentResolver/provider IPC
 * instead of injecting fake InputStreams. No user files, SAF grants, or write
 * permission is involved. The F1.28 DocumentsUI suite separately verifies
 * actual platform-grant acquisition and revocation.
 */
public final class F129FaultyContentProvider extends ContentProvider {
    static final String AUTHORITY = "com.readroid.app.f129.testprovider";
    static final Uri MISSING = Uri.parse("content://" + AUTHORITY + "/gone");
    static final Uri TRUNCATED = Uri.parse("content://" + AUTHORITY + "/truncated");
    static final Uri BLOCKED = Uri.parse("content://" + AUTHORITY + "/blocked");

    private volatile CountDownLatch firstChunk = new CountDownLatch(1);
    private volatile CountDownLatch allowFinish = new CountDownLatch(1);
    private volatile boolean revokeNextOpen;

    @Override public boolean onCreate() { return true; }

    @Override public String getType(Uri uri) {
        return "application/vnd.android.package-archive";
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection,
            String[] selectionArgs, String sortOrder) {
        // Metadata may succeed even if openFile later fails (TOCTOU).
        String[] requested = projection == null
            ? new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE}
            : projection;
        MatrixCursor cursor = new MatrixCursor(requested);
        Object[] row = new Object[requested.length];
        for (int i = 0; i < requested.length; i++) {
            if (OpenableColumns.DISPLAY_NAME.equals(requested[i]))
                row[i] = "f129_untrusted.apk";
            else if (OpenableColumns.SIZE.equals(requested[i])) row[i] = 131072;
        }
        cursor.addRow(row);
        return cursor;
    }

    @Override public ParcelFileDescriptor openFile(Uri uri, String mode)
            throws FileNotFoundException {
        if (!"r".equals(mode) || revokeNextOpen || MISSING.equals(uri))
            throw new FileNotFoundException("F129 document vanished or grant expired");
        if (!TRUNCATED.equals(uri) && !BLOCKED.equals(uri))
            throw new FileNotFoundException("Unknown test document");
        final ParcelFileDescriptor[] pipe;
        try {
            pipe = ParcelFileDescriptor.createPipe();
        } catch (IOException error) {
            throw new FileNotFoundException("Cannot create F129 read-only pipe");
        }
        final boolean stalled = BLOCKED.equals(uri);
        final CountDownLatch start = firstChunk;
        final CountDownLatch finish = allowFinish;
        new Thread(() -> {
            ParcelFileDescriptor writer = pipe[1];
            try {
                try (OutputStream output = new ParcelFileDescriptor.AutoCloseOutputStream(
                        writer)) {
                    byte[] chunk = new byte[32768];
                    for (int i = 0; i < chunk.length; i++) chunk[i] = (byte) (i & 255);
                    output.write(chunk);
                    output.flush();
                    start.countDown();
                    if (stalled) {
                        // A provider that ignores interruption while handling
                        // the open file descriptor, until externally released.
                        finish.await(12, TimeUnit.SECONDS);
                    } else {
                        // Deliver a short, malformed stream to exercise
                        // archive validation. A clean EOF is NOT APK validity.
                        output.write(chunk);
                    }
                }
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
                try { writer.closeWithError("F129 provider interrupted"); }
                catch (IOException ignoredClose) {}
            } catch (IOException ignored) {
                try { writer.closeWithError("F129 provider read disconnected"); }
                catch (IOException ignoredClose) {}
            } finally {
                start.countDown();
            }
        }, "F129-faulty-provider-pipe").start();
        return pipe[0];
    }

    @Override public Bundle call(String method, String arg, Bundle extras) {
        Bundle out = new Bundle();
        if ("arm".equals(method)) {
            firstChunk = new CountDownLatch(1);
            allowFinish = new CountDownLatch(1);
            revokeNextOpen = false;
            out.putBoolean("ok", true);
        } else if ("await-first".equals(method)) {
            try { out.putBoolean("ok", firstChunk.await(8, TimeUnit.SECONDS)); }
            catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                out.putBoolean("ok", false);
            }
        } else if ("revoke".equals(method)) {
            // Provider-side denial on the NEXT open; unlike F1.28 this is not
            // Android's persisted-grant revocation.
            revokeNextOpen = true;
            out.putBoolean("ok", true);
        } else if ("release".equals(method)) {
            allowFinish.countDown();
            out.putBoolean("ok", true);
        }
        return out;
    }

    @Override public Uri insert(Uri uri, ContentValues values) {
        throw new UnsupportedOperationException("Read-only test provider");
    }
    @Override public int update(Uri uri, ContentValues values,
            String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("Read-only test provider");
    }
    @Override public int delete(Uri uri, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("Read-only test provider");
    }
}
