# FIX23: targeted native fence waits on Turnip Adreno 650

## Observed FIX22 failure

The supplied 07:31:43 recording identifies FIX22. World construction and
main-thread finalization complete. Device idle returns in about 1 ms,
and renderer world reset completes at 07:32:02.039.
At approximately 07:32:02.178 the native game thread enters an infinite
`vkWaitForFences` call with four fences, from engine offset `0x18f8bb8`.
It remains pending at 3.764 and 8.767 seconds.

The exact FIX22 map, matched to engine Build ID
`c3371c03ee2d553a7af34007d2b2ed8aa45dd5c0`, resolves the call into
`VDevice::waitAny(unsigned long)` [0x18f8b10,0x18f8c98).
Symbol resolution run:
https://github.com/Erken22/Gothic-Open-Android/actions/runs/40807113635

This establishes the multi-fence waiting path, not a proven driver bug
or the particular upstream caller of waitFence. The log does not prove
that all four submitted GPU jobs are actually stalled. It does not
justify disabling HiZ, reducing shadows, or skipping intro videos.

## Change

For blocking `waitFence` calls on bundled Turnip Adreno 650, call native
`vkWaitForFences` with only the requested fence and waitAll=true.
The previous path waited on every outstanding timeline fence, then polled
all their statuses in a loop. Waiting for the specific requested fence
preserves the API contract and bypasses the observed multi-fence path.
This is a targeted workaround requiring confirmation on the user's phone.

- Zero-time polling is unchanged.
- Finite millisecond timeouts convert to nanoseconds as before.
- Infinite timeout remains infinite.
- Native timeout maps to VK_NOT_READY; it does not release GPU resources.
- Only confirmed completion marks the fence successful and clears payload.
- Driver errors propagate; no fabricated completion or bypassed waits.
- The existing timeline mutex protects the native fence against recycling.
- Fence-pool waitAny logic, system Qualcomm fallback, and other GPUs retain
  their original paths.
- Full HiZ, shadows, fog, SSAO and resolution are unchanged.

Retain FIX22 watchdog and add a bounded engine call stack captured before
native fence waits. The capture does not cross into the driver's incomplete
unwind information. It is logged only on waits exceeding 3 seconds.
Publish exact native symbols and set the release tag's source target explicitly.

## Validation

- Patch applies to the exact upstream OpenGothic/Tempest sources.
- Deterministic native stub tests execute the actual patched waitFence body:
  exact target handle/count, waitAll, finite/infinite timeout, zero-time poll,
  native timeout, native error, resource payload retention, null/completed
  fences, and unchanged fallback/system/other-GPU behavior.
- Private Vulkan ELF loading regression passes.
- Concurrent watchdog test passes, including stack capture.
- ARM64 CI checks APK signature, private imports/exports, build markers,
  watchdog markers and native-map Build ID.
- No claim of device-confirmed black-screen repair until runtime testing.
