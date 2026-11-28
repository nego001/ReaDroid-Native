package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class NativeHexIntegrationInstrumentedTest {
    private static final String PATH = "assets/synthetic.bin";
    private static final class Fake implements NativeHexBackend.Driver {
        int init, calls, abi=1;
        String value="ok";
        boolean missing, fail;
        public int initialize() { init++; if(missing)throw new UnsatisfiedLinkError("synthetic"); return abi; }
        public String format(byte[] bytes) { calls++; if(fail)throw new IllegalStateException("synthetic"); return value; }
    }
    @Test public void disabledNeverLoads() {
        Fake f=new Fake();NativeHexBackend.Selector s=new NativeHexBackend.Selector(f);
        assertFalse(s.select(new byte[0],"ok",false).nativeUsed);
        assertEquals(0,f.init);assertEquals(0,f.calls);
    }
    @Test public void missingLibraryAndWrongAbiLatchFallback() {
        for(boolean missing:new boolean[]{true,false}){
            Fake f=new Fake();f.missing=missing;f.abi=2;
            NativeHexBackend.Selector s=new NativeHexBackend.Selector(f);
            for(int i=0;i<2;i++)assertEquals("ok",s.select(new byte[0],"ok",true).dump);
            assertEquals(1,f.init);assertEquals(0,f.calls);
        }
    }
    @Test public void mismatchAndNativeFailureLatchFallback() {
        for(boolean fail:new boolean[]{true,false}){
            Fake f=new Fake();f.fail=fail;f.value="incorrect";
            NativeHexBackend.Selector s=new NativeHexBackend.Selector(f);
            for(int i=0;i<2;i++){
                NativeHexBackend.Selection v=s.select(new byte[0],"ok",true);
                assertFalse(v.nativeUsed);assertEquals("ok",v.dump);
            }
            assertEquals(1,f.init);assertEquals(1,f.calls);
        }
    }
    @Test public void matchingCandidateSelected() {
        Fake f=new Fake();NativeHexBackend.Selector s=new NativeHexBackend.Selector(f);
        assertTrue(s.select(new byte[0],"ok",true).nativeUsed);
        assertTrue(s.select(new byte[0],"ok",true).nativeUsed);
        assertEquals(1,f.init);assertEquals(2,f.calls);
    }
    @Test public void realApkPreviewUsesExpectedBackendWithoutChangingSource() throws Exception {
        String expected=InstrumentationRegistry.getArguments().getString("nativeHexExpected");
        assertNotNull("explicit backend expectation",expected);
        boolean enabled=Boolean.parseBoolean(expected);
        assertEquals(enabled,BuildConfig.NATIVE_HEX_ENABLED);
        File file=File.createTempFile("native_hex_",".apk",InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            byte[] b=new byte[4097];b[0]=65;b[1]=66;b[2]=67;
            try(ZipOutputStream zip=new ZipOutputStream(Files.newOutputStream(file.toPath()))){
                zip.putNextEntry(new ZipEntry(PATH));zip.write(b);zip.closeEntry();
            }
            String before=ApkIntegrity.sha256(file);
            ApkHexPreview.Result p=ApkHexPreview.read(file,PATH);
            assertEquals(enabled,p.nativeUsed);assertEquals(4096,p.shown);
            assertTrue(p.truncated);assertTrue(p.dump.startsWith("00000000  41 42 43"));
            assertEquals(before,ApkIntegrity.sha256(file));
            System.out.println("U2_4_ACTUAL_HEX_BACKEND_PASS native="+p.nativeUsed);
        }finally{file.delete();}
    }
}
