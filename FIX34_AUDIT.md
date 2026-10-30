# FIX34 — SSAO bucket addressing experiment

## Problem and change

The original SSAO keeps 25 per-pixel hit weights and reads/writes a dynamically
indexed private array. FIX34 offers a separate shader where each valid bin uses
a constant-index switch case. This lets the compiler choose control flow instead
of private-array index lowering. Whether this helps Adreno 650 is unknown: more
divergence or code size can also make it slower.

The original shader stays byte-for-byte unchanged. Candidate changes only
`addHit`; sample count (32), iterations (8), hemisphere/noise, radius, projection,
depth selection, convergence barriers/threshold, workgroup size, AO resolution,
output and resolve are unchanged. The subtraction/addition/max operation order
is retained. Hemisphere sample directions map inside bins 0..24; a defensive
default returns for an invalid bin instead of an undefined out-of-bounds access.

The rejected FIX33 subgroup shader and subgroup feature requests are removed.
Qualified bundled Turnip / Adreno 650 alone can use the candidate. Other devices
retain original pipelines. Existing FIX25 batching, FIX28 Turnip autotune,
FIX31 bounded diagnostics and FIX32 stage mapping remain.

## Measurement and rollback

Eight counterbalanced original/candidate GPU pairs, independently for full and
half resolution. Candidate is selected only if median is >5% faster and at least
6 of 8 pair comparisons win; incomplete/noisy comparisons retain the original.
This is a regression guard, not proof of a controlled benchmark or visual match.

## Validation

CPU test executes the actual old/new addHit functions for 640,000 updates,
including all 25 bins and repeated/random hits; compares the complete private
array, hit masks and accumulated AO by float bit patterns. The rest of the shader
must be identical. CI compiles/validates all four shader variants plus native APK,
existing renderer tests, Vulkan loader ABI and consistent Android update signing.
CPU arithmetic checks do not establish bit-identical output from the GPU compiler.

Phone performance/visual/stability validation pending. No FPS gain claimed.
