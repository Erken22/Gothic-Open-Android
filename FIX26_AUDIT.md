# FIX26 SSAO sampling reuse

Base: FIX25 audit commit 999a0b15be54b4d987a1f1c09d9c7877772c396b.
Engine exact upstream 18336539f4b1a8d7b325930f613811f59fbde5db.

FIX25 phone log 2026-10-29_10-04-33 confirms descriptor indexing and 16777216 texture/storage capacity, bindless batches active, 24 draw batches. CPU command recording ~4–6 ms vs ~18–29 ms in FIX24 log, but different scenes/settings prevent attributing an exact FPS gain. FPS varies 22–28, then 40–48, then 13–19; GPU samples 21–74 ms with SSAO up to21.46 ms and shadow map up to20.04 ms. No fatal exception/signal/FORTIFY match in this recording. This does not prove long-run stability or fix resume.

Qualified bundled Turnip Adreno650 gets SSAO_ROTATION_CACHE full/half shaders. Baseline shaders remain selectable for other devices. First32 workgroup invocations calculate shared unrotated sample directions; existing initial barrier publishes them. Each pixel calculates its original random-angle sin/cos once, then uses angle addition to rotate cached samples. No extra barrier/subgroup requirement, sample count reduction, radius change, lower resolution, convergence change, or blur change. Shared storage increases by32 vec3 (implementation packing applies). Arithmetic is mathematically equivalent but float rounding can change individual boundary decisions; visual device QA remains necessary. No guaranteed performance gain until tested on actual GPU.

Host test executes real patched GLSL sampling functions translated with float vector stubs:262144 comparisons, max component error5.06639481e-7 (<2e-6), z identical, all32 sample indices covered. Existing namespace/cached dispatch/fence concurrency/material gating/metrics tests pass. Fresh source fixture applies all anchors. CI must compile/validate baseline/full, baseline/half, cached/full, cached/half SPIR-V and build signed ARM64 APK.

Preserve FIX23 targeted fence completion, private Vulkan ABI, shared C++ runtime, FIX21 VSM startup exclusion, FIX25 RTSM/mesh/tess/ray-query guards, frame sampling and standard shadow maps.

Build and publication verified below; actual device validation pending.

## Published verification

Build/tag source:61c16a1e88e962d78a92cc8185d6d09e6cacf187; GitHub Actions run40822353087 job123277461292:success. Four SPIR-V variants compile and pass spirv-val; all host checks pass; ARM64 build and APK packaging/signature/ABI/native-symbol Build-ID match checks pass.

Release exact-067-fix26 targets the exact build SHA. APK GothicLauncher-arm64-OpenGothic067-FIX26-TURNIP.apk,22737783bytes, SHA256013a6d6492f52d8e97b396a2cade887e2646fd2a47e87b9f210e65a3319efe9b. Certificate SHA25618bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611. GitHub release asset digest matches build log hash. New FIX26 SSAO marker is present in packaged engine. Symbols archive published alongside APK. Device shader compilation, visual quality, FPS and resume remain unverified until phone feedback.
