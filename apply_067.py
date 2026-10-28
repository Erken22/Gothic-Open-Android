#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()

def replace_once(rel, old, new):
    p = root / rel
    s = p.read_text(encoding="utf-8")
    if old not in s:
        raise SystemExit(f"anchor not found in {rel}: {old[:160]!r}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")

# FIX16 / OpenGothic 0.6.7
# Keep upstream Android rendering/lifecycle changes intact.
# Only add Direct Folder support for an existing Gothic installation.

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
        // game.txt remains only the save/settings namespace used by 0.6.7.
        try (FileOutputStream out = new FileOutputStream(new File(root, "game.txt"))) {
            out.write((game().folder + "\\n").getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            message(e.getMessage());
            return;
        }

        // The engine reads this optional absolute path before the normal
        // app-private <root>/<game> path. Keeping it separate avoids breaking
        // 0.6.7's per-game User directory and save/settings isolation.
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

replace_once(
    "android/launcher/res/values-de/og_strings.xml",
    '<string name="og_import_zip">ZIP importieren</string>',
    '<string name="og_import_zip">Spielordner auswählen</string>'
)
replace_once(
    "android/launcher/res/values-pl/og_strings.xml",
    '<string name="og_import_zip">Importuj ZIP</string>',
    '<string name="og_import_zip">Wybierz folder gry</string>'
)

replace_once(
    "android/launcher/res/values/og_strings.xml",
    '    <string name="og_err_open_archive">Cannot open the archive.</string>\n',
    '    <string name="og_err_open_archive">Cannot open the archive.</string>\n'
    '    <string name="og_err_direct_folder">Select the Gothic game root containing Data and _work.</string>\n'
    '    <string name="og_err_direct_primary">Select a folder in the phone internal shared storage.</string>\n'
)
replace_once(
    "android/launcher/res/values-ru/og_strings.xml",
    '    <string name="og_err_open_archive">Не удалось открыть архив.</string>\n',
    '    <string name="og_err_open_archive">Не удалось открыть архив.</string>\n'
    '    <string name="og_err_direct_folder">Выберите корневую папку Gothic, содержащую Data и _work.</string>\n'
    '    <string name="og_err_direct_primary">Выберите папку во внутренней общей памяти телефона.</string>\n'
)

replace_once(
    "android/launcher/res/values-de/og_strings.xml",
    '    <string name="og_err_open_archive">Das Archiv konnte nicht geöffnet werden.</string>\n',
    '    <string name="og_err_open_archive">Das Archiv konnte nicht geöffnet werden.</string>\n'
    '    <string name="og_err_direct_folder">Wähle den Gothic-Spielordner mit Data und _work aus.</string>\n'
    '    <string name="og_err_direct_primary">Wähle einen Ordner im gemeinsamen internen Speicher des Telefons aus.</string>\n'
)
replace_once(
    "android/launcher/res/values-pl/og_strings.xml",
    '    <string name="og_err_open_archive">Nie udało się otworzyć archiwum.</string>\n',
    '    <string name="og_err_open_archive">Nie udało się otworzyć archiwum.</string>\n'
    '    <string name="og_err_direct_folder">Wybierz główny folder gry Gothic zawierający Data i _work.</string>\n'
    '    <string name="og_err_direct_primary">Wybierz folder we współdzielonej pamięci wewnętrznej telefonu.</string>\n'
)

# Engine side: if launcher wrote game-path.txt, use the absolute installation
# path directly. game.txt remains a short game ID for save/settings separation.
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
  std::ifstream file(std::filesystem::path(applicationSupportDirectory())/"game-path.txt");
  std::string direct;
  std::getline(file,direct);
  while(!direct.empty() && std::isspace(uint8_t(direct.back())))
    direct.pop_back();
  if(!direct.empty()) {
    std::filesystem::path path(direct);
    std::error_code ec;
    if(path.is_absolute() && std::filesystem::is_directory(path,ec) && !ec)
      return path.u16string();
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
# FIX17: Adreno 650 driver-safe visibility fallback on top of upstream 0.6.7.
#
# Keep upstream 0.6.7 Adreno fixes (bindless disabled, flattened varyings),
# frame pacing and lifecycle. Only bypass HiZ rejection on Adreno 650:
# cluster initialization and GPU-driven indirect draws remain active, but the
# main visibility pass uses frustum-only culling so false HiZ rejection cannot
# make the hero, NPCs, walls or objects disappear in pieces.
# ---------------------------------------------------------------------------
replace_once(
    "common/graphics/drawcommands.cpp",
    '#include <Tempest/Log>\n',
    '#include <Tempest/Log>\n#include <string_view>\n'
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
    const std::string_view name = Resources::device().properties().name;
    const bool match = name.find("Adreno")!=std::string_view::npos &&
                       name.find("650")!=std::string_view::npos;
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

print("FIX17 0.6.7: Adreno 650 frustum-only visibility fallback applied")



# ---------------------------------------------------------------------------
# FIX18: hybrid Adreno 650 visibility + Android CMAA2.
#
# Keep FIX17's safety for every instanced object (hero/NPC/vobs): instances
# never use HiZ rejection. Re-enable the HiZ pipeline only so distant/small
# landscape clusters can be rejected conservatively. Large on-screen world
# geometry is also protected from HiZ rejection. This regains some occlusion
# without returning the object/character breakage seen before FIX17.
# ---------------------------------------------------------------------------

# Allow pass 0 to build the landscape HiZ pyramid again.
replace_once(
    "common/graphics/drawcommands.cpp",
    '''    if(adreno650VisibilityFallback)
      return;
''',
    '''    // FIX18: keep building HiZ; the shader itself only allows conservative
    // rejection for small landscape clusters on Adreno 650.
'''
)

# Use the HiZ variants again. The shader limits actual rejection on Adreno 650.
replace_once(
    "common/graphics/drawcommands.cpp",
    '''    auto* pso = &Shaders::inst().visibilityPassSh;
    if(!adreno650VisibilityFallback) {
      if(viewport==SceneGlobals::V_Main)
        pso = &Shaders::inst().visibilityPassHiZ;
      else if(viewport==SceneGlobals::V_HiZ)
        pso = &Shaders::inst().visibilityPassHiZCr;
      }
''',
    '''    auto* pso = &Shaders::inst().visibilityPassSh;
    if(viewport==SceneGlobals::V_Main)
      pso = &Shaders::inst().visibilityPassHiZ;
    else if(viewport==SceneGlobals::V_HiZ)
      pso = &Shaders::inst().visibilityPassHiZCr;
'''
)

replace_once(
    "common/graphics/drawcommands.cpp",
    'Log::i("Visibility: Adreno 650 frustum-only fallback enabled; HiZ rejection bypassed");',
    'Log::i("Visibility: Adreno 650 hybrid mode enabled; instances frustum-only, conservative landscape HiZ");'
)

# Conservative HiZ footprint and depth margin.
replace_once(
    "shader/materials/visibility_pass.comp",
    '''  ibbox[0] = clamp(ibbox[0], ivec2(0), hiZsize - ivec2(1));
  ibbox[1] = clamp(ibbox[1], ivec2(0), hiZsize - ivec2(1));

  float bz      = packHiZ(depthMin);
  float z       = hiZFetch(hiZ, ibbox);
  if(bz > z)
    return false;
''',
    '''  ibbox[0] = clamp(ibbox[0] - ivec2(2), ivec2(0), hiZsize - ivec2(1));
  ibbox[1] = clamp(ibbox[1] + ivec2(2), ivec2(0), hiZsize - ivec2(1));

  float bz      = packHiZ(depthMin);
  float z       = hiZFetch(hiZ, ibbox);
  const float conservativeBias = 0.01;
  if(bz > z + conservativeBias)
    return false;
'''
)

# On Adreno 650 only small landscape clusters can be HiZ-rejected.
# Every instanced object and large/near world surface stays frustum-only.
replace_once(
    "shader/materials/visibility_pass.comp",
    '''#if defined(HIZ)
  if(!hiZTest(aabb, depthMin))
    return;
#endif
''',
    '''#if defined(HIZ)
  bool allowHiZReject = true;
#if defined(__ANDROID__)
  if(cluster.instanceId!=0xFFFFFFFF) {
    allowHiZReject = false;
    }
  else {
    const vec2 boxPx = max((aabb.zw-aabb.xy)*scene.screenRes, vec2(0));
    // Never occlusion-reject large nearby world surfaces. Only relatively
    // small/far landscape clusters are eligible for the driver-sensitive test.
    if(boxPx.x*boxPx.y >= 8192.0)
      allowHiZReject = false;
    }
#endif
  if(allowHiZReject && !hiZTest(aabb, depthMin))
    return;
#endif
'''
)

# CMAA2 is present in 0.6.7 but disabled by default. Preset 1 is the light
# Android default; PC/default command-line behaviour remains unchanged.
replace_once(
    "common/commandline.h",
    '    uint32_t            aaPresetId = 0;\n',
    '''#if defined(__ANDROID__)
    uint32_t            aaPresetId = 1;
#else
    uint32_t            aaPresetId = 0;
#endif
'''
)

print("FIX18 0.6.7: hybrid landscape HiZ + frustum-only instances + Android CMAA2 preset 1")

