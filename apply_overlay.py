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
# The compatibility shader produces the same max-depth mip pyramid, but one mip
# level per dispatch. There is no inter-workgroup synchronization, global
# counter or coherent multi-mip image array. The rest of the HiZ/occlusion path
# stays exactly enabled.
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
    // Qualcomm-safe path: one level per dispatch. This keeps the full HiZ
    // pyramid and occlusion culling, but avoids the original cross-workgroup
    // atomic/barrier algorithm that crashes this driver.
    cmd.setPipeline(shaders.hiZMipAdreno);
    for(uint32_t i=1; i<mip; ++i) {
      const uint32_t w = std::max(1u, uint32_t(hiz.hiZ.w()) >> i);
      const uint32_t h = std::max(1u, uint32_t(hiz.hiZ.h()) >> i);
      cmd.setBinding(0, hiz.hiZ, Sampler::nearest(ClampMode::ClampToEdge), i-1);
      cmd.setBinding(1, hiz.hiZ, Sampler::nearest(ClampMode::ClampToEdge), i);
      cmd.dispatchThreads(size_t(w), size_t(h));
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

print("Direct-folder + functional Adreno 650 HiZ compatibility overlay applied")
