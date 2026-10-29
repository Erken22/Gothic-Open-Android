# FIX26 SSAO sampling reuse

Base: FIX25 audit commit 999a0b15be54b4d987a1f1c09d9c7877772c396b.
Engine exact upstream 18336539f4b1a8d7b325930f613811f59fbde5db.

FIX25 phone log 2026-10-29_10-04-33 confirms descriptor indexing and 16777216 texture/storage capacity, bindless batches active, 24 draw batches. CPU command recording ~4–6 ms vs ~18–29 ms in FIX24 log, but different scenes/settings prevent attributing an exact FPS gain. FPS varies 22–28, then 40–48, then 13–19; GPU samples 21–74 ms with SSAO up to21.46 ms and shadow map up to20.04 ms. No fatal exception/signal/FORTIFY match in this recording. This does not prove long-run stability or fix resume.

Qualified bundled Turnip Adreno650 gets SSAO_ROTATION_CACHE full/half shaders. Baseline shaders remain selectable for other devices. First32 workgroup invocations calculate shared unrotated sample directions; existing initial barrier publishes them. Each pixel calculates its original random-angle sin/cos once, then uses angle addition to rotate cached samples. No extra barrier/subgroup requirement, sample count reduction, radius change, lower resolution, convergence change, or blur change. Shared storage increases by32 vec3 (implementation packing applies). Arithmetic is mathematically equivalent but float rounding can change individual boundary decisions; visual device QA remains necessary. No guaranteed performance gain until tested on actual GPU.

Host test executes real patched GLSL sampling functions translated with float vector stubs:262144 comparisons, max component error5.06639481e-7 (<2e-6), z identical, all32 sample indices covered. Existing namespace/cached dispatch/fence concurrency/material gating/metrics tests pass. Fresh source fixture applies all anchors. CI must compile/validate baseline/full, baseline/half, cached/full, cached/half SPIR-V and build signed ARM64 APK.

Preserve FIX23 targeted fence completion, private Vulkan ABI, shared C++ runtime, FIX21 VSM startup exclusion, FIX25 RTSM/mesh/tess/ray-query guards, frame sampling and standard shadow maps.

Build/publication and actual device validation pending.
