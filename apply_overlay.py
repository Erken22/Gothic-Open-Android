#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()

def replace_once(path, old, new):
    p = root / path
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Patch anchor not found in {path}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")

# Add special broad-storage permission. This is for a sideload build: the native
# engine needs a real filesystem path and cannot consume SAF content:// streams.
replace_once(
    "android/launcher/AndroidManifest.xml",
    '    <uses-permission android:name="android.permission.VIBRATE" />\n',
    '    <uses-permission android:name="android.permission.VIBRATE" />\n'
    '    <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" tools:ignore="ScopedStorage" />\n'
)

# Make the tiny direct-folder activity the app entry point. Keep the full
# upstream launcher available from its "Обычный лаунчер" button.
old_activity = '''        <activity
            android:name="org.opengothic.app.LauncherActivity"
            android:configChanges="orientation|screenSize|screenLayout|smallestScreenSize|keyboardHidden"
            android:exported="true"
            android:screenOrientation="sensorLandscape"
            tools:ignore="DiscouragedApi,LockedOrientationActivity">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
'''
new_activity = '''        <activity
            android:name="org.opengothic.app.LauncherActivity"
            android:configChanges="orientation|screenSize|screenLayout|smallestScreenSize|keyboardHidden"
            android:exported="false"
            android:screenOrientation="sensorLandscape"
            tools:ignore="DiscouragedApi,LockedOrientationActivity" />
        <activity
            android:name="org.opengothic.app.DirectFolderActivity"
            android:configChanges="orientation|screenSize|screenLayout|smallestScreenSize|keyboardHidden"
            android:exported="true"
            android:screenOrientation="sensorLandscape"
            android:theme="@style/Launcher"
            tools:ignore="DiscouragedApi,LockedOrientationActivity">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
'''
replace_once("android/launcher/AndroidManifest.xml", old_activity, new_activity)

# Copy our small launcher into the same package as the upstream helper classes.
source = Path(__file__).resolve().parent / "overlay" / "DirectFolderActivity.java"
target = root / "android/launcher/java/org/opengothic/app/DirectFolderActivity.java"
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(source, target)

# Native OpenGothic normally forces Android data to
# <app external files>/Gothic2. Before that fallback, read an optional absolute
# path written by DirectFolderActivity. Saves/settings still use game.txt and
# remain under the app's own User/Gothic2 directory.
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
      auto direct = std::filesystem::u8path(path);
      std::error_code ec;
      if(direct.is_absolute() && std::filesystem::is_directory(direct,ec) && !ec)
        return direct.u16string();
    }
  }

  auto name = androidGame();
  auto game = appDir;
'''
replace_once("common/utils/installdetect.cpp", old_detect, new_detect)

print("Direct-folder overlay applied")
