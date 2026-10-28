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

print("FIX16 0.6.7: Direct Folder applied; upstream Adreno/lifecycle/rendering kept intact")
