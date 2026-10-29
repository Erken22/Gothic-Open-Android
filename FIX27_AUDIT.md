# FIX27 opaque ordinary shadow depth

Base FIX25 audit 999a0b15be54b4d987a1f1c09d9c7877772c396b; upstream engine18336539f4b1a8d7b325930f613811f59fbde5db. FIX26 SSAO rotation experiment omitted entirely by using FIX25 source.

Controlled user logs25logcat_recording_2026-10-29_11-05-33.zip and26logcat_recording_2026-10-29_11-06-48.zip: shadows1024, fog64x32x32, bindless24 batches both. MeanFPS20.207 vs20.235, median SSAO6.839583 vs6.847031ms, median ShadowMap#1 19.6730205 vs19.703411ms; no meaningful improvement/regression established. Dominant shadow pass deserves isolated investigation.

FIX27: in the existing non-particle vertex-pipeline branch, bundled Turnip Adreno650 + Material::Solid + T_Shadow uses original vertex shader with empty Tempest Shader() fragment argument. Same RenderState, depth Greater/write, culling, geometry, deformation, update cadence, range and selected resolution. AlphaTest, PFX, main, HiZ, VSM and other devices retain fragment stages. Tempest Device::implPipeline passes null shader handles through; Vulkan VPipeline skips null modules/stages and retains rasterization. This is an optimization experiment; Turnip may already optimize empty fragments, so no FPS gain is assumed.

CI compiles/disassembles ordinary solid depth fragments for landscape/object and requires no stores/discard/atomics/image writes/depth override; alpha-tested baseline must retain OpKill. No shader source modification is needed. Real patched pipeline-creation branch is exercised with device recorders over target/non-target, alpha modes, pass modes and five mesh types: only eligible shadows omit FS, same vertex source/state and other fragment paths preserved.

Android shadow markers split ordinary maps into setup, solid, alpha and particles. CPU generated metrics header aggregates complete per-layer total and subpasses before top-four sorting, avoiding loss of smaller subpasses. Existing fence-ready timestamp reads and24 sparse sample budget unchanged. No new GPU waits. Host metrics test checks sums/partition/top-four alongside cadence and units. Namespace, cached dispatch, targeted fence lifetime and material selection regressions pass. Fresh exact-source anchors apply.

Keep prior launch, C++ runtime, private Vulkan ABI, targeted fence, full Turnip HiZ, capability-guarded bindless and VSM/RTSM/mobile-stage guards.

Build/publication and device validation pending.

## Runner allocation blocker

Run40828052739 build source7d758ce8f3013fe288e63af82674301a0f76b3d1 failed before executing steps. Attempt1 job123295552636: runner_id0, steps[], created06:14:49Z/completed06:14:52Z. Retried once through failed-jobs rerun; attempt2 job123361905192 also runner_id0, steps[], created09:17:53Z/completed09:17:56Z. There is no compiler/test result from either run. Job-log download returns404 BlobNotFound. GitHub connector does not expose check-run annotations; browser is signed out and shows404 for this private run. Exact allocation rejection reason is unknown; do not assert a billing/quota issue without annotation evidence. No FIX27 APK was produced. User can inspect the run annotation in their GitHub account; all source and host tests are preserved.

## Successful publication

User screenshot identified the earlier pre-run rejection as failed recent account payments or spending limit; no compile error was involved. After user requested another attempt, rerun attempt3 of40828052739, job123380601154, succeeded for exact source7d758ce8f3013fe288e63af82674301a0f76b3d1. All host checks, original empty solid-fragment/retained alpha-discard SPIR-V validation, ARM64 compilation, signature, private ABI and packaged/native Build-ID equality checks passed. Packaged engine contains FIX27 opaque-depth policy and shadow aggregate markers.

Release exact-067-fix27 targets exact build7d758ce8f3013fe288e63af82674301a0f76b3d1. APK22696823bytes, SHA256aeeb1ec057979af1d6a911f04c93f55cad59a4a8afaec895aa1e3c6b92fbe0e4; release asset digest matches build checksum. Certificate SHA25618bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611 (same as prior builds). Symbols archive published alongside APK. Device rendering, startup/resume and actual FPS improvement remain unverified until phone feedback. No performance gain is claimed from CI success.
