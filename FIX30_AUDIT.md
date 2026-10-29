# FIX30: fog scheduling experiment

FIX29 device log 2026-10-29 22:59:39: all eight shared-bin SSAO pairs lost; median private 8.274297 ms vs shared 8.493307 ms. Selector retained original. FIX30 restores original SSAO only and retains FIX28 driver policy.

Candidate fog shader keeps all 32 iterations/samples, exact per-index interpolation, sampler and bounds behavior. Changes scheduling to four independent requests per loop and 8x8 rather than 8x16 workgroups. Original shader file remains byte-for-byte unchanged. VSM/raytracing paths do not use candidate.

Turnip Adreno 650 only. Eight counterbalanced GPU pairs, >5% median improvement AND >=6 pair wins required; incomplete samples fall back. No GPU waits added. Measurements are scene/clock dependent; fixed camera is required for useful comparison. No phone performance gain or graphics correctness claimed yet.
