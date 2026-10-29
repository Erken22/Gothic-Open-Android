# FIX33 measured SSAO subgroup reductions

FIX32 phone: masks 252/248 applied; 38 barriers retained, broad flags 16->0. First 19 frame summaries median 23.573161 vs FIX31 23.646974; first 10 GPU samples 43.1340615 vs 43.0816655 ms. No demonstrated speedup; no GPU/fatal errors in recording. Keep semantically precise mapping but do not claim a gain.

Original SSAO 8x8 workgroup compiled with subgroup size64 on this phone. Candidate uses unsigned subgroupMax for maxSteps and convergence float bit patterns only if gl_NumSubgroups==1; otherwise original shared atomics/barriers. Needs supported compute subgroup basic/arithmetic and supported+enabled shaderSubgroupUniformControlFlow extension/feature with SPIR-V execution mode. No implicit reconvergence assumptions. Other GPUs retain original pipeline; original shader/include byte-for-byte preserved.

All 32 samples, eight maximum iterations, sphere radius100, noise, geometric sampling, half-resolution pixel/depth selection, thresholds, accumulation and resolve remain unchanged. Separate full/half paired selectors: eight AB/BA pairs, >5% median improvement and >=6 wins required, incomplete fallback original. Compiler statistics are not runtime counters. Phone visual correctness and gain unverified.
