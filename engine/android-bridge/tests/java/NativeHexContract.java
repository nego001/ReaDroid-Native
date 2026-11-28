package com.readroid.app;
import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.concurrent.*;

public final class NativeHexContract {
    private static int checks=0;
    private static void check(boolean value, String name){
        if(!value)throw new AssertionError(name);
        checks++;System.out.println("U2_2_JNI_CHECK_PASS "+name);
    }
    private static void invalid(byte[] bytes,long offset,String name){
        try{NativeHexBridge.format(bytes,offset);throw new AssertionError(name);}
        catch(IllegalArgumentException expected){check(true,name);}
    }
    private static byte[] sequence(int n){
        byte[] b=new byte[n];for(int i=0;i<n;i++)b[i]=(byte)i;return b;
    }
    public static void main(String[] args)throws Exception{
        System.load(args[0]);
        check(NativeHexBridge.abiVersion()==1,"abi_version");
        Method original=ApkHexPreview.class.getDeclaredMethod("format",byte[].class);
        original.setAccessible(true);
        for(int n:new int[]{0,1,17,256,4096}){
            byte[] b=sequence(n);byte[] copy=b.clone();
            String expected=(String)original.invoke(null,(Object)b);
            check(expected.equals(NativeHexBridge.format(b,0))&&Arrays.equals(b,copy),"parity_"+n);
        }
        check(NativeHexBridge.format(new byte[]{65},0x100000000L).startsWith("100000000  41"),"offset_64");
        check(NativeHexBridge.format(new byte[]{65},Long.MAX_VALUE).startsWith("7FFFFFFFFFFFFFFF  41"),"max_offset");
        invalid(null,0,"null");invalid(new byte[4097],0,"oversize");
        invalid(new byte[1],-1,"negative_offset");invalid(new byte[2],Long.MAX_VALUE,"overflow");
        ExecutorService pool=Executors.newFixedThreadPool(4);
        try{
            java.util.List<Future<Boolean>> tasks=new java.util.ArrayList<>();
            for(int i=0;i<64;i++){
                final int n=i;
                tasks.add(pool.submit(()->{
                    byte[] b=sequence(256+n);
                    return NativeHexBridge.format(b,0).equals(original.invoke(null,(Object)b));
                }));
            }
            for(Future<Boolean> f:tasks)if(!f.get())throw new AssertionError("concurrency");
            check(true,"64_parallel_calls");
        }finally{pool.shutdownNow();}
        System.out.println("U2_2_HOST_JNI_PASS "+checks);
    }
}
