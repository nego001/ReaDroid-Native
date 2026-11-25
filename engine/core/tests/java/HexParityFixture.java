package com.readroid.app;

import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;

/** Host-only parity fixture. Calls the actual unchanged F2.2 Java formatter. */
public final class HexParityFixture {
    public static void main(String[] args) throws Exception {
        byte[] b;
        switch (args[0]) {
            case "empty": b = new byte[0]; break;
            case "single": b = new byte[]{(byte)255}; break;
            case "boundary": b = new byte[17]; b[0]=65; b[1]=32; b[2]=(byte)255; b[16]=90; break;
            case "all": b=new byte[256]; for(int i=0;i<b.length;i++)b[i]=(byte)i; break;
            case "max": b=new byte[4096]; for(int i=0;i<b.length;i++)b[i]=(byte)i; break;
            default: throw new IllegalArgumentException("Unknown fixture");
        }
        Method m=ApkHexPreview.class.getDeclaredMethod("format",byte[].class);
        m.setAccessible(true);
        String dump=(String)m.invoke(null,(Object)b);
        System.out.write(dump.getBytes(StandardCharsets.UTF_8));
    }
}
