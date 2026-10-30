# FIX43 SSAO Hammersley rotation: experimental GPU FPS build

Base: FIX42 (full-resolution sky pixel early exit) and unchanged FIX40T graphics and fog timing.

SSAO is ~8.3 ms in current phone GPU samples. The original kernel computes two trigonometric operations for each of 32 samples/pixel. Hammersley angular offsets are a fixed 32-point bit-reversal pattern. FIX43 replaces per-sample sine/cosine with an 8-element quarter-circle lookup and two sine/cosine operations per non-sky pixel, rotating each vector using a 2x2 matrix.

Mathematical check: compare 64,000 rotated directions in original angular formula against quarter-circle factoring, tolerance 3e-12 in double precision; geometry and sample count not reduced. Float32 numerical rounding may shift exact shadow sampling at edge pixels. This is experimental until checked visually on phone.

32 taps, AO spatial resolution, shadow maps, fog, materials and visual features remain the same. No per-frame synchronization or driver workarounds. Verify speed against FIX42 and FIX40T in same camera position, AO Method Original, Fog shadow clip Original, same warmth/thermal state. If slower, revert independently from FIX42.
