# FIX45: measure shadow-cache feasibility

Based on FIX43 commit d9208edb78e56b555d39f4c826abf8c402c13403, OpenGothic 0.6.7 and pinned Tempest. This diagnostic precedes a possible static-shadow cache. It does not implement caching or claim an FPS gain. FIX44 subgroup experiment and separate physics/upstream branches are not merged.

## Measurements

DrawCommands::commandId can reuse an existing command for matching pipelines. Record a union of every contributing source type instead of assuming the command's first type describes the entire batch. Also union material frame-animation flags. Categories: landscape, static, movable, animated, particles, morph, mixed, texture-animated. These identify sources only: Static can move in wind; Landscape can have other mutable state. None is automatically approved for caching.

Insert ordinary-shadow GPU markers only after the existing empty/pipeline checks, before the same binding/draw commands. Preserve command order, count, payload, culling, shaders, shadow resolution and image contents. Mark only category transitions, at most eight ordinary transitions plus one overflow marker per drawCommon invocation. Once capped, all remaining commands are labeled overflow. Four shadow invocations add at most 36 markers; existing 256-query GPU limit and 128-entry command-audit limit remain unchanged. Marker-limit warnings invalidate fine attribution. No new waits or query readbacks.

Existing at-most-24 sparse GPU samples log `FIX45 shadow source: tag=... ms=... frame-ms=...`. Sum repeated tags within each sample. Existing FIX39 shadow totals still include all intervals; never add the new source intervals on top of those totals. Bottom-of-pipe boundaries affect overlap and include marker overhead, so interval times are diagnostic estimates, not exact hardware utilization or guaranteed savings. The initial unlabeled solid/alpha intervals contain setup overhead.

Every 120 active-shadow drawShadowMap calls, log exact equality counts for the far world-space shadow matrix, compared to its preceding observation. Preserve the previous matrix across reporting windows. No epsilon approximation; even a small finite difference counts as changed. Equality only shows a necessary condition for reusing an exactly projected map. It does not check geometry, material, animation, shadow-map identity, load/resume or world invalidation. The counter must never drive caching. Changing matrices even while standing would motivate a stable-projection design rather than skipping updates.

## Verification

Apply all existing overlays to a pristine source tree then FIX45. Compile and execute the actual helper and modified frame metrics with UBSan. Tests cover every type, mixed source masks, animated materials, repeated categories, 10,000 category transitions capped at nine markers, tiny matrix changes, cross-window comparisons, repeated-source intervals and unchanged aggregate shadow/full-frame totals. CI additionally compiles/signs ARM64 APK, validates shaders, package, Vulkan proxy and native symbols. Phone measurements and visual stability remain pending.

## Phone protocol

Use the same save and graphics settings as FIX43. AO method Original, Fog shadow clip Original for the baseline. Keep the existing Half-res SSAO choice identical between runs. After loading, stand still facing the costly outdoor scene for 60 seconds, then walk and turn for another 30 seconds. Send logcat covering both phases. Check shadow movement and normal game stability. FIX45 is a measurement build; use the results to choose a cache scope and invalidation scheme before an optimization build.

## Build status

Host and CI helper/integration tests passed. GitHub Actions run 42237140853, job 127957601606 completed successfully. Native/Gradle build took 10m21s. Build commit and release tag exact-067-fix45 both point to 7f8115011b3031faae435f4cf8c8567bc3e51fa4.

APK: GothicLauncher-arm64-OpenGothic067-FIX45-TURNIP.apk, 22750071 bytes. SHA-256: 107e285b38e2de2b90ab3111152663b14767d51ab497eb7fbcfc6c8af4022cb1. The build's sha256sum matches GitHub's release-asset digest. Signer SHA-256: 18bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611. Package org.opengothic.launcher, version 0.6.7. Private Vulkan/C++ linkage, embedded diagnostic strings and native build-ID/symbol preservation passed.

Release: https://github.com/Erken22/Gothic-Open-Android/releases/tag/exact-067-fix45
CI: https://github.com/Erken22/Gothic-Open-Android/actions/runs/42237140853

Additional source finding: Sky::updateLight computes solar direction from millisecond game time, while WorldView::preFrameUpdate recomputes both shadow matrices. Exact projection reuse can therefore be scarce even while the camera is still. Phone counters must establish its actual frequency; a stable projection may be required before caching. Source masks conservatively retain types/material flags ever added to a live command, so stale mixed flags can underestimate the candidate scope rather than falsely certify a static packet. Device FPS, cacheability and image stability remain unverified.
