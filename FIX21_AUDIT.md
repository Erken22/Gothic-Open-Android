# FIX21: Turnip menu startup shader failure

Input APK: FIX20, SHA-256 b2da87b45153e40df92c40eb352663b5e39055e7a0ca7e61e2ddb609ebdc90f1 (matches published release).
Input log: logcat_recording_2026-10-29_06-05-25.zip.

The FIX19 loader failure is absent. The engine starts, identifies Turnip Adreno (TM) 650, and initializes standard shadow-map resolution 1024.
The next explicit driver failure is:
Compute shader (vsm_list_pages.comp) which has workgroup barrier cannot be used because it's impossible to have enough concurrent waves.
It is followed by FORTIFY destroyed-mutex errors and SIGABRT. The recording has no usable native backtrace, so the later mutex failure has not been independently symbolicated.

Source evidence:
- vsm_list_pages uses a 32x32 (1024 invocation) compute workgroup with barriers.
- isVsmSupported tests broad advertised device limits and triggers eager creation of all VSM pipelines.
- Actual rendered VSM mode is separately selected by CommandLine::isVirtualShadow; this is an undocumented debug startup flag, default false.
- The Android launcher does not request that flag; normal shadows use conventional shadow maps.

FIX21 makes the Android VSM pipeline availability check require the explicit startup request before allocating/compiling the optional pipeline family. Desktop behavior and explicit startup requests retain their previous behavior.
Normal mobile shadow resolution, effects, render scale, Turnip loading and full HiZ are unchanged.
A startup log marker identifies the conventional-shadow path and confirms that unrequested VSM compilation was skipped.
The patch applied cleanly and Python syntax validation passed. Android compilation and APK linkage/signature checks run in CI.
Gameplay FPS, startup on the phone, rendering stability and background/foreground behavior remain device checks, not established results.
