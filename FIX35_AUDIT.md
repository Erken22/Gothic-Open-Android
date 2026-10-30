# FIX35 — measured HQ fog mask/fragment fusion

## Scope

Build from clean FIX32 renderer policy, removing the rejected FIX33 subgroup and
FIX34 bucket-switch AO candidates and their tuners. Original SSAO restored.
Keep FIX25 batching, FIX28 Turnip autotune, bounded renderer audit, FIX32 stage
mapping, private Vulkan ABI, targeted fence waits and same Android update signing.

A separate `fog3d_fused` fragment pipeline computes the ordinary-shadow HQ fog
mask locally instead of writing/reading `sky.occlusionLut` between two passes.
Keep 32 shadow steps, original loop and comparisons, noise sampled at integer
invocation coordinates, original projection and `dFogMax` mask clamp. Keep final
fragment integration, sky handling, sun/exposure scaling and blending unchanged.

## Critical dependency

The old compute samples pre-water zbuffer. Final fog sees depth after water and
translucency. Candidate samples the existing raw R32F `sceneDepth` snapshot for
mask construction, while keeping current `zbuffer` for final fog integration.
`stash.frag` copies raw depth before water. It must remain in the render graph.
Do not substitute current depth in the mask, change noise to half-pixel values,
or clamp the final fog integration depth to the mask range.

Gate fusion to bundled Turnip Adreno 650, ordinary shadows, HQ fog, matching
nonempty snapshot dimensions. VSM/RTSM/pathtrace and other devices keep the old
path. Store the chosen path once in prepareFog so producer and consumer cannot
choose different modes within one frame. Candidate pipeline compiles only on
eligible driver/device; its SPIR-V is built and validated by CI regardless.

## Measurement / fallback

Use eight counterbalanced original/fused samples. Original sample includes BOTH
`Fog original mask` and `Fog original apply`; fused includes `Fog fused apply`.
Explicit end markers avoid swallowing unrelated following draws in these ranges.
Require >5% median fog-chain improvement, >1% median whole-GPU-frame improvement,
and >=6/8 paired wins for both fog and frame. Missing, duplicate, mixed or invalid
samples do not count; incomplete measurements fall back. Choice freezes for the
process. At most 24 sparse GPU samples; first sixteen sampled at one-second
intervals. Read results after the existing fence; no extra CPU/GPU waits added.
The whole-frame gate guards against merely relocating work between markers.
ABBA and thresholds are not proof against scene/thermal/driver-tuning changes.

## Validation

- Actual candidate mask helper translated into a small CPU vector model, compared
  to the old mask path for 50,000 random projections/pixels/depths. Exercises integer
  noise, odd dimensions, sky/clamp, shadow bounds and distinct pre/post-water depth.
- Source assertions keep the original 32-step loop and final integration unchanged.
- Real C++ tuner tests aggregate original producer+consumer, verify ABBA, separate
  whole-frame/fog thresholds and wins, frozen decision, malformed and partial data.
- Existing loader, dispatch-cache, fence, materials, autotune, depth layout,
  command/compiler audit and exhaustive stage-mapping tests retained.
- CI validates original compute, original HQ fragment and fused HQ fragment SPIR-V,
  then builds/signs APK and verifies libraries/exports/native symbol build IDs.

CPU model does not establish GPU pixel equivalence. Phone screenshots/motion,
water, sunshafts, depth edges, performance and stability still require validation.
No measured FPS gain claimed yet.

Build/publication pending.

## Verified build

- Build/tag commit: `a2af6cef38a8df39dd217a00583f037ffd9e7ed3`.
- Actions run `41000949645`, job `123884944126`: success.
- All host regressions, 50,000-case mask test and paired whole-frame tuner tests
  passed. Original compute/original fragment/fused fragment compiled and passed
  spirv-val. Native APK, library/loader ABI, native-symbol Build ID and signature
  verification passed.
- APK: 22,729,591 bytes; SHA-256
  `0679783e1e8e8a59a5b0d5e6b3784d9e421f9cca48bf2e9ac8b3fdeb075964e7`.
- Signer SHA-256:
  `18bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611`.
- Release: https://github.com/Erken22/Gothic-Open-Android/releases/tag/exact-067-fix35

Phone FPS, image quality, sunshafts at water boundaries and stability unverified.
