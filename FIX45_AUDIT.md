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

## Phone result: 2026-11-06 20:34:56 recording

Source: user-supplied logcat_recording_2026-11-06_20-34-56.zip (2,012,697-byte text). Gameplay GPU/CPU metrics are present: the earlier permission-blocked Fight.dat startup failure is absent. No native fatal signal, AndroidRuntime fatal exception, unhandled native exception or explicit Vulkan device loss is present in this recording. Nonfatal ZenKit parsing warnings occur while loading. This does not establish all-scene or resume stability.

There are 15 GPU samples and nine frame summaries. Median sampled GPU frame 45.016249 ms; median displayed interval FPS 22.328251 (range 20.181625–25.832387). These are not a controlled comparison against the previous APK.

**Settings changed during the recording.** Initial AO Original, half=1, fog ORIGINAL. AO switched 0→1→0→1, last at 20:35:16.086. Fog changed to TEST at 20:35:16.977. The last 12 GPU samples use SAO manual half; first three use original SSAO. Original AO median 8.263437 ms (n=3), manual SAO median 10.7073175 ms (n=12). This is not a matched A/B trial, but confirms that the known slower prototype was active. Restore AO method Original for normal play and baseline work; do not claim an FPS optimization from this recording.

Far-shadow median 10.422916 ms. Sum repeated source intervals within each sample before taking a median:

| Far-shadow source | Median ms across 15 samples |
| --- | ---: |
| Mixed source packets | 7.025676 |
| Animated source | 1.570208 |
| Landscape source | 1.450833 |
| Morph source | 0.217604 |
| Frame-animated material | 0.009740 |

Source medians need not sum to median whole shadow time. Setup and particles are also part of the existing whole-shadow total. One 54.286457-ms GPU sample has 9.588177 ms attributed to the undivided shadow setup marker; do not assign that outlier to static geometry. No src=overflow or [marker limit] appears.

Mixed packets dominate, so these measurements cannot attribute their full cost to cacheable static geometry. Pipeline-based command merging must be classified by actual immutable/mutable content before a static-shadow cache can be justified. Pure Landscape is only approximately 1.45 ms here; 10.4 ms must not be advertised as the available saving.

Six projection windows: (comparisons, identical, changed) = (119,54,65), (120,120,0), (120,108,12), (120,0,120), (120,0,120), (120,0,120). Across all windows 282/719 identical, but the identical-heavy windows overlap settings interaction; they do not establish reuse frequency during continuous gameplay. In the final 360 observations all matrices changed. Freezing the existing far shadow map would therefore use stale projection during that interval.

Decision: restore Original AO immediately. For further optimization, quantify mixed-packet immutable content and develop projection stabilization / explicit invalidation before attempting static-map reuse. No cache or new FPS gain is validated by this log. No APK change is needed to restore Original AO.
