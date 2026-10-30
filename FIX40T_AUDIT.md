# FIX40T phone audit and targeted GPU profiling

FIX40 verified APK launched on Xiaomi Mi 10T Pro / Adreno 650. Source: `logcat_recording_2026-10-30_15-30-42.txt` (44,458 lines).

Modes: `Fog shadow clip ORIGINAL` then `TEST` then `ORIGINAL`. Unfortunately AO was also changed from `Original SSAO` to manual `SAO` for most of the `TEST` window. Measured GPU samples:

| Window | Samples | GPU median (ms) | AO median (ms) |
| --- | ---: | ---: | ---: |
| Fog ORIGINAL + SSAO | 4 | 42.627108 | 8.3128905 |
| Fog TEST + SAO | 12 | 44.5777855 | 10.695937 |
| Fog ORIGINAL + SSAO | 2 | 41.6827335 | 8.2696875 |

These are NOT comparable tests of the fog optimization alone. The old fog pass reached top-four in one sampled frame at 5.954896 ms; no `Fog-sunshaft-occlusion` pass was present in top-four during TEST, so the pass time is **unknown**, not zero. No SIGSEGV, Fatal signal, FATAL EXCEPTION, VK_ERROR or device loss found. MIUI's separate ANR detector tag alone is not evidence of game ANR. App paused/returned test incomplete.

## FIX40T diagnostic-only patch

Do not alter any GLSL, shader algorithm, AO, textures, shadow resolution, driver, frame scheduling or sampler. Add only mode-tagged `setDebugMarker` for HQ fog (TEST/ORIGINAL) and print its already-available GPU timing with whole-frame timing at each existing bounded GPU sample, even if outside top-four. Capture label at GPU command-recording time to avoid reading the wrong menu state when deferred results arrive.

For reliable phone A/B: select **AO method = Original** for the entire comparison, keep camera/world/save and graphics settings fixed, then switch `Fog shadow clip: Original -> Test -> Original -> Test`. Give each stage enough frames for sparse GPU samples. Compare sampled fog pass times AND total GPU times and inspect fog graphics. Do not claim speedup without phone data.
