# FIX24: reduce Vulkan CPU overhead after confirmed FIX23 startup recovery

## Evidence and scope

The user confirms FIX23 now renders the world but reports very low FPS.
The supplied 08:13:06 log identifies FIX23, activates targeted native fence
completion, loads the world and logs full HiZ on Turnip Adreno 650.
No watchdog stall is recorded. The log has no engine frame/pass timing
measurements. MIUI's 50/60 Hz display changes are not game FPS readings.

The FIX23 proxy resolves each loader-level Vulkan function through dlsym
on every call, including per-draw and per-binding commands. It also retains
per-call watchdog registry locks and captures unwind stacks for native
fence waits. These are concrete sources of avoidable CPU overhead; their
share of the user's frame time is not yet measured.

## Change

- Use thread-safe function-local static pointers to bind each loader-level
  Vulkan entry point once. The chosen loader is already fixed for process
  lifetime by g_once and never unloaded.
- Preserve normal per-instance/per-device GetProcAddr queries and their
  results. Cache the loader routine, not results for individual devices.
- Remove the per-call watchdog, detached reporting thread, mutex registry,
  stack capture, and QueueSubmit2 observation trampoline.
- Retain private symbol namespace, shared C++ runtime, Turnip, FIX21 shader
  startup selection and the device-confirmed FIX23 targeted fence wait.
- Keep full HiZ, rendering resolution, shadow quality, SSAO, fog and HDR
  configuration unchanged.
- Log one CPU frame summary per two seconds of active world rendering.
  Separate pacing, simulation, UI/fence checks, command recording, submit
  and present/acquire. Include actual completed-frame rate and skipped count.
- Capture at most eight GPU timing samples, spaced by at least two seconds.
  Read the existing nonblocking query results only after the normal slot
  fence is ready. Report total and four largest pass intervals. Do not add
  a GPU wait for profiling, modify render passes, or write a per-frame CSV.

This reduces known proxy overhead. No numerical device FPS improvement or
remaining GPU/CPU bottleneck is claimed before runtime testing.

## Validation

- Exact source patch application passes.
- 80,000 calls from eight concurrent host threads perform exactly one
  loader lookup while preserving every command and argument.
- Per-device function queries still return different driver pointers and
  unsupported queries remain null.
- Private Vulkan ELF namespace/collision regression passes.
- FIX23 native wait tests, including timeout/resource lifetime and protection
  against concurrent fence recycling, pass unchanged.
- Deterministic frame summary math, timing units, skipped counts, report
  cadence, top-pass selection and bounded GPU sample budget pass.
- ARM64 CI verifies signature/linkage, new dispatch/frame markers, absence
  of old watchdog markers, and exact native symbol-map Build ID.

## Strict compiler correction

Initial CI run 40812011027 stopped in the new timing summary's partial_sort
iterator expression because the engine treats signedness conversions as
errors. Commit `fb7101908bc5e5d463f933a901508c556465d2b8` explicitly casts
the bounded top-four count to the container's difference_type. The host
frame metrics test now uses -Wall -Wextra -Wconversion -Wsign-conversion
-Werror and passes. Runtime rendering behavior is unaffected by this type
correction. Replacement build: https://github.com/Erken22/Gothic-Open-Android/actions/runs/40813636509
