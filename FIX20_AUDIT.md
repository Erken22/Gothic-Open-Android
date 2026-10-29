# FIX20 Android Vulkan loader correction

Input: logcat_recording_2026-10-29_05-34-56.zip.
The game process fails during System.loadLibrary, before engine startup:
UnsatisfiedLinkError: cannot locate symbol "opengothic_vulkan_is_turnip" referenced by libopengothic.so.

FIX19's proxy used the public Android SONAME libvulkan.so. This can resolve to Android's system Vulkan, which cannot export the app-specific helper. Merely checking APK exports did not exercise the real dynamic loader.

FIX20 uses libopengothic_vulkan.so and prefixes all 107 direct Vulkan entry points with opengothic_. This also prevents a preloaded system Vulkan from interposing individual core entry points. Original vk* strings remain unchanged when resolving driver entry points dynamically.

Checks completed before Android packaging:
- Patch applied cleanly to OpenGothic 18336539 and Tempest 8c7c47fc.
- Python and shell syntax validation passed.
- Generated 107 wrappers from the pinned Khronos registry.
- Host regression reproduced the old missing-helper crash by preloading a library with SONAME libvulkan.so.
- The same regression successfully loaded the new engine/proxy; the helper resolved and the engine's core Vulkan function address differed from the preloaded system function.
- Automated APK checks require the private dependency and prefixed engine imports, and reject a direct libvulkan.so dependency and unprefixed wrapper exports.

Render resolution, shadows and effects are not changed by this loader correction. Android startup, actual Turnip selection, gameplay stability/FPS and pause/resume still require device verification.

Android build source commit: ff6ffdc663fb76811c64164df0d866cea266c177.
