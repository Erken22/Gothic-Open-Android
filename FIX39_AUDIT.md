# FIX39: spatial ambient obscurance prototype

## Purpose and scope
Exact OpenGothic 0.6.7 commit `18336539f4b1a8d7b325930f613811f59fbde5db`, its pinned Tempest, existing Android package/update signature, bundled Turnip and 107-wrapper private Vulkan proxy. Retained FIX32 rendering path. FIX33–38 optional experiments are absent, including FIX37 fusion and FIX38 lazy-bin initialization. Other chats' physics/new-upstream work is not merged.

FIX38 phone result: SSAO 8.274609 vs 8.268203 ms, only 3/8 wins: no useful speedup. Rather than another rearrangement of the same producer, FIX39 adds a separate **different AO formula**. Image equivalence, unchanged artistic appearance and a speedup are NOT claimed.

## Method
Independent SAO/Alchemy-style spatial obscurance kernel. Reference research: McGuire et al., *The Alchemy Screen-Space Ambient Obscurance Algorithm* and McGuire/Mara/Luebke, *Scalable Ambient Obscurance*; inspected Filament's `filament/src/materials/ssao/saoImpl.fs` as a primary implementation reference (https://github.com/google/filament/blob/main/filament/src/materials/ssao/saoImpl.fs). This is an independently implemented integration, not a full Filament SAO/CACAO/GTAO port. No Filament source blocks are copied.

At the same half resolution, select the unchanged nearest-depth representative of each 2x2 block and reconstruct its view-space point and normal using existing conventions. Use 32 deterministic spiral disk taps (7 turns, squared radial distribution), projected nominal radius 100 world units, one full-resolution-pixel minimum tap radius. Fetch depth at actual texel centers. Reject offscreen/sky taps and points beyond the world-space radius. Accumulate squared radial falloff times positive normal separation, with bias 1 world unit and peak regularization squared 100. Visibility is clamped `1 - (2*radius/32)*sum`.

No per-pixel 25-bin histogram, group convergence/barriers/atomics or tangent-frame hemisphere projection. Fixed 32 taps can be more work than the original adaptive path in some scenes. No depth mip hierarchy, deinterleaving, temporal accumulation or history is implemented in this first prototype. Existing RG32F AO/representative-linear-depth output and the existing full-resolution 3x3 edge-aware resolve remain unchanged. Lighting/fog/shadows/render scale are unchanged.

Old and new nominal radius values are both 100, but their sample distributions, estimators, bias and response differ. This is not a quality-preserving algebraic rewrite or a guarantee that 32 spatial taps match 32 old hemisphere samples. Noise, contact darkness, edge halos, thin geometry and motion require device comparison. Unsupported/full-resolution/pathtrace modes retain original producer.

## Controls and acceptance
Video settings adds **AO method: Original | SAO test | Compare**. Existing Half-res SSAO must be On. Nine rows retain their original 625 spacing; start y=1450, final row y=6450/end=7050, Back y=7350/end=8000, inside 8192 menu coordinates. Existing fonts/background and generic choicebox interaction are reused.

- Original: original producer.
- SAO test: explicit manual candidate selection, for image comparison; not automatic approval.
- Compare: eight ABBA original/SAO timing pairs, then **always original**, including when timing thresholds pass. Logs report performance separately from acceptance. New `aoMethod39` defaults to Compare in this experimental APK, so first game entry collects the comparison without editing files.

Only bundled Turnip Adreno 650 with RG32F storage and half-AO / non-pathtrace uses candidate. AO disabled keeps its original early return. Mode/candidate is captured once per producer invocation. Original shader and filter are unchanged byte-for-byte. Manual-mode tags are separate from comparison tags and do not contaminate paired observations. The test is bounded to the existing 24 sparse GPU samples, no new waits/readbacks. The first 16 samples are at 1-second spacing, then 10 seconds. Restart the process to repeat a completed comparison. Timings require >5% AO and >1% frame median reduction and >=6/8 wins each to report a performance pass; this does not approve quality or enable SAO permanently.

## Validation and limits
Local apply to pristine target files and existing Vulkan namespace/cache/autotune, targeted-fence, bindless/material policy, depth layout, command/compiler audit, shader-stage barrier mapping and frame-summary tests. Actual C++ comparison controller tests enforce original after completion even on a performance pass, ABBA order, frozen/partial fallback and invalid/mixed/duplicate sample rejection.

Actual scalar shader contribution/visibility functions compiled on CPU with UBSan: flat-plane/below-horizon/radius/coincident-point invariants, 64 perspective plane+wall cases and 100,000 finite/bounded random cases. Near contact averaged visibility 0.899759, minimum 0.700463; **10/64 noise rotations were near white** in this synthetic sparse point-sampling case. This explicitly exposes sampling variance; the existing spatial resolve may reduce it, but device pictures/motion must judge it. It is not a GPU image test or proof of comparable appearance. Normal reconstruction, old producer and shared upsampler hashes are checked; integration gates and menu coordinate bounds are checked.

CI must additionally compile/spirv-val both producers, build/sign ARM64 APK, verify private Vulkan/C++ linkage and package identity, and preserve exact native symbols. Phone FPS, pixel quality and UI rendering remain pending. A compiler-statistics improvement alone cannot validate the result.

## Phone check
Install over the preceding FPS build. Keep existing graphics settings and stay still for 30–60 seconds after loading the same location to collect default Compare. Send logcat. For visible comparison, change AO method between Original and SAO test at the same camera position and capture both screenshots; keep Half-res SSAO On. Inspect wall corners, steps, foliage/fences/thin objects and noise during movement. Compare returns to original automatically; select SAO test explicitly to view candidate after the timing run.
