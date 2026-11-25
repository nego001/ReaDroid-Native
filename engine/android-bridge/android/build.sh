#!/usr/bin/env bash
# Isolated Android ELF build laboratory, no APK packaging or installation.
set -euo pipefail
root="$(cd "$(dirname "$0")/../../.." && pwd)"
bridge="$root/engine/android-bridge"
ndk="$ANDROID_NDK_HOME"
work="$1"
mkdir -p "$work"
work="$(cd "$work" && pwd)"
[[ "$(grep '^Pkg.Revision' "$ndk/source.properties" | tr -d '[:space:]')" == "Pkg.Revision=27.2.12479018" ]]
bin="$ndk/toolchains/llvm/prebuilt/linux-x86_64/bin"
mkdir -p "$work/classes" "$work/headers"
javac -encoding UTF-8 -h "$work/headers" -d "$work/classes" "$bridge/java/com/readroid/app/NativeHexBridge.java"
export CARGO_TARGET_DIR="$work/target"
cd "$bridge"
cargo +1.85.1 fetch --locked
for spec in "arm64-v8a aarch64-linux-android aarch64-linux-android26-clang 183" "x86_64 x86_64-linux-android x86_64-linux-android26-clang 62"; do
    read -r abi target clang machine <<< "$spec"
    mkdir -p "$work/libs/$abi"
    compiler="$bin/$clang"
    key="$(printf '%s' "$target" | tr '[:lower:]-' '[:upper:]_')"
    env "CARGO_TARGET_$(printf '%s' "$key")_LINKER=$compiler" \
        cargo +1.85.1 build --release --locked --offline --target "$target"
    "$compiler" -std=c11 -Wall -Wextra -Werror -O2 -fPIC -fstack-protector-strong -shared \
        -I"$work/headers" "$bridge/src/jni_hex.c" \
        "$work/target/$target/release/libnegrodroid_jni_bridge.a" \
        -Wl,--no-undefined -Wl,--gc-sections -Wl,--exclude-libs,ALL \
        -Wl,-z,relro,-z,now,-z,noexecstack,-z,max-page-size=16384 \
        -Wl,-soname,libnegrodroid_hex.so \
        -Wl,--version-script,"$bridge/android/jni.exports" \
        -ldl -llog -lm -lunwind -o "$work/libs/$abi/libnegrodroid_hex.so"
    python3 "$bridge/android/verify_elf.py" "$work/libs/$abi/libnegrodroid_hex.so" "$machine" "$bin/llvm-readelf" "$bin/llvm-nm"
    printf 'U2_3_ANDROID_ABI_BUILD_PASS %s api=26\n' "$abi"
done
git diff --exit-code -- Cargo.lock
printf 'U2_3_ANDROID_BUILD_MATRIX_PASS 2\n'
