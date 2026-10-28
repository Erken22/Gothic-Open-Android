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


# This build has no Steam login/download/import/update UI. Keep only the Java
# classes required by the direct-folder launcher and the native game activity.
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

# Remove launcher-only Android components from the manifest.
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

# Drop Steam/network Gradle dependencies. The direct-folder APK does not use
# any third-party Java library.
cmake = root / "CMakeLists.txt"
ct = cmake.read_text(encoding="utf-8")
dep_start = ct.find('    # The login to Steam and the download of the games')
dep_end_marker = '      "com.squareup.okio:okio:3.16.0")'
if dep_start < 0 or dep_end_marker not in ct:
    raise SystemExit("Android dependency block not found in CMakeLists.txt")
dep_end = ct.index(dep_end_marker, dep_start) + len(dep_end_marker)
ct = ct[:dep_start] + '    )' + ct[dep_end:]
cmake.write_text(ct, encoding="utf-8")

print("Modern direct-folder + Adreno 650 SafeGpu overlay applied")
