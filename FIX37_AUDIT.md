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

## CI release result
Run [41006729152](https://github.com/Erken22/Gothic-Open-Android/actions/runs/41006729152), job 123903200086: success. Native Gradle build completed in 8m 2s; shader validation, host tests, ARM64 build, packaging/private Vulkan linkage, signing and native symbol/build-ID preservation passed. Existing third-party compiler warnings remain; no compile failure. Tag `exact-067-fix37` points to build commit `fd7e324b55374bd2d2fe96e91a19f9b2d2d44518`.

APK `GothicLauncher-arm64-OpenGothic067-FIX37-TURNIP.apk`: 22,729,591 bytes, SHA256 `dd546086c256f3005abd7ba8d4a0299e6519484f77f7a656a1509c0f7f0500ef`. Verified signer SHA256 `18bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611` (same update identity). Release asset digest agrees with signed build output. Phone result pending; no FPS or pixel-equivalence claim.

## Phone log: 2026-10-30 10:21
Analyzed supplied `logcat_recording_2026-10-30_10-21-01.zip` directly. FIX37 build and bundled-driver/material gates executed; all eight ABBA pairs collected at 10:21:15.826–10:21:30.999. Tuner selected **original**.

| Median GPU interval | Original ms | Fused ms | Observation |
|---|---:|---:|---|
| Resolve plus ambient | 1.520234 | 1.150026 | 24.35% smaller, 7/8 pair wins |
| Whole sampled frame | 40.264609 | 40.889348 | 1.55% larger, only 4/8 pair wins |

Local chain difference is about 0.370 ms. This is a promising limited result, not a confirmed whole-frame FPS gain. Do not interpret the whole-frame comparison as proof of a regression either: far-shadow region varies from 10.439 to 4.250 ms during the A/B window, SSAO varies from 8.580 to 6.172 ms, and scene/workload equivalence is not established. Original ambient timings in samples 1 and 5 are unusually small (~0.033 ms), as is fused sample 5 (~0.073 ms); these are recorded as-is and not selectively removed to improve the outcome. No cause is established for these small intervals. The stable-looking second pair has chain 1.532656 vs 1.153073 ms and frame 42.512759 vs 42.093593 ms, but one pair is insufficient evidence.

No fatal signal/exception, VK_ERROR, GPU fault, ANR, device-lost or assertion-failure signatures were found. This log cannot validate image quality. Keep candidate optional/original selected. A stationary repeat on the same APK could establish whether the small local saving survives whole-frame comparison; a rebuild is unnecessary for that check. The much larger remaining SSAO producer (~8 ms in several samples) remains a separate optimization target.

## Stationary phone repeat: 2026-10-30 10:23:59
Supplied `logcat_recording_2026-10-30_10-23-59.zip` contains a fresh complete eight-pair run. Workload is substantially steadier: far shadow during the A/B window stays about 10.37–10.51 ms; SSAO producer stays about 8.18–8.36 ms. Original ambient is consistently 0.73–0.82 ms; the previous run's tiny ambient intervals do not recur.

- Resolve+ambient median: original **1.5094795 ms**, fused **1.1780985 ms**, saving **0.331381 ms / 21.95%**, 8/8 pair wins.
- Whole-frame median: original **42.2386445 ms**, fused **41.961848 ms**, saving **0.2767965 ms / 0.6553%**, 6/8 pair wins.
- Tuner selected **original** because whole-frame gain is below the predefined >1% threshold. Chain and pair-win gates pass. Do not change the threshold after observing this result.
- First original frame is higher (43.619426 ms) than the remaining baseline samples; median limits its influence. Result supports a small local improvement, with whole-frame timing trending in the same direction. It does not establish a perceptible FPS gain or isolate every timing confounder.
- Most subsequent CPU-window FPS readings are about 23.5–23.9; these mix candidate/original windows or follow fallback and are not a separate path-matched FPS comparison.
- No fatal signal/exception, VK_ERROR, GPU fault, ANR, device-lost or assertion-failure signatures found. Pixels still require visual assessment.

The repeat resolves the previous varying-workload ambiguity enough to classify this experiment as a small saving below the current adoption threshold. Retain measured fallback behavior; next substantial target remains the SSAO producer (~8.3 ms), rather than further tuning this ~0.33 ms resolve saving. No further identical repeat or APK rebuild is needed solely to classify FIX37.
