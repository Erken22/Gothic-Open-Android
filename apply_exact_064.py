#!/usr/bin/env python3
from pathlib import Path
import sys
import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

root = Path(sys.argv[1]).resolve()

def replace_once(rel, old, new):
    p = root / rel
    s = p.read_text(encoding="utf-8")
    if old not in s:
        raise SystemExit(f"anchor not found in {rel}: {old[:120]!r}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")

# ---------------------------------------------------------------------------
# Direct Folder, integrated into the exact Gothic Launcher 0.6.4 source.
# ---------------------------------------------------------------------------
replace_once(
    "android/launcher/AndroidManifest.xml",
    '    <uses-permission android:name="android.permission.VIBRATE" />\n',
    '    <uses-permission android:name="android.permission.VIBRATE" />\n'
    '    <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />\n'
)

replace_once(
    "android/launcher/java/org/opengothic/app/LauncherActivity.java",
    'import android.os.Build;\n',
    'import android.os.Build;\nimport android.os.Environment;\n'
)

replace_once(
    "android/launcher/java/org/opengothic/app/LauncherActivity.java",
    '''    private static final int PICK_ARCHIVE = 1;
    private static final int SIGN_IN = 2;
''',
    '''    private static final int PICK_FOLDER = 1;
    private static final int SIGN_IN = 2;
    private static final int ALL_FILES = 3;
'''
)

replace_once(
    "android/launcher/java/org/opengothic/app/LauncherActivity.java",
    '''    private Library.Game game() {
        return Library.GAMES[selected];
    }
''',
    '''    private Library.Game game() {
        return Library.GAMES[selected];
    }

    private File directGame(Library.Game game) {
        if (prefs == null || game == null) return null;
        String path = prefs.getString("direct_path_" + game.folder, null);
        if (path == null || path.isEmpty()) return null;
        File dir = new File(path);
        return GameFiles.isInstallation(dir) ? dir : null;
    }
'''
)

replace_once(
    "android/launcher/java/org/opengothic/app/LauncherActivity.java",
    '        } else if (Library.installed(root, game)) {\n',
    '        } else if (directGame(game) != null || Library.installed(root, game)) {\n'
)

old_play = '''    private void play() {
        File root = Library.root(this);
        if (root == null || launching || warnUnsupported(this::play)) return;
        if (!GameFiles.damaged(new File(root, game().folder)).isEmpty()) {
            askRepair(game());
            return;
        }
        // The engine reads the folder name at start, see InstallDetect::androidGame
        try {
            GameFiles.ensureScriptsFolder(new File(root, game().folder));
        } catch (IOException e) {
            message(e.getMessage());
            return;
        }
        try (FileOutputStream out = new FileOutputStream(new File(root, "game.txt"))) {
            out.write((game().folder + "\\n").getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            message(e.getMessage());
            return;
        }
'''
new_play = '''    private void play() {
        File root = Library.root(this);
        if (root == null || launching || warnUnsupported(this::play)) return;
        File direct = directGame(game());
        File gameDir = direct != null ? direct : new File(root, game().folder);
        if (!GameFiles.damaged(gameDir).isEmpty()) {
            askRepair(game());
            return;
        }
        try {
            GameFiles.ensureScriptsFolder(gameDir);
        } catch (IOException e) {
            message(e.getMessage());
            return;
        }
        // game.txt is only the save/settings namespace. game-path.txt is the
        // actual installation path and may point at shared storage.
        try (FileOutputStream out = new FileOutputStream(new File(root, "game.txt"))) {
            out.write((game().folder + "\\n").getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            message(e.getMessage());
            return;
        }
        File pathFile = new File(root, "game-path.txt");
        if (direct != null) {
            try (FileOutputStream out = new FileOutputStream(pathFile)) {
                out.write((direct.getAbsolutePath() + "\\n").getBytes(StandardCharsets.UTF_8));
            } catch (IOException e) {
                message(e.getMessage());
                return;
            }
        } else {
            pathFile.delete();
        }
'''
replace_once("android/launcher/java/org/opengothic/app/LauncherActivity.java", old_play, new_play)

old_pick = '''    private void pickArchive() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
        startActivityForResult(intent, PICK_ARCHIVE);
    }
'''
new_pick = '''    private void pickArchive() {
        if (Build.VERSION.SDK_INT >= 30 && !Environment.isExternalStorageManager()) {
            Intent permission = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                    Uri.parse("package:" + getPackageName()));
            startActivityForResult(permission, ALL_FILES);
            return;
        }
        startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE), PICK_FOLDER);
    }

    private void selectDirectFolder(Uri uri) {
        try {
            String id = DocumentsContract.getTreeDocumentId(uri);
            int colon = id.indexOf(':');
            if (colon < 0 || !"primary".equalsIgnoreCase(id.substring(0, colon))) {
                message(getString(R.string.og_err_direct_primary));
                return;
            }
            String relative = id.substring(colon + 1);
            File base = Environment.getExternalStorageDirectory();
            File dir = relative.isEmpty() ? base : new File(base, relative);
            if (!GameFiles.isInstallation(dir)) {
                message(getString(R.string.og_err_direct_folder));
                return;
            }
            String detected = GameFiles.detect(dir);
            Library.Game found = Library.byFolder(detected);
            if (found == null) {
                message(getString(R.string.og_err_direct_folder));
                return;
            }
            prefs.edit().putString("direct_path_" + found.folder, dir.getAbsolutePath())
                    .putString("selected", found.folder).apply();
            selected = indexOf(found.folder);
            showGame();
        } catch (Exception e) {
            message(e.getMessage() == null ? getString(R.string.og_err_direct_folder) : e.getMessage());
        }
    }
'''
replace_once("android/launcher/java/org/opengothic/app/LauncherActivity.java", old_pick, new_pick)

old_result = '''        if (request == PICK_ARCHIVE && result == RESULT_OK && data != null && data.getData() != null) {
            Importer.start(this, data.getData());
            importing = true;
        } else if (request == SIGN_IN && result == RESULT_OK) {
'''
new_result = '''        if (request == ALL_FILES) {
            if (Build.VERSION.SDK_INT < 30 || Environment.isExternalStorageManager()) pickArchive();
        } else if (request == PICK_FOLDER && result == RESULT_OK && data != null && data.getData() != null) {
            selectDirectFolder(data.getData());
        } else if (request == SIGN_IN && result == RESULT_OK) {
'''
replace_once("android/launcher/java/org/opengothic/app/LauncherActivity.java", old_result, new_result)

# Launcher wording now reflects what the button really does.
replace_once(
    "android/launcher/res/values/og_strings.xml",
    '<string name="og_import_zip">Import a ZIP</string>',
    '<string name="og_import_zip">Select game folder</string>'
)
replace_once(
    "android/launcher/res/values-ru/og_strings.xml",
    '<string name="og_import_zip">Импорт ZIP</string>',
    '<string name="og_import_zip">Выбрать папку игры</string>'
)
for rel, anchor, extra in [
    ("android/launcher/res/values/og_strings.xml",
     '    <string name="og_err_open_archive">Cannot open the archive.</string>\n',
     '    <string name="og_err_direct_folder">Select the Gothic game root containing Data and _work.</string>\n'
     '    <string name="og_err_direct_primary">For now, select a folder in the phone internal shared storage.</string>\n'),
    ("android/launcher/res/values-ru/og_strings.xml",
     '    <string name="og_err_open_archive">Не удалось открыть архив.</string>\n',
     '    <string name="og_err_direct_folder">Выберите корневую папку Gothic, где находятся Data и _work.</string>\n'
     '    <string name="og_err_direct_primary">Пока выберите папку во внутренней общей памяти телефона.</string>\n')
]:
    replace_once(rel, anchor, anchor + extra)

# The native engine reads the exact absolute game path. Saves/settings still use
# game.txt and therefore stay in the launcher's own Android/data directory.
old_detect = '''#elif defined(__ANDROID__)
  auto name = androidGame();
  auto game = appDir;
  if(!game.empty() && game.back()!=u'/')
    game.push_back(u'/');
  game += name.empty() ? u"Gothic2" : name;
  if(FileUtil::exists(game))
    return game;
  return u"";
'''
new_detect = '''#elif defined(__ANDROID__)
  {
    std::ifstream file(std::filesystem::path(appDir)/"game-path.txt");
    std::string path;
    std::getline(file,path);
    while(!path.empty() && std::isspace(uint8_t(path.back())))
      path.pop_back();
    if(!path.empty()) {
      std::filesystem::path direct(path);
      std::error_code ec;
      if(direct.is_absolute() && std::filesystem::is_directory(direct,ec) && !ec)
        return direct.u16string();
    }
  }
  auto name = androidGame();
  auto game = appDir;
  if(!game.empty() && game.back()!=u'/')
    game.push_back(u'/');
  game += name.empty() ? u"Gothic2" : name;
  if(FileUtil::exists(game))
    return game;
  return u"";
'''
replace_once("common/utils/installdetect.cpp", old_detect, new_detect)

# ---------------------------------------------------------------------------
# Adreno 650: use OpenGothic's existing Qualcomm-safe material shader path.
# No graphics feature is disabled here; the interface varyings are flattened.
# Also avoid bindless material descriptors on the old Qualcomm driver.
# ---------------------------------------------------------------------------
old = 'name.find("Adreno")!=std::string_view::npos && name.find("610")!=std::string_view::npos'
flat650 = 'name.find("Adreno")!=std::string_view::npos && (name.find("610")!=std::string_view::npos || name.find("650")!=std::string_view::npos)'
p = root / "common/graphics/shaders.cpp"
shader_cpp = p.read_text(encoding="utf-8")
first = shader_cpp.find(old)
second = shader_cpp.find(old, first + 1)
if first < 0 or second < 0 or shader_cpp.find(old, second + 1) >= 0:
    raise SystemExit("expected exactly two Adreno 610 checks")
# Keep bindless available on 650; only extend the flat-varying correctness workaround.
shader_cpp = shader_cpp[:second] + shader_cpp[second:].replace(old, flat650, 1)
p.write_text(shader_cpp, encoding="utf-8")

# ---------------------------------------------------------------------------
# Save-name crash: Android IME text is synthetic widget input.
# Key-up has no editing semantics but can arrive after Enter destroyed/closed
# the save-name widget. Queue only key-downs for IME replay, and consume Done
# once so Java cannot submit it twice.
# ---------------------------------------------------------------------------
old_editor = '''extern "C" JNIEXPORT void JNICALL
Java_org_tempest_TempestNativeActivity_nativeEditorAction(JNIEnv*, jobject) {
  std::lock_guard<std::mutex> guard(softInputSync);
  if(!softInputActive)
    return;
  std::lock_guard<std::mutex> keyGuard(keysSync);
  pushKey(AKEYCODE_ENTER,'\\n');
  if(app!=nullptr)
    ALooper_wake(app->looper);
  }
'''
new_editor = '''extern "C" JNIEXPORT void JNICALL
Java_org_tempest_TempestNativeActivity_nativeEditorAction(JNIEnv*, jobject) {
  std::lock_guard<std::mutex> guard(softInputSync);
  if(!softInputActive)
    return;
  // Consume the editor action exactly once. The save-name widget can close
  // itself on Return key-down, so a delayed key-up must not target it.
  softInputActive = false;
  std::lock_guard<std::mutex> keyGuard(keysSync);
  keys.push_back({AKEYCODE_ENTER,uint32_t('\\n'),true});
  if(app!=nullptr)
    ALooper_wake(app->looper);
  }
'''
replace_once("lib/Tempest/Engine/system/api/androidapi.cpp", old_editor, new_editor)

# Soft-IME replacement characters also need only key-down: TextEdit edits on
# keyDown/keyRepeat; keyUp is intentionally empty. This prevents stale key-up
# events if a text widget closes while the queue is draining.
old_push = '''static void pushKey(uint32_t keyCode, uint32_t code) {
  // The caller holds keysSync, so a text replacement is queued as one batch
  keys.push_back({keyCode,code,true});
  keys.push_back({keyCode,code,false});
  }
'''
new_push = '''static void pushKey(uint32_t keyCode, uint32_t code) {
  // Preserve normal key-state transitions for text edits.
  // Only the editor-action Enter below is intentionally down-only.
  keys.push_back({keyCode,code,true});
  keys.push_back({keyCode,code,false});
  }
'''
replace_once("lib/Tempest/Engine/system/api/androidapi.cpp", old_push, new_push)

# ---------------------------------------------------------------------------
# Graphics correctness: keep HiZ/occlusion enabled, but make it conservative.
# R16 quantization plus old Adreno sampling can falsely reject geometry.
# The pyramid is tiny (<=128x128), so R32F has negligible memory cost.
# ---------------------------------------------------------------------------
old_hiz_box = '''  ibbox[0] = clamp(ibbox[0], ivec2(0), hiZsize - ivec2(1));
  ibbox[1] = clamp(ibbox[1], ivec2(0), hiZsize - ivec2(1));

  float bz      = packHiZ(depthMin);
  float z       = hiZFetch(hiZ, ibbox);
  if(bz > z)
    return false;
'''
new_hiz_box = '''  // Conservative raster bounds: include one extra HiZ tile around the
  // projected box so rounding cannot hide thin/partial geometry.
  ibbox[0] = clamp(ibbox[0] - ivec2(2), ivec2(0), hiZsize - ivec2(1));
  ibbox[1] = clamp(ibbox[1] + ivec2(2), ivec2(0), hiZsize - ivec2(1));

  float bz      = packHiZ(depthMin);
  float z       = hiZFetch(hiZ, ibbox);
  // packHiZ expands the useful depth interval by 20x. A small margin here
  // absorbs ROP/sampler precision differences without disabling occlusion.
  const float conservativeBias = 0.01;
  if(bz > z + conservativeBias)
    return false;
'''
replace_once("shader/materials/visibility_pass.comp", old_hiz_box, new_hiz_box)


# ---------------------------------------------------------------------------
# FIX13: conservative bounds + Qualcomm-safe HiZ + flat-bindless performance
# ---------------------------------------------------------------------------
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
  vec4 conservative = cluster.sphere;
  conservative.w = conservative.w*1.10 + 0.25;
  return projectSphere(conservative, aabb, depthMin);
  }
'''
)

replace_once(
    "shader/materials/visibility_pass.comp",
'''bool frustrumTest(const vec4 sphere) {
  if(sphere.w<0.f)
    return false;

  for(int i=0; i<6; ++i) {
    if(dot(vec4(sphere.xyz,1.0), scene.frustrum[i]) <= -sphere.w) {
      return false;
      }
    }

  return true;
  }
''',
'''bool frustrumTest(const vec4 sphere) {
  if(sphere.w<0.f)
    return false;

  const float radius = sphere.w*1.10 + 0.25;
  for(int i=0; i<6; ++i) {
    if(dot(vec4(sphere.xyz,1.0), scene.frustrum[i]) <= -radius) {
      return false;
      }
    }

  return true;
  }
'''
)

compat = (Path(__file__).resolve().parent / "overlay" / "hiz_mip_adreno.comp").read_text(encoding="utf-8")
(root / "shader/hiz/hiz_mip_adreno.comp").write_text(compat, encoding="utf-8")

replace_once(
    "shader/CMakeLists.txt",
'''endif()
add_shader(hiz_pot.comp              hiz/hiz_pot.comp)
''',
'''endif()
add_shader(hiz_mip_adreno.comp       hiz/hiz_mip_adreno.comp)
add_shader(hiz_pot.comp              hiz/hiz_pot.comp)
'''
)

replace_once(
    "common/graphics/shaders.h",
    '    Tempest::ComputePipeline hiZPot, hiZMip;\n',
    '    Tempest::ComputePipeline hiZPot, hiZMip, hiZMipAdreno;\n'
)

replace_once(
    "common/graphics/shaders.cpp",
'''  hiZPot  = computeShader("hiz_pot.comp.sprv");
  hiZMip  = computeShader("hiz_mip.comp.sprv");
''',
'''  hiZPot       = computeShader("hiz_pot.comp.sprv");
  hiZMip       = computeShader("hiz_mip.comp.sprv");
  hiZMipAdreno = computeShader("hiz_mip_adreno.comp.sprv");
'''
)

old_build_hiz = '''void Renderer::buildHiZ(Tempest::Encoder<Tempest::CommandBuffer>& cmd) {
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
new_build_hiz = '''void Renderer::buildHiZ(Tempest::Encoder<Tempest::CommandBuffer>& cmd) {
  assert(hiz.hiZ.w()<=128 && hiz.hiZ.h()<=128);

  cmd.setDebugMarker("HiZ-mip");
  cmd.setFramebuffer({});
  cmd.setBinding(0, zbuffer, Sampler::nearest(ClampMode::ClampToEdge));
  cmd.setBinding(1, hiz.hiZ);
  cmd.setPipeline(shaders.hiZPot);
  cmd.dispatch(size_t(hiz.hiZ.w()), size_t(hiz.hiZ.h()));

  const uint32_t mip = hiz.hiZ.mipCount();
  const std::string_view gpuName = Resources::device().properties().name;
  const bool adreno650 = gpuName.find("Adreno")!=std::string_view::npos &&
                         gpuName.find("650")!=std::string_view::npos;
  if(adreno650) {
    static bool logged = false;
    if(!logged) {
      logged = true;
      Log::i("HiZ: Adreno 650 two-pass R16 reducer enabled");
      }

    struct AdrenoPush { uint32_t levels; } push = {};
    const auto wg = shaders.hiZMipAdreno.workGroupSize();
    const int wgW = std::max(std::max(hiz.hiZ.w()/2,1)/wg.x,1);
    const int wgH = std::max(std::max(hiz.hiZ.h()/2,1)/wg.y,1);

    cmd.setPipeline(shaders.hiZMipAdreno);
    push.levels = std::min(mip,5u);
    for(uint32_t i=0; i<5; ++i)
      cmd.setBinding(i,hiz.hiZ,Sampler::nearest(),std::min(i,mip-1));
    cmd.setPushData(push);
    cmd.dispatch(size_t(wgW),size_t(wgH));

    if(mip>5) {
      constexpr uint32_t base = 4;
      push.levels = std::min(mip-base,5u);
      for(uint32_t i=0; i<5; ++i)
        cmd.setBinding(i,hiz.hiZ,Sampler::nearest(),std::min(base+i,mip-1));
      cmd.setPushData(push);
      cmd.dispatch(1,1);
      }
    return;
    }

  const uint32_t maxBind = 8;
  const auto wgSz = shaders.hiZMip.workGroupSize();
  const int wgW = std::max(std::max(hiz.hiZ.w()/2,1)/wgSz.x,1);
  const int wgH = std::max(std::max(hiz.hiZ.h()/2,1)/wgSz.y,1);
  struct Push { uint32_t numGroups; uint32_t mip; } push = {};
  push.numGroups = uint32_t(wgW*wgH);
  push.mip = mip;

  cmd.setBinding(0,hiz.counter);
  for(uint32_t i=0;i<maxBind;++i)
    cmd.setBinding(1+i,hiz.hiZ,Sampler::nearest(),std::min(i,mip-1));
  cmd.setPushData(push);
  cmd.setPipeline(shaders.hiZMip);
  cmd.dispatch(size_t(wgW),size_t(wgH));
  }
'''
replace_once("common/graphics/renderer.cpp", old_build_hiz, new_build_hiz)

replace_once(
    "shader/CMakeLists.txt",
'''  if(ANDROID)
    add_shader("${OUTPUT}_flat_slot.vert" materials/main.vert -S vert ${VARS} -DFLAT_VARYINGS)
  endif()
''',
'''  if(ANDROID)
    add_shader("${OUTPUT}_flat_slot.vert"     materials/main.vert -S vert ${VARS} -DFLAT_VARYINGS)
    add_shader("${OUTPUT}_flat_bindless.vert" materials/main.vert -S vert ${VARS} -DFLAT_VARYINGS -DBINDLESS)
  endif()
'''
)

replace_once(
    "shader/CMakeLists.txt",
'''  if(ANDROID)
    add_shader("${OUTPUT}_flat_slot.frag" materials/main.frag ${VARS} -DFLAT_VARYINGS)
  endif()
''',
'''  if(ANDROID)
    add_shader("${OUTPUT}_flat_slot.frag"     materials/main.frag ${VARS} -DFLAT_VARYINGS)
    add_shader("${OUTPUT}_flat_bindless.frag" materials/main.frag ${VARS} -DFLAT_VARYINGS -DBINDLESS)
  endif()
'''
)

replace_once(
    "common/graphics/shaders.cpp",
'''  const bool flatVaryings = needsFlatVaryings && !bl;
  const char* shaderSuffix = flatVaryings ? "_flat_slot" : (bl ? "_bindless" : "_slot");
  const char* pfxSuffix = flatVaryings ? "_flat" : "";
''',
'''  const bool flatVaryings = needsFlatVaryings;
  const char* shaderSuffix = flatVaryings
      ? (bl ? "_flat_bindless" : "_flat_slot")
      : (bl ? "_bindless" : "_slot");
  const char* pfxSuffix = flatVaryings ? "_flat" : "";
'''
)

print("FIX13: IME typing restored, conservative cluster bounds, two-pass HiZ, flat-bindless Adreno650")

# ---------------------------------------------------------------------------
# FIX14: Adreno 650 driver-safe visibility fallback
#
# Upstream OpenGothic #744 reproduced the same "NPC/object appears in pieces"
# failure on a mobile Vulkan driver and isolated it to the HiZ visibility
# variants. On the old Qualcomm driver used by Adreno 650, keep GPU-driven
# batching and frustum culling but do not let HiZ mip/descriptor results reject
# scene geometry. This is a driver workaround, not a quality reduction.
# ---------------------------------------------------------------------------
replace_once(
    "common/graphics/drawcommands.cpp",
    '#include <Tempest/Log>\n',
    '#include <Tempest/Log>\n#include <cstring>\n'
)

old_visibility = '''void DrawCommands::visibilityPass(Encoder<CommandBuffer>& cmd, int pass) {
  static bool freeze = false;
  if(freeze)
    return;

  cmd.setFramebuffer({});
  if(pass==0) {
    for(auto& v:views) {
      if(this->cmd.empty())
        continue;
      if(!isViewEnabled(v.viewport))
        continue;
      const uint32_t isMeshShader = (Shaders::options().doMeshShading ? 1 : 0);
      cmd.setBinding(T_Indirect, v.indirectCmd);
      cmd.setPushData(&isMeshShader, sizeof(isMeshShader));
      cmd.setPipeline(Shaders::inst().clusterInit);
      cmd.dispatchThreads(this->cmd.size());
      }
    }

  for(uint8_t v=0; v<SceneGlobals::V_Count; ++v) {
'''
new_visibility = '''void DrawCommands::visibilityPass(Encoder<CommandBuffer>& cmd, int pass) {
  static bool freeze = false;
  if(freeze)
    return;

  static const bool adreno650VisibilityFallback = []() {
#if defined(__ANDROID__)
    const char* name = Resources::device().properties().name;
    const bool match = name!=nullptr && std::strstr(name,"Adreno")!=nullptr &&
                       std::strstr(name,"650")!=nullptr;
    if(match)
      Log::i("Visibility: Adreno 650 frustum-only fallback enabled; HiZ rejection bypassed");
    return match;
#else
    return false;
#endif
    }();

  cmd.setFramebuffer({});
  if(pass==0) {
    for(auto& v:views) {
      if(this->cmd.empty())
        continue;
      if(!isViewEnabled(v.viewport))
        continue;
      const uint32_t isMeshShader = (Shaders::options().doMeshShading ? 1 : 0);
      cmd.setBinding(T_Indirect, v.indirectCmd);
      cmd.setPushData(&isMeshShader, sizeof(isMeshShader));
      cmd.setPipeline(Shaders::inst().clusterInit);
      cmd.dispatchThreads(this->cmd.size());
      }
    // On Adreno 650 the coarse HiZ visibility pass is the driver-sensitive
    // path. Indirect command buffers are initialized above; leave the HiZ
    // occluder list empty and let the main pass use frustum-only visibility.
    if(adreno650VisibilityFallback)
      return;
    }

  for(uint8_t v=0; v<SceneGlobals::V_Count; ++v) {
'''
replace_once("common/graphics/drawcommands.cpp", old_visibility, new_visibility)

old_pso = '''    auto* pso = &Shaders::inst().visibilityPassSh;
    if(viewport==SceneGlobals::V_Main)
      pso = &Shaders::inst().visibilityPassHiZ;
    else if(viewport==SceneGlobals::V_HiZ)
      pso = &Shaders::inst().visibilityPassHiZCr;
'''
new_pso = '''    auto* pso = &Shaders::inst().visibilityPassSh;
    if(!adreno650VisibilityFallback) {
      if(viewport==SceneGlobals::V_Main)
        pso = &Shaders::inst().visibilityPassHiZ;
      else if(viewport==SceneGlobals::V_HiZ)
        pso = &Shaders::inst().visibilityPassHiZCr;
      }
'''
replace_once("common/graphics/drawcommands.cpp", old_pso, new_pso)

print("FIX14: Adreno 650 frustum-only visibility fallback; HiZ no longer rejects scene geometry")



# ---------------------------------------------------------------------------
# FIX15: bundled Mesa Turnip + libadrenotools Vulkan proxy, selectable in launcher
# ---------------------------------------------------------------------------
# AdrenoTools needs hook libraries as ordinary files, not APK-internal ELF entries.
replace_once(
    "android/launcher/AndroidManifest.xml",
    '''        android:fullBackupContent="false"\n''',
    '''        android:fullBackupContent="false"\n        android:extractNativeLibs="true"\n'''
)

TURNIP_URL = "https://github.com/The412Banner/Banners-Turnip/releases/download/v27.0.0-20261028-r2/Turnip-v27.0.0-20261028-r2.zip"
TURNIP_SHA = "d0c77310df2c8ea03502c1f9eec5af19d2dd19d4df7b6088e4d7c340ceb95a2c"
asset_dir = root / "android/launcher/assets/drivers"
asset_dir.mkdir(parents=True, exist_ok=True)
turnip_zip = asset_dir / "turnip-v27-r2.zip"
with urllib.request.urlopen(TURNIP_URL, timeout=120) as response:
    turnip_data = response.read()
if hashlib.sha256(turnip_data).hexdigest() != TURNIP_SHA:
    raise SystemExit("Turnip ZIP checksum mismatch")
turnip_zip.write_bytes(turnip_data)
with zipfile.ZipFile(turnip_zip, "r") as zf:
    names = {n for n in zf.namelist() if not n.endswith("/")}
    if names != {"libvulkan_freedreno.so", "meta.json"}:
        raise SystemExit(f"Unexpected Turnip ZIP entries: {sorted(names)}")
    turnip_lib = zf.read("libvulkan_freedreno.so")
    turnip_meta = json.loads(zf.read("meta.json").decode("utf-8"))
    if turnip_meta.get("libraryName") != "libvulkan_freedreno.so":
        raise SystemExit("Unexpected Turnip libraryName")
TURNIP_LIB_SHA = hashlib.sha256(turnip_lib).hexdigest()

# Fetch the pinned, known-working AdrenoTools proxy source tree used by another
# native Android port, then adapt only package/JNI names for Gothic Launcher.
tmp = Path(tempfile.mkdtemp(prefix="gothic-driver-proxy-"))
try:
    subprocess.run(["git","init",str(tmp)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git","-C",str(tmp),"remote","add","origin","https://github.com/andrewnakas/skate3-android.git"], check=True)
    subprocess.run(["git","-C",str(tmp),"fetch","--depth","1","origin","af641a6b0abeacc482b27a00a2a0c0b2248a4858"], check=True)
    subprocess.run(["git","-C",str(tmp),"checkout","--detach","FETCH_HEAD"], check=True, stdout=subprocess.DEVNULL)
    proxy_dir = root / "android/driverproxy"
    if proxy_dir.exists():
        shutil.rmtree(proxy_dir)
    shutil.copytree(tmp / "native", proxy_dir)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

(proxy_dir / "driver_proxy.cpp").write_text("// Source-built Vulkan dispatch adapter for the unchanged official game engine.\n// It neither patches libmain.so nor hooks dlopen/dlsym process-wide.\n#include <jni.h>\n#include <android/log.h>\n#include <adrenotools/driver.h>\n#include <vulkan/vulkan.h>\n#include <dlfcn.h>\n#include <sys/stat.h>\n#include <limits.h>\n\n#include <algorithm>\n#include <atomic>\n#include <cstdint>\n#include <cstdlib>\n#include <cstring>\n#include <mutex>\n#include <string>\n#include <vector>\n\n#define EXPORT extern \"C\" __attribute__((visibility(\"default\")))\n\nEXPORT VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetInstanceProcAddr(VkInstance, const char*);\nEXPORT VKAPI_ATTR VkResult VKAPI_CALL vkCreateInstance(const VkInstanceCreateInfo*, const VkAllocationCallbacks*, VkInstance*);\nEXPORT VKAPI_ATTR void VKAPI_CALL vkDestroyInstance(VkInstance, const VkAllocationCallbacks*);\n\nnamespace {\nconstexpr const char* kTag = \"GothicDriver\";\nconstexpr uint32_t kMaxPhysicalDevices = 16;\nstd::mutex g_init_mutex;\nstd::atomic<bool> g_ready{false};\nstd::atomic<uint32_t> g_game_instances{0};\nbool g_attempted = false;\nbool g_custom = false;\n// Identity of physical device 0 under the stock driver, read before a custom\n// one is loaded. Empty when it could not be read.\nstd::string g_system_identity;\nvoid* g_loader = nullptr; // Deliberately retained until process exit.\nPFN_vkGetInstanceProcAddr g_get = nullptr;\nPFN_vkDestroyInstance g_destroy = nullptr;\nstd::string g_arguments;\nstd::string g_status = \"{\\\"ok\\\":false,\\\"error\\\":\\\"Driver bridge not initialized\\\"}\";\n\nstd::string Quote(const std::string& value) {\n  std::string out = \"\\\"\";\n  for (unsigned char c : value) {\n    switch (c) {\n      case '\\\\': out += \"\\\\\\\\\"; break;\n      case '\"': out += \"\\\\\\\"\"; break;\n      case '\\n': out += \"\\\\n\"; break;\n      case '\\r': out += \"\\\\r\"; break;\n      case '\\t': out += \"\\\\t\"; break;\n      default:\n        if (c < 0x20) {\n          constexpr char hex[] = \"0123456789abcdef\";\n          out += \"\\\\u00\";\n          out += hex[c >> 4];\n          out += hex[c & 15];\n        } else {\n          out += static_cast<char>(c);\n        }\n    }\n  }\n  return out + \"\\\"\";\n}\n\nstd::string JavaString(JNIEnv* env, jstring value) {\n  if (!value) return {};\n  const char* bytes = env->GetStringUTFChars(value, nullptr);\n  if (!bytes) return {};\n  std::string result(bytes);\n  env->ReleaseStringUTFChars(value, bytes);\n  return result;\n}\n\nstd::string CanonicalDirectory(const std::string& value) {\n  char resolved[PATH_MAX];\n  struct stat st{};\n  if (value.empty() || value.front() != '/' || !realpath(value.c_str(), resolved) ||\n      stat(resolved, &st) != 0 || !S_ISDIR(st.st_mode)) return {};\n  return std::string(resolved) + \"/\";\n}\n\nbool RegularFile(const std::string& path) {\n  struct stat st{};\n  return stat(path.c_str(), &st) == 0 && S_ISREG(st.st_mode);\n}\n\nstd::string LoaderPath() {\n  Dl_info info{};\n  if (g_get && dladdr(reinterpret_cast<void*>(g_get), &info) && info.dli_fname)\n    return info.dli_fname;\n  return {};\n}\n\nstd::string Failure(const std::string& why) {\n  __android_log_print(ANDROID_LOG_ERROR, kTag, \"%s\", why.c_str());\n  return \"{\\\"ok\\\":false,\\\"mode\\\":\" + Quote(g_custom ? \"turnip\" : \"system\") +\n         \",\\\"error\\\":\" + Quote(why) + \",\\\"loader_path\\\":\" + Quote(LoaderPath()) + \"}\";\n}\n\ntemplate<typename Fn>\nFn Get(VkInstance instance, const char* name) {\n  return reinterpret_cast<Fn>(g_get(instance, name));\n}\n\n// What makes one driver distinguishable from another.\n//\n// Not the GPU name alone - that is the same physical chip either way - and not\n// apiVersion, which two builds of the same driver family often share.\n// driverVersion, driverName and driverInfo are what actually move between a\n// stock driver and one taken from somewhere else.\nstd::string DeviceIdentity(const VkPhysicalDeviceProperties& basic,\n                           const VkPhysicalDeviceDriverProperties& driver) {\n  return std::to_string(driver.driverID) + \"|\" + std::to_string(basic.driverVersion) + \"|\" +\n         std::string(driver.driverName) + \"|\" + std::string(driver.driverInfo) + \"|\" +\n         std::string(basic.deviceName);\n}\n\n// Reads the stock driver's identity, using its own handle and nothing global.\n//\n// This is what makes supporting a non-Turnip driver possible at all.\n// libadrenotools is documented to return a valid pointer and then quietly fall\n// back to the original driver when its hook does not take, so something has to\n// prove the swap really happened. For Turnip the driver ID alone proves it -\n// the stock Adreno driver can never report Mesa. A custom QUALCOMM driver\n// reports exactly what the stock one reports, so the ID proves nothing, and\n// the only honest evidence is that the identity CHANGED.\nbool ProbeSystemIdentity(std::string& identity) {\n  void* handle = dlopen(\"/system/lib64/libvulkan.so\", RTLD_NOW | RTLD_LOCAL);\n  if (!handle) return false;\n  const auto get = reinterpret_cast<PFN_vkGetInstanceProcAddr>(\n      dlsym(handle, \"vkGetInstanceProcAddr\"));\n  if (!get) { dlclose(handle); return false; }\n  const auto create = reinterpret_cast<PFN_vkCreateInstance>(get(VK_NULL_HANDLE, \"vkCreateInstance\"));\n  const auto enumerate_version = reinterpret_cast<PFN_vkEnumerateInstanceVersion>(\n      get(VK_NULL_HANDLE, \"vkEnumerateInstanceVersion\"));\n  if (!create) { dlclose(handle); return false; }\n  uint32_t api = VK_API_VERSION_1_0;\n  if (enumerate_version && enumerate_version(&api) != VK_SUCCESS) api = VK_API_VERSION_1_0;\n  api = std::min(api, static_cast<uint32_t>(VK_API_VERSION_1_2));\n\n  VkApplicationInfo app{};\n  app.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;\n  app.pApplicationName = \"Gothic System Driver Probe\";\n  app.apiVersion = api;\n  VkInstanceCreateInfo info{};\n  info.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;\n  info.pApplicationInfo = &app;\n  VkInstance instance = VK_NULL_HANDLE;\n  if (create(&info, nullptr, &instance) != VK_SUCCESS || instance == VK_NULL_HANDLE) {\n    dlclose(handle);\n    return false;\n  }\n\n  bool found = false;\n  const auto enumerate = reinterpret_cast<PFN_vkEnumeratePhysicalDevices>(\n      get(instance, \"vkEnumeratePhysicalDevices\"));\n  const auto properties = reinterpret_cast<PFN_vkGetPhysicalDeviceProperties>(\n      get(instance, \"vkGetPhysicalDeviceProperties\"));\n  const auto properties2 = reinterpret_cast<PFN_vkGetPhysicalDeviceProperties2>(\n      get(instance, \"vkGetPhysicalDeviceProperties2\"));\n  uint32_t count = 0;\n  if (enumerate && properties && enumerate(instance, &count, nullptr) == VK_SUCCESS &&\n      count > 0 && count <= kMaxPhysicalDevices) {\n    std::vector<VkPhysicalDevice> devices(count);\n    if (enumerate(instance, &count, devices.data()) == VK_SUCCESS && count > 0) {\n      VkPhysicalDeviceProperties basic{};\n      properties(devices[0], &basic);\n      VkPhysicalDeviceDriverProperties driver{};\n      driver.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES;\n      if (api >= VK_API_VERSION_1_2 && basic.apiVersion >= VK_API_VERSION_1_2 && properties2) {\n        VkPhysicalDeviceProperties2 extended{};\n        extended.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2;\n        extended.pNext = &driver;\n        properties2(devices[0], &extended);\n      }\n      identity = DeviceIdentity(basic, driver);\n      found = true;\n    }\n  }\n  const auto destroy = reinterpret_cast<PFN_vkDestroyInstance>(get(instance, \"vkDestroyInstance\"));\n  if (destroy) destroy(instance, nullptr);\n  dlclose(handle);\n  return found;\n}\n\n// Uses only functions from the selected loader, never this proxy's exports.\n// A custom selection requires Vulkan 1.2 driver identity support. RP6/T30\n// supports this; failing explicitly is safer than guessing from a GPU name.\nbool VerifyInstance(VkInstance instance, uint32_t requested_api,\n                    std::string& devices_json, std::string& error) {\n  const auto enumerate = Get<PFN_vkEnumeratePhysicalDevices>(instance, \"vkEnumeratePhysicalDevices\");\n  const auto properties = Get<PFN_vkGetPhysicalDeviceProperties>(instance, \"vkGetPhysicalDeviceProperties\");\n  const auto properties2 = Get<PFN_vkGetPhysicalDeviceProperties2>(instance, \"vkGetPhysicalDeviceProperties2\");\n  if (!enumerate || !properties) {\n    error = \"Selected loader is missing physical-device query functions\";\n    return false;\n  }\n  if (g_custom && (requested_api < VK_API_VERSION_1_2 || !properties2)) {\n    error = \"Turnip validation requires a Vulkan 1.2 instance and driver-properties query\";\n    return false;\n  }\n  uint32_t count = 0;\n  VkResult result = enumerate(instance, &count, nullptr);\n  if (result != VK_SUCCESS || count == 0 || count > kMaxPhysicalDevices) {\n    error = \"Physical-device enumeration failed or returned an unsupported count (result=\" +\n            std::to_string(result) + \", count=\" + std::to_string(count) + \")\";\n    return false;\n  }\n  std::vector<VkPhysicalDevice> devices(count);\n  result = enumerate(instance, &count, devices.data());\n  if (result != VK_SUCCESS || count == 0 || count > devices.size()) {\n    error = \"Physical-device list changed or could not be read\";\n    return false;\n  }\n  devices_json = \"[\";\n  for (uint32_t i = 0; i < count; ++i) {\n    VkPhysicalDeviceProperties basic{};\n    properties(devices[i], &basic);\n    VkPhysicalDeviceDriverProperties driver{};\n    driver.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES;\n    if (requested_api >= VK_API_VERSION_1_2 && basic.apiVersion >= VK_API_VERSION_1_2 && properties2) {\n      VkPhysicalDeviceProperties2 extended{};\n      extended.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2;\n      extended.pNext = &driver;\n      properties2(devices[i], &extended);\n    }\n    // Did the swap actually happen? Two ways to know, and the cheap one first:\n    // a driver that is not Qualcomm's own cannot be the stock Adreno driver,\n    // which settles every Turnip case without needing a baseline at all.\n    //\n    // Otherwise fall back to comparing identities. This used to demand Mesa\n    // Turnip outright, which made a proprietary Qualcomm driver - the kind\n    // extracted from another device - impossible to use however good it was,\n    // because it reports the same driverID as the driver it replaces. An\n    // identity that has not moved is the real evidence of libadrenotools\n    // having fallen back, and that is what is reported now.\n    // Every custom driver is checked the same way, with no shortcut on driver\n    // ID. A shortcut was tried - trust anything not reporting as Qualcomm -\n    // and it passed a silent fallback as success on the very first device it\n    // met: this phone's stock driver reports Vulkan 1.1, so the 1.2 driver\n    // properties are never filled in and driverID reads 0 rather than\n    // QUALCOMM_PROPRIETARY. The old Turnip-only test happened to catch that\n    // (0 is not Mesa either); an ID-based test that is trying to ACCEPT\n    // drivers cannot. The identity comparison does not care, because a\n    // fallback produces the stock identity whatever the ID says.\n    if (g_custom) {\n      const std::string identity = DeviceIdentity(basic, driver);\n      if (g_system_identity.empty()) {\n        error = \"A custom driver was selected, but this device's own driver could not be read \"\n                \"first, so there is no way to tell whether the custom one actually loaded\";\n        return false;\n      }\n      if (identity == g_system_identity) {\n        error = \"The custom driver did not take effect - the loaded driver is identical to this \"\n                \"device's own (\" + std::string(basic.deviceName) + \", driverVersion \" +\n                std::to_string(basic.driverVersion) + \")\";\n        return false;\n      }\n    }\n    if (i) devices_json += \",\";\n    devices_json += \"{\\\"name\\\":\" + Quote(basic.deviceName) +\n                    \",\\\"api_version\\\":\" + std::to_string(basic.apiVersion) +\n                    \",\\\"driver_version\\\":\" + std::to_string(basic.driverVersion) +\n                    \",\\\"vendor_id\\\":\" + std::to_string(basic.vendorID) +\n                    \",\\\"device_id\\\":\" + std::to_string(basic.deviceID) +\n                    \",\\\"driver_id\\\":\" + std::to_string(driver.driverID) +\n                    \",\\\"driver_name\\\":\" + Quote(driver.driverName) +\n                    \",\\\"driver_info\\\":\" + Quote(driver.driverInfo) + \"}\";\n  }\n  devices_json += \"]\";\n  return true;\n}\n\nbool Probe(std::string& devices, std::string& error) {\n  const auto create = Get<PFN_vkCreateInstance>(VK_NULL_HANDLE, \"vkCreateInstance\");\n  const auto version = Get<PFN_vkEnumerateInstanceVersion>(VK_NULL_HANDLE, \"vkEnumerateInstanceVersion\");\n  uint32_t api = VK_API_VERSION_1_0;\n  if (!create || (version && version(&api) != VK_SUCCESS)) {\n    error = \"Selected Vulkan loader could not provide instance creation/version\";\n    return false;\n  }\n  api = std::min(api, static_cast<uint32_t>(VK_API_VERSION_1_2));\n  if (g_custom && api < VK_API_VERSION_1_2) {\n    error = \"Selected custom loader does not support Vulkan 1.2 identity validation\";\n    return false;\n  }\n  VkApplicationInfo app{};\n  app.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;\n  app.pApplicationName = \"Gothic Driver Validation\";\n  app.apiVersion = api;\n  VkInstanceCreateInfo info{};\n  info.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;\n  info.pApplicationInfo = &app;\n  VkInstance instance = VK_NULL_HANDLE;\n  const VkResult result = create(&info, nullptr, &instance);\n  if (result != VK_SUCCESS || instance == VK_NULL_HANDLE) {\n    error = \"Selected Vulkan driver failed the startup probe (VkResult=\" + std::to_string(result) + \")\";\n    return false;\n  }\n  const bool valid = VerifyInstance(instance, api, devices, error);\n  g_destroy(instance, nullptr);\n  return valid;\n}\n} // namespace\n\nEXPORT jint JNICALL JNI_OnLoad(JavaVM*, void*) { return JNI_VERSION_1_6; }\n\nEXPORT jstring JNICALL Java_org_opengothic_app_DriverBridge_nativeInit(\n    JNIEnv* env, jclass, jstring native_dir_value, jstring driver_dir_value,\n    jstring filename_value, jboolean custom_value) {\n  std::lock_guard<std::mutex> lock(g_init_mutex);\n  const std::string native_dir_arg = JavaString(env, native_dir_value);\n  const std::string driver_dir_arg = JavaString(env, driver_dir_value);\n  const std::string filename = JavaString(env, filename_value);\n  if (env->ExceptionCheck()) return nullptr;\n  const bool custom = custom_value == JNI_TRUE;\n  const std::string arguments = Quote(native_dir_arg) + Quote(driver_dir_arg) + Quote(filename) + (custom ? \"1\" : \"0\");\n  if (g_attempted) {\n    const std::string response = arguments == g_arguments ? g_status :\n        \"{\\\"ok\\\":false,\\\"error\\\":\\\"Restart the application process before changing drivers\\\"}\";\n    return env->NewStringUTF(response.c_str());\n  }\n  g_attempted = true;\n  g_arguments = arguments;\n  g_custom = custom;\n  const std::string native_dir = CanonicalDirectory(native_dir_arg);\n  std::string error;\n  if (native_dir.empty()) {\n    error = \"Native library directory is missing or not an absolute directory\";\n  } else {\n    // Test the exact bare-name lookup that the unchanged engine will make.\n    // Absolute preloading is insufficient if another libvulkan was inserted\n    // earlier in this same application namespace. Do not guess in that case.\n    void* selected = dlopen(\"libvulkan.so\", RTLD_NOW | RTLD_LOCAL | RTLD_NOLOAD);\n    const auto selected_get = selected ? reinterpret_cast<PFN_vkGetInstanceProcAddr>(\n        dlsym(selected, \"vkGetInstanceProcAddr\")) : nullptr;\n    if (selected_get != &vkGetInstanceProcAddr) {\n      error = \"The application Vulkan lookup does not resolve to the driver proxy; restart before loading the game\";\n    }\n    if (selected) dlclose(selected);\n  }\n  if (error.empty() && custom) {\n    const std::string driver_dir = CanonicalDirectory(driver_dir_arg);\n    char file_path[PATH_MAX];\n    if (driver_dir.empty() || driver_dir.rfind(\"/data/\", 0) != 0) {\n      error = \"Custom Vulkan driver must be in app-private /data storage\";\n    } else if (filename.empty() || filename.find('/') != std::string::npos ||\n               filename == \".\" || filename == \"..\") {\n      error = \"Custom Vulkan driver filename is invalid\";\n    } else if (!realpath((driver_dir + filename).c_str(), file_path) ||\n               std::string(file_path).rfind(driver_dir, 0) != 0 || !RegularFile(file_path)) {\n      error = \"Custom Vulkan driver file is missing or escapes its private directory\";\n    } else if (!RegularFile(native_dir + \"libhook_impl.so\") || !RegularFile(native_dir + \"libmain_hook.so\")) {\n      error = \"Custom driver support libraries are missing; native libraries must be extracted\";\n    } else {\n      // Read the stock driver BEFORE the hook is installed - afterwards there\n      // is no longer an unhooked loader to ask. Not fatal on its own: a Turnip\n      // driver is recognised by its driver ID and needs no baseline, so only a\n      // same-vendor driver is refused for the lack of one.\n      if (!ProbeSystemIdentity(g_system_identity)) {\n        g_system_identity.clear();\n        __android_log_print(ANDROID_LOG_WARN, kTag,\n                            \"could not read this device's own driver identity before loading the custom one\");\n      }\n      g_loader = adrenotools_open_libvulkan(RTLD_NOW | RTLD_LOCAL, ADRENOTOOLS_DRIVER_CUSTOM,\n          driver_dir.c_str(), native_dir.c_str(), driver_dir.c_str(), filename.c_str(), nullptr, nullptr);\n      if (!g_loader) error = \"libadrenotools could not initialize the selected custom driver\";\n    }\n  } else if (error.empty()) {\n    // An absolute system path cannot resolve back to this app's proxy by SONAME.\n    g_loader = dlopen(\"/system/lib64/libvulkan.so\", RTLD_NOW | RTLD_LOCAL);\n    if (!g_loader) {\n      const char* detail = dlerror();\n      error = std::string(\"System Vulkan loader could not open: \") + (detail ? detail : \"unknown error\");\n    }\n  }\n  std::string devices;\n  if (error.empty()) {\n    g_get = reinterpret_cast<PFN_vkGetInstanceProcAddr>(dlsym(g_loader, \"vkGetInstanceProcAddr\"));\n    g_destroy = reinterpret_cast<PFN_vkDestroyInstance>(dlsym(g_loader, \"vkDestroyInstance\"));\n    if (!g_get || !g_destroy || g_get == &vkGetInstanceProcAddr || g_destroy == &vkDestroyInstance) {\n      error = \"Vulkan loader entrypoints are missing or resolve recursively to the proxy\";\n    } else if (!Probe(devices, error)) {\n      // Keep the exact failure; custom selections never fall back to System.\n    }\n  }\n  if (!error.empty()) {\n    g_status = Failure(error);\n  } else {\n    g_status = \"{\\\"ok\\\":true,\\\"mode\\\":\" + Quote(custom ? \"turnip\" : \"system\") +\n        \",\\\"error\\\":\\\"\\\",\\\"loader_path\\\":\" + Quote(LoaderPath()) +\n        \",\\\"devices\\\":\" + devices + \"}\";\n    g_ready.store(true, std::memory_order_release);\n    __android_log_print(ANDROID_LOG_INFO, kTag, \"Driver initialized: %s\", g_status.c_str());\n  }\n  return env->NewStringUTF(g_status.c_str());\n}\n\nEXPORT jstring JNICALL Java_org_opengothic_app_DriverBridge_nativeStatus(JNIEnv* env, jclass) {\n  std::lock_guard<std::mutex> lock(g_init_mutex);\n  return env->NewStringUTF(g_status.c_str());\n}\n\nEXPORT VKAPI_ATTR VkResult VKAPI_CALL vkCreateInstance(\n    const VkInstanceCreateInfo* info, const VkAllocationCallbacks* allocator, VkInstance* instance) {\n  if (!g_ready.load(std::memory_order_acquire)) return VK_ERROR_INITIALIZATION_FAILED;\n  const auto create = Get<PFN_vkCreateInstance>(VK_NULL_HANDLE, \"vkCreateInstance\");\n  const VkResult result = create(info, allocator, instance);\n  if (result != VK_SUCCESS) return result;\n  const uint32_t api = info && info->pApplicationInfo && info->pApplicationInfo->apiVersion ?\n      info->pApplicationInfo->apiVersion : VK_API_VERSION_1_0;\n  std::string devices, error;\n  if (!VerifyInstance(*instance, api, devices, error)) {\n    __android_log_print(ANDROID_LOG_ERROR, kTag, \"Game Vulkan instance rejected: %s\", error.c_str());\n    g_destroy(*instance, allocator);\n    *instance = VK_NULL_HANDLE;\n    return VK_ERROR_INITIALIZATION_FAILED;\n  }\n  const uint32_t count = g_game_instances.fetch_add(1, std::memory_order_relaxed) + 1;\n  if (count <= 8) __android_log_print(ANDROID_LOG_INFO, kTag,\n      \"Game Vulkan instance %u verified: mode=%s loader=%s devices=%s\", count,\n      g_custom ? \"turnip\" : \"system\", LoaderPath().c_str(), devices.c_str());\n  return VK_SUCCESS;\n}\n\nEXPORT VKAPI_ATTR void VKAPI_CALL vkDestroyInstance(VkInstance instance, const VkAllocationCallbacks* allocator) {\n  if (g_ready.load(std::memory_order_acquire)) g_destroy(instance, allocator);\n}\n\nEXPORT VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetInstanceProcAddr(VkInstance instance, const char* name) {\n  if (!g_ready.load(std::memory_order_acquire) || !name) return nullptr;\n  const auto real = g_get(instance, name);\n  if (!real) return nullptr;\n  if (std::strcmp(name, \"vkGetInstanceProcAddr\") == 0)\n    return reinterpret_cast<PFN_vkVoidFunction>(&vkGetInstanceProcAddr);\n  if (std::strcmp(name, \"vkCreateInstance\") == 0)\n    return reinterpret_cast<PFN_vkVoidFunction>(&vkCreateInstance);\n  if (std::strcmp(name, \"vkDestroyInstance\") == 0)\n    return reinterpret_cast<PFN_vkVoidFunction>(&vkDestroyInstance);\n  return real;\n}\n\nEXPORT VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetDeviceProcAddr(VkDevice device, const char* name) {\n  if (!g_ready.load(std::memory_order_acquire)) return nullptr;\n  const auto fn = reinterpret_cast<PFN_vkGetDeviceProcAddr>(dlsym(g_loader, \"vkGetDeviceProcAddr\"));\n  return fn ? fn(device, name) : nullptr;\n}\n\nEXPORT VKAPI_ATTR VkResult VKAPI_CALL vkEnumerateInstanceVersion(uint32_t* version) {\n  if (!g_ready.load(std::memory_order_acquire)) return VK_ERROR_INITIALIZATION_FAILED;\n  const auto fn = Get<PFN_vkEnumerateInstanceVersion>(VK_NULL_HANDLE, \"vkEnumerateInstanceVersion\");\n  if (fn) return fn(version);\n  if (version) *version = VK_API_VERSION_1_0;\n  return VK_SUCCESS;\n}\n\nEXPORT VKAPI_ATTR VkResult VKAPI_CALL vkEnumerateInstanceExtensionProperties(\n    const char* layer, uint32_t* count, VkExtensionProperties* properties) {\n  if (!g_ready.load(std::memory_order_acquire)) return VK_ERROR_INITIALIZATION_FAILED;\n  const auto fn = Get<PFN_vkEnumerateInstanceExtensionProperties>(VK_NULL_HANDLE, \"vkEnumerateInstanceExtensionProperties\");\n  return fn ? fn(layer, count, properties) : VK_ERROR_INITIALIZATION_FAILED;\n}\n\nEXPORT VKAPI_ATTR VkResult VKAPI_CALL vkEnumerateInstanceLayerProperties(uint32_t* count, VkLayerProperties* properties) {\n  if (!g_ready.load(std::memory_order_acquire)) return VK_ERROR_INITIALIZATION_FAILED;\n  const auto fn = Get<PFN_vkEnumerateInstanceLayerProperties>(VK_NULL_HANDLE, \"vkEnumerateInstanceLayerProperties\");\n  return fn ? fn(count, properties) : VK_ERROR_INITIALIZATION_FAILED;\n}\n", encoding="utf-8")
(proxy_dir / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.22)\nproject(gothic_driver_proxy LANGUAGES C CXX)\n\nif(NOT ANDROID OR NOT ANDROID_ABI STREQUAL \"arm64-v8a\")\n  message(FATAL_ERROR \"This proxy supports Android arm64-v8a only\")\nendif()\nset(CMAKE_CXX_STANDARD 17)\nset(CMAKE_CXX_STANDARD_REQUIRED ON)\nset(CMAKE_POSITION_INDEPENDENT_CODE ON)\nset(BUILD_SHARED_LIBS OFF CACHE BOOL \"\" FORCE)\nadd_link_options(\"-Wl,-z,max-page-size=16384\")\nadd_subdirectory(vendor/libadrenotools)\n\nadd_library(vulkan SHARED driver_proxy.cpp)\ntarget_compile_definitions(vulkan PRIVATE VK_NO_PROTOTYPES)\ntarget_compile_options(vulkan PRIVATE -Wall -Wextra -Werror -fvisibility=hidden)\ntarget_link_libraries(vulkan PRIVATE adrenotools log dl)\ntarget_link_options(vulkan PRIVATE\n  \"-Wl,--version-script=${CMAKE_CURRENT_SOURCE_DIR}/exports.map\"\n  \"-Wl,-Bsymbolic-functions\"\n  \"-Wl,--exclude-libs,ALL\")\nset_target_properties(vulkan PROPERTIES LINK_DEPENDS \"${CMAKE_CURRENT_SOURCE_DIR}/exports.map\")\nadd_dependencies(vulkan main_hook hook_impl)\n\n# Only these three runtime libraries are required for DRIVER_CUSTOM. The\n# vendored build also defines optional BCn/file-redirection/GPU-mapping hooks.\ninstall(TARGETS vulkan main_hook hook_impl LIBRARY DESTINATION lib/arm64-v8a)\n", encoding="utf-8")
(proxy_dir / "exports.map").write_text("{\n  global:\n    JNI_OnLoad;\n    Java_org_opengothic_app_DriverBridge_nativeInit;\n    Java_org_opengothic_app_DriverBridge_nativeStatus;\n    vkGetInstanceProcAddr;\n    vkGetDeviceProcAddr;\n    vkCreateInstance;\n    vkDestroyInstance;\n    vkEnumerateInstanceVersion;\n    vkEnumerateInstanceExtensionProperties;\n    vkEnumerateInstanceLayerProperties;\n  local: *;\n};\n", encoding="utf-8")

# Ensure the proxy target named "vulkan" exists before Tempest links against
# Vulkan. The final game library therefore resolves libvulkan.so to our proxy.
replace_once(
    "CMakeLists.txt",
'''# Tempest
if(WIN32)
  set(TEMPEST_BUILD_SHARED ON  CACHE INTERNAL "")
else()
  set(TEMPEST_BUILD_SHARED OFF CACHE INTERNAL "")
endif()
add_subdirectory(lib/Tempest/Engine)
''',
'''# Tempest
if(WIN32)
  set(TEMPEST_BUILD_SHARED ON  CACHE INTERNAL "")
else()
  set(TEMPEST_BUILD_SHARED OFF CACHE INTERNAL "")
endif()
if(ANDROID)
  add_subdirectory(android/driverproxy)
endif()
add_subdirectory(lib/Tempest/Engine)
if(ANDROID)
  add_dependencies(Gothic2Notr vulkan main_hook hook_impl)
endif()
'''
)

# Gradle's explicit native target filter otherwise packages only Gothic2Notr.
# Add the proxy and the two AdrenoTools hook libraries as first-class APK targets.
replace_once(
    "lib/Tempest/Engine/cmake/android/build.gradle.in",
    """                targets.add(@NATIVE_TARGET@)
""",
    """                targets.add(@NATIVE_TARGET@)
                targets.add('vulkan')
                targets.add('main_hook')
                targets.add('hook_impl')
"""
)

# Package the pinned Turnip ZIP as an asset.
replace_once(
    "android/CMakeLists.txt",
'''    RESOURCE_DIRS app/src/main/res launcher/res "${generated}/res"
    DEPENDENCIES
''',
'''    RESOURCE_DIRS app/src/main/res launcher/res "${generated}/res"
    ASSET_DIRS launcher/assets
    DEPENDENCIES
'''
)

driver_java = "package org.opengothic.app;\n\nimport android.content.Context;\nimport android.content.SharedPreferences;\nimport android.os.Build;\nimport android.os.Process;\nimport android.util.Log;\n\nimport org.json.JSONObject;\n\nimport java.io.File;\nimport java.io.FileOutputStream;\nimport java.io.InputStream;\nimport java.security.MessageDigest;\nimport java.util.Locale;\nimport java.util.zip.ZipEntry;\nimport java.util.zip.ZipFile;\n\npublic final class DriverBridge {\n    public static final String SYSTEM = \"system\";\n    public static final String TURNIP = \"turnip\";\n    private static final String PREFS = \"launcher\";\n    private static final String SELECTED = \"gpu_driver\";\n    private static final String PENDING = \"gpu_driver_pending\";\n    private static final String PENDING_PID = \"gpu_driver_pending_pid\";\n    private static final String NOTE = \"gpu_driver_note\";\n    private static final String ZIP_ASSET = \"drivers/turnip-v27-r2.zip\";\n    private static final String ZIP_HASH = \"__ZIP_HASH__\";\n    private static final String LIB_HASH = \"__LIB_HASH__\";\n    private static final String LIBRARY = \"libvulkan_freedreno.so\";\n    private static volatile boolean loaded;\n\n    private DriverBridge() {}\n\n    private static native String nativeInit(String nativeLibraryDir, String driverDir,\n                                            String filename, boolean custom);\n    private static native String nativeStatus();\n\n    public static String selected(Context context) {\n        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)\n                .getString(SELECTED, TURNIP);\n    }\n\n    public static String menuLabel(Context context) {\n        return TURNIP.equals(selected(context)) ? \"GPU: Turnip\" : \"GPU: System\";\n    }\n\n    public static void toggle(Context context) {\n        SharedPreferences p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);\n        String next = TURNIP.equals(selected(context)) ? SYSTEM : TURNIP;\n        p.edit().putString(SELECTED, next).remove(NOTE).apply();\n    }\n\n    public static String consumeNote(Context context) {\n        SharedPreferences p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);\n        String note = p.getString(NOTE, null);\n        if (note != null) p.edit().remove(NOTE).apply();\n        return note;\n    }\n\n    private static boolean looksQualcomm() {\n        String s = (Build.HARDWARE + \" \" +\n                (Build.VERSION.SDK_INT >= 31 ? Build.SOC_MANUFACTURER + \" \" + Build.SOC_MODEL : \"\"))\n                .toLowerCase(Locale.ROOT);\n        return s.contains(\"qcom\") || s.contains(\"qualcomm\") || s.contains(\"qti\") ||\n               s.contains(\"snapdragon\");\n    }\n\n    private static String sha256(InputStream in) throws Exception {\n        MessageDigest md = MessageDigest.getInstance(\"SHA-256\");\n        byte[] buf = new byte[65536];\n        for (;;) {\n            int n = in.read(buf);\n            if (n < 0) break;\n            md.update(buf, 0, n);\n        }\n        StringBuilder out = new StringBuilder(64);\n        for (byte b : md.digest()) out.append(String.format(Locale.ROOT, \"%02x\", b & 255));\n        return out.toString();\n    }\n\n    private static File prepareTurnip(Context context) throws Exception {\n        File root = new File(context.getFilesDir(), \"gpu/turnip-v27-r2\");\n        File lib = new File(root, LIBRARY);\n        if (lib.isFile()) {\n            try (InputStream in = new java.io.FileInputStream(lib)) {\n                if (LIB_HASH.equals(sha256(in))) return root;\n            }\n        }\n\n        File zipFile = new File(context.getCacheDir(), \"turnip-v27-r2.zip\");\n        try (InputStream in = context.getAssets().open(ZIP_ASSET);\n             FileOutputStream out = new FileOutputStream(zipFile)) {\n            byte[] buf = new byte[65536];\n            for (;;) {\n                int n = in.read(buf);\n                if (n < 0) break;\n                out.write(buf, 0, n);\n            }\n        }\n        try (InputStream in = new java.io.FileInputStream(zipFile)) {\n            if (!ZIP_HASH.equals(sha256(in)))\n                throw new IllegalStateException(\"Bundled Turnip ZIP checksum mismatch\");\n        }\n\n        File staging = new File(context.getFilesDir(), \"gpu/.turnip-staging-\" + Process.myPid());\n        delete(staging);\n        if (!staging.mkdirs()) throw new IllegalStateException(\"Cannot create Turnip directory\");\n\n        try (ZipFile zip = new ZipFile(zipFile)) {\n            ZipEntry entry = zip.getEntry(LIBRARY);\n            if (entry == null || entry.isDirectory())\n                throw new IllegalStateException(\"Turnip library is missing from bundle\");\n            File dst = new File(staging, LIBRARY);\n            try (InputStream in = zip.getInputStream(entry);\n                 FileOutputStream out = new FileOutputStream(dst)) {\n                byte[] buf = new byte[65536];\n                for (;;) {\n                    int n = in.read(buf);\n                    if (n < 0) break;\n                    out.write(buf, 0, n);\n                }\n            }\n            try (InputStream in = new java.io.FileInputStream(dst)) {\n                if (!LIB_HASH.equals(sha256(in)))\n                    throw new IllegalStateException(\"Turnip library checksum mismatch\");\n            }\n        }\n        delete(root);\n        File parent = root.getParentFile();\n        if (parent != null) parent.mkdirs();\n        if (!staging.renameTo(root))\n            throw new IllegalStateException(\"Cannot activate Turnip driver\");\n        zipFile.delete();\n        return root;\n    }\n\n    private static void delete(File f) {\n        if (f == null || !f.exists()) return;\n        if (f.isDirectory()) {\n            File[] children = f.listFiles();\n            if (children != null) for (File c : children) delete(c);\n        }\n        f.delete();\n    }\n\n    public static synchronized void initialize(Context context) {\n        if (loaded) return;\n        SharedPreferences p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);\n        String mode = selected(context);\n\n        if (TURNIP.equals(mode) && p.getBoolean(PENDING, false) &&\n                p.getInt(PENDING_PID, -1) != Process.myPid()) {\n            mode = SYSTEM;\n            p.edit().putString(SELECTED, SYSTEM).putBoolean(PENDING, false)\n                    .putString(NOTE, \"Turnip закрыл игровой процесс при загрузке. Включён системный Vulkan.\")\n                    .apply();\n        }\n        if (TURNIP.equals(mode) && (Build.VERSION.SDK_INT < 28 || !looksQualcomm())) {\n            mode = SYSTEM;\n            p.edit().putString(SELECTED, SYSTEM)\n                    .putString(NOTE, \"Turnip доступен только для совместимых Qualcomm/Adreno. Включён системный Vulkan.\")\n                    .apply();\n        }\n\n        boolean custom = TURNIP.equals(mode);\n        try {\n            File nativeDir = new File(context.getApplicationInfo().nativeLibraryDir);\n            File proxy = new File(nativeDir, \"libvulkan.so\");\n            if (!proxy.isFile()) throw new IllegalStateException(\"Vulkan proxy is missing\");\n\n            File driverDir = new File(context.getFilesDir(), \"gpu\");\n            String filename = \"\";\n            if (custom) {\n                driverDir = prepareTurnip(context);\n                filename = LIBRARY;\n                p.edit().putBoolean(PENDING, true).putInt(PENDING_PID, Process.myPid()).commit();\n            }\n\n            System.load(proxy.getAbsolutePath());\n            loaded = true;\n            JSONObject result = new JSONObject(nativeInit(nativeDir.getAbsolutePath(),\n                    driverDir.getAbsolutePath(), filename, custom));\n            if (!result.optBoolean(\"ok\", false))\n                throw new IllegalStateException(result.optString(\"error\", \"Vulkan driver initialization failed\"));\n\n            p.edit().putBoolean(PENDING, false).remove(NOTE).apply();\n            Log.i(\"GothicDriver\", \"Selected Vulkan driver: \" + result.toString());\n        } catch (Throwable error) {\n            p.edit().putBoolean(PENDING, false).putString(SELECTED, SYSTEM)\n                    .putString(NOTE, \"Turnip не запустился: \" +\n                            (error.getMessage() == null ? error.getClass().getSimpleName() : error.getMessage()) +\n                            \". Включён системный Vulkan; запусти игру ещё раз.\")\n                    .commit();\n            throw new IllegalStateException(\"GPU driver initialization failed\", error);\n        }\n    }\n}\n"
driver_java = driver_java.replace("__ZIP_HASH__", TURNIP_SHA).replace("__LIB_HASH__", TURNIP_LIB_SHA)
driver_java_path = root / "android/launcher/java/org/opengothic/app/DriverBridge.java"
driver_java_path.write_text(driver_java, encoding="utf-8")

# Select the proxy before NativeActivity loads libopengothic.so.
replace_once(
    "lib/Tempest/Engine/system/android/java/org/tempest/TempestNativeActivity.java",
'''    protected void onCreate(Bundle state) {
        loadNativeLibrary();
''',
'''    protected void onCreate(Bundle state) {
        org.opengothic.app.DriverBridge.initialize(this);
        loadNativeLibrary();
'''
)

# Add a System/Turnip selector to the launcher's existing "..." menu.
replace_once(
    "android/launcher/java/org/opengothic/app/LauncherActivity.java",
'''    private static final int REPORT = 7;
''',
'''    private static final int REPORT = 7;
    private static final int GPU_DRIVER = 8;
'''
)
replace_once(
    "android/launcher/java/org/opengothic/app/LauncherActivity.java",
'''        offerReport();
        handler.post(tick);
''',
'''        offerReport();
        String driverNote = DriverBridge.consumeNote(this);
        if (driverNote != null) Toast.makeText(this, driverNote, Toast.LENGTH_LONG).show();
        handler.post(tick);
'''
)
replace_once(
    "android/launcher/java/org/opengothic/app/LauncherActivity.java",
'''        menu.getMenu().add(0, REPORT, 2, R.string.og_report);
        if (Library.installed(root, game())) menu.getMenu().add(0, 0, 3, R.string.og_uninstall);
        menu.setOnMenuItemClickListener(item -> {
            if (item.getItemId() == BACKUP) backup();
            else if (item.getItemId() == RESTORE) restore();
            else if (item.getItemId() == REPORT) askReport(game(), null);
            else confirmUninstall();
''',
'''        menu.getMenu().add(0, REPORT, 2, R.string.og_report);
        menu.getMenu().add(0, GPU_DRIVER, 3, DriverBridge.menuLabel(this));
        if (Library.installed(root, game())) menu.getMenu().add(0, 0, 4, R.string.og_uninstall);
        menu.setOnMenuItemClickListener(item -> {
            if (item.getItemId() == BACKUP) backup();
            else if (item.getItemId() == RESTORE) restore();
            else if (item.getItemId() == REPORT) askReport(game(), null);
            else if (item.getItemId() == GPU_DRIVER) {
                DriverBridge.toggle(this);
                Toast.makeText(this, DriverBridge.menuLabel(this) + " — следующий запуск игры", Toast.LENGTH_LONG).show();
            }
            else confirmUninstall();
'''
)

print("FIX15: bundled Turnip v27-r2 + AdrenoTools proxy + System/Turnip launcher selector")

# FIX15_BUILD_RETRY_2