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

## Verified build

- Source/build/tag commit: `e855323523124ae67ebe4796f2e1c1d425ad0d27`.
- GitHub Actions run `40994254589`, job `123863579731`: success.
- All host checks, four glslang/spirv-val shader variants, native build,
  packaging/loader ABI, build-ID/symbol matching and signing checks passed.
- APK: 22,758,263 bytes; SHA-256
  `b174d1fcfd9a6a1ce1173a70704b463f8bbc2ec105262ce99eb0f8b9b0bdd17b`.
- Signer SHA-256:
  `18bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611`.
- Release: https://github.com/Erken22/Gothic-Open-Android/releases/tag/exact-067-fix34
- Phone FPS, visual match and stability remain unverified.

## Phone result — candidate rejected, 2026-10-30

Log: `logcat_recording_2026-10-30_08-40-31.zip`; FIX34 confirmed.
Half-resolution SSAO: original median 8.325182 ms, candidate 9.132786 ms
(+9.7007% time); candidate wins 0/8. Automatic selector retained original.
The last original sample fell to 6.563489 ms alongside other pass changes,
so the final pair is not scene-stable. First seven pairs still all reject the
candidate; medians 8.329531 vs 9.127291 ms (~9.58% slower).
Compiler reports half-resolution instruction count 811 -> 1156, registers
16 -> 21, Max Waves Per Core 8 -> 6. These are compiler statistics, not live
occupancy measurements. More instructions/register use is consistent with the
measured regression; this is not a measured attribution of GPU bottlenecks.
During the early test FPS ~23; later ~25-29 with a changed workload. Later FPS
must not be attributed to this rejected candidate. No fatal signal, Vulkan
error, GPU fault or OpenGothic ANR found in this recording.
This bucket-switch approach should be removed from the next build.
