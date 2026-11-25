/* Isolated JNI glue; copies Java array before calling Rust. */
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#include "com_readroid_app_NativeHexBridge.h"

#define INPUT_MAX 4096
#define OUTPUT_MAX (86 * 256 + 1)

extern int32_t nd_hex_abi_version(void);
extern int32_t nd_hex_format(const uint8_t *input, size_t len, int64_t offset,
                            uint8_t *out, size_t cap);

static void fail(JNIEnv *env, const char *name, const char *message) {
    if ((*env)->ExceptionCheck(env)) return;
    jclass type = (*env)->FindClass(env, name);
    if (type != NULL) {
        (*env)->ThrowNew(env, type, message);
        (*env)->DeleteLocalRef(env, type);
    }
}

JNIEXPORT jint JNICALL Java_com_readroid_app_NativeHexBridge_abiVersion
  (JNIEnv *env, jclass cls) {
    (void)env; (void)cls;
    return (jint)nd_hex_abi_version();
}

JNIEXPORT jstring JNICALL Java_com_readroid_app_NativeHexBridge_format
  (JNIEnv *env, jclass cls, jbyteArray input, jlong offset) {
    (void)cls;
    if (input == NULL || offset < 0) {
        fail(env, "java/lang/IllegalArgumentException", "invalid hex input");
        return NULL;
    }
    jsize len = (*env)->GetArrayLength(env, input);
    if (len < 0 || len > INPUT_MAX ||
        (len > 0 && offset > INT64_MAX - (int64_t)(len - 1))) {
        fail(env, "java/lang/IllegalArgumentException", "hex window out of bounds");
        return NULL;
    }
    uint8_t bytes[INPUT_MAX];
    uint8_t output[OUTPUT_MAX];
    if (len > 0) {
        (*env)->GetByteArrayRegion(env, input, 0, len, (jbyte *)bytes);
        if ((*env)->ExceptionCheck(env)) return NULL;
    }
    int32_t n = nd_hex_format(bytes, (size_t)len, (int64_t)offset, output, sizeof output);
    if (n < 0 || (size_t)n >= sizeof output || output[n] != 0) {
        fail(env, "java/lang/IllegalStateException", "native hex failed");
        return NULL;
    }
    /* Rust hex formatter emits ASCII only, valid modified UTF-8. */
    return (*env)->NewStringUTF(env, (const char *)output);
}
