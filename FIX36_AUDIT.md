# FIX36 — indexed opaque landscape in the far shadow

## Scope

Clean FIX32 rendering base (FIX25 bindless batches, FIX28 Turnip autotune, FIX31
bounded diagnostics, FIX32 dependency stage projection). Original AO and original
fog; rejected/under-threshold FIX33–35 candidates are not active or compiled.
Qualified bundled Turnip Adreno 650 with bindless and native vertex path only.

Only opaque bindless Landscape commands in Shadow1 can use the candidate.
Static/movable objects, characters, morphs, alpha-tested leaves, particles, near
shadows, HiZ and GBuffer remain on their original geometry path. Landscape here
means the game's world mesh, not only ground. No view/culling/shadow resolution,
projection, material, winding or visible-triangle simplification is introduced.

## Data / ABI

Original path presents 192 sequential triangle corners per meshlet to the vertex
shader, then manually pulls local vertex indices. Candidate expands the SAME
visible meshlet payload to uint32 indices `relativePayloadSlot*64+localVertex`.
An indexed vertex shader decodes slot/vertex and calls the unchanged vertex
pulling/transformation/projection functions. Shared local vertices can thus share
an input vertex index. GPU vertex reuse and timing gains remain implementation-
dependent; no 3x performance claim is made.

One 64-thread group per visible meshlet writes its 64 triangles. Last-word
metadata decodes real primitive count exactly like original processMeshlet.
Unused triangle slots become degenerate (local vertex zero repeated), producing
no depth fragments. Real triangle corner order is unchanged. A setup dispatch
produces a 32-byte record: VkDrawIndexedIndirectCommand at offset0 (20 bytes),
VkDispatchIndirectCommand at offset20 (12 bytes). firstInstance/vertexOffset are
zero; drawCount=1. No multiDrawIndirect or drawIndirectFirstInstance feature is
needed. This retains one draw per existing eligible batch, not CPU per-meshlet
submission. Index generation itself is additional GPU work and bandwidth.

New generic Encoder/API indexed-indirect entry defaults to UnsupportedExtension
on other backends. Vulkan registers index reads as GraphicsRead (which includes
VERTEX_INPUT/INDEX_READ), argument reads as Indirect, and uses the existing
resource tracker/chunk barrier mechanism. Existing SSBO creation already includes
INDEX_BUFFER usage; allocator policy unchanged. Private loader adds exactly one
prefixed core symbol, vkCmdDrawIndexedIndirect (108 wrappers instead of107).

## Bounds / fallback

Per-batch current index allocation <=32MiB and device maxStorageBufferRange;
aggregate candidate index bytes <=64MiB. Fixed-size records add 32 bytes/batch.
At most43690 meshlet slots/batch; arithmetic and positive signed gl_VertexIndex
range bounded. Oversized/non-bindless/non-landscape/nonopaque batches stay
original. OutOfHost/VideoMemory and bad_alloc disable this world's experiment;
other errors propagate. Old buffers retire via Resources::recycle. Temporary
retired allocations may coexist until fences complete; cap is not total app RAM.
CPU preparation snapshots the mode once; both GPU preparation and draw use it.

## Measurement

Eight counterbalanced pairs, requiring >5% median whole far-shadow-region gain,
>1% median whole GPU-frame gain and >=6/8 wins for both. Region begins before
closing the prior pass, includes BOTH GPU preparation dispatches, barriers,
far shadow setup, all solid/alpha/particle work and pass closure. Explicit end
marker excludes subsequent lighting. Unrelated work in the full frame still
contributes to its regression guard. Missing/nested/duplicate/malformed regions
are rejected; incomplete samples select original; choice freezes per process.
No CPU readback of visible commands and no new GPU completion wait added.
At most24 sparse timestamped samples. ABBA does not eliminate scene/thermal or
Turnip autotune bias; phone tests must keep camera/settings stable initially.

## Validation

- Fresh patch application to pristine pinned source files.
- 2,304,000 checks executing actual index codec: 0..64 triangles, randomized
  local vertices/payload slots, winding/order, degenerate tails, shared indices
  and distinct transforms across slots; 20/32-byte argument ABI and bounds.
- Actual new Vulkan method executed with mocks: index/indirect tracking precedes
  bind/draw; UINT32, offset, drawCount1 and stride0 validated.
- Actual paired-controller tests: complete region aggregation, whole-frame gate,
  ABBA, paired wins, malformed/partial/unsupported fallback and frozen selection.
- Existing namespace/cache/fence/material/autotune/depth-layout/audit/stage tests.
- CI compiles/spirv-val checks both setup/build kernels and indexed vertex shader;
  builds/signs APK and verifies libraries, private exports and native build IDs.

CPU tests do not validate GPU rasterization, barriers on real hardware, driver
vertex reuse, image equality, stability or FPS. Phone validation pending.
Build/publication pending.

## Verified build

- Build/tag commit: `a82ebe3990defc88a6e818bbac019b139d2a2d6b`.
- Actions run `41004158039`, job `123895128619`: success.
- Host regressions, 2,304,000 codec checks, actual Vulkan forwarding mocks and
  whole-region/frame selection checks passed. Both compute shaders and indexed
  vertex SPIR-V compiled and passed spirv-val. Native APK build, private exports
  (including opengothic_vkCmdDrawIndexedIndirect), symbol Build ID and signing
  checks passed.
- APK: 22,733,687 bytes; SHA-256
  `d0d4a3bfa32a37c3a4ef200cf7f5239afe266443a6df5492e340ddf0758b17c3`.
- Signer SHA-256:
  `18bff2093896acea815c4fbfc342f72a694fd91d46b4ece5ab3e8e86e13ff611`.
- Release: https://github.com/Erken22/Gothic-Open-Android/releases/tag/exact-067-fix36

Phone path eligibility, rasterization, motion/shadow stability and FPS unverified.

## Phone result — no material whole-frame gain, 2026-10-30

Log `logcat_recording_2026-10-30_09-54-16.zip`, FIX36 confirmed. Candidate is
eligible and executed: one batch, capacity8504 meshlets, 6,531,072 index bytes.
Command sample2 shows two preparation dispatches and the indexed draw path's
existing ten solid indirect batches (one eligible landscape replacement).
Indirect dispatch group count is not available from this CPU command audit.

All8 medians: complete shadow region original10.388255 ms, indexed10.313333 ms
(0.074922 ms / 0.7212% less time). Whole GPU frame42.801457 vs42.7909885 ms
(0.0104685 ms / 0.02446% less time). Shadow pair wins7/8, frame pair wins3/8.
Selector correctly retained original; neither median threshold nor frame wins met.

Scene/workload changes in pairs7–8 (~35–39-ms frames instead of~43). First6
stable-region medians: shadow10.3894265 vs10.3174995 ms (~0.6923% lower), frame
42.8459625 vs42.9052855 ms (indexed~0.059323 ms /0.1385% higher). This subset also
shows no useful GPU-frame improvement. Later25–29 FPS is not attributable to the
candidate: original was selected and scene changed.

No Fatal signal, FATAL EXCEPTION, VK_ERROR, GPU fault or OpenGothic ANR found.
No images supplied: pixel/shadow equivalence is still not established.
This experiment covers only opaque Landscape in the far shadow. It does not
measure the benefit of indexed rendering for all static/movable/animated draws.
No direct vertex invocation counters or isolated index-generation timing were
collected; cannot attribute the negligible net gain to a proven hardware cause.
Keep the prototype disabled; do not automatically expand its scope on this result.
