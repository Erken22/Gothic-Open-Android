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
    // Migrate only the old stock mobile defaults; never overwrite values the
    // player already changed deliberately.
    if(Gothic::settingsGetI(Section,SettingNames[Mobile::SettingShadows])==256)
      Gothic::settingsSetI(Section,SettingNames[Mobile::SettingShadows],1024);
    if(Gothic::settingsGetI(Section,SettingNames[Mobile::SettingFps])==30)
      Gothic::settingsSetI(Section,SettingNames[Mobile::SettingFps],60);
    Gothic::settingsSetI(Section,"version",4);
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

# Do not drop scene detail as an Android-only shortcut. HiZ already handles
# occlusion; the main and shadow views should keep the complete geometry list.
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
      push.minObjectPixels = 0.f;
      }
    else if(SceneGlobals::isShadowView(viewport)) {
      push.minObjectPixels = 0.f;
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

# ---------------------------------------------------------------------------
# Android lifecycle / resume support in Tempest
#
# NativeActivity emits APP_CMD_TERM_WINDOW whenever the app is backgrounded.
# Tempest currently treats TERM_WINDOW exactly like DESTROY, sends CloseEvent
# and exits the process. Keep the logical Window alive instead. A stable
# wrapper tracks the current ANativeWindow; on INIT_WINDOW we switch it,
# dispatch resize, recreate Vulkan surface/swapchain, then release the old
# native window.
# ---------------------------------------------------------------------------
replace_once(
    "lib/Tempest/Engine/system/api/androidapi.h",
'''    static std::filesystem::path internalDataPath();
    static std::filesystem::path externalDataPath();
''',
'''    static std::filesystem::path internalDataPath();
    static std::filesystem::path externalDataPath();
    static void*                 nativeWindow(SystemApi::Window* w);
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''static bool             active     = false;
static bool             hasWindow  = false;
''',
'''static bool             active     = false;
static bool             hasWindow  = false;

struct AndroidWindowHandle {
  ANativeWindow* native = nullptr;
  };
static AndroidWindowHandle androidWindow;
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''std::filesystem::path AndroidApi::externalDataPath() {
  assert(app!=nullptr && app->activity!=nullptr);
  const char* path = app->activity->externalDataPath;
  return path!=nullptr ? path : "";
  }
''',
'''std::filesystem::path AndroidApi::externalDataPath() {
  assert(app!=nullptr && app->activity!=nullptr);
  const char* path = app->activity->externalDataPath;
  return path!=nullptr ? path : "";
  }

void* AndroidApi::nativeWindow(SystemApi::Window* w) {
  if(w==nullptr)
    return nullptr;
  auto* h = reinterpret_cast<AndroidWindowHandle*>(w);
  return h->native;
  }
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''void AndroidApi::updateWindow() {
  if(app==nullptr || app->window==nullptr)
    return;

  hasWindow = true;
  if(mainWindow==nullptr)
    return;

  SizeEvent event(ANativeWindow_getWidth(app->window),ANativeWindow_getHeight(app->window));
  AndroidApi::dispatchResize(*mainWindow,event);
  }
''',
'''void AndroidApi::updateWindow() {
  if(app==nullptr || app->window==nullptr)
    return;

  hasWindow = true;
  if(mainWindow==nullptr)
    return;

  ANativeWindow* oldWindow = androidWindow.native;
  ANativeWindow* newWindow = app->window;
  if(oldWindow!=newWindow) {
    ANativeWindow_acquire(newWindow);
    androidWindow.native = newWindow;
    }

  Log::i("Android window init/resume: ",
         ANativeWindow_getWidth(newWindow),"x",ANativeWindow_getHeight(newWindow));

  // MainWindow::resizeEvent resets the swapchain. The Android Vulkan backend
  // recreates VkSurfaceKHR on reset, so it now binds the new ANativeWindow.
  SizeEvent event(ANativeWindow_getWidth(newWindow),ANativeWindow_getHeight(newWindow));
  AndroidApi::dispatchResize(*mainWindow,event);

  // The old window must remain referenced until the old Vulkan surface has
  // been destroyed by resizeEvent/swapchain.reset().
  if(oldWindow!=nullptr && oldWindow!=newWindow)
    ANativeWindow_release(oldWindow);
  }
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''    case APP_CMD_TERM_WINDOW:
    case APP_CMD_DESTROY:
      hasWindow = false;
      if(mainWindow!=nullptr) {
        CloseEvent event;
        AndroidApi::dispatchClose(*mainWindow,event);
        }
      isExit.store(true);
      break;
''',
'''    case APP_CMD_TERM_WINDOW:
      // Normal Android backgrounding destroys only the native surface. Keep
      // the game process, world and Tempest Window alive until INIT_WINDOW.
      hasWindow = false;
      active = false;
      releaseAllTouches();
      Log::i("Android window suspended (TERM_WINDOW), keeping game alive");
      break;
    case APP_CMD_DESTROY:
      hasWindow = false;
      if(mainWindow!=nullptr) {
        CloseEvent event;
        AndroidApi::dispatchClose(*mainWindow,event);
        }
      isExit.store(true);
      break;
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''  mainWindow = owner;
  ANativeWindow_acquire(app->window);
  return reinterpret_cast<SystemApi::Window*>(app->window);
''',
'''  mainWindow = owner;
  androidWindow.native = app->window;
  ANativeWindow_acquire(androidWindow.native);
  return reinterpret_cast<SystemApi::Window*>(&androidWindow);
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''void AndroidApi::implDestroyWindow(SystemApi::Window* w) {
  ANativeWindow_release(reinterpret_cast<ANativeWindow*>(w));
  mainWindow = nullptr;
  touches.clear();
  }
''',
'''void AndroidApi::implDestroyWindow(SystemApi::Window* w) {
  auto* h = reinterpret_cast<AndroidWindowHandle*>(w);
  if(h!=nullptr && h->native!=nullptr) {
    ANativeWindow_release(h->native);
    h->native = nullptr;
    }
  mainWindow = nullptr;
  touches.clear();
  }
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''Rect AndroidApi::implWindowClientRect(SystemApi::Window* w) {
  const auto window = reinterpret_cast<ANativeWindow*>(w);
  return Rect(0,0,ANativeWindow_getWidth(window),ANativeWindow_getHeight(window));
  }
''',
'''Rect AndroidApi::implWindowClientRect(SystemApi::Window* w) {
  auto* h = reinterpret_cast<AndroidWindowHandle*>(w);
  if(h==nullptr || h->native==nullptr)
    return Rect();
  return Rect(0,0,ANativeWindow_getWidth(h->native),ANativeWindow_getHeight(h->native));
  }
'''
)

replace_once(
    "lib/Tempest/Engine/gapi/vulkan/vswapchain.cpp",
'''#elif defined(__ANDROID__)
#  include <android/native_window.h>
#  include <vulkan/vulkan_android.h>
''',
'''#elif defined(__ANDROID__)
#  include <android/native_window.h>
#  include <vulkan/vulkan_android.h>
#  include "system/api/androidapi.h"
'''
)

replace_once(
    "lib/Tempest/Engine/gapi/vulkan/vswapchain.cpp",
'''#elif defined(__ANDROID__)
  VkAndroidSurfaceCreateInfoKHR createInfo = {};
  createInfo.sType  = VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR;
  createInfo.window = reinterpret_cast<ANativeWindow*>(hwnd);
  return vkCreateAndroidSurfaceKHR(instance,&createInfo,nullptr,pSurface);
''',
'''#elif defined(__ANDROID__)
  VkAndroidSurfaceCreateInfoKHR createInfo = {};
  createInfo.sType  = VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR;
  createInfo.window = reinterpret_cast<ANativeWindow*>(
      AndroidApi::nativeWindow(reinterpret_cast<SystemApi::Window*>(hwnd)));
  if(createInfo.window==nullptr)
    return VK_ERROR_SURFACE_LOST_KHR;
  return vkCreateAndroidSurfaceKHR(instance,&createInfo,nullptr,pSurface);
'''
)

replace_once(
    "lib/Tempest/Engine/gapi/vulkan/vswapchain.cpp",
'''void VSwapchain::reset() {
  cleanupSwapchain();
  createSwapchain(device);
  }
''',
'''void VSwapchain::reset() {
  cleanupSwapchain();
#if defined(__ANDROID__)
  // APP_CMD_TERM_WINDOW invalidates the old Android surface. INIT_WINDOW may
  // point the stable Tempest window handle at a different ANativeWindow.
  cleanupSurface();
#endif
  createSwapchain(device);
  }
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

print("Direct-folder + conservative HiZ + Android resume/swapchain fix applied")
