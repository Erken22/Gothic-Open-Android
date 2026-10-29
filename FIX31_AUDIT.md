# FIX31 renderer diagnostics

FIX30 phone experiment rejected: original fog median 5.969349 ms vs candidate 6.5797135 ms (+10.225%), 0/8 wins; original retained. FIX31 restores FIX28 rendering unchanged.

Compiler executable statistics require qualified Turnip Adreno650, advertised extension, feature2 entry point, supported pipelineExecutableInfo bit, and no descriptor heap. Capture-statistics flags apply only to original SSAO/fog compute pipelines. Data are compile-time, not live counters. Query failures are logged and ignored; no feature is forced.

Four already-timestamped command buffers per process record commands, render pass attachment operations and broad stage barriers. Nominal bytes are width*height*format-size for LOAD/STORE, not measured DDR traffic (compression, tile behavior and caching unknown). Unsupported formats count separately. Indirect vertex/group counts are unknown and not guessed. No extra GPU timestamp queries, readbacks or synchronization. Output happens on sampled recording only and can perturb CPU timing. No FPS improvement claimed.
