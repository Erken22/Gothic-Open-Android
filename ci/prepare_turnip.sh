#!/usr/bin/env bash
set -euxo pipefail

JNI="$GITHUB_WORKSPACE/src/android/turnip/jniLibs/arm64-v8a"
mkdir -p "$JNI" "$GITHUB_WORKSPACE/src/android/turnip"

python3 overlay/gen_vulkan_proxy.py \
  Vulkan-Headers/registry/vk.xml \
  src/android/turnip/vulkan_proxy.cpp

CLANG="$ANDROID_HOME/ndk/27.0.12077973/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++"
SYSROOT="$ANDROID_HOME/ndk/27.0.12077973/toolchains/llvm/prebuilt/linux-x86_64/sysroot"
NM="$ANDROID_HOME/ndk/27.0.12077973/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-nm"

"$CLANG" --target=aarch64-none-linux-android24 \
  --sysroot="$SYSROOT" \
  -std=c++20 -fsyntax-only \
  -I"$GITHUB_WORKSPACE/VulkanSDK/include" \
  src/android/turnip/vulkan_proxy.cpp
echo "Vulkan proxy syntax check: PASS"

"$CLANG" --target=aarch64-none-linux-android24 \
  --sysroot="$SYSROOT" \
  -std=c++20 -shared -fPIC -fvisibility=hidden \
  -I"$GITHUB_WORKSPACE/VulkanSDK/include" \
  src/android/turnip/vulkan_proxy.cpp -ldl -llog \
  -o /tmp/libvulkan-proxy.so

"$NM" -D --defined-only /tmp/libvulkan-proxy.so | tee /tmp/vulkan-proxy-symbols.txt
for sym in \
  vkGetInstanceProcAddr \
  vkGetDeviceProcAddr \
  vkCreateInstance \
  vkCreateFence \
  vkCmdDraw \
  vkCreateGraphicsPipelines \
  opengothic_vulkan_is_turnip
do
  grep -Eq "[[:space:]]${sym}$" /tmp/vulkan-proxy-symbols.txt
done
VK_EXPORTS="$(awk '$3 ~ /^vk[A-Za-z0-9_]+$/ {n++} END {print n+0}' /tmp/vulkan-proxy-symbols.txt)"
test "$VK_EXPORTS" -ge 107
echo "Vulkan proxy dynamic export check: PASS ($VK_EXPORTS vk exports)"

curl -fL --retry 3 \
  -o turnip-r6.zip \
  https://github.com/StevenMXZ/Adreno-Tools-Drivers/releases/download/v37/Turnip_v26.3.0-R6.zip
echo "5fa2305eb9eff64d9347a670e6ca5ef7c518f60e9e782a4db7ee5588c9852d81  turnip-r6.zip" | sha256sum -c -

rm -rf turnip-r6
mkdir turnip-r6
unzip -q turnip-r6.zip -d turnip-r6
find turnip-r6 -maxdepth 3 -type f -print

DRIVER="$(find turnip-r6 -type f \( -name 'libvulkan_freedreno.so' -o -name '*vulkan*.so' -o -name '*.so' \) | head -n1)"
test -n "$DRIVER"
cp "$DRIVER" "$JNI/libvulkan_freedreno.so"

rm -rf adrenotools adrenotools-build
git clone https://github.com/bylaws/libadrenotools.git adrenotools
git -C adrenotools checkout 8fae8ce254dfc1344527e05301e43f37dea2df80
git -C adrenotools submodule update --init --recursive

"$ANDROID_HOME/cmake/3.22.1/bin/cmake" \
  -S adrenotools -B adrenotools-build -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$ANDROID_HOME/ndk/27.0.12077973/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a \
  -DANDROID_PLATFORM=android-28 \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=ON
"$ANDROID_HOME/cmake/3.22.1/bin/cmake" --build adrenotools-build -- -j2

for lib in libadrenotools.so libmain_hook.so libfile_redirect_hook.so libgsl_alloc_hook.so libhook_impl.so; do
  SRC="$(find adrenotools-build -type f -name "$lib" | head -n1)"
  test -n "$SRC"
  cp "$SRC" "$JNI/$lib"
done

ls -lh "$JNI"
READELF="$ANDROID_HOME/ndk/27.0.12077973/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"
if find "$JNI" -maxdepth 1 -type f -name '*.so' -print0 | xargs -0 -I{} sh -c '"$0" -d "$1" 2>/dev/null | grep -q "libc++_shared.so"' "$READELF" {}; then
  cp "$ANDROID_HOME/ndk/27.0.12077973/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so" "$JNI/libc++_shared.so"
  echo "Packaged libc++_shared.so for Turnip/adrenotools dependency"
fi

echo "Turnip/AdrenoTools preparation: PASS"
