# FIX42 full-resolution SSAO sky optimization

Based on verified FIX40T (OpenGothic 0.6.7, Turnip on Snapdragon 865 / Adreno 650).

From the 2026-10-30 17:11 phone log: frame GPU median 42.83ms, SSAO median roughly 8.3ms, far shadow layer 10.4ms and fog roughly 5.98ms; ~23.5 FPS at 2400x1080.

## Optimization
The 32-sample original full-resolution SSAO kernel currently reconstructs 4 adjacent depths, 3 world positions, a surface normal and tangent basis **even for fully sky pixels** (z >= 1.0). But those pixels have `estimateMaxSteps(z)==0` and cannot contribute shadows. FIX42 skips depth reconstruction and tangent generation only for `valid && z>=1.0` and explicitly writes unoccluded AO=1 instead of an undefined 0/0 NaN. Geometry SSAO algorithm, sample count, convergence, textures, dimensions, shadow quality and fog are unchanged. The `SSAO_HALF_RES` variant inherits the safe sky behavior but does not change its 2x2 depth selection.

Expected benefit depends on visible sky coverage, and is **unproven until device A/B**. No new Vulkan waits, CPU staging, GPU readbacks or renderer changes.

## Verification
Compile both full and half-resolution original SSAO shaders with `glslangValidator`, run spirv-val, and examine GPU samples to compare AO and full-frame times on the same scene. Revert if slower or any visible AO artifacts.
