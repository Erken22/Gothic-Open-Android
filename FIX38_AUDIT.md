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

## CI release result
Run [41012295371](https://github.com/Erken22/Gothic-Open-Android/actions/runs/41012295371), job 123920654074: success. Original/candidate shader compilation and SPIR-V validation, all host checks, native ARM64 build (Gradle 10m 30s), packaging, signing/private linkage and exact native symbol/build-ID preservation passed. Tag `exact-067-fix38` points to build commit `f1732b2503b2d8bd2989966d025aff66b16268d4`.

APK `GothicLauncher-arm64-OpenGothic067-FIX38-TURNIP.apk`: 22,733,687 bytes. SHA256 `46637d36ac96c7dbbe2e34df77e30be31016e9a82dc16cb7d02cfd5b5f02d4e6`. Release asset digest agrees with signed build output. Signer SHA256 `18bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611`, same update identity. Phone performance and visual validation pending.

## Phone result: 2026-10-30 11:23:06
Analyzed supplied `logcat_recording_2026-10-30_11-23-06.txt`. Both paths executed; eight complete pairs. Tuner selected **original**.

| Median GPU time | Original ms | Lazy ms | Nominal difference |
|---|---:|---:|---|
| SSAO producer | 8.274609 | 8.268203 | -0.006406 ms / -0.0774% |
| Whole sampled frame | 43.167629 | 43.072056 | -0.095573 ms / -0.2214% |

Only 3/8 SSAO pairs and 5/8 whole-frame pairs favor candidate. Differences are small relative to per-pair variation, do not pass the predefined gates and do not demonstrate a useful speedup. First original frame is elevated at 45.601822 ms; median limits its influence. Far-shadow region stays ~10.33–10.45 ms through the A/B window, much steadier than the first FIX37 log. No identical repeat is required to classify this result.

Compiler records distinguish full original (712 instructions) and half original (811). Relevant half-AO comparison is **811 original vs 807 candidate instructions**, registers used **16 vs 16**, compiler Max Waves Per Core **8 vs 8**, STP/LDP **0/0 for both**. Compile-time statistics show only a small generated-code change; they are not live GPU occupancy, utilization or proof of physical memory traffic. Eager initialization removal did not produce a meaningful end-to-end gain on this device. Do not retain this candidate as an enabled optimization in the next build.

No fatal signal/exception, VK_ERROR, GPU fault, ANR, device-lost or assertion-failure signatures found. No visual equivalence can be established from this log alone. Keep original selected. A larger AO implementation change remains a separate next experiment and must include image-quality comparison, rather than assuming timing alone validates a new AO formula.
