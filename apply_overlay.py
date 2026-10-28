#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()

def replace_once(path, old, new):
    p = root / path
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Patch anchor not found in {path}: {old[:160]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")

# Direct-folder launcher: use the user's existing Gothic II installation
# in shared storage without importing or duplicating the game data.
replace_once(
    "android/AndroidManifest.xml",
    '    <uses-permission android:name="android.permission.VIBRATE" />\n',
    '    <uses-permission android:name="android.permission.VIBRATE" />\n'
    '    <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />\n'
)
replace_once(
    "android/AndroidManifest.xml",
    'android:name="org.opengothic.app.LauncherActivity"',
    'android:name="org.opengothic.app.DirectFolderActivity"'
)

launcher_src = Path(__file__).resolve().parent / "overlay" / "DirectFolderActivityModern.java"
shutil.copy2(launcher_src, root / "android/java/org/opengothic/app/DirectFolderActivity.java")

# Native install detection prefers the absolute direct-folder path selected by
# DirectFolderActivity. Saves/configuration stay in the app's own directory.
old_detect = '''#elif defined(__ANDROID__)
  auto path = Tempest::AndroidApi::externalDataPath().u16string();
  if(path.empty())
    return u"";
'''
new_detect = '''#elif defined(__ANDROID__)
  auto appData = Tempest::AndroidApi::externalDataPath();
  if(appData.empty())
    return u"";

  {
    std::ifstream in(std::filesystem::path(appData)/"game-path.txt");
    std::string selectedPath;
    if(in && std::getline(in,selectedPath)) {
      while(!selectedPath.empty() && (selectedPath.back()=='\\r' || selectedPath.back()=='\\n'))
        selectedPath.pop_back();
      std::filesystem::path direct(selectedPath);
      std::error_code ec;
      if(direct.is_absolute() && std::filesystem::is_directory(direct,ec) && !ec)
        return direct.u16string();
    }
  }

  auto path = appData.u16string();
'''
replace_once("common/utils/installdetect.cpp", old_detect, new_detect)

# ---------------------------------------------------------------------------
# Adreno 650 HiZ compatibility
#
# Do NOT disable HiZ, visibility, mesh rendering or optional graphics features.
# Qualcomm's driver crashed in Renderer::buildHiZ while executing the original
# hiz_mip.comp. That shader builds several mip levels in one dispatch and uses
# a global atomic counter to make the last workgroup continue the reduction.
#
# The compatibility shader produces the same max-depth mip pyramid in two
# dispatches: mips 1..4 are reduced per workgroup, then one workgroup finishes
# the top mips. There is no global atomic counter or inter-workgroup
# synchronization. The rest of the HiZ/occlusion path stays exactly enabled.
# ---------------------------------------------------------------------------

# Add the compatibility shader to the source tree and shader build.
hiz_src = Path(__file__).resolve().parent / "overlay" / "hiz_mip_adreno.comp"
shutil.copy2(hiz_src, root / "shader/hiz/hiz_mip_adreno.comp")

replace_once(
    "shader/CMakeLists.txt",
    'add_shader(hiz_mip.comp            hiz/hiz_mip.comp)\n',
    'add_shader(hiz_mip.comp            hiz/hiz_mip.comp)\n'
    'add_shader(hiz_mip_adreno.comp     hiz/hiz_mip_adreno.comp)\n'
)

replace_once(
    "common/graphics/shaders.h",
    '    Tempest::ComputePipeline hiZPot, hiZMip;\n',
    '    Tempest::ComputePipeline hiZPot, hiZMip, hiZMipAdreno;\n'
)

replace_once(
    "common/graphics/shaders.cpp",
    '  hiZPot  = computeShader("hiz_pot.comp.sprv");\n'
    '  hiZMip  = computeShader("hiz_mip.comp.sprv");\n',
    '  hiZPot       = computeShader("hiz_pot.comp.sprv");\n'
    '  hiZMip       = computeShader("hiz_mip.comp.sprv");\n'
    '  hiZMipAdreno = computeShader("hiz_mip_adreno.comp.sprv");\n'
)

replace_once(
    "common/graphics/renderer.cpp",
    '#include <cassert>\n',
    '#include <cassert>\n#include <cstring>\n'
)

old_hiz = '''void Renderer::buildHiZ(Tempest::Encoder<Tempest::CommandBuffer>& cmd) {
  assert(hiz.hiZ.w()<=128 && hiz.hiZ.h()<=128); // shader limitation

  cmd.setDebugMarker("HiZ-mip");
  cmd.setFramebuffer({});
  cmd.setBinding(0, zbuffer, Sampler::nearest(ClampMode::ClampToEdge));
  cmd.setBinding(1, hiz.hiZ);
  cmd.setPipeline(shaders.hiZPot);
  cmd.dispatch(size_t(hiz.hiZ.w()), size_t(hiz.hiZ.h()));

  const uint32_t maxBind = 8, mip = hiz.hiZ.mipCount();
  const auto     wgSz = shaders.hiZMip.workGroupSize();
  const int      wgW  = std::max(std::max(hiz.hiZ.w()/2, 1) / wgSz.x, 1);
  const int      wgH  = std::max(std::max(hiz.hiZ.h()/2, 1) / wgSz.y, 1);
  struct Push {
    uint32_t numGroups;
    uint32_t mip;
    } push = {};
  push.numGroups = uint32_t(wgW * wgH);
  push.mip       = mip;

  cmd.setBinding(0, hiz.counter);
  for(uint32_t i=0; i<maxBind; ++i)
    cmd.setBinding(1+i, hiz.hiZ, Sampler::nearest(), std::min(i, mip-1));
  cmd.setPushData(push);
  cmd.setPipeline(shaders.hiZMip);
  //cmd.dispatchThreads(std::max(uint32_t(hiz.hiZ.w())/2u, 1u), std::max(uint32_t(hiz.hiZ.h())/2u, 1u));
  cmd.dispatch(size_t(wgW), size_t(wgH));
  }
'''

new_hiz = '''void Renderer::buildHiZ(Tempest::Encoder<Tempest::CommandBuffer>& cmd) {
  assert(hiz.hiZ.w()<=128 && hiz.hiZ.h()<=128); // shader limitation

  cmd.setDebugMarker("HiZ-mip");
  cmd.setFramebuffer({});
  cmd.setBinding(0, zbuffer, Sampler::nearest(ClampMode::ClampToEdge));
  cmd.setBinding(1, hiz.hiZ);
  cmd.setPipeline(shaders.hiZPot);
  cmd.dispatch(size_t(hiz.hiZ.w()), size_t(hiz.hiZ.h()));

  const uint32_t mip = hiz.hiZ.mipCount();
  const char* gpuName = Resources::device().properties().name;
  const bool adreno650 = gpuName!=nullptr && std::strstr(gpuName,"Adreno (TM) 650")!=nullptr;

  if(adreno650) {
    static bool loggedCompat = false;
    if(!loggedCompat) {
      loggedCompat = true;
      Log::i("HiZ: Adreno 650 two-pass compatibility reducer enabled (full HiZ remains active)");
      }

    // Qualcomm-safe path: preserve the original per-workgroup reduction, but
    // split off the final cross-workgroup stage. This removes the global
    // atomic/counter that crashes the driver and avoids one dispatch per mip.
    struct AdrenoPush { uint32_t levels; } ap = {};
    const auto awg = shaders.hiZMipAdreno.workGroupSize();
    const int aw = std::max(std::max(hiz.hiZ.w()/2,1)/awg.x,1);
    const int ah = std::max(std::max(hiz.hiZ.h()/2,1)/awg.y,1);

    cmd.setPipeline(shaders.hiZMipAdreno);
    ap.levels = std::min(mip,5u);
    for(uint32_t i=0; i<5; ++i)
      cmd.setBinding(i,hiz.hiZ,Sampler::nearest(),std::min(i,mip-1));
    cmd.setPushData(ap);
    cmd.dispatch(size_t(aw),size_t(ah));

    if(mip>5) {
      constexpr uint32_t base = 4;
      ap.levels = std::min(mip-base,5u);
      for(uint32_t i=0; i<5; ++i)
        cmd.setBinding(i,hiz.hiZ,Sampler::nearest(),std::min(base+i,mip-1));
      cmd.setPushData(ap);
      cmd.dispatch(1,1);
      }
    return;
    }

  const uint32_t maxBind = 8;
  const auto     wgSz = shaders.hiZMip.workGroupSize();
  const int      wgW  = std::max(std::max(hiz.hiZ.w()/2, 1) / wgSz.x, 1);
  const int      wgH  = std::max(std::max(hiz.hiZ.h()/2, 1) / wgSz.y, 1);
  struct Push {
    uint32_t numGroups;
    uint32_t mip;
    } push = {};
  push.numGroups = uint32_t(wgW * wgH);
  push.mip       = mip;

  cmd.setBinding(0, hiz.counter);
  for(uint32_t i=0; i<maxBind; ++i)
    cmd.setBinding(1+i, hiz.hiZ, Sampler::nearest(), std::min(i, mip-1));
  cmd.setPushData(push);
  cmd.setPipeline(shaders.hiZMip);
  cmd.dispatch(size_t(wgW), size_t(wgH));
  }
'''
replace_once("common/graphics/renderer.cpp", old_hiz, new_hiz)

# Mobile defaults in the upstream fork are deliberately very conservative
# (256 shadow map and 30 FPS). On Adreno 650 this hides shadows and caps a
# device that can run substantially faster. Keep the user's resolution/effects
# choices, but use a real shadow map and a 60 FPS cap by default/migration.
replace_once(
    "common/utils/androidinput.h",
    '  int shadows     = 256; // shadow map size, 0 disables shadows\n'
    '  int effects     = 0;   // SSAO\n'
    '  int fps         = 30;\n',
    '  int shadows     = 1024; // shadow map size, 0 disables shadows\n'
    '  int effects     = 0;    // SSAO (kept optional for performance)\n'
    '  int fps         = 60;\n'
)

replace_once(
    "common/utils/androidinput.cpp",
    '#include <Tempest/Event>\n',
    '#include <Tempest/Event>\n#include <Tempest/Log>\n'
)

replace_once(
    "common/utils/androidinput.cpp",
'''    Gothic::settingsSetI(Section,"version",3);
    Gothic::flushSettings();
    }

#ifdef __ANDROID__
''',
'''    Gothic::settingsSetI(Section,"version",3);
    Gothic::flushSettings();
    }

  if(Gothic::settingsGetI(Section,"version")<4) {
    // Migrate only the old stock shadow default; preserve a value the player
    // deliberately selected.
    if(Gothic::settingsGetI(Section,SettingNames[Mobile::SettingShadows])==256)
      Gothic::settingsSetI(Section,SettingNames[Mobile::SettingShadows],1024);
    Gothic::settingsSetI(Section,"version",4);
    Gothic::flushSettings();
    }

  if(Gothic::settingsGetI(Section,"version")<5) {
    // Earlier test builds could already be marked version 4 while still
    // carrying the stock 30 FPS cap. Lift that cap once, without changing
    // resolution, shadows or effects.
    if(Gothic::settingsGetI(Section,SettingNames[Mobile::SettingFps])==30)
      Gothic::settingsSetI(Section,SettingNames[Mobile::SettingFps],60);
    Gothic::settingsSetI(Section,"version",5);
    Gothic::flushSettings();
    }

  {
    const auto p = preferences();
    Log::i("Mobile profile: resolution=",p.resolution,"%, shadows=",p.shadows,
           ", effects=",p.effects,", fps=",p.fps);
  }

#ifdef __ANDROID__
'''
)

# The fork's original 2px/1px thresholds caused visible popping. Use only
# sub-pixel rejection for static non-animated details: below this size the
# object cannot contribute a stable visible pixel, while skipping it saves
# visibility payload and draw work. Characters/morph/water are excluded by
# the shader itself.
replace_once(
    "common/graphics/drawcommands.cpp",
'''    if(viewport==SceneGlobals::V_Main) {
      push.minObjectPixels = 2.f;
      }
    else if(SceneGlobals::isShadowView(viewport)) {
      push.minObjectPixels = 1.f;
      const auto& shadow = *scene.shadowMap[viewport-SceneGlobals::V_Shadow0];
''',
'''    if(viewport==SceneGlobals::V_Main) {
      push.minObjectPixels = 0.35f;
      }
    else if(SceneGlobals::isShadowView(viewport)) {
      push.minObjectPixels = 0.5f;
      const auto& shadow = *scene.shadowMap[viewport-SceneGlobals::V_Shadow0];
'''
)

# Conservative HiZ occlusion for mobile/Adreno.
# The renderer used a tight transformed bucket AABB for every object and an
# exact depth comparison. Animated/morphed geometry can extend beyond that
# static box, while R16 HiZ quantization and tile boundaries can make exact
# comparisons falsely reject visible meshlets. Keep HiZ enabled, but make the
# test conservative instead of deleting geometry.
replace_once(
    "shader/materials/visibility_pass.comp",
'''  ibbox[0] = clamp(ibbox[0], ivec2(0), hiZsize - ivec2(1));
  ibbox[1] = clamp(ibbox[1], ivec2(0), hiZsize - ivec2(1));

  float bz      = packHiZ(depthMin);
  float z       = hiZFetch(hiZ, ibbox);
  if(bz > z)
    return false;
''',
'''  // Expand by one base HiZ texel on every side. This makes the query
  // conservative at tile boundaries: extra sampled area can only raise the
  // max-depth value and therefore can never create a false occlusion.
  ibbox[0] -= ivec2(2);
  ibbox[1] += ivec2(2);
  ibbox[0] = clamp(ibbox[0], ivec2(0), hiZsize - ivec2(1));
  ibbox[1] = clamp(ibbox[1], ivec2(0), hiZsize - ivec2(1));

  float bz      = packHiZ(depthMin);
  float z       = hiZFetch(hiZ, ibbox);
  // R16 stores the pyramid at half-float precision. Require a real depth gap,
  // not a quantization-sized difference, before rejecting a cluster.
  const float conservativeDepthBias = 0.01;
  if(bz > z + conservativeDepthBias)
    return false;
'''
)

replace_once(
    "shader/materials/visibility_pass.comp",
'''bool projectCluster(const Cluster cluster, out vec4 aabb, out float depthMin) {
  if(cluster.instanceId==0xFFFFFFFF)
    return projectSphere(cluster.sphere, aabb, depthMin);
  // return projectSphere(cluster.sphere, aabb, depthMin);
  return projectInstance(cluster, aabb, depthMin);
  }
''',
'''bool projectCluster(const Cluster cluster, out vec4 aabb, out float depthMin) {
  // Use the world-space cluster sphere for every HiZ query. It is looser than
  // the bucket AABB but cannot cut off animated vertices, split static meshes,
  // wall pieces or authored meshlet bounds. HiZ remains active; only the bound
  // used to prove full occlusion becomes conservative.
  return projectSphere(cluster.sphere, aabb, depthMin);
  }
'''
)

# Android-fork-only meshlet LOD is not present in upstream OpenGothic and
# can select incomplete meshlet ranges for Gothic II assets (e.g. missing head
# or chunks of props/walls). Restore upstream behavior: always submit the
# cluster's original full meshlet range. HiZ/frustum/distance culling remains.
replace_once(
    "shader/materials/visibility_pass.comp",
'''  uint meshletId  = cluster.firstMeshlet;
  uint meshletCount = uint(cluster.meshletCount);
  // Use camera distance in every pass, including HiZ and shadows, to keep
  // depth and color geometry identical. Close objects retain full detail.
  if(instanceId!=0xFFFFFFFF && (cluster.lod.x!=0 || cluster.lod.z!=0)) {
    const vec3 offset = cluster.sphere.xyz-scene.camPos;
    const float detail = mix(1.0, 0.15, push.modelDetail);
    const float radius = max(cluster.sphere.w,1.0);
    const float distanceSquared = dot(offset,offset)*detail*detail;
    if(distanceSquared>144.0*radius*radius && cluster.lod.z>0) {
      meshletId = cluster.lod.z;
      meshletCount = cluster.lod.w;
      } else if(distanceSquared>25.0*radius*radius && cluster.lod.x>0) {
      meshletId = cluster.lod.x;
      meshletCount = cluster.lod.y;
      }
    }
''',
'''  const uint meshletId  = cluster.firstMeshlet;
  const uint meshletCount = uint(cluster.meshletCount);
'''
)

# Keep HiZ for the expensive static world and static instances. Characters,
# morphing geometry and water bypass occlusion because their bounds change.
# Large near-camera clusters also bypass HiZ. This restores most of the
# performance benefit without reintroducing the partial-character bug.
replace_once(
    "shader/materials/visibility_pass.comp",
'''#if defined(HIZ)
  if(!hiZTest(aabb, depthMin))
    return;
#endif
''',
'''#if defined(HIZ)
  const uint hizBucketId = cluster.bucketId_commandId >> 16;
  const bool dynamicGeometry =
      cluster.instanceId!=0xFFFFFFFF &&
      (bucket[hizBucketId].flags & (BK_SKIN | BK_MORPH | BK_WATER))!=0;
  bool useHiZ = !dynamicGeometry;
  const vec2 projectedSpan = max(aabb.zw-aabb.xy,vec2(0));
  if(max(projectedSpan.x,projectedSpan.y)>0.10)
    useHiZ = false;
  if(useHiZ && !hiZTest(aabb, depthMin))
    return;
#endif
'''
)

# Keep three CPU command/fence slots in flight on Android. Tempest's Android
# swapchain normally asks for minImageCount+1 (typically 3), so two application
# slots unnecessarily serialize CPU/GPU work. This changes buffering only, not
# rendering quality.
replace_once(
    "common/resources.h",
    '''      MaxFramesInFlight = 2,
      ShadowLayers      = 2,
''',
    '''      MaxFramesInFlight = 3,
      ShadowLayers      = 2,
'''
)

# The Russian scripts contain a BL target with no function symbol. ZenKit's
# lenient VM already treats this instruction as skippable. Avoid stopping on
# the red script-error overlay for exactly that known lenient case.
replace_once(
    "common/game/gamescript.cpp",
'''  vm.register_exception_handler([](zenkit::DaedalusVm& v, const zenkit::DaedalusScriptError& exc, const zenkit::DaedalusInstruction& instr) {
    const auto ret = zenkit::lenient_vm_exception_handler(v,exc,instr);
''',
'''  vm.register_exception_handler([](zenkit::DaedalusVm& v, const zenkit::DaedalusScriptError& exc, const zenkit::DaedalusInstruction& instr) {
    const std::string_view what(exc.what());
    if(instr.op==zenkit::DaedalusOpcode::BL && what.starts_with("bl: no symbol found for address "))
      return zenkit::DaedalusVmExceptionStrategy::CONTINUE;
    const auto ret = zenkit::lenient_vm_exception_handler(v,exc,instr);
'''
)

# Gradle performs a second CMake configure. After the first configure the
# stock tempest-opengothic.patch is applied, then our post-config resume patch
# adds extra lines to the same Tempest files. A strict git --reverse --check
# can no longer recognize the stock patch at that point. The resume marker is
# only created after a successful first configure, so it safely means the
# stock patch is already present.
replace_once(
    "cmake/tempestpatch.cmake",
'''  if(NOT OG_TEMPEST_PATCHED EQUAL 0)
    execute_process(
''',
'''  if(NOT OG_TEMPEST_PATCHED EQUAL 0)
    file(READ "${OG_TEMPEST_DIR}/Engine/system/api/androidapi.h" OG_TEMPEST_ANDROIDAPI_H)
    string(FIND "${OG_TEMPEST_ANDROIDAPI_H}" "nativeWindow(SystemApi::Window* w)" OG_TEMPEST_RESUME_MARKER)
    if(NOT OG_TEMPEST_RESUME_MARKER EQUAL -1)
      # The normal OpenGothic patch was applied by the first configure and the
      # post-config Android lifecycle patch extended those same files.
      set(OG_TEMPEST_PATCHED 0)
    endif()
  endif()

  if(NOT OG_TEMPEST_PATCHED EQUAL 0)
    execute_process(
'''
)

# Keep only Java pieces required for direct-folder launching and the game.
java_dir = root / "android/java/org/opengothic/app"
keep_java = {
    "DirectFolderActivity.java",
    "GameActivity.java",
    "GameFiles.java",
    "Haptics.java",
    "SystemUi.java",
}
for java in java_dir.glob("*.java"):
    if java.name not in keep_java:
        java.unlink()

manifest = root / "android/AndroidManifest.xml"
mt = manifest.read_text(encoding="utf-8")
for block in [
'''        <!-- Mods: adding of zip files and the choice of the mods that start with the game -->
        <activity android:name="org.opengothic.app.ModsActivity" android:exported="false"
            android:screenOrientation="landscape"
            android:configChanges="orientation|screenSize|keyboardHidden" />
''',
'''        <!-- The login to Steam, the first screen when nobody is signed in -->
        <activity android:name="org.opengothic.app.SteamLoginActivity" android:exported="false"
            android:screenOrientation="landscape" android:windowSoftInputMode="adjustResize"
            android:configChanges="orientation|screenSize|keyboardHidden" />
''',
'''        <!-- The answer of the system installer to the update -->
        <receiver android:name="org.opengothic.app.UpdateReceiver" android:exported="false" />
        <service android:name="org.opengothic.app.SteamDownloadService" android:exported="false"
            android:foregroundServiceType="dataSync" />
''',
]:
    mt = mt.replace(block, "")
manifest.write_text(mt, encoding="utf-8")

# No Steam/network Java dependency is needed when the data already exists.
cmake = root / "CMakeLists.txt"
ct = cmake.read_text(encoding="utf-8")
dep_start = ct.find('    # The login to Steam and the download of the games')
dep_end_marker = '      "com.squareup.okio:okio:3.16.0")'
if dep_start < 0 or dep_end_marker not in ct:
    raise SystemExit("Android dependency block not found in CMakeLists.txt")
dep_end = ct.index(dep_end_marker, dep_start) + len(dep_end_marker)
ct = ct[:dep_start] + '    )' + ct[dep_end:]
cmake.write_text(ct, encoding="utf-8")

print("Direct-folder + upstream meshlets + selective HiZ + triple-buffer FPS/resume instrumentation applied")

# Resume-safe swapchain teardown: presentation may outlive frame fences.
replace_once(
    "common/mainwindow.cpp",
    '''void MainWindow::resizeEvent(SizeEvent&) {
  for(auto& i:fence)
    i.wait();
  swapchain.reset();
''',
    '''void MainWindow::resizeEvent(SizeEvent&) {
#if defined(__ANDROID__)
  // A NativeActivity resume replaces ANativeWindow/VkSurfaceKHR. Waiting only
  // frame fences is not sufficient to guarantee presentation has released the
  // old BufferQueue. Drain the device before destroying that surface.
  device.waitIdle();
#endif
  for(auto& i:fence)
    i.wait();
  swapchain.reset();
'''
)

replace_once(
    "common/mainwindow.cpp",
'''    fps.push(t-time);
    if(Gothic::inst().isBenchmarkMode() && Gothic::inst().world()!=nullptr && Gothic::inst().world()->currentCs()!=nullptr)
''',
'''    fps.push(t-time);
#if defined(__ANDROID__)
    static uint64_t perfLogAt = 0;
    if(t-perfLogAt>=5000) {
      perfLogAt = t;
      Log::i("Runtime FPS: ",fps.get(),", target=",
             AndroidInput::preferences().fps,", frameLimitMs=",maxFpsInv);
      }
#endif
    if(Gothic::inst().isBenchmarkMode() && Gothic::inst().world()!=nullptr && Gothic::inst().world()->currentCs()!=nullptr)
'''
)
