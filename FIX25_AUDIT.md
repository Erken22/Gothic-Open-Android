# FIX25: qualified Turnip material batching

## FIX24 device evidence

The user reports a modest perceived FPS increase. The supplied 09:14:14
recording identifies FIX24 and confirms cached dispatch, targeted fence
completion and full HiZ. Early completed-frame summaries are about 28--33
FPS, with 19--21 ms command recording, 5--6 ms simulation and 6--9 ms
present/acquire. Captured GPU frames are mostly 32--36 ms; GBuffer is about
9 ms and the largest ordinary shadow-map interval about 6--8 ms.
Later summaries fall to 12--18 FPS with 21--29 ms command recording and
24--48 ms present/acquire. Shadows and fog settings change during the log.
This is not a controlled before/after benchmark; do not attribute the
entire difference to one setting or claim a specific gain over FIX23.
The initial eight GPU samples do not cover all later heavy moments.

## Change

The existing Android hasBindless guard disables batching for every GPU
whose name contains Adreno, including the bundled Mesa Turnip driver.
The existing command grouping code assigns a common bucket only in
bindless mode, so the guard keeps material buckets separate in all normal
geometry, shadow and depth passes.

Allow the existing bindless path only on a device identifying itself as
Turnip + Adreno + 650 and using the custom-loader helper, and only when the
original nonuniform indexing and >=65000 texture/storage capacity checks
pass. Preserve the existing CommandLine bindless opt-out. All other Adreno
cases retain the previous slot fallback; other GPUs and desktop selection
keep their original capability checks.

Avoid introducing additional rendering features as a batching side effect:
retain vertex-stage material pipelines, block newly enabled ray-query
shading and mesh shading on the qualified device, and retain previous
mobile tessellation exclusion. Keep experimental RTSM unsupported, as it
was with the previous slot-material mode; do not eagerly create its new
kernels just because bindless became available. The existing Android VSM
startup guard remains in place. Frame-animated materials keep their
existing per-material fallback.

Do not modify geometry, texture content, shadows/resolution, SSAO, fog,
HDR settings or full HiZ. Retain FIX23 targeted waits and FIX24 dispatch
cache. Log selected material capabilities and changed draw-batch counts.
Extend sparse nonblocking GPU samples to 24: initial eight every two
seconds, then ten-second spacing, to observe heavier scenes and settings.

Bindless shaders are an existing renderer path, but compilation and output
on this particular mobile driver require a device test. No FPS gain or
successful mode activation is claimed before that test.

## Validation

- Exact source replacement and Python syntax checks pass.
- Strict host tests execute the actual patched material selection and
  rendering policy for qualified/nonqualified drivers, descriptor limits,
  missing indexing, Android and desktop; preserve ray/mesh/RTSM exclusions.
- Existing private Vulkan ABI, 80000-call concurrent cache, native fence
  lifetime and frame timing/sampling tests pass.
- CI compiles ARM64, all existing SPIR-V variants, and verifies APK
  signing/linkage/build markers and native symbol-map Build ID.
