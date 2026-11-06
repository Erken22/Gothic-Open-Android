# OpenGothic Android: concrete next optimization decision
Date: 2026-11-06. Target: OpenGothic 0.6.7, Mi 10T Pro / Adreno 650, private Turnip Vulkan proxy. Research and source inspection only; no new APK or measured speedup in this step.

## Decision
The next substantial, bounded GPU experiment should integrate the complete official FidelityFX CACAO Vulkan implementation, including depth preparation, deinterleaving/mips, AO generation, edge-aware filtering and final upscale. This is a candidate to replace the existing expensive AO chain. It is not the failed independently written FIX39 SAO formula and must not be advertised as proven faster on this phone.

Use the existing original AO as the image/performance reference. Retire the failed SAO test from ordinary optimization menus so an obsolete saved choice cannot silently select it. Keep the original option for rollback. No default automatic acceptance based solely on shader compilation.

## Evidence from our code and phone
- Original half-AO producer remains around 8.26–8.33 ms. Original shader retains a dynamically indexed 25-bin private histogram, per-hit unprojection, projected depth fetches and group convergence atomics/barriers. Rewriting one of those components has repeatedly failed to yield a useful whole-frame gain. It is not established whether the limiting factor is ALU, texture locality, register pressure or synchronization.
- FIX39 independently written 32-tap SAO was measured slower, around 10.7 ms. The latest log accidentally selected it for 12/15 GPU samples. Simply using a different formula is insufficient.
- Far shadows are about 10.4 ms; FIX45 attributed about 7.03 ms to mixed source packets and only about 1.45 ms to pure Landscape (medians per sample, not additive guarantees). A cache for Landscape alone cannot remove 10.4 ms.
- Last 360 observed far-shadow matrices all changed. Source confirms dependence on camera pose and solar direction computed from millisecond game time. An unchanged-projection cache cannot be assumed useful during play. Stable projection, content classification and invalidation would be a larger independent project.
- Renderer currently uses CMAA2 and has no existing temporal AO accumulation in the inspected path. A first implementation should not depend on motion-vector/TAA infrastructure.

## Why CACAO is implementable
The standalone official repository includes a Vulkan backend in ffx-cacao/src/ffx_cacao_impl.cpp and its public integration API in ffx-cacao/inc/ffx_cacao_impl.h. The implementation has separate precompiled SPIR-V variants and optional 16-bit mode. No DirectX renderer port is required.

Primary references:
- https://github.com/GPUOpen-Effects/FidelityFX-CACAO/blob/master/ffx-cacao/readme.md
- https://github.com/GPUOpen-Effects/FidelityFX-CACAO/blob/master/ffx-cacao/src/ffx_cacao_impl.cpp
- https://gpuopen.com/manuals/fidelityfx_sdk/techniques/combined-adaptive-compute-ambient-occlusion/
- Comparison candidate: https://github.com/GameTechDev/XeGTAO/blob/master/README.md

The official CACAO documentation explicitly describes deinterleaved depth and optional depth mips as a GPU cache-efficiency measure. In its downsampled configuration, four depth slices each have quarter input width/height, totaling one quarter of the original pixel count. That is a sensible first candidate against our current half-width/half-height AO producer, rather than secretly cutting the total evaluated pixel count again. Input/output buffer sizes and final upscale still follow CACAO's own contract. Similar pixel count does not imply identical sample distribution or appearance.

XeGTAO is also a plausible alternative, with depth prefilter, core pass and spatial denoising. TAA is optional, not mandatory. It has an HLSL/DirectX-oriented reference integration, while CACAO already supplies the Vulkan host backend. Do not quote its published RTX/iGPU timings as predictions for Adreno.

## Integration work that cannot be skipped
1. Pin official sources and shader binaries/build inputs by immutable commit/checksum; retain license notices. Disable the SDK's independent profiling/debug-marker machinery initially and use existing bounded engine timestamps.
2. Introduce a deliberate Tempest/Vulkan bridge for the device, physical device, command buffer and image views. External commands must run outside render passes. Flush and reconcile Tempest's resource-state tracking, layouts and binding caches; raw insertion behind the tracker is unsafe.
3. Route all Vulkan entry points through libopengothic_vulkan.so / the existing prefixed dispatch. Never introduce a direct libvulkan.so dependency or unprefixed Vulkan imports into the Android engine.
4. Start with the official FP32 variant. The inspected Tempest VDevice creation does not explicitly enable shaderFloat16/16-bit-storage feature chains. Driver extension availability alone does not authorize FP16 shaders. Add queried/enabled capability gates before a separate FP16 experiment; retain FP32 fallback.
5. Match engine projection/depth conventions, sky depth, matrix layout and world scale. Current gbufNormal is an integer-packed normal texture; it cannot be passed as CACAO's expected normal image without conversion. First use CACAO's supported depth-derived-normal path, then separately evaluate existing-normal conversion if useful.
6. Supply final AO in the format and dimensions consumed by ambient lighting. Handle resize, internal render scale, world changes, Android surface recreation and resource lifetime across in-flight frames.
7. Compare the full AO chain, including depth preparation, generation, blur and upscale, against original producer plus its resolve. A faster core kernel with expensive prep is not a win.
8. Judge pictures and motion in wall corners, stairs, grass/fences, thin geometry and depth edges. Different AO algorithms can alter radius, darkness, halos and noise. Tune against the reference; do not claim exact visual equivalence.

## Acceptance and budget
Keep camera/save, settings and warmth comparable; use repeated ABBA runs after startup, then a moving-camera test. Require a meaningful median improvement in the entire AO chain and full GPU frame, consistent paired wins, and approved image quality. Compiler statistics are not acceptance evidence.

For scale only: at an illustrative 43-ms baseline, saving 4 ms gives 39 ms, approximately 25.6 FPS. Reaching 30 FPS needs about 9.7 ms total savings. Therefore even a successful AO replacement is unlikely by itself to guarantee stable 30 FPS in the expensive scene. These are arithmetic scenarios, not projected measurements.

If CACAO is not faster or produces unacceptable artifacts, reject it rather than stacking it with failed prototypes. After a confirmed AO improvement, investigate conservative hierarchical acceleration of fog shadow sampling or a broader shadow geometry/projection redesign as independent measured changes. Do not reduce shadow resolution or disable effects and label that an equivalent-quality optimization.
