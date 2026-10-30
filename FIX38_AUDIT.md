# FIX38: lazy private SSAO hit-bin initialization

## Target and scope
Exact OpenGothic 0.6.7 commit `18336539f4b1a8d7b325930f613811f59fbde5db`, pinned Tempest, existing Android package and signing identity. Retained FIX32 rendering path. FIX37's optional resolve/ambient fusion is absent to isolate the producer experiment; FIX33–36 failed/insufficient experiments are absent. Bundled Turnip policy and proxy remain unchanged (107 core wrappers).

The original SSAO producer costs ~8.3 ms in the stationary FIX37 phone repeat. FIX37 saved ~0.33 ms in resolve/ambient and ~0.66% of the frame, below the unchanged adoption threshold. This experiment targets work inside the producer while preserving its algorithm.

## Candidate
Original eagerly zeroes a private float[25] for every invocation, then tracks touched hit bins in an existing uint `hits` mask. Candidate removes only that zeroing loop and changes `addHit` to read an old bin value only when its existing hit bit is set. On first hit, old value is explicitly 0; the same hit/miss masks and subtraction/addition/max order are retained, and the bin is written. Misses set only anySmp and do not authorize a bin read. State/mask resets remain per invocation. All other shader code is byte-identical.

Same 32 samples, 8 iteration limit, sample directions/noise, radius 100, depth and normal reconstruction, 5x5 histogram, distance weights, group-wide convergence, workgroup 8x8, half-AO representative depth and upsampling filter. No sample-count or resolution reduction, no new AO formula. Full-resolution SSAO and non-target drivers use their original shader.

Candidate may be slower: it adds a per-hit mask test/branch, and the backend may already optimize eager stores. No guaranteed memory, register-pressure or FPS reduction is claimed. Dynamic indexing and the 25-entry private array remain; this is not a replacement of the AO algorithm or a claim to eliminate spills.

## Integration and measurement
Candidate pipeline created only on bundled Turnip Adreno 650 with RG32F storage; selected only for half-AO. Debug marker identifies original/candidate GPU timings. Eight ABBA pairs compare whole SSAO and total sampled GPU-frame medians, with >5% SSAO and >1% whole-frame gain and at least 6/8 paired wins each required. Otherwise original. Invalid, duplicate, mixed, missing or incomplete samples cannot select candidate. Choice freezes per process. Budget remains 24 sparse samples, read after existing fences with no added GPU waits. `FIX38 SSAO-lazy` identifies decisions in logcat. Thresholds were not relaxed to adopt the smaller FIX37 result.

## Validation
Local: apply to pristine target files; Python syntax; instrument actual original/candidate hit/miss functions with poisoned private bins and read-before-write tracking. 1,280,000 hit/miss updates across all 25 bins, repeated bins, misses and invocation resets: CPU bit-identical accumulated values, masks and resolved AO; no unwritten reads. Test asserts shader differs only at eager initialization and guarded old-value load. Existing Vulkan namespace/cache/autotune, target-fence, material gating, frame timing/tuner, depth-layout, render-audit and stage-barrier tests pass.

CI additionally compiles and spirv-val checks original/candidate half-AO, builds Android ARM64, checks private Vulkan/C++ runtime linkage, verifies signed package/version/build ID and preserves exact native symbols. Phone performance and pixels remain pending; CPU equality/CI do not prove bit-identical GPU results or a speedup.
