# OpenGothic Android 0.6.7 — FIX19 audit (2026-10-29)

## Baseline and source
- Patch repository: Erken22/Gothic-Open-Android.
- FIX19 source branch head: 69eea3460b21cb21a106e0f4d388efb3170dc7cc.
- OpenGothic base: 18336539f4b1a8d7b325930f613811f59fbde5db.
- Tempest base: 8c7c47fc03c6d774cde2fb2ec8240567c27a4817.
- FIX17 is the reported more stable baseline. FIX18 hybrid HiZ regressed object/texture visibility.

## Evidence read
- logcat_recording_2026-10-29_03-56-52.zip explicitly identifies FIX18 Hybrid and Adreno (TM) 650, system driver, shadows 1024.
- Its visibility message confirms hybrid landscape HiZ with frustum-only instances.
- PowerKeeper repeatedly reports "temp is too high limits system res" during the game session; this is a thermal-policy observation, not proof of the sole FPS bottleneck.
- Earlier org.opengothic.mobile logcat_recording_2026-10-29_00-26-20.zip records about 9.9–10.7 FPS in-world with CPU encode about 27–28 ms and present (including acquisition) about 54–57 ms. This is an earlier separate build; do not present these as FIX17/FIX18/FIX19 measured FPS.
- No valid FIX19 runtime capture exists yet.

## FIX19 behavior audited
- Bundles Turnip 26.3.0-R6 through pinned libadrenotools.
- Uses normal HiZ with Turnip and the FIX17 frustum-only fallback on system Adreno 650 if custom loader initialization fails.
- Does not reduce render resolution, remove shadows, or disable visual effects.
- Custom-driver fallback covers loader failure; it does not prove recovery from later runtime driver faults.
- Keeps upstream lifecycle handling. Resume correctness remains unverified on the target phone.
- Python patch applies cleanly to the exact OpenGothic/Tempest base. Python syntax and shell syntax checks passed.
- Proxy exports 107 Vulkan entry points; extra Vulkan entry points used by the engine are loaded dynamically through instance/device proc-address functions.

## Required device validation
- Install over the existing org.opengothic.launcher package; preserve saves/settings.
- Compare the same save, camera location and graphics settings against FIX17.
- Record FPS in gameplay, not the launcher/menu; use comparable device temperature.
- Inspect hero, walls and objects while rotating/moving the camera.
- Test multiple background/foreground cycles and screen lock/unlock.
- Capture logcat from startup so the actual selected Vulkan driver can be confirmed.
- Stable graphics, FPS improvement and resume must not be marked fixed until device evidence confirms them.
