#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()

def replace_once(path, old, new):
    p = root / path
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Patch anchor not found in {path}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")

# Single-game Gothic II: NotR APK: allow the native engine to read the user's
# selected folder as a normal filesystem path.
replace_once(
    "android/app/src/main/AndroidManifest.xml",
    '    <uses-permission android:name="android.permission.VIBRATE" />\n',
    '    <uses-permission android:name="android.permission.VIBRATE" />\n'
    '    <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" tools:ignore="ScopedStorage" />\n'
)

# Replace ZIP-import setup with the tiny direct-folder selector.
source = Path(__file__).resolve().parent / "overlay" / "SetupActivity.java.in"
target = root / "android/app/SetupActivity.java.in"
shutil.copy2(source, target)

# Native OpenGothic normally checks <app external files>/Gothic2 on Android.
# Prefer an absolute path written by SetupActivity, then retain the old fallback.
old_detect = '''#elif defined(__ANDROID__)
  auto name = androidGame();
  auto game = appDir;
'''
new_detect = '''#elif defined(__ANDROID__)
  {
    std::ifstream file(std::filesystem::path(applicationSupportDirectory())/"game-path.txt");
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
'''
replace_once("common/utils/installdetect.cpp", old_detect, new_detect)

print("Direct-folder Gothic II: NotR overlay applied")
