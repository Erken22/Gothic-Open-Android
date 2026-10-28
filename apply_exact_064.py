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
for old in [
    'name.find("Adreno")!=std::string_view::npos && name.find("610")!=std::string_view::npos'
]:
    new = 'name.find("Adreno")!=std::string_view::npos && (name.find("610")!=std::string_view::npos || name.find("650")!=std::string_view::npos)'
    # occurs twice in shaders.cpp: bindless and flat varyings.
    p = root / "common/graphics/shaders.cpp"
    s = p.read_text(encoding="utf-8")
    if s.count(old) != 2:
        raise SystemExit(f"expected two Adreno 610 checks, found {s.count(old)}")
    p.write_text(s.replace(old, new), encoding="utf-8")

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
  // Android IME input is text editing, not a physical held key. Widgets edit
  // on key-down and their key-up handler is empty.
  keys.push_back({keyCode,code,true});
  }
'''
replace_once("lib/Tempest/Engine/system/api/androidapi.cpp", old_push, new_push)

# ---------------------------------------------------------------------------
# Graphics correctness: keep HiZ/occlusion enabled, but make it conservative.
# R16 quantization plus old Adreno sampling can falsely reject geometry.
# The pyramid is tiny (<=128x128), so R32F has negligible memory cost.
# ---------------------------------------------------------------------------
replace_once(
    "common/graphics/renderer.cpp",
    '  hiz.hiZ       = device.image2d(TextureFormat::R16,  hw, hh, true);',
    '  hiz.hiZ       = device.image2d(TextureFormat::R32F, hw, hh, true);'
)

old_hiz_box = '''  ibbox[0] = clamp(ibbox[0], ivec2(0), hiZsize - ivec2(1));
  ibbox[1] = clamp(ibbox[1], ivec2(0), hiZsize - ivec2(1));

  float bz      = packHiZ(depthMin);
  float z       = hiZFetch(hiZ, ibbox);
  if(bz > z)
    return false;
'''
new_hiz_box = '''  // Conservative raster bounds: include one extra HiZ tile around the
  // projected box so rounding cannot hide thin/partial geometry.
  ibbox[0] = clamp(ibbox[0] - ivec2(1), ivec2(0), hiZsize - ivec2(1));
  ibbox[1] = clamp(ibbox[1] + ivec2(1), ivec2(0), hiZsize - ivec2(1));

  float bz      = packHiZ(depthMin);
  float z       = hiZFetch(hiZ, ibbox);
  // packHiZ expands the useful depth interval by 20x. A small margin here
  // absorbs ROP/sampler precision differences without disabling occlusion.
  const float conservativeBias = 0.02;
  if(bz > z + conservativeBias)
    return false;
'''
replace_once("shader/materials/visibility_pass.comp", old_hiz_box, new_hiz_box)

print("Exact Gothic Launcher 0.6.4 Direct Folder + Save + Adreno650 graphics fixes applied")
