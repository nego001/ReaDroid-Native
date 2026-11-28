package com.readroid.app;

import java.io.InterruptedIOException;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

public final class NativeHexSessionContract {
    private static int checks;
    private static void check(boolean ok, String name) {
        if(!ok) throw new AssertionError(name);
        checks++; System.out.println("U2_5_SESSION_CHECK_PASS "+name);
    }
    private static NativeHexBackend.Selection selected(String s) {
        return new NativeHexBackend.Selection(s,true);
    }
    private static void interrupted(NativeHexSession s) throws Exception {
        try { s.format(new byte[0],"",true); throw new AssertionError("expected cancellation"); }
        catch(InterruptedIOException expected) {}
    }
    public static void main(String[] args) throws Exception {
        AtomicInteger calls=new AtomicInteger();
        NativeHexSession.Manager m=new NativeHexSession.Manager(1,(b,t,e)->{
            calls.incrementAndGet(); return selected(t);
        });
        try(NativeHexSession s=m.open()){
            check(!s.format(new byte[0],"",false).nativeUsed&&calls.get()==0,"disabled_no_backend");
            try { s.format(new byte[0],"",true); throw new AssertionError("reused"); }
            catch(IllegalStateException expected){ check(true,"single_use"); }
        }
        try(NativeHexSession s=m.open()){
            s.cancel(); interrupted(s); check(calls.get()==0,"pre_cancel_no_backend");
        }
        NativeHexSession closed=m.open();closed.close();closed.close();
        try{closed.format(new byte[0],"",true);throw new AssertionError("closed");}
        catch(IllegalStateException expected){check(true,"closed_rejected");}
        try(NativeHexSession s=m.open()){
            ExecutorService foreign=Executors.newSingleThreadExecutor();
            try {
                check(foreign.submit(()->{
                    try{s.format(new byte[0],"",true);return false;}
                    catch(IllegalStateException expected){return true;}
                }).get(5,TimeUnit.SECONDS),"foreign_owner_rejected");
            } finally {foreign.shutdownNow();}
            check(s.format(new byte[0],"",true).nativeUsed,"owner_still_usable");
        }
        try(NativeHexSession s=m.open()){
            Thread.currentThread().interrupt();
            try{interrupted(s);check(Thread.currentThread().isInterrupted(),"interrupt_preserved");}
            finally{Thread.interrupted();}
        }
        try(NativeHexSession s=m.open()){
            try{s.format(new byte[4097],"",true);throw new AssertionError("oversize");}
            catch(IllegalArgumentException expected){check(true,"oversize_rejected");}
        }
        CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
        AtomicReference<NativeHexSession> active=new AtomicReference<>();
        NativeHexSession.Manager bounded=new NativeHexSession.Manager(1,(b,t,e)->{
            entered.countDown();
            try{if(!release.await(5,TimeUnit.SECONDS))throw new AssertionError("release timeout");}
            catch(InterruptedException ex){Thread.currentThread().interrupt();throw new AssertionError(ex);}
            return selected(t);
        });
        ExecutorService pool=Executors.newSingleThreadExecutor();
        try{
            Future<Boolean> first=pool.submit(()->{
                try(NativeHexSession s=bounded.open()){
                    active.set(s);
                    try{s.format(new byte[0],"",true);return false;}
                    catch(InterruptedIOException expected){return true;}
                }
            });
            if(!entered.await(5,TimeUnit.SECONDS))throw new AssertionError("admission timeout");
            active.get().cancel();
            try(NativeHexSession s=bounded.open()){
                check(!s.format(new byte[0],"fallback",true).nativeUsed,"cancelled_inflight_retains_slot");
            }
            release.countDown();
            check(first.get(5,TimeUnit.SECONDS),"cancelled_result_discarded");
            try(NativeHexSession s=bounded.open()){
                check(s.format(new byte[0],"",true).nativeUsed,"slot_released_after_exit");
            }
        }finally{release.countDown();pool.shutdownNow();}
        AtomicInteger attempts=new AtomicInteger();
        NativeHexSession.Manager throwsOnce=new NativeHexSession.Manager(1,(b,t,e)->{
            if(attempts.getAndIncrement()==0)throw new IllegalStateException("synthetic");
            return selected(t);
        });
        try(NativeHexSession s=throwsOnce.open()){
            try{s.format(new byte[0],"",true);throw new AssertionError("failure");}
            catch(IllegalStateException expected){check(true,"failure_propagates");}
        }
        try(NativeHexSession s=throwsOnce.open()){
            check(s.format(new byte[0],"",true).nativeUsed,"slot_released_on_failure");
        }
        System.out.println("U2_5_HOST_SESSION_PASS "+checks);
    }
}
