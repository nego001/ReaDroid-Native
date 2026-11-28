package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.Assert.*;

/** Deterministic low-space probes without actually filling Android disk. */
@RunWith(AndroidJUnit4.class)
public final class RebuildStorageBudgetInstrumentedTest {
    private static final long MIB = 1024L * 1024;

    @Test public void boundedWritesPreserveBytesAndRequireFinalReserve()
            throws Exception {
        ByteArrayOutputStream sink = new ByteArrayOutputStream();
        RebuildStorageBudget.CheckedOutputStream guard =
            new RebuildStorageBudget.CheckedOutputStream(sink,
                () -> 100 * MIB, 128, 64, 8);
        byte[] payload = "safe small staging ZIP".getBytes(StandardCharsets.UTF_8);
        guard.write(payload);
        assertEquals(payload.length, guard.writtenBytes());
        guard.close();
        guard.verifyFinal();
        assertArrayEquals(payload, sink.toByteArray());
    }

    @Test public void insufficientFreeSpaceRejectsBeforeWriting()
            throws Exception {
        ByteArrayOutputStream sink = new ByteArrayOutputStream();
        try {
            new RebuildStorageBudget.CheckedOutputStream(sink,
                () -> 63 * MIB, 128, 64 * MIB, 8);
            fail("Below-reserve storage cannot start staging");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("Espaço insuficiente"));
            assertEquals(0, sink.size());
        }
    }

    @Test public void stageQuotaRejectsNextChunkBeforeWriting()
            throws Exception {
        ByteArrayOutputStream sink = new ByteArrayOutputStream();
        RebuildStorageBudget.CheckedOutputStream guard =
            new RebuildStorageBudget.CheckedOutputStream(sink,
                () -> 100 * MIB, 5, 64, 2);
        guard.write(new byte[]{1,2,3,4});
        try {
            guard.write(new byte[]{5,6});
            fail("Exceeding the compressed-stage cap must fail closed");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("Cota"));
        } finally { guard.close(); }
        assertArrayEquals(new byte[]{1,2,3,4}, sink.toByteArray());
    }

    @Test public void periodicCheckRejectsLowSpaceWithoutExtraWrites()
            throws Exception {
        AtomicLong available = new AtomicLong(100 * MIB);
        ByteArrayOutputStream sink = new ByteArrayOutputStream();
        RebuildStorageBudget.CheckedOutputStream guard =
            new RebuildStorageBudget.CheckedOutputStream(sink,
                available::get, 32, 64 * MIB, 4);
        guard.write(new byte[]{1,2,3,4});
        available.set(64 * MIB);
        try {
            guard.write(new byte[]{5,6,7,8});
            fail("Next batch must not consume the 64 MiB safety reserve");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("Espaço insuficiente"));
        } finally { guard.close(); }
        assertArrayEquals(new byte[]{1,2,3,4}, sink.toByteArray());
    }

    @Test public void eofCheckRejectsReserveLossForShortZip()
            throws Exception {
        AtomicLong available = new AtomicLong(100 * MIB);
        ByteArrayOutputStream sink = new ByteArrayOutputStream();
        RebuildStorageBudget.CheckedOutputStream guard =
            new RebuildStorageBudget.CheckedOutputStream(sink,
                available::get, 100, 64 * MIB, 32);
        guard.write(42);
        guard.close();
        available.set(63 * MIB);
        try {
            guard.verifyFinal();
            fail("Final probe must detect space exhausted after short output");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("Espaço insuficiente"));
        }
        assertEquals(1, sink.size());
    }

    @Test public void interruptionRejectsNextWriteWithoutMutatingStage()
            throws Exception {
        ByteArrayOutputStream sink = new ByteArrayOutputStream();
        RebuildStorageBudget.CheckedOutputStream guard =
            new RebuildStorageBudget.CheckedOutputStream(sink,
                () -> 100 * MIB, 100, 64 * MIB, 8);
        Thread.currentThread().interrupt();
        try {
            guard.write(7);
            fail("Canceled worker must not write another byte");
        } catch (InterruptedIOException expected) {
            assertNotNull(expected.getMessage());
        } finally {
            Thread.interrupted();
            guard.close();
        }
        assertEquals(0, sink.size());
    }
}
