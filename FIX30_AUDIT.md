# FIX30: fog scheduling experiment

FIX29 device log 2026-10-29 22:59:39: all eight shared-bin SSAO pairs lost; median private 8.274297 ms vs shared 8.493307 ms. Selector retained original. FIX30 restores original SSAO only and retains FIX28 driver policy.

Candidate fog shader keeps all 32 iterations/samples, exact per-index interpolation, sampler and bounds behavior. Changes scheduling to four independent requests per loop and 8x8 rather than 8x16 workgroups. Original shader file remains byte-for-byte unchanged. VSM/raytracing paths do not use candidate.

Turnip Adreno 650 only. Eight counterbalanced GPU pairs, >5% median improvement AND >=6 pair wins required; incomplete samples fall back. No GPU waits added. Measurements are scene/clock dependent; fixed camera is required for useful comparison. No phone performance gain or graphics correctness claimed yet.

## Baseline device observations

FIX29 recording contains 17 frame summaries: median 23.741620 FPS, range 12.118153–28.871867. The isolated 12.118153 summary follows MIUI Recents at 23:00:28 and resume at 23:00:29, so it is not evidence of steady rendering throughput. Initial low-variance segment stays around 23.6–23.8 FPS. First 16 sparse GPU samples median 42.516639 ms. No fatal signal, fatal Java exception or VK_ERROR_DEVICE_LOST found in this recording. New candidate must be assessed within FIX30 using its paired measurements, with camera/settings held fixed.

## Verified build

Run 40928828922 / job 123641511321 succeeded. Exact source/tag commit: f1c439f6190bc3be0486166be3c32dfe503cd7a7. Release tag exact-067-fix30 points to this build commit.

APK size: 22717303 bytes. SHA256: f302c3daebc3f08cc6d3b1e5c6bb6f768712dec037a927c7836be6ccc110be3c. Certificate SHA256: 18bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611 (unchanged).

Local host tests and CI tests passed, including real loop positions/masks for 100000 rays, 32-sample preservation, odd-sized dispatch, A/B selection/fallback, private Vulkan ABI, cached dispatch concurrency, fence lifetime, material gates, Turnip policy and depth layout. Both fog SPIR-V variants validated. Full Android ARM64 build, signature and packaged linkage checks succeeded; exact native Build IDs matched. Phone performance/visuals remain unverified.

APK: https://github.com/Erken22/Gothic-Open-Android/releases/download/exact-067-fix30/GothicLauncher-arm64-OpenGothic067-FIX30-TURNIP.apk
