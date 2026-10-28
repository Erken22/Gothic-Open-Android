#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()

def replace_once(path, old, new):
    p = root / path
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Patch anchor not found in {path}: {old[:140]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")

# Use a tiny launcher that selects an existing Gothic II folder instead of
# importing/copying game data into the application directory.
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

source = Path(__file__).resolve().parent / "overlay" / "DirectFolderActivityModern.java"
target = root / "android/java/org/opengothic/app/DirectFolderActivity.java"
shutil.copy2(source, target)

# The current Android engine normally looks for Gothic2 below its own external
# files directory. Prefer an absolute path selected by DirectFolderActivity.
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

# The supplied logcat is from Adreno 650 and dies inside Qualcomm's
# vkCreateGraphicsPipelines shader compiler. The modern Android fork already
# has SafeGpu crash tracking; start this specific driver in its minimal profile
# immediately so the first test does not have to crash once to learn it.
old_safe = '''  s.level = level;
  s.ready = true;
'''
new_safe = '''#if defined(__ANDROID__)
  if(s.identity.find("Adreno (TM) 650")!=std::string::npos) {
    level = std::max(level,int(Minimal));
    Log::e("Safe GPU mode: forced minimal profile for Adreno 650");
    }
#endif

  s.level = level;
  s.ready = true;
'''
replace_once("common/graphics/safegpu.cpp", old_safe, new_safe)

print("Modern direct-folder + Adreno 650 SafeGpu overlay applied")
