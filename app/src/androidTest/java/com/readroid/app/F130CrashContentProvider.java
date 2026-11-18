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
 * F1.30: intentionally crashable provider in the AndroidTest APK ONLY.
 *
 * The test manifest puts this provider into the :f130crash process. Killing
 * it must NOT kill the AndroidJUnitRunner or the actual app under test.
 * A pipe stays open after a valid ZIP prefix until the remote provider dies;
 * the client sees EOF/EIO and must refuse to commit a partial import.
 */
public final class F130CrashContentProvider extends ContentProvider {
    static final String AUTHORITY = "com.readroid.app.f130.crashprovider";
    static final Uri SOURCE = Uri.parse("content://" + AUTHORITY + "/interrupted.zip");
    private final CountDownLatch bytesWritten = new CountDownLatch(1);
    private volatile ParcelFileDescriptor producer;

    @Override public boolean onCreate() { return true; }
    @Override public String getType(Uri uri) {
        return "application/vnd.android.package-archive";
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection,
            String[] selectionArgs, String sortOrder) {
        String[] columns = projection == null
            ? new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE}
            : projection;
        MatrixCursor result = new MatrixCursor(columns);
        Object[] row = new Object[columns.length];
        for (int i = 0; i < columns.length; i++) {
            if (OpenableColumns.DISPLAY_NAME.equals(columns[i]))
                row[i] = "f130_remote_provider.apk";
            if (OpenableColumns.SIZE.equals(columns[i])) row[i] = 131072;
        }
        result.addRow(row);
        return result;
    }

    @Override public ParcelFileDescriptor openFile(Uri uri, String mode)
            throws FileNotFoundException {
        if (!SOURCE.equals(uri) || !"r".equals(mode))
            throw new FileNotFoundException("F130 test source unavailable");
        final ParcelFileDescriptor[] pipe;
        try { pipe = ParcelFileDescriptor.createPipe(); }
        catch (IOException e) { throw new FileNotFoundException("F130 pipe unavailable"); }
        producer = pipe[1];

        // Write a plausible ZIP local-file record and hold the writer open.
        // An open Fd is killed with the provider; a successful source read
        // cannot be interpreted as a validated archive without ZIP admission.
        new Thread(() -> {
            try {
                OutputStream out = new ParcelFileDescriptor.AutoCloseOutputStream(pipe[1]);
                byte[] zipLocalHeader = new byte[]{
                    0x50, 0x4b, 0x03, 0x04, 20, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0
                };
                out.write(zipLocalHeader);
                out.flush();
                bytesWritten.countDown();
                // Do NOT close the descriptor; the provider process dies
                // while the client's next read is blocked.
                Thread.sleep(30000);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
            } catch (IOException unavailable) {
                bytesWritten.countDown();
            }
        }, "F130-remote-pipe-writer").start();
        return pipe[0];
    }

    @Override public Bundle call(String method, String arg, Bundle extras) {
        Bundle response = new Bundle();
        if ("pid".equals(method)) {
            response.putInt("pid", android.os.Process.myPid());
            return response;
        }
        if ("await-bytes".equals(method)) {
            try { response.putBoolean("ready", bytesWritten.await(10, TimeUnit.SECONDS)); }
            catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                response.putBoolean("ready", false);
            }
            return response;
        }
        if ("die".equals(method)) {
            response.putInt("pid", android.os.Process.myPid());
            new Thread(() -> {
                try { Thread.sleep(200); }
                catch (InterruptedException ignored) { Thread.currentThread().interrupt(); }
                android.os.Process.killProcess(android.os.Process.myPid());
            }, "F130-remote-process-death").start();
            return response;
        }
        throw new IllegalArgumentException("Unsupported F130 test command");
    }

    @Override public Uri insert(Uri uri, ContentValues values) {
        throw new UnsupportedOperationException("F130 read only");
    }
    @Override public int delete(Uri uri, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("F130 read only");
    }
    @Override public int update(Uri uri, ContentValues values,
            String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("F130 read only");
    }
}
