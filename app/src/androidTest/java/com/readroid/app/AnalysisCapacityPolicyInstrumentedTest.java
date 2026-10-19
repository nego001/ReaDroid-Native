package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class AnalysisCapacityPolicyInstrumentedTest {
    private static final long GIB = 1024L * 1024 * 1024;
    private static final long GB = 1000L * 1000 * 1000;
    private static final long MIB = 1024L * 1024;

    private static AnalysisCapacityPolicy.Capabilities device(long size, long cache,
            long dest, long memory, long stream, long indexed, long writable,
            boolean seek, boolean indexEngine, boolean writingEngine, boolean approved) {
        return new AnalysisCapacityPolicy.Capabilities(size, cache, dest, memory,
            stream, indexed, writable, true, seek, indexEngine, writingEngine, approved);
    }

    @Test public void oneGiBStreamingIsReadOnlyNotAFullCopy() {
        AnalysisCapacityPolicy.Decision d = AnalysisCapacityPolicy.decide(
            AnalysisCapacityPolicy.Operation.SHA256_STREAM,
            device(GIB, 80*MIB, 80*MIB, 64*MIB, 2*GIB, 0, 0, false, false, false, true));
        assertEquals(AnalysisCapacityPolicy.Mode.STREAM_READ_ONLY, d.mode);
        assertTrue(d.allowed);
        assertTrue(d.reason.contains("não copia"));
    }

    @Test public void fiveHundredGbMayBeStreamInspectedWhenEngineAndUserAllowIt() {
        AnalysisCapacityPolicy.Decision d = AnalysisCapacityPolicy.decide(
            AnalysisCapacityPolicy.Operation.SHA256_STREAM,
            device(500*GB, 128*MIB, 128*MIB, 64*MIB, 600*GB, 0, 0,
                false, false, false, true));
        assertEquals(AnalysisCapacityPolicy.Mode.STREAM_READ_ONLY, d.mode);
        assertTrue(d.allowed);
        // Policy approval is NOT evidence an actual Android engine supports it.
    }

    @Test public void fiveHundredGbCannotBeCopiedIntoSmallDevice() {
        AnalysisCapacityPolicy.Decision d = AnalysisCapacityPolicy.decide(
            AnalysisCapacityPolicy.Operation.MODIFY_AND_EXPORT,
            device(500*GB, 64*GIB, 64*GIB, 128*MIB, 600*GB, 600*GB, 600*GB,
                true, true, true, true));
        assertEquals(AnalysisCapacityPolicy.Mode.BLOCKED, d.mode);
        assertTrue(d.reason.contains("espaço"));
    }

    @Test public void zip500GbRequiresRealSeekAndIndexEngine() {
        AnalysisCapacityPolicy.Capabilities p = device(500*GB,
            128*MIB, 128*MIB, 128*MIB, 600*GB, 600*GB, 0,
            true, true, false, true);
        assertEquals(AnalysisCapacityPolicy.Mode.INDEXED_RANDOM_ACCESS,
            AnalysisCapacityPolicy.decide(AnalysisCapacityPolicy.Operation.ZIP_INDEX, p).mode);
        p = device(500*GB, 128*MIB, 128*MIB, 128*MIB, 600*GB, 600*GB, 0,
            false, true, false, true);
        assertEquals(AnalysisCapacityPolicy.Mode.METADATA_ONLY,
            AnalysisCapacityPolicy.decide(AnalysisCapacityPolicy.Operation.ZIP_INDEX, p).mode);
    }

    @Test public void missingConsentOnlyAllowsMetadata() {
        AnalysisCapacityPolicy.Capabilities p = device(GIB, 5*GIB, 5*GIB,
            128*MIB, 5*GIB, 5*GIB, 5*GIB, true, true, true, false);
        assertEquals(AnalysisCapacityPolicy.Mode.METADATA_ONLY,
            AnalysisCapacityPolicy.decide(AnalysisCapacityPolicy.Operation.MODIFY_AND_EXPORT, p).mode);
        assertEquals(AnalysisCapacityPolicy.Mode.METADATA_ONLY,
            AnalysisCapacityPolicy.decide(AnalysisCapacityPolicy.Operation.METADATA, p).mode);
    }

    @Test public void unknownSizeCannotSlipThroughAuthorization() {
        AnalysisCapacityPolicy.Capabilities p = device(-1, 5*GIB, 5*GIB,
            128*MIB, Long.MAX_VALUE, Long.MAX_VALUE, Long.MAX_VALUE,
            true, true, true, true);
        assertEquals(AnalysisCapacityPolicy.Mode.METADATA_ONLY,
            AnalysisCapacityPolicy.decide(AnalysisCapacityPolicy.Operation.ZIP_INDEX, p).mode);
        assertEquals(AnalysisCapacityPolicy.Mode.METADATA_ONLY,
            AnalysisCapacityPolicy.decide(AnalysisCapacityPolicy.Operation.MODIFY_AND_EXPORT, p).mode);
    }

    @Test public void backendNotReadyCannotClaimFullEditingSupport() {
        AnalysisCapacityPolicy.Capabilities p = device(5*GIB, 20*GIB, 20*GIB,
            128*MIB, 10*GIB, 10*GIB, 10*GIB,
            true, true, false, true);
        assertEquals(AnalysisCapacityPolicy.Mode.BLOCKED,
            AnalysisCapacityPolicy.decide(AnalysisCapacityPolicy.Operation.MODIFY_AND_EXPORT, p).mode);
    }

    @Test public void arithmeticRemainsBoundedAtLongMaximum() {
        assertFalse(AnalysisCapacityPolicy.hasHeadroom(
            Long.MAX_VALUE, Long.MAX_VALUE, 64*MIB));
        assertFalse(AnalysisCapacityPolicy.hasHeadroom(-1, 1, 0));
        assertFalse(AnalysisCapacityPolicy.hasHeadroom(10, 20, 1));
    }
}
