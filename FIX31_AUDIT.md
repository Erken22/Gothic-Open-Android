# FIX31 renderer diagnostics

FIX30 phone experiment rejected: original fog median 5.969349 ms vs candidate 6.5797135 ms (+10.225%), 0/8 wins; original retained. FIX31 restores FIX28 rendering unchanged.

Compiler executable statistics require qualified Turnip Adreno650, advertised extension, feature2 entry point, supported pipelineExecutableInfo bit, and no descriptor heap. Capture-statistics flags apply only to original SSAO/fog compute pipelines. Data are compile-time, not live counters. Query failures are logged and ignored; no feature is forced.

Four already-timestamped command buffers per process record commands, render pass attachment operations and broad stage barriers. Nominal bytes are width*height*format-size for LOAD/STORE, not measured DDR traffic (compression, tile behavior and caching unknown). Unsupported formats count separately. Indirect vertex/group counts are unknown and not guessed. No extra GPU timestamp queries, readbacks or synchronization. Output happens on sampled recording only and can perturb CPU timing. No FPS improvement claimed.

## Source review for the next structural change

- Main HDR scene attachments already use R11G11B10UF; do not claim a free RGBA32F-to-compact conversion win.
- Standard shadows already prefer sampled Depth16 where supported. Main depth prefers Depth32F. Device format log must confirm actual selection.
- `Renderer::draw` separates GBuffer, shadow maps, compute SSAO/fog, lighting, scene stash, water, transparency, reflections and final fog. SSAO reads neighboring pixels, so merging the whole chain into one local-read subpass is not a drop-in change.
- `stashSceneAux` copies color and depth before water; the scene snapshot is also sampled by Ghost/translucent material paths. Skipping it on a simplistic no-water test can corrupt unrelated effects.
- Water clears the GBuffer attachments for later reflection/underwater uses. Preserve those consumers when considering render-pass consolidation.
- Audit rows follow the current command marker at record time. Setup before the next marker belongs to the preceding row, so row timings/counts must not be interpreted as complete logical-pass boundaries without reading the call order. Counts are command-buffer totals for the four samples, not aggregate process/device counters.

## Verified release

Run 40954679922, job 123731573681 succeeded. Exact build/tag source: 33f75b1c7d3def810ea32fd22c2bca75fad3c58e. APK size 22709111 bytes; SHA256 ce693164c3e245261078e7ec53b0bb77240bb1a18f7834d79b11e10e06846193. Certificate SHA256 unchanged: 18bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611.

Host tests passed, including ASan/UBSan bounds checks on real query/report helpers, query errors/incomplete enumeration, all statistic formats, nominal attachment arithmetic and atomic four-sample budget. CI Android ARM64 build, signature/private Vulkan packaging and native Build-ID checks passed. Phone diagnostics and feature availability remain unverified. This is a diagnostic build, with no new FPS gain claimed.

APK: https://github.com/Erken22/Gothic-Open-Android/releases/download/exact-067-fix31/GothicLauncher-arm64-OpenGothic067-FIX31-TURNIP.apk

Record logcat before application startup to include compiler statistics, then 45–60 seconds in the same saved scene/settings. Inspect `FIX31 renderer audit`, `FIX31 compiler`, `FIX31 stat`, `FIX31 command-audit`, `FIX31 pass`, and existing GPU/frame timings. Compiler capability=0 or query errors must be reported as unavailable, not interpreted as zero registers/instructions. Do not infer physical memory bandwidth or live shader utilization from these metrics.
