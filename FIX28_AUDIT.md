# FIX28 measured Turnip selection

Base FIX27 audit ba7458f40e865e4de72af13e25ef1de72865efea; exact upstream engine18336539f4b1a8d7b325930f613811f59fbde5db.

FIX27 device log15-16-05: opaque vertex-only path active,24 bindless batches, shadows1024/fog64x32x32. Initial stable FPS19.6–19.7; later20–24. Far shadow total~19.1ms splits into setup~9.6/solid~5.45/alpha~4.02. Timestamp interval includes deferred rendering/transition work; it does NOT prove9.6ms is CPU preparation, a particular barrier or just clearing. No useful gain from removing empty fragment stage established.

Use FIX25 material/SSAO paths, retain complete FIX27 shadow subpass metrics. Remove empty-fragment experiment and its obsolete host test. Before loading bundled Turnip, set TU_AUTOTUNE_ALGO=profiled and TU_AUTOTUNE_FLAGS=tune_small unless externally overridden. Append startup-only diagnostics to existing TU_DEBUG; preserve original values for custom-driver load failure. No change when AdrenoTools is unavailable. System fallback ignores no newly inherited defaults after failure. Cached dispatch and private ABI retained.

Mesa official documentation https://docs.mesa3d.org/drivers/freedreno.html describes default bandwidth estimation, measured profiled mode and tune_small for few-draw passes. Bundled26.3.0-R6 binary contains autotune configuration keys/tune_small. Bindless batching creates few heavy draws; testing measured selection is a hypothesis, not a proven cause/fix. Continuous measured tuning can add overhead/FPS variance and is not guaranteed faster. Phone log must confirm driver-recognized algorithm/flags and compare same save/camera/settings against FIX25.

Align toLayout(DepthAttach) from DEPTH_ATTACHMENT_OPTIMAL to DEPTH_STENCIL_ATTACHMENT_OPTIMAL, matching beginRendering's actual attachment imageLayout. Keep existing image aspects, read-only layouts, stage/access masks and all barriers. No synchronization removed. No rendering quality, resolution, shadow range/update frequency, AO sample count or fog changes.

Host tests execute generated loader with mocked dlopen/dlsym to check policy before custom-driver open, existing overrides, fallback restoration and missing-AdrenoTools path. Real extracted layout mapper checked for depth16/depth32/depth-stencil and unchanged color/storage/transfer/presentation. Fresh source applies; namespace, cached dispatch, frame metrics, targeted fence concurrency and material gating regressions pass. Native device results pending.

Build and publication verified below; phone results pending.

## Published verification

Source/tag4956dec1800ed52f05e89d17730e6f3ad46cda9a; Actions run40857748491 job123392895334 succeeded. All host tests, full ARM64 build, signature/private ABI and packaged/native symbol Build-ID equality checks passed. Loader autotune marker is present in packaged proxy. Release exact-067-fix28 targets exact source. APK22700919bytes, SHA2564d240e37666f6f3ca80792ec590a8ef2046419ac4e9e3207c8ed7befdaa67959; GitHub asset digest matches CI checksum. Certificate SHA25618bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611. Symbols archive also published.

The layout alignment is a consistency change, not an established performance cause: the Vulkan specification describes the layouts as equivalent for their corresponding aspects with appropriate support (https://docs.vulkan.org/spec/latest/chapters/resources.html). No claim that this alone fixes performance or a proven validation fault. Actual driver algorithm activation, learned mode choices, startup/resume stability, image quality and FPS remain unverified until phone feedback. Request90–120sec same save/fixed camera/settings to observe learning and later behavior. Do not claim guaranteed acceleration from build success.
