# FIX40 — conservative outside-map fog shadow shortcut

## Baseline
OpenGothic 0.6.7 pinned to `18336539f4b1a8d7b325930f613811f59fbde5db`, Tempest pinned by upstream, FIX39 Turnip / Vulkan proxy / signing. FIX39 phone measurements found 32-tap spatial SAO slower: original AO 8.29 ms, SAO ~10.73 ms. The comparison mode is no longer selected by default; saved Compare=2 is interpreted as Original and the menu offers only manual SAO test.

## Candidate
Only HQ ordinary-shadow `fog3d.comp` shader, bundled Turnip Adreno 650 eligibility. The original shader and its 32 shadow samples, depth, noise, fog apply, resolution, render scale, shadow maps and alpha testing are retained. The extra compute variant `fog3d_cull40.comp` conservatively skips the entire loop when an affine shadow ray is provably beyond one homogeneous shadow-map clip half-space for *all* 32 taps.

The noise comes from `fract`, so t belongs to [0,65/64). Test both endpoint positions at 0 and 65/64 against each of x>w, -x>w, y>w, -y>w with 0.1% w-based positive guard margin. Each inequality is affine in t, so if both endpoints satisfy one out-of-map inequality, the original `shadowFactor` returns true for all taps; the R32UI mask is exactly `0xFFFFFFFFu`. In all other pixels, run the unchanged original loop. Cannot claim benefit when the scene's fog rays mostly remain inside the shadow map. All tested paths leave ordinary fog application unchanged.

## Controls
Video setting `Fog shadow clip: Original|Test`. Fresh defaults test candidate; original remains one menu change away. For an existing user, setting `fogOutside40` may persist if previously added. `AO method` default Original. Only Android and qualified Turnip enable candidate; other drivers keep original.

## Acceptance
Compare same save, camera pose, settings, AO=Original, Half-res fog unchanged, and 60+ seconds each of Original/Test (ABBA sequence preferred). Inspect fog shafts, map edges, night/day and movement. Compare median whole-GPU-frame and `Fog-sunshaft-occlusion` GPU timestamps, not average FPS alone. This build **does not automatically choose a faster variant** and does not establish performance or pixel equivalence without device testing.

## Verification
Host randomized test includes 150,000 rays and 96 sampled original clip checks per eligible case, including negative w and near-edge values. CI must run test, compile and spirv-val both shaders, compile/sign ARM64, validate Vulkan proxy, build IDs and signer. No compilation or phone performance claimed before CI completes.
