#!/usr/bin/env bash
set -euxo pipefail
APK="$1"
unzip -l "$APK" | tee apk-files.txt
for lib in libvulkan.so libvulkan_freedreno.so libadrenotools.so libmain_hook.so libhook_impl.so; do
  grep -q "lib/arm64-v8a/$lib" apk-files.txt
done
unzip -p "$APK" lib/arm64-v8a/libopengothic.so > packaged-libopengothic.so
READELF="$ANDROID_HOME/ndk/27.0.12077973/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"
"$READELF" -d packaged-libopengothic.so | tee needed.txt
grep -q "Shared library: \[libvulkan.so\]" needed.txt
