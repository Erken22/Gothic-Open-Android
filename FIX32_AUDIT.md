# FIX32 shader access barrier stage projection

FIX31 phone log 2026-10-30 02:22:46: median FPS 23.646974; GPU 43.0816655 ms, SSAO 8.3231505 ms, fog 5.981250 ms. Four identical sampled command structures: 13 render passes, 104 draw calls (60 indirect), 24 dispatches, 38 barriers, 16 using broad graphics stage masks. Nominal attachment load+store volume 159998528 bytes, not physical DDR traffic. SSAO compiler reports 16 registers, zero STP/LDP; fog five registers. This does not prove actual live cache/memory/ALU bottlenecks.

For qualified Turnip Adreno650 only, GraphicsRead/Write stage projections retain all logical-device enabled graphics shader stages; read also covers vertex/index input. They stop including color output, early/late depth tests and draw-indirect by default; those accesses remain covered by their existing dedicated SyncStage flags. All access masks, barrier count/generation, resource dependence tracking, layouts, shader source, formats, quality and resolution remain unchanged.

Actual enabled feature structures are used, not public engine props, which hide Qualcomm geometry/tessellation. Task/mesh are included when enabled. Non-target devices retain original ALL_GRAPHICS defaults. No changes to cross-command-buffer lifetime or existing fence fix. Timing benefit unknown until controlled phone comparison. Bounded diagnostics retained.

Validation uses the real patched toStage function over all 4096 SyncStage bit patterns, 16 shader feature combinations, source/destination and acceleration-structure modes. Memory access masks are compared against the original mapping for every case. Non-target stage/access behavior is identical. Dedicated color, depth, indirect, compute, host and transfer stage mappings are explicitly checked. Existing fence lifetime/concurrency, private Vulkan dispatch/cache, material capability, loader policy, depth layout and diagnostic tests passed locally.

Sparse existing BOTTOM_OF_PIPE timestamps and record-time diagnostic logging can perturb measured frames; compare both aggregate FPS and the same sparse GPU metrics against FIX31. A lower broad-stage counter alone is not evidence of an FPS improvement. Compiler statistics remain compile-time data, not live utilization.

## Verified release

Run 40958980031, job 123746453389 succeeded. Exact build/tag commit 973b66b4ae8a4635e89bd9005573ffc9f6d5c793. APK size 22709111 bytes, SHA256 a7eedfad0ecbbd06432f72d0fa4c52ca1db0dbf2d452d4534a6edccf148516c2. Same certificate SHA256 18bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611.

CI tests, full Android ARM64 build, APK signature/private ABI checks and native Build-ID matching passed. Device graphics/performance not yet tested. Startup marker `FIX32 shader barriers` reports enabled masks. Verify both GPU/frame timings and visual correctness on phone; lower broad-barrier counts alone are not a speedup.

APK: https://github.com/Erken22/Gothic-Open-Android/releases/download/exact-067-fix32/GothicLauncher-arm64-OpenGothic067-FIX32-TURNIP.apk
