package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.InterruptedIOException;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class NativeHexSessionInstrumentedTest {
    @Test public void cancelledAndConsumedSessionCannotReachBackend() throws Exception {
        AtomicInteger calls=new AtomicInteger();
        NativeHexSession.Manager m=new NativeHexSession.Manager(1,(b,t,e)->{
            calls.incrementAndGet();return new NativeHexBackend.Selection(t,true);
        });
        try(NativeHexSession s=m.open()){
            s.cancel();
            try{s.format(new byte[0],"",true);fail("cancelled");}
            catch(InterruptedIOException expected){}
            try{s.format(new byte[0],"",true);fail("reused");}
            catch(IllegalStateException expected){}
        }
        assertEquals(0,calls.get());
        try(NativeHexSession s=m.open()){
            assertTrue(s.format(new byte[0],"",true).nativeUsed);
        }
        assertEquals(1,calls.get());
    }
    @Test public void reentrantAdmissionFallsBackWithoutBlocking() throws Exception {
        NativeHexSession.Manager[] m=new NativeHexSession.Manager[1];
        m[0]=new NativeHexSession.Manager(1,(b,t,e)->{
            try(NativeHexSession inner=m[0].open()){
                NativeHexBackend.Selection fallback=inner.format(b,"fallback",true);
                assertFalse(fallback.nativeUsed);assertEquals("fallback",fallback.dump);
                return new NativeHexBackend.Selection(t,true);
            }catch(InterruptedIOException ex){throw new AssertionError(ex);}
        });
        try(NativeHexSession s=m[0].open()){
            assertTrue(s.format(new byte[0],"",true).nativeUsed);
        }
    }
}
