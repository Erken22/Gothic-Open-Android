#!/usr/bin/env bash
set -euxo pipefail

JNI="$GITHUB_WORKSPACE/src/android/turnip/jniLibs/arm64-v8a"
mkdir -p "$JNI" "$GITHUB_WORKSPACE/src/android/turnip"

python3 overlay/gen_vulkan_proxy.py   Vulkan-Headers/registry/vk.xml   src/android/turnip/vulkan_proxy.cpp

CLANG="$ANDROID_HOME/ndk/27.0.12077973/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++"
"$CLANG" --target=aarch64-none-linux-android24 \
  --sysroot="$ANDROID_HOME/ndk/27.0.12077973/toolchains/llvm/prebuilt/linux-x86_64/sysroot" \
  -std=c++20 -fsyntax-only \
  -I"$GITHUB_WORKSPACE/VulkanSDK/include" \
  src/android/turnip/vulkan_proxy.cpp
echo "Vulkan proxy syntax check: PASS"

curl -fL --retry 3   -o turnip-r6.zip   https://github.com/StevenMXZ/Adreno-Tools-Drivers/releases/download/v37/Turnip_v26.3.0-R6.zip
echo "5fa2305eb9eff64d9347a670e6ca5ef7c518f60e9e782a4db7ee5588c9852d81  turnip-r6.zip" | sha256sum -c -

rm -rf turnip-r6
mkdir turnip-r6
unzip -q turnip-r6.zip -d turnip-r6
find turnip-r6 -maxdepth 3 -type f -print

DRIVER="$(find turnip-r6 -type f \( -name 'libvulkan_freedreno.so' -o -name '*vulkan*.so' -o -name '*.so' \) | head -n1)"
test -n "$DRIVER"
cp "$DRIVER" "$JNI/libvulkan_freedreno.so"

git clone https://github.com/bylaws/libadrenotools.git adrenotools
git -C adrenotools checkout 8fae8ce254dfc1344527e05301e43f37dea2df80
git -C adrenotools submodule update --init --recursive

"$ANDROID_HOME/cmake/3.22.1/bin/cmake" -S adrenotools -B adrenotools-build -G Ninja   -DCMAKE_TOOLCHAIN_FILE="$ANDROID_HOME/ndk/27.0.12077973/build/cmake/android.toolchain.cmake"   -DANDROID_ABI=arm64-v8a   -DANDROID_PLATFORM=android-28   -DCMAKE_BUILD_TYPE=Release   -DBUILD_SHARED_LIBS=ON
"$ANDROID_HOME/cmake/3.22.1/bin/cmake" --build adrenotools-build -- -j2

for lib in libadrenotools.so libmain_hook.so libfile_redirect_hook.so libgsl_alloc_hook.so libhook_impl.so; do
  SRC="$(find adrenotools-build -type f -name "$lib" | head -n1)"
  test -n "$SRC"
  cp "$SRC" "$JNI/$lib"
done

ls -lh "$JNI"
