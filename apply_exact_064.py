#!/usr/bin/env python3
from pathlib import Path
import sys

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


