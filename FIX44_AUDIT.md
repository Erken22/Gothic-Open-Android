# FIX44: original SSAO group-shared atomic contention optimization

User data: 2026-10-30 19:00–19:02 FIX42 vs FIX43 logs each show 16 GPU samples; median AO 8.313 vs 8.303 ms, median GPU frame 43.20 vs 42.95ms. These tiny changes do not establish an FPS improvement.

FIX44 uses subgroupMax for per-wave reductions before updating the existing shared group-wide maxima with subgroupElect atomics. With workgroup 8x8=64 threads, it reduces atomic contention up to 64x (e.g. 2 atomics instead of 64 for subgroup width 32), without changing group-wide max, sample count (32), pixel resolution, iteration budget, AO weights, fog or shadows. The normal-shader subgroup requirements must be supported by target Vulkan device; **an APK compile does not prove mobile subgroup support**, so watch for pipeline creation errors. This is an isolated experimental branch and the known-good FIX43 remains unchanged.

A/B protocol: compare FIX43 and FIX44 on the same saved scene with AO Method Original, Half-res SSAO Off, Fog shadow clip Original, and identical other settings. Examine GPU SSAO pass medians rather than only FPS, which includes CPU and fluctuating rendering load. Revert if improvement below noise or any visual difference.
