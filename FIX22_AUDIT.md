# FIX22: New Game ANR diagnostics

## Evidence

The supplied ANR at 2026-10-29 06:36:17 +0500 belongs to
`org.opengothic.launcher:game`, PID 23116, exact FIX21 engine Build ID
`124d1bdb9f8761183346afa95e6ad2b9f265a482`.

The native game thread 23146 sleeps in libc poll, called from bundled
`libvulkan_freedreno.so+0x9ea17c`, Build ID
`c9437d802197d6203c97d3cb8b399c849bbc7324`.
The driver frame does not unwind to the engine. The load worker 23203
and material worker 23210 are no longer present in the thread list.
The Java main thread is idle in its event loop. The log does not establish
which Vulkan entry point called this driver wait, nor prove a GPU fault,
CPU deadlock, or memory exhaustion.

Disassembly at the driver PC shows a poll over a vector of sync FDs with
an infinite-capable timeout. This fits the driver's KGSL synchronization
wait-any implementation. It is evidence of a synchronization wait, not a
reason to lower rendering quality or disable HiZ without further evidence.

## Change

This is a diagnostic build, not a claimed ANR fix.

- Trace Vulkan calls pending for at least 3 seconds, repeating every 5
  seconds, from an independent thread. Include native TID, engine caller
  module/offset, elapsed time, and timeout/count details where applicable.
- Cover acquire, fence waits, device/queue idle, submit, present, and
  graphics/compute pipeline compilation. Cover dynamically resolved
  QueueSubmit2 and QueueSubmit2KHR through GetDeviceProcAddr as well.
- Emit completion when an already reported call returns.
- Delimit world load worker completion, main-thread finalization,
  device.waitIdle and renderer reset.
- Publish an exact, Build-ID-checked native function map with the APK so
  observed engine addresses can be mapped to functions.

Retain FIX20 private Vulkan ABI, shared C++ runtime, FIX21 VSM startup
selection, Turnip, full HiZ, ordinary shadows, resolution, SSAO and fog.
Do not change synchronization, Vulkan timeouts or success/error results.
The watchdog never calls the graphics API. Diagnostics use a fixed-size
64-entry registry; short calls produce no logging.

## Validation

- All source replacements apply to exact OpenGothic/Tempest commits.
- Host ELF regression reproduces the original public Vulkan SONAME
  collision and verifies that the private proxy still loads/binds.
- A concurrent watchdog test verifies a >3s call reports its metadata,
  emits completion on return, and does not log a concurrent short call.
- CI builds ARM64, checks APK signature/linkage/build markers, and verifies
  unstripped native symbols have the packaged engine's Build ID.
- No Android device reproduction or confirmed black-screen repair yet.

## Published build

- Source commit: `34aa4b0742a7bec3125262e8605d7a041ab35dcd`.
- Successful CI run: https://github.com/Erken22/Gothic-Open-Android/actions/runs/40804485091
- APK: `GothicLauncher-arm64-OpenGothic067-FIX22-TURNIP.apk`, 22,692,727 bytes.
- SHA256: `7cab03ba7dc9d25293cca06005892a39645b64e0719e83d588f9deb9c9469a0d`.
- Signature certificate matches FIX20/FIX21; private ABI and watchdog marker verified.
- Exact native map Build ID matched the packaged engine in CI and is attached to the release.
- Additional host forwarding check: both QueueSubmit2 spellings preserve arguments and VkResult; unsupported entry points remain null; registry clears after return.
- GitHub release uses the inherited default target `main`; use the immutable source commit and workflow above for source provenance, rather than inferring it from the release tag.
