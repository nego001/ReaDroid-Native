package com.readroid.app;

/** Host laboratory only. Not loaded by the Android application. */
final class NativeHexBridge {
    private NativeHexBridge() {}
    static native int abiVersion();
    static native String format(byte[] bytes, long offset);
}
