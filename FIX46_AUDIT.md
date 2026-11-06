# FIX46: complete upstream CACAO Vulkan integration

Baseline: FIX45 build 7f8115011b3031faae435f4cf8c8567bc3e51fa4, exact OpenGothic 0.6.7 and its pinned Tempest. Other-chat physics/new-upstream work is not merged.

## Implementation

Official FidelityFX-CACAO pinned to 0ddca95e6714727a252ead345591ca8f2598f261. Use its complete Vulkan backend, depth preparation/mips, AO generation, edge-aware blur and bilateral upscale. Generate 33 real FP32 SPIR-V modules with Microsoft DXC v1.8.2407; compiler archive SHA256 b58725ac191df0686994fb9d54d27ee8dd3f180b023d562733112a499ea1195c. No native FP16 feature is requested. The two upstream shader lookup tables both reference FP32 binaries; initialization flags are always zero.

Narrow upstream compatibility edits: express dynamic integer Load offsets as coordinate addition for current DXC; five input depth descriptors use DEPTH_STENCIL_READ_ONLY_OPTIMAL to match Tempest; signed upscale halo coordinates, bit parity and clamped raw border loads prevent left/top uint underflow; include the same Vulkan SDK handle declarations as the engine. Preserve upstream notices and package CACAO_LICENSE.txt. No independent replacement AO formula.

Each fenced VCommandBuffer owns its own lazy CACAO context, descriptor sets, constant buffers and scratch images. No shared in-flight scratch/UBO writes. Recreate size-dependent resources when input/output views, dimensions or downsample mode change. Initialization errors disable candidate and retain original. All external Vulkan calls inherit the private prefixed namespace; no direct libvulkan dependency is allowed.

Tempest Encoder exposes a narrow optional AO command with default false for other backends. End any render pass, register input depth read/output storage write with ResourceState, flush dependencies, call upstream, restore final AO from shader-read layout to GENERAL, reconcile tracker and invalidate encoder/backend pipeline/binding/push caches. No new queue/device waits, fences or GPU query readbacks in production.

Query and enable shaderStorageImageExtendedFormats and shaderImageGatherExtended only if supported; gate candidate on those enabled features, compute limits and required sampled/storage/filterable image formats. Target remains bundled Turnip Adreno 650; other paths use original. Candidate contexts use FP32 code although official working depth uses R16F. Convert Gothic centimetres to metres through the depth-unpack projection numerator; radius=1m, fade 500–1000m. Symmetric perspective only, nonfinite/nonstandard/morphed projection falls back to original for the process. HIGH quality, two edge-aware blur passes, depth-derived normals, no temporal jitter/history.

Half-res SSAO On selects CACAO downsampled path: four quarter-width/quarter-height working slices, approximately the same quarter pixel budget as original half-width/half-height AO (rounding differs for odd dimensions). Off selects native CACAO. Input depth and final R8 AO retain the internal render dimensions. Lighting uses the final upstream output directly; original producer/resolve are skipped only when CACAO actually recorded successfully. This is a different AO algorithm; same nominal radius does not prove identical image quality.

## Controls and acceptance

Replace failed SAO menu option with **AO method: Original | CACAO test | Compare**, new aoMethod46 setting default Compare. Old aoMethod39 is forced to Original, avoiding a saved slow SAO choice. Bounded eight-pair ABBA Compare measures the WHOLE original producer+resolve versus WHOLE CACAO chain, plus full sampled GPU frame. Existing sparse sampling/readback only. After comparison always Original, including when >5% chain and >1% frame median gains and >=6/8 paired wins pass. Logs report performance separately from visual approval. Choose CACAO test manually for image comparison. Unsupported candidate aborts comparison and uses Original until restart. No automatic visual acceptance or promised FPS gain.

## Verification

Actual official constants executed under UBSan: centimetres/metres depth reconstruction at multiple distances and far plane, odd/even buffer sizes. Actual new ABBA controller tested for order, completion, partial fallback and Original even on performance pass. All 33 FP32 modules inspected: no Float16, only Shader, Image1D, Sampled1D, StorageImageExtendedFormats and ImageGatherExtended; max workgroup 256. Host C++ syntax checks pass for Vulkan bridge, encoder and upstream backend. CI additionally spirv-val all modules, compile/sign Android ARM64, validate package/private Vulkan/C++ linkage, license asset and exact native symbols.

CI build, runtime image checks and phone performance pending at initial commit. A successful build cannot establish phone speed or pixel quality.

## Phone test

Use same save/camera and graphics settings, Fog shadow clip Original. Leave default Compare, stand still for 60 seconds after loading and send logcat; do not cycle graphics settings during timing. Restart process to repeat. Then select Original and CACAO test at the same camera for screenshots of corners, stairs, foliage/fences and thin geometry; also inspect motion. Report any crash, black frame or resize/resume issue. This experimental APK does not establish stable 30 FPS.

## Full Vulkan correctness tests and border fix

The complete FP32 chain ran locally on Mesa llvmpipe (LLVM 19.1.7), with exactly the requested storage-image-extended/gather-extended device features. SwiftShader lacked the required capabilities and was not used as validation. Software Vulkan timings are not Adreno benchmarks.

Initial strict flat-plane test failed: first four left columns darkened (minimum 214/255, mean 254.366) while the interior was 255. Traced upstream unsigned halo coordinates subtracting 2 and negative remainder/array layer handling. Fixed signed halo coordinates, explicit bit parity and clamped raw depth/AO/guide loads. Kept the strict original flat-plane assertion; no test threshold was relaxed.

Final complete-chain cases, HIGH quality and depth-derived normals:
- 128x128 downsampled: sky 255 everywhere, flat 255 everywhere, contact case minimum 185, mean 246.806.
- 129x131 downsampled: sky and flat 255 everywhere, contact minimum 126, mean 240.478.
- 129x131 native: sky and flat 255 everywhere, contact minimum 132, mean 245.530.

All cases pass; CI runs the same headless Vulkan test in addition to unit/SPIR-V/native checks. Contact numbers are synthetic functional responses, not image equivalence to original SSAO or phone visual validation. Updated Android build pending.
