# FIX33 measured SSAO subgroup reductions

FIX32 phone: masks 252/248 applied; 38 barriers retained, broad flags 16->0. First 19 frame summaries median 23.573161 vs FIX31 23.646974; first 10 GPU samples 43.1340615 vs 43.0816655 ms. No demonstrated speedup; no GPU/fatal errors in recording. Keep semantically precise mapping but do not claim a gain.

Original SSAO 8x8 workgroup compiled with subgroup size64 on this phone. Candidate uses unsigned subgroupMax for maxSteps and convergence float bit patterns only if gl_NumSubgroups==1; otherwise original shared atomics/barriers. Needs supported compute subgroup basic/arithmetic and supported+enabled shaderSubgroupUniformControlFlow extension/feature with SPIR-V execution mode. No implicit reconvergence assumptions. Other GPUs retain original pipeline; original shader/include byte-for-byte preserved.

All 32 samples, eight maximum iterations, sphere radius100, noise, geometric sampling, half-resolution pixel/depth selection, thresholds, accumulation and resolve remain unchanged. Separate full/half paired selectors: eight AB/BA pairs, >5% median improvement and >=6 wins required, incomplete fallback original. Compiler statistics are not runtime counters. Phone visual correctness and gain unverified.

Validation before phone testing: real old/new convergence helpers compared using CPU workgroup barriers and a model of the specified unsigned subgroup reduction, for 256 groups of 64 invocations, with random bit patterns, NaN/Inf/signed-zero and threshold cases; original multi-subgroup fallback exercised. This is not a GPU execution or pixel-equivalence test. Sampling and normal-reconstruction functions, workgroup size and sample count contracts checked unchanged. Original/candidate full/half shaders compile and SPIR-V validates; candidate modules contain SubgroupUniformControlFlowKHR and OpGroupNonUniformUMax. Existing selector cadence/ABBA/threshold/fallback tests and Vulkan stability tests passed.

## Verified release

Run 40963063061 / job 123760525769 succeeded. Exact build/tag commit b58bbb504edc807af4c8631b81c6bfc9e8851cdd. APK size 22758263 bytes, SHA256 b473dcbe29288648d7f1b46547aef8ea839c5f7b6d65e46823e53a309111fa07. Certificate SHA256 unchanged: 18bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611.

CI host tests, four original/candidate full/half SPIR-V compilations and validations, candidate execution-mode/UMax presence checks, full Android ARM64 build, signature/private Vulkan ABI packaging and native Build-ID matching passed. Device feature availability, graphics and actual FPS are unverified; no phone speedup claimed.

APK: https://github.com/Erken22/Gothic-Open-Android/releases/download/exact-067-fix33/GothicLauncher-arm64-OpenGothic067-FIX33-TURNIP.apk

Next device log: record before startup; inspect FIX33 subgroup support size/arithmetic/uniform-flow, SSAO A/B startup, eight samples per path for the active full/half mode, final SSAO choice and compiler stats for ssao_wave.comp. If unsupported, candidate is not compiled or selected. If incomplete or slower, original remains. Compare within-recording paired timings; moving camera/scene changes and thermals confound cross-build FPS. First 30 seconds fixed camera/settings, then move to check graphics. Multi-subgroup shader branch retains original atomics/barriers even when the candidate pipeline is selected.
