# FIX41: zipped VDF compatibility only

Based on OpenGothic 0.6.7 FIX40T; shader performance, shadow algorithms, AO and viewport are unchanged.

## Phone evidence
The phone run log `logcat_recording_2026-10-30_17-11-42.txt` contains exactly two errors:
- `Data/Union.vdf` — Detected compressed VDF (build ZenKit with ZK_ENABLE_ZIPPED_VDF=ON to enable support)
- `Data/Plugins/zGamePad.vdf` — the same error.

Also in FIX40T: 16 GPU samples, all `Fog-sunshaft-occlusion ORIGINAL`, median 5.9803385 ms, GPU whole-frame median 42.827291 ms. 8 FPS summaries median 23.4781645. AO logged as requested=0/effective=0 (original). No SIGSEGV, fatal Java exception or Vulkan device loss in this recording.

## Change
Set `ZK_ENABLE_ZIPPED_VDF ON CACHE INTERNAL` before `add_subdirectory(lib/ZenKit)`. This directs ZenKit to include its existing Union ZippedStream decompressor and link required `miniz` and `squish`. The original error is caused by a build option, not corrupted assets.

This does NOT imply that Union or zGamePad plugins themselves are executable inside OpenGothic, nor does it promise any FPS improvement. Verify archives are opened, not just recognized, in follow-up log.

## Fog evaluation
Original mode was the only one used in this log; no TEST measurements, so no justified performance claim about FIX40 fog shortcut. Keep AO=Original in A/B mode switching.
