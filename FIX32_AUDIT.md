# FIX32 shader access barrier stage projection

FIX31 phone log 2026-10-30 02:22:46: median FPS 23.646974; GPU 43.0816655 ms, SSAO 8.3231505 ms, fog 5.981250 ms. Four identical sampled command structures: 13 render passes, 104 draw calls (60 indirect), 24 dispatches, 38 barriers, 16 using broad graphics stage masks. Nominal attachment load+store volume 159998528 bytes, not physical DDR traffic. SSAO compiler reports 16 registers, zero STP/LDP; fog five registers. This does not prove actual live cache/memory/ALU bottlenecks.

For qualified Turnip Adreno650 only, GraphicsRead/Write stage projections retain all logical-device enabled graphics shader stages; read also covers vertex/index input. They stop including color output, early/late depth tests and draw-indirect by default; those accesses remain covered by their existing dedicated SyncStage flags. All access masks, barrier count/generation, resource dependence tracking, layouts, shader source, formats, quality and resolution remain unchanged.

Actual enabled feature structures are used, not public engine props, which hide Qualcomm geometry/tessellation. Task/mesh are included when enabled. Non-target devices retain original ALL_GRAPHICS defaults. No changes to cross-command-buffer lifetime or existing fence fix. Timing benefit unknown until controlled phone comparison. Bounded diagnostics retained.
