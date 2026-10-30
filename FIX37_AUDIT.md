# FIX37: measured SSAO resolve / ambient fusion

## Scope
Exact OpenGothic 0.6.7 source `18336539f4b1a8d7b325930f613811f59fbde5db` and its pinned Tempest submodule. Same bundled Turnip, package and signing identity. Based on the retained FIX32 rendering path: FIX33/34 AO rewrites, FIX35 fog fusion and FIX36 indexed shadow prototype are absent. FIX36 phone measurements did not establish useful whole-frame improvement.

## Change
The existing half-resolution SSAO producer writes AO plus depth in RG32F. Its separate full-resolution upsample compute pass previously called `ssaoResolveHalf`, wrote R8, then ordinary ambient lighting read that R8 image. Candidate ambient lighting calls the **same unchanged helper**, sampling the same half-AO and current pre-water depth, with the same linear-depth conversion and sky-depth guard. Explicit packUnorm4x8/unpackUnorm4x8 retains UNORM8 precision. Main ambient color/normal/irradiance/exposure/blend/depth state is unchanged. No AO generation, radius, sample count, depth tolerance, resolution, fog or shadow quality reduction.

Candidate applies only on bundled Turnip Adreno 650 with RG32F storage, half-resolution AO, GI None, non-pathtrace. AO disabled, full-resolution AO, probes and surfel GI retain their original pipelines. One candidate flag is captured in prepareSSAO and reused in drawAmbient. Candidate skips only the upsample dispatch; original resource allocation remains, so no RAM saving is claimed. Automatic resource tracking handles the half-AO compute-write to fragment-read transition.

## Measurement and fallback
At most 24 sparse GPU samples, read after existing submission fences, without additional GPU waits. Up to eight ABBA original/candidate pairs. Original cost is the sum of `AO original resolve` and `AO original ambient`; candidate cost is `AO fused ambient`. Whole-frame GPU time is also compared. Candidate must lower chain median by more than 5%, frame median by more than 1%, and win at least 6/8 corresponding chain and frame pairs. Otherwise original wins. Missing, mixed, duplicate, non-finite and negative measurements are rejected; an incomplete experiment falls back to original when the budget ends. Choice freezes per process. Logs start `FIX37 AO-resolve`.

These timestamps include surrounding scheduling/cache effects and instrumentation. Moving a marker or reducing a dispatch alone does not establish a gain. Stable scene and phone temperature are required for meaningful comparison. The candidate may lose because fragment execution and texture scheduling differ from compute.

## Validation
Local: apply against pristine target files; Python syntax; existing Vulkan namespace/cache/autotune, target-fence, bindless gating, depth-layout, render-audit, all shader-stage barrier mappings, frame summary/budget and actual C++ tuner tests pass. Boundary checks pin unchanged AO producer/helper/original fallback and prove ambient changes are limited to the AO accessor plus its new depth binding; verify gating, pipeline/binding choice and per-frame snapshot.

CI additionally compiles original resolve, original ambient and candidate ambient with glslangValidator, runs spirv-val, and verifies pack/unpack survive into candidate SPIR-V. Android ARM64 native compile, packaging, private Vulkan linkage, release signing, version/build ID and symbol preservation must pass before APK delivery.

Phone performance and pixels remain unvalidated. Host checks/CI do not prove a speedup or pixel equivalence on Adreno. UNORM8 quantization preserves precision but FP scheduling and exact rounding at ties may differ from the original attachment conversion. Inspect depth edges/thin geometry and scene brightness on device; retain original fallback.
