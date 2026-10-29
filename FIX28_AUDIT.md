# FIX28 measured Turnip selection

Base FIX27 audit ba7458f40e865e4de72af13e25ef1de72865efea; exact upstream engine18336539f4b1a8d7b325930f613811f59fbde5db.

FIX27 device log15-16-05: opaque vertex-only path active,24 bindless batches, shadows1024/fog64x32x32. Initial stable FPS19.6–19.7; later20–24. Far shadow total~19.1ms splits into setup~9.6/solid~5.45/alpha~4.02. Timestamp interval includes deferred rendering/transition work; it does NOT prove9.6ms is CPU preparation, a particular barrier or just clearing. No useful gain from removing empty fragment stage established.

Use FIX25 material/SSAO paths, retain complete FIX27 shadow subpass metrics. Remove empty-fragment experiment and its obsolete host test. Before loading bundled Turnip, set TU_AUTOTUNE_ALGO=profiled and TU_AUTOTUNE_FLAGS=tune_small unless externally overridden. Append startup-only diagnostics to existing TU_DEBUG; preserve original values for custom-driver load failure. No change when AdrenoTools is unavailable. System fallback ignores no newly inherited defaults after failure. Cached dispatch and private ABI retained.

Mesa official documentation https://docs.mesa3d.org/drivers/freedreno.html describes default bandwidth estimation, measured profiled mode and tune_small for few-draw passes. Bundled26.3.0-R6 binary contains autotune configuration keys/tune_small. Bindless batching creates few heavy draws; testing measured selection is a hypothesis, not a proven cause/fix. Continuous measured tuning can add overhead/FPS variance and is not guaranteed faster. Phone log must confirm driver-recognized algorithm/flags and compare same save/camera/settings against FIX25.

Correct toLayout(DepthAttach) from DEPTH_ATTACHMENT_OPTIMAL to DEPTH_STENCIL_ATTACHMENT_OPTIMAL, matching beginRendering's actual attachment imageLayout. Keep existing image aspects, read-only layouts, stage/access masks and all barriers. No synchronization removed. No rendering quality, resolution, shadow range/update frequency, AO sample count or fog changes.

Host tests execute generated loader with mocked dlopen/dlsym to check policy before custom-driver open, existing overrides, fallback restoration and missing-AdrenoTools path. Real extracted layout mapper checked for depth16/depth32/depth-stencil and unchanged color/storage/transfer/presentation. Fresh source applies; namespace, cached dispatch, frame metrics, targeted fence concurrency and material gating regressions pass. Native device results pending.

Build/publication pending.
