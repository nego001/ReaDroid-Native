package com.readroid.app;

import android.content.Context;
import android.net.Uri;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.file.Files;
import java.util.Arrays;

import static org.junit.Assert.*;

/**
 * Checks byte-verified SAF export with file:// as a local ContentResolver target.
 * A full DocumentsUI flow is covered by the separate emulator UI smoke.
 */
@RunWith(AndroidJUnit4.class)
public final class SafExportVerifierInstrumentedTest {
    private enum ProviderFault {
        NONE, SILENT_TRUNCATION, SAME_LENGTH_CORRUPTION, EXTRA_BYTES,
        READBACK_MISSING, THROW_MID_WRITE, THROW_ON_CLOSE
    }

    private static final class FaultyProvider implements SafExportVerifier.ExportTarget {
        private final ProviderFault fault;
        private final ByteArrayOutputStream stored = new ByteArrayOutputStream();

        FaultyProvider(ProviderFault fault) { this.fault = fault; }

        @Override public OutputStream openWrite() {
            return new OutputStream() {
                @Override public void write(int value) throws IOException {
                    write(new byte[]{(byte) value}, 0, 1);
                }

                @Override public void write(byte[] bytes, int off, int len)
                        throws IOException {
                    if (fault == ProviderFault.THROW_MID_WRITE) {
                        stored.write(bytes, off, Math.min(len, 23));
                        throw new IOException("Falha simulada durante gravação");
                    }
                    if (fault == ProviderFault.SILENT_TRUNCATION) {
                        int remaining = Math.max(0, 12345 - stored.size());
                        stored.write(bytes, off, Math.min(len, remaining));
                    } else {
                        stored.write(bytes, off, len);
                    }
                }

                @Override public void close() throws IOException {
                    if (fault == ProviderFault.THROW_ON_CLOSE)
                        throw new IOException("Provider falhou ao fechar gravação");
                }
            };
        }

        @Override public InputStream openRead() {
            if (fault == ProviderFault.READBACK_MISSING) return null;
            byte[] value = stored.toByteArray();
            if (fault == ProviderFault.SAME_LENGTH_CORRUPTION && value.length > 0)
                value[0] ^= 0x5a;
            if (fault == ProviderFault.EXTRA_BYTES) {
                value = Arrays.copyOf(value, value.length + 1);
                value[value.length - 1] = 0x39;
            }
            return new ByteArrayInputStream(value);
        }
    }

    private static byte[] fixtureBytes() {
        byte[] bytes = new byte[150 * 1024 + 13];
        for (int i = 0; i < bytes.length; i++)
            bytes[i] = (byte) ((i * 37 + 17) & 255);
        return bytes;
    }

    private static void verifyProviderFailure(ProviderFault fault, String expectedText)
            throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File source = File.createTempFile("negrecodroid_fault_", ".apk",
            context.getCacheDir());
        byte[] original = fixtureBytes();
        try {
            Files.write(source.toPath(), original);
            try {
                SafExportVerifier.copyAndVerify(source, new FaultyProvider(fault));
                fail("Provider fault " + fault + " must not produce a successful export");
            } catch (IOException expected) {
                assertTrue(fault + ": " + expected.getMessage(),
                    expected.getMessage().contains(expectedText));
            }
            assertArrayEquals("Failure must never modify the cached source",
                original, Files.readAllBytes(source.toPath()));
        } finally {
            source.delete();
        }
    }

    @Test public void directFileUriCannotOverwriteSourceApk() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File source = File.createTempFile("negrecodroid_self_", ".apk",
            context.getCacheDir());
        byte[] original = fixtureBytes();
        try {
            Files.write(source.toPath(), original);
            try {
                SafExportVerifier.copyAndVerify(
                    context.getContentResolver(), source, Uri.fromFile(source));
                fail("File URI alias of the original must not be exported over");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("APK de origem"));
            }
            assertArrayEquals(original, Files.readAllBytes(source.toPath()));
        } finally {
            source.delete();
        }
    }

    @Test public void silentShortWriteCannotPretendToBeVerified() throws Exception {
        verifyProviderFailure(ProviderFault.SILENT_TRUNCATION, "não confere");
    }

    @Test public void sameLengthBitFlipCannotPretendToBeVerified() throws Exception {
        verifyProviderFailure(ProviderFault.SAME_LENGTH_CORRUPTION, "SHA-256");
    }

    @Test public void trailingBytesCannotPretendToBeVerified() throws Exception {
        verifyProviderFailure(ProviderFault.EXTRA_BYTES, "bytes extras");
    }

    @Test public void unavailableReadbackCannotPretendToBeVerified() throws Exception {
        verifyProviderFailure(ProviderFault.READBACK_MISSING, "reler");
    }

    @Test public void interruptedWriteCannotPretendToBeVerified() throws Exception {
        verifyProviderFailure(ProviderFault.THROW_MID_WRITE, "durante gravação");
    }

    @Test public void closeFailureCannotPretendToBeVerified() throws Exception {
        verifyProviderFailure(ProviderFault.THROW_ON_CLOSE, "fechar gravação");
    }

    @Test public void verifiedFakeProviderProvidesIndependentControl() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File source = File.createTempFile("negrecodroid_control_", ".apk",
            context.getCacheDir());
        byte[] original = fixtureBytes();
        try {
            Files.write(source.toPath(), original);
            FaultyProvider good = new FaultyProvider(ProviderFault.NONE);
            assertEquals(original.length, SafExportVerifier.copyAndVerify(source, good));
            assertArrayEquals(original, good.stored.toByteArray());
            assertArrayEquals(original, Files.readAllBytes(source.toPath()));
        } finally {
            source.delete();
        }
    }

    private static File newSourceFixture() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File source = File.createTempFile("f112_saf_", ".apk", context.getCacheDir());
        Files.write(source.toPath(), fixtureBytes());
        return source;
    }

    @Test public void permanentlyStalledReadbackIsRejectedWithoutEndlessLoop()
            throws Exception {
        File source = newSourceFixture();
        try {
            ByteArrayOutputStream written = new ByteArrayOutputStream();
            SafExportVerifier.ExportTarget provider = new SafExportVerifier.ExportTarget() {
                @Override public OutputStream openWrite() { return written; }
                @Override public InputStream openRead() {
                    return new InputStream() {
                        @Override public int read() { return 0; }
                        @Override public int read(byte[] b, int off, int len) { return 0; }
                    };
                }
            };
            try {
                SafExportVerifier.copyAndVerify(source, provider);
                fail("Provider returning zero bytes forever must not hang");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("sem progresso"));
            }
            assertArrayEquals(fixtureBytes(), Files.readAllBytes(source.toPath()));
            assertArrayEquals(fixtureBytes(), written.toByteArray());
        } finally { source.delete(); }
    }

    @Test public void temporaryZeroReadbacksAreTolerated()
            throws Exception {
        File source = newSourceFixture();
        try {
            ByteArrayOutputStream written = new ByteArrayOutputStream();
            SafExportVerifier.ExportTarget provider = new SafExportVerifier.ExportTarget() {
                @Override public OutputStream openWrite() { return written; }
                @Override public InputStream openRead() {
                    return new ByteArrayInputStream(written.toByteArray()) {
                        int zeros = 2;
                        @Override public synchronized int read(byte[] bytes,
                                int off, int length) {
                            if (zeros-- > 0) return 0;
                            return super.read(bytes, off, length);
                        }
                    };
                }
            };
            assertEquals(fixtureBytes().length,
                SafExportVerifier.copyAndVerify(source, provider));
            assertArrayEquals(fixtureBytes(), written.toByteArray());
        } finally { source.delete(); }
    }

    @Test public void readbackProviderFailureAfterPartialBytesCannotSucceed()
            throws Exception {
        File source = newSourceFixture();
        try {
            ByteArrayOutputStream written = new ByteArrayOutputStream();
            SafExportVerifier.ExportTarget provider = new SafExportVerifier.ExportTarget() {
                @Override public OutputStream openWrite() { return written; }
                @Override public InputStream openRead() {
                    byte[] values = written.toByteArray();
                    return new InputStream() {
                        int calls;
                        @Override public int read() throws IOException {
                            throw new IOException("Provedor falhou na releitura");
                        }
                        @Override public int read(byte[] b, int off, int len)
                                throws IOException {
                            if (++calls > 1)
                                throw new IOException("Provedor falhou na releitura");
                            int n = Math.min(11, len);
                            System.arraycopy(values, 0, b, off, n);
                            return n;
                        }
                    };
                }
            };
            try {
                SafExportVerifier.copyAndVerify(source, provider);
                fail("Interrupted provider readback cannot be marked successful");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("falhou na releitura"));
            }
            assertArrayEquals(fixtureBytes(), Files.readAllBytes(source.toPath()));
        } finally { source.delete(); }
    }

    @Test public void cancellationDuringWriteCloseSkipsReadback()
            throws Exception {
        File source = newSourceFixture();
        try {
            java.util.concurrent.atomic.AtomicInteger reads =
                new java.util.concurrent.atomic.AtomicInteger();
            SafExportVerifier.ExportTarget provider = new SafExportVerifier.ExportTarget() {
                @Override public OutputStream openWrite() {
                    return new ByteArrayOutputStream() {
                        @Override public void close() throws IOException {
                            super.close();
                            Thread.currentThread().interrupt();
                        }
                    };
                }
                @Override public InputStream openRead() {
                    reads.incrementAndGet();
                    return new ByteArrayInputStream(fixtureBytes());
                }
            };
            try {
                SafExportVerifier.copyAndVerify(source, provider);
                fail("Cancellation after closing write must not be accepted");
            } catch (java.io.InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("interrompida"));
            } finally { Thread.interrupted(); }
            assertEquals("No readback should begin after cancellation",
                0, reads.get());
            assertArrayEquals(fixtureBytes(), Files.readAllBytes(source.toPath()));
        } finally {
            Thread.interrupted();
            source.delete();
        }
    }

    @Test public void changedLocalStageAfterInitialHashRejectsBeforeReadback()
            throws Exception {
        File source = newSourceFixture();
        try {
            java.util.concurrent.atomic.AtomicInteger reads =
                new java.util.concurrent.atomic.AtomicInteger();
            ByteArrayOutputStream written = new ByteArrayOutputStream();
            SafExportVerifier.ExportTarget provider = new SafExportVerifier.ExportTarget() {
                @Override public OutputStream openWrite() throws IOException {
                    byte[] altered = fixtureBytes();
                    altered[altered.length / 2] ^= 1;
                    Files.write(source.toPath(), altered);
                    return written;
                }
                @Override public InputStream openRead() {
                    reads.incrementAndGet();
                    return new ByteArrayInputStream(written.toByteArray());
                }
            };
            try {
                SafExportVerifier.copyAndVerify(source, provider);
                fail("Mutated local staging file must not receive success");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("mudou durante"));
            }
            assertEquals(0, reads.get());
        } finally { source.delete(); }
    }

    @Test public void copiesEveryByteAndConfirmsSha256() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File original = File.createTempFile("negresco_source_", ".apk", context.getCacheDir());
        File saved = File.createTempFile("negresco_dest_", ".apk", context.getCacheDir());
        try {
            byte[] bytes = new byte[257 * 1024 + 31];
            for (int index = 0; index < bytes.length; index++)
                bytes[index] = (byte) ((index * 37 + 17) & 255);
            Files.write(original.toPath(), bytes);
            long copied = SafExportVerifier.copyAndVerify(
                context.getContentResolver(), original, Uri.fromFile(saved));
            assertEquals(bytes.length, copied);
            assertArrayEquals(bytes, Files.readAllBytes(saved.toPath()));
            assertArrayEquals(bytes, Files.readAllBytes(original.toPath()));
        } finally {
            original.delete();
            saved.delete();
        }
    }

    @Test public void rejectsMissingSourceWithoutModifyingDestination() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File missing = new File(context.getCacheDir(), "nonexistent_source_edit_test.apk");
        File destination = File.createTempFile("negresco_untouched_", ".apk", context.getCacheDir());
        byte[] sentinel = new byte[]{1, 4, 9, 16};
        try {
            missing.delete();
            Files.write(destination.toPath(), sentinel);
            try {
                SafExportVerifier.copyAndVerify(
                    context.getContentResolver(), missing, Uri.fromFile(destination));
                fail("A missing source must not export");
            } catch (java.io.IOException expected) {
                assertArrayEquals(sentinel, Files.readAllBytes(destination.toPath()));
            }
        } finally {
            destination.delete();
        }
    }
}
