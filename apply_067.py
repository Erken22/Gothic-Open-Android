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
# FIX20: bundled Turnip on 0.6.7.
# Turnip gets the normal full HiZ path. If the custom driver cannot load,
# system Qualcomm automatically stays on the proven FIX17 frustum-only path.
# ---------------------------------------------------------------------------

replace_once(
    "common/graphics/drawcommands.cpp",
    '#include <Tempest/Log>\n#include <string_view>\n',
    '#include <Tempest/Log>\n#include <string_view>\n#if defined(__ANDROID__)\nextern "C" int opengothic_vulkan_is_turnip();\n#endif\n'
)

replace_once(
    "common/graphics/drawcommands.cpp",
    '''    const bool match = name.find("Adreno")!=std::string_view::npos &&
                       name.find("650")!=std::string_view::npos;
    if(match)
      Log::i("Visibility: Adreno 650 frustum-only fallback enabled; HiZ rejection bypassed");
''',
    '''    const bool match = name.find("Adreno")!=std::string_view::npos &&
                       name.find("650")!=std::string_view::npos &&
                       opengothic_vulkan_is_turnip()==0;
    if(match)
      Log::i("Visibility: system Adreno 650 -> FIX17 frustum-only fallback");
    else if(name.find("Adreno")!=std::string_view::npos && name.find("650")!=std::string_view::npos)
      Log::i("Visibility: Turnip Adreno 650 -> full HiZ enabled");
'''
)

# Extract native libraries: libadrenotools installs hook libraries from the
# real nativeLibraryDir and cannot operate on compressed in-APK .so files.
replace_once(
    "android/launcher/AndroidManifest.xml",
    '        android:hasCode="true"\n',
    '        android:hasCode="true"\n        android:extractNativeLibs="true"\n'
)

replace_once(
    "lib/Tempest/Engine/cmake/android/build.gradle.in",
    '''def extraAssets = assetProperty ? providers.gradleProperty(assetProperty).orNull : null
''',
    '''def extraAssets = assetProperty ? providers.gradleProperty(assetProperty).orNull : null
def nativeSourceRoot = file(@NATIVE_CMAKE@).parentFile
'''
)

replace_once(
    "lib/Tempest/Engine/cmake/android/build.gradle.in",
    '''            assets.srcDirs = @ASSET_DIRS@
            if (extraAssets) {
''',
    '''            assets.srcDirs = @ASSET_DIRS@
            jniLibs.srcDirs += [new File(nativeSourceRoot, "android/turnip/jniLibs")]
            if (extraAssets) {
'''
)

replace_once(
    "lib/Tempest/Engine/cmake/android/build.gradle.in",
    '''    androidResources {
        noCompress.addAll(@NO_COMPRESS@)
    }
''',
    '''    packagingOptions {
        jniLibs {
            useLegacyPackaging = true
            pickFirsts += ["**/libc++_shared.so"]
        }
    }
    androidResources {
        noCompress.addAll(@NO_COMPRESS@)
    }
'''
)

# Define app-local libvulkan.so before Tempest. Tempest's Android Vulkan link
# resolves to this proxy, which loads Turnip through libadrenotools and falls
# back to /system/lib64/libvulkan.so if custom loading fails.
replace_once(
    "CMakeLists.txt",
    '''# Tempest
if(WIN32)
''',
    '''# FIX20 Android Vulkan proxy
if(ANDROID)
  # Keep direct Vulkan calls in our private ABI, independent of Android public libvulkan.
  foreach(og_vk IN ITEMS
    vkAcquireNextImageKHR
    vkAllocateCommandBuffers
    vkAllocateDescriptorSets
    vkAllocateMemory
    vkBeginCommandBuffer
    vkBindBufferMemory
    vkBindImageMemory
    vkCmdBeginRenderPass
    vkCmdBindDescriptorSets
    vkCmdBindIndexBuffer
    vkCmdBindPipeline
    vkCmdBindVertexBuffers
    vkCmdBlitImage
    vkCmdClearColorImage
    vkCmdCopyBuffer
    vkCmdCopyBufferToImage
    vkCmdCopyImageToBuffer
    vkCmdDispatch
    vkCmdDispatchIndirect
    vkCmdDraw
    vkCmdDrawIndexed
    vkCmdDrawIndirect
    vkCmdEndRenderPass
    vkCmdFillBuffer
    vkCmdPipelineBarrier
    vkCmdPushConstants
    vkCmdResetQueryPool
    vkCmdSetScissor
    vkCmdSetViewport
    vkCmdUpdateBuffer
    vkCmdWriteTimestamp
    vkCreateAndroidSurfaceKHR
    vkCreateBuffer
    vkCreateCommandPool
    vkCreateComputePipelines
    vkCreateDescriptorPool
    vkCreateDescriptorSetLayout
    vkCreateDevice
    vkCreateFence
    vkCreateFramebuffer
    vkCreateGraphicsPipelines
    vkCreateImage
    vkCreateImageView
    vkCreateInstance
    vkCreatePipelineLayout
    vkCreateQueryPool
    vkCreateRenderPass
    vkCreateSampler
    vkCreateSemaphore
    vkCreateShaderModule
    vkCreateSwapchainKHR
    vkDestroyBuffer
    vkDestroyCommandPool
    vkDestroyDescriptorPool
    vkDestroyDescriptorSetLayout
    vkDestroyDevice
    vkDestroyFence
    vkDestroyFramebuffer
    vkDestroyImage
    vkDestroyImageView
    vkDestroyPipeline
    vkDestroyPipelineLayout
    vkDestroyQueryPool
    vkDestroyRenderPass
    vkDestroySampler
    vkDestroySemaphore
    vkDestroyShaderModule
    vkDestroySurfaceKHR
    vkDestroySwapchainKHR
    vkDeviceWaitIdle
    vkEndCommandBuffer
    vkEnumerateDeviceExtensionProperties
    vkEnumerateInstanceExtensionProperties
    vkEnumerateInstanceLayerProperties
    vkEnumeratePhysicalDevices
    vkFlushMappedMemoryRanges
    vkFreeCommandBuffers
    vkFreeMemory
    vkGetBufferMemoryRequirements
    vkGetDeviceProcAddr
    vkGetDeviceQueue
    vkGetFenceStatus
    vkGetImageMemoryRequirements
    vkGetInstanceProcAddr
    vkGetPhysicalDeviceFeatures
    vkGetPhysicalDeviceFormatProperties
    vkGetPhysicalDeviceMemoryProperties
    vkGetPhysicalDeviceProperties
    vkGetPhysicalDeviceQueueFamilyProperties
    vkGetPhysicalDeviceSurfaceCapabilitiesKHR
    vkGetPhysicalDeviceSurfaceFormatsKHR
    vkGetPhysicalDeviceSurfacePresentModesKHR
    vkGetPhysicalDeviceSurfaceSupportKHR
    vkGetQueryPoolResults
    vkGetSwapchainImagesKHR
    vkInvalidateMappedMemoryRanges
    vkMapMemory
    vkQueuePresentKHR
    vkQueueSubmit
    vkQueueWaitIdle
    vkResetCommandBuffer
    vkResetCommandPool
    vkResetDescriptorPool
    vkResetFences
    vkUnmapMemory
    vkUpdateDescriptorSets
    vkWaitForFences)
    add_compile_definitions("${og_vk}=opengothic_${og_vk}")
  endforeach()
  add_library(vulkan SHARED android/turnip/vulkan_proxy.cpp)
  target_include_directories(vulkan PRIVATE "$ENV{VULKAN_SDK}/include")
  target_link_libraries(vulkan PRIVATE dl log)
  target_link_options(vulkan PRIVATE "-Wl,--exclude-libs,ALL")
  set_target_properties(vulkan PROPERTIES OUTPUT_NAME "opengothic_vulkan"
    CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES)
endif()

# Tempest
if(WIN32)
'''
)

replace_once(
    "CMakeLists.txt",
    '''target_link_libraries(Gothic2Notr PRIVATE OpenGothic)
''',
    '''target_link_libraries(Gothic2Notr PRIVATE OpenGothic)
if(ANDROID)
  target_link_libraries(Gothic2Notr PRIVATE vulkan)
endif()
'''
)

print("FIX20 0.6.7: bundled Turnip + full HiZ; system Adreno falls back to FIX17")


# FIX21: on Android, VSM is an opt-in debug startup path. Avoid eagerly
# compiling its 1024-thread kernels when ordinary shadow maps are selected.
# Turnip a6xx advertises 1024 invocations, but vsm_list_pages exceeds the
# concurrent-wave/register budget. Keep explicit -vsm support and desktop
# runtime toggling unchanged; normal mobile shadow resolution is untouched.
replace_once(
    "common/graphics/shaders.cpp",
    '''bool Shaders::isVsmSupported() {
  auto& gpu = Resources::device().properties();
''',
    '''bool Shaders::isVsmSupported() {
#if defined(__ANDROID__)
  if(!CommandLine::inst().isVirtualShadow())
    return false;
#endif
  auto& gpu = Resources::device().properties();
'''
)
replace_once(
    "common/graphics/shaders.cpp",
    '''  opts.doVirtualShadow  = Shaders::isVsmSupported()  && CommandLine::inst().isVirtualShadow();
''',
    '''  opts.doVirtualShadow  = Shaders::isVsmSupported()  && CommandLine::inst().isVirtualShadow();
#if defined(__ANDROID__)
  if(!CommandLine::inst().isVirtualShadow())
    Log::i("Shadow startup: standard shadow maps; unrequested virtual shadow pipelines skipped");
#endif
'''
)
print("FIX21: ordinary Android shadows preserve quality; unused VSM pipelines are not created")

# FIX22 diagnostics: delimit world finalization without changing synchronization.
replace_once('common/gothic.cpp',
    '        pendingGame = std::move(next);',
    '        Log::i("FIX22 load: worker finished world construction");\n        pendingGame = std::move(next);')
replace_once('common/mainwindow.cpp',
    'void MainWindow::onWorldLoaded() {',
    'void MainWindow::onWorldLoaded() {\n  Log::i("FIX22 load: main-thread finalization entered");')
replace_once('common/mainwindow.cpp',
    '  device.waitIdle();\n  time.step("finish/reset-input-and-gpu-wait");',
    '  Log::i("FIX22 load: before device.waitIdle");\n  device.waitIdle();\n  Log::i("FIX22 load: after device.waitIdle");\n  time.step("finish/reset-input-and-gpu-wait");')
replace_once('common/mainwindow.cpp',
    '  renderer.onWorldChanged();\n  time.step("finish/command-buffers-and-renderer-reset");',
    '  Log::i("FIX22 load: before renderer.onWorldChanged");\n  renderer.onWorldChanged();\n  Log::i("FIX22 load: renderer world reset complete");\n  time.step("finish/command-buffers-and-renderer-reset");')
print('FIX22: pending Vulkan call watchdog and world-finalization diagnostics; rendering unchanged')

# FIX23: target-specific native wait on Turnip Adreno 650.
replace_once("lib/Tempest/Engine/gapi/vulkan/vdevice.cpp", '#include "vdevice.h"\n', '#include "vdevice.h"\n#if defined(__ANDROID__)\nextern "C" int opengothic_vulkan_is_turnip();\n#endif\n')
replace_once("lib/Tempest/Engine/gapi/vulkan/vdevice.cpp", 'VkResult VDevice::waitFence(VFence& t, uint64_t timeout) {\n  {\n    std::lock_guard<std::mutex> guard(timeline.sync);\n    if(t.fence==VK_NULL_HANDLE || t.status==VK_SUCCESS)\n      return VK_SUCCESS;\n    if(timeout==0) {\n      const auto st = vkGetFenceStatus(device.impl, t.fence);\n      t.setStatus(st);\n      if(st<=0 && st!=VK_NOT_READY)\n        return st;\n      return VK_NOT_READY;\n      }\n  }\n\n  auto tickCount = []() {\n    auto now = std::chrono::steady_clock::now();\n    auto ms = std::chrono::time_point_cast<std::chrono::milliseconds>(now);\n    return uint64_t(ms.time_since_epoch().count())-uint64_t(INT64_MIN);\n    };\n\n  auto start = tickCount();\n  while(true) {\n    static const uint64_t toNano = uint64_t(1000*1000);\n    uint64_t vkTime = 0;\n    if(timeout < std::numeric_limits<uint64_t>::max()/toNano) {\n      vkTime = timeout*toNano; // millis to nano convertion\n      } else {\n      vkTime = std::numeric_limits<uint64_t>::max();\n      }\n\n    std::lock_guard<std::mutex> guard(timeline.sync);\n    waitAny(vkTime);\n    if(t.fence==VK_NULL_HANDLE || t.status==VK_SUCCESS)\n      return VK_SUCCESS;\n    if(t.status<0 && t.status!=VK_NOT_READY)\n      return t.status;\n\n    auto now = tickCount();\n    if(now-start > timeout)\n      return VK_NOT_READY;\n    timeout -= (now-start);\n    }\n  }\n', 'VkResult VDevice::waitFence(VFence& t, uint64_t timeout) {\n  {\n    std::lock_guard<std::mutex> guard(timeline.sync);\n    if(t.fence==VK_NULL_HANDLE || t.status==VK_SUCCESS)\n      return VK_SUCCESS;\n    if(timeout==0) {\n      const auto st = vkGetFenceStatus(device.impl, t.fence);\n      t.setStatus(st);\n      if(st<=0 && st!=VK_NOT_READY)\n        return st;\n      return VK_NOT_READY;\n      }\n  }\n\n#if defined(__ANDROID__)\n  // Wait for this submission, not an unrelated group of timeline fences.\n  // FIX22 identifies the Turnip a650 hang in the multi-fence waitAny path.\n  if(opengothic_vulkan_is_turnip()!=0 && std::strstr(props.name,"Adreno")!=nullptr &&\n     std::strstr(props.name,"650")!=nullptr) {\n    static const uint64_t toNano = uint64_t(1000*1000);\n    const uint64_t vkTime = timeout < std::numeric_limits<uint64_t>::max()/toNano\n                             ? timeout*toNano : std::numeric_limits<uint64_t>::max();\n    std::lock_guard<std::mutex> guard(timeline.sync);\n    if(t.fence==VK_NULL_HANDLE || t.status==VK_SUCCESS)\n      return VK_SUCCESS;\n    if(t.status<0)\n      return t.status;\n    const auto result = vkWaitForFences(device.impl,1,&t.fence,VK_TRUE,vkTime);\n    if(result==VK_TIMEOUT)\n      return VK_NOT_READY;\n    if(result==VK_SUCCESS)\n      t.setStatus(VK_SUCCESS);\n    return result;\n    }\n#endif\n\n  auto tickCount = []() {\n    auto now = std::chrono::steady_clock::now();\n    auto ms = std::chrono::time_point_cast<std::chrono::milliseconds>(now);\n    return uint64_t(ms.time_since_epoch().count())-uint64_t(INT64_MIN);\n    };\n\n  auto start = tickCount();\n  while(true) {\n    static const uint64_t toNano = uint64_t(1000*1000);\n    uint64_t vkTime = 0;\n    if(timeout < std::numeric_limits<uint64_t>::max()/toNano) {\n      vkTime = timeout*toNano; // millis to nano convertion\n      } else {\n      vkTime = std::numeric_limits<uint64_t>::max();\n      }\n\n    std::lock_guard<std::mutex> guard(timeline.sync);\n    waitAny(vkTime);\n    if(t.fence==VK_NULL_HANDLE || t.status==VK_SUCCESS)\n      return VK_SUCCESS;\n    if(t.status<0 && t.status!=VK_NOT_READY)\n      return t.status;\n\n    auto now = tickCount();\n    if(now-start > timeout)\n      return VK_NOT_READY;\n    timeout -= (now-start);\n    }\n  }\n')
replace_once("lib/Tempest/Engine/gapi/vulkan/vdevice.cpp", '  createLogicalDevice(pdev);\n', '#if defined(__ANDROID__)\n  if(opengothic_vulkan_is_turnip()!=0 && std::strstr(props.name,"Adreno")!=nullptr &&\n     std::strstr(props.name,"650")!=nullptr)\n    Log::i("FIX23 fence waits: Turnip Adreno 650 uses targeted native completion");\n#endif\n  createLogicalDevice(pdev);\n')

# FIX24: low-overhead frame counters and sparse non-blocking GPU samples.
(root / "common/utils/androidframeprofile.h").write_text('#pragma once\n#include <Tempest/Log>\n#include <algorithm>\n#include <array>\n#include <chrono>\n#include <cstdint>\n#include <string_view>\n#include <cmath>\n\n// One CPU summary every two seconds and at most 24 sparse GPU samples.\n// GPU results are read only after the existing submission fence is ready.\n// Render-thread state; configured before deferred shader compilation starts.\nstruct AndroidSsaoTuner {\n  struct State {\n    std::array<double,8> original{},shared{};\n    size_t no=0,ns=0;\n    bool nextShared=false,decided=false;\n  };\n  static auto& states() {static std::array<State,2> value{};return value;}\n  static bool& supported() {static bool value=false;return value;}\n  static void configure(bool value) {supported()=value;}\n  static bool useShared(bool half) {return supported() && states()[half?1u:0u].nextShared;}\n  static double median(std::array<double,8> data) {\n    std::sort(data.begin(),data.end());\n    return (data[3]+data[4])*0.5;\n  }\n  static void finish(State& s,size_t mode) {\n    if(s.decided) return;\n    s.decided=true;s.nextShared=false;\n    if(s.no<8 || s.ns<8) {\n      if(s.no+s.ns>0)\n        Tempest::Log::i("FIX29 SSAO choice: mode=",mode," path=private incomplete samples");\n      return;\n    }\n    size_t wins=0;\n    for(size_t i=0;i<8;++i)\n      if(s.shared[i]<s.original[i]) ++wins;\n    const double oldMs=median(s.original),newMs=median(s.shared);\n    s.nextShared=(newMs<oldMs*0.95 && wins>=6);\n    Tempest::Log::i("FIX29 SSAO choice: mode=",mode," path=",s.nextShared?"shared":"private",\n        " private-ms=",oldMs," shared-ms=",newMs," pair-wins=",wins,"/8");\n  }\n  static void finishAll() {\n    if(!supported()) return;\n    for(size_t i=0;i<states().size();++i) finish(states()[i],i);\n  }\n  static void observe(std::string_view name,double ms) {\n    if(!supported() || !std::isfinite(ms) || ms<=0) return;\n    bool shared=false;size_t mode=0;\n    if(name=="SSAO private full") {}\n    else if(name=="SSAO shared full") shared=true;\n    else if(name=="SSAO private half") mode=1;\n    else if(name=="SSAO shared half") {shared=true;mode=1;}\n    else return;\n    auto& s=states()[mode];\n    if(s.decided) return;\n    auto& count=shared?s.ns:s.no;\n    if(count>=8) return;\n    (shared?s.shared:s.original)[count++]=ms;\n    Tempest::Log::i("FIX29 SSAO sample: mode=",mode," path=",shared?"shared":"private"," ms=",ms," n=",count);\n    if(s.no==8 && s.ns==8) finish(s,mode);\n    else s.nextShared=(s.no>s.ns || (s.no==s.ns && (s.no%2u)!=0));\n  }\n};\n\ntemplate<size_t Slots>\nstruct AndroidFrameMetrics {\n  static uint64_t now() {\n    return uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(\n        std::chrono::steady_clock::now().time_since_epoch()).count());\n    }\n  void resetWindow() {\n    start=0; frames=0; skipped=0;\n    sums.fill(0);\n    }\n  void skip() { ++skipped; }\n  bool captureGpu(uint64_t time) {\n    if(samples>=24) {AndroidSsaoTuner::finishAll();return false;}\n    if(time<nextSample) return false;\n    ++samples;\n    nextSample=time+(samples<16 ? 1000000u : 10000000u);\n    return true;\n    }\n  template<class Timings>\n  void logGpu(const Timings& timings) {\n    if(timings.empty())\n      return;\n    for(const auto& timing:timings) AndroidSsaoTuner::observe(timing.name,timing.milliseconds);\n    double total=0;\n    for(const auto& timing:timings)\n      total+=timing.milliseconds;\n    Tempest::Log::i("FIX29 GPU sample: total-ms=",total);\n    // Aggregate all shadow subpasses, even if they are absent from the top four.\n    struct Shadow {double total=0,solid=0,alpha=0,particles=0,setup=0;};\n    std::array<Shadow,2> shadows{};\n    for(const auto& timing:timings) {\n      const std::string_view name=timing.name;\n      int layer=-1;\n      if(name.starts_with("ShadowMap #0")) layer=0;\n      if(name.starts_with("ShadowMap #1")) layer=1;\n      if(layer<0) continue;\n      auto& sh=shadows[size_t(layer)];\n      sh.total+=timing.milliseconds;\n      if(name.ends_with(" solid")) sh.solid+=timing.milliseconds;\n      else if(name.ends_with(" alpha")) sh.alpha+=timing.milliseconds;\n      else if(name.ends_with(" particles")) sh.particles+=timing.milliseconds;\n      else sh.setup+=timing.milliseconds;\n      }\n    for(size_t i=0;i<shadows.size();++i) {\n      const auto& sh=shadows[i];\n      if(sh.total>0)\n        Tempest::Log::i("FIX29 shadow: layer=",i," total-ms=",sh.total,\n            " solid-ms=",sh.solid," alpha-ms=",sh.alpha," particles-ms=",sh.particles," setup-ms=",sh.setup);\n      }\n    auto sorted=timings;\n    const auto count=std::min(size_t(4),sorted.size());\n    std::partial_sort(sorted.begin(),sorted.begin()+static_cast<typename Timings::difference_type>(count),sorted.end(),\n                      [](const auto& a,const auto& b){return a.milliseconds>b.milliseconds;});\n    for(size_t i=0;i<count;++i)\n      Tempest::Log::i("FIX29 GPU pass: ",sorted[i].name," ms=",sorted[i].milliseconds);\n    }\n  void frame(uint64_t begin,uint64_t paced,uint64_t simulated,uint64_t recorded,\n             uint64_t submitted,uint64_t presented,uint64_t recordBegin,\n             uint32_t width,uint32_t height) {\n    if(start==0)\n      start=begin;\n    ++frames;\n    const uint64_t spans[]={paced-begin,simulated-paced,recordBegin-simulated,\n                            recorded-recordBegin,submitted-recorded,presented-submitted};\n    for(size_t i=0;i<sums.size();++i)\n      sums[i]+=double(spans[i]);\n    const auto elapsed=presented-start;\n    if(elapsed<2000000)\n      return;\n    const double unit=1.0/(1000.0*double(frames));\n    Tempest::Log::i("FIX29 frame: fps=",double(frames)*1000000.0/double(elapsed),\n        " pace-ms=",sums[0]*unit," sim-ms=",sums[1]*unit," ui-ms=",sums[2]*unit,\n        " record-ms=",sums[3]*unit," submit-ms=",sums[4]*unit," present-ms=",sums[5]*unit,\n        " skipped=",skipped," output=",width,"x",height);\n    resetWindow();\n    }\n  std::array<bool,Slots> pending{};\n  std::array<double,6> sums{};\n  uint64_t start=0,frames=0,skipped=0,nextSample=0;\n  uint32_t samples=0;\n};\n', encoding="utf-8")
replace_once('common/mainwindow.cpp', '#include "utils/saveloadprofile.h"\n', '#include "utils/saveloadprofile.h"\n#if defined(__ANDROID__)\n#include "utils/androidframeprofile.h"\n#endif\n')
replace_once('common/mainwindow.cpp', 'void MainWindow::render(){\n  CpuTrace frameTrace("OpenGothic::frame");', 'void MainWindow::render(){\n#if defined(__ANDROID__)\n  static AndroidFrameMetrics<Resources::MaxFramesInFlight> frameMetrics;\n  const auto metricsBegin=AndroidFrameMetrics<Resources::MaxFramesInFlight>::now();\n  const bool metricsWorld=Gothic::inst().isInGame() &&\n      Gothic::inst().checkLoading()==Gothic::LoadState::Idle && !video.isActive() && !rootMenu.isActive();\n  if(!metricsWorld)\n    frameMetrics.resetWindow();\n#endif\n  CpuTrace frameTrace("OpenGothic::frame");')
replace_once('common/mainwindow.cpp', '    framePacer.wait();\n#endif', '    framePacer.wait();\n    const auto metricsPaced=AndroidFrameMetrics<Resources::MaxFramesInFlight>::now();\n#endif')
replace_once('common/mainwindow.cpp', '    auto& sync = fence[cmdId];\n    bool ready;', '#if defined(__ANDROID__)\n    const auto metricsSimulated=AndroidFrameMetrics<Resources::MaxFramesInFlight>::now();\n#endif\n    auto& sync = fence[cmdId];\n    bool ready;')
replace_once('common/mainwindow.cpp', '    if(!ready) {\n      CpuTrace trace("OpenGothic::skipped frame");', '    if(!ready) {\n#if defined(__ANDROID__)\n      if(metricsWorld) frameMetrics.skip();\n#endif\n      CpuTrace trace("OpenGothic::skipped frame");')
replace_once('common/mainwindow.cpp', '    const bool captureGpu = profileGpu && gpuProfileLog.is_open()', '    bool captureGpu = profileGpu && gpuProfileLog.is_open()')
replace_once('common/mainwindow.cpp', '    if(captureGpu)\n      ++gpuProfileAttempts;\n    {\n    CpuTrace trace("OpenGothic::record");', '#if defined(__ANDROID__)\n    if(frameMetrics.pending[cmdId]) {\n      if(metricsWorld) frameMetrics.logGpu(cmd.gpuTimings());\n      frameMetrics.pending[cmdId]=false;\n      }\n    const bool autoCapture=metricsWorld &&\n        frameMetrics.captureGpu(AndroidFrameMetrics<Resources::MaxFramesInFlight>::now());\n    frameMetrics.pending[cmdId]=autoCapture;\n    captureGpu=captureGpu || autoCapture;\n    const auto metricsRecordBegin=AndroidFrameMetrics<Resources::MaxFramesInFlight>::now();\n#endif\n    if(captureGpu)\n      ++gpuProfileAttempts;\n    {\n    CpuTrace trace("OpenGothic::record");')
replace_once('common/mainwindow.cpp', '    {\n    CpuTrace trace("OpenGothic::submit");', '#if defined(__ANDROID__)\n    const auto metricsRecorded=AndroidFrameMetrics<Resources::MaxFramesInFlight>::now();\n#endif\n    {\n    CpuTrace trace("OpenGothic::submit");')
replace_once('common/mainwindow.cpp', '    {\n    CpuTrace trace("OpenGothic::present");', '#if defined(__ANDROID__)\n    const auto metricsSubmitted=AndroidFrameMetrics<Resources::MaxFramesInFlight>::now();\n#endif\n    {\n    CpuTrace trace("OpenGothic::present");')
replace_once('common/mainwindow.cpp', '    cmdId = (cmdId+1u)%Resources::MaxFramesInFlight;', '#if defined(__ANDROID__)\n    if(metricsWorld)\n      frameMetrics.frame(metricsBegin,metricsPaced,metricsSimulated,metricsRecorded,\n                         metricsSubmitted,AndroidFrameMetrics<Resources::MaxFramesInFlight>::now(),\n                         metricsRecordBegin,swapchain.w(),swapchain.h());\n#endif\n    cmdId = (cmdId+1u)%Resources::MaxFramesInFlight;')

# FIX29: permit native bindless batching on the qualified Mesa driver only.
replace_once('common/graphics/shaders.cpp', '#include "resources.h"\n', '#include "resources.h"\n#if defined(__ANDROID__)\nextern "C" int opengothic_vulkan_is_turnip();\n#endif\n')
replace_once('common/graphics/shaders.cpp', 'static bool hasBindless() {\n  const auto& p = Resources::device().properties();\n#if defined(__ANDROID__)\n  const std::string_view name = p.name;\n  // Adreno drivers crash compiling the bindless depth pipelines (seen on Adreno 610, 642L, 650 and 725)\n  if(name.find("Adreno")!=std::string_view::npos) {\n    Log::i("Disabling bindless material shaders for ",name);\n    return false;\n    }\n#endif\n  if(p.descriptors.nonUniformIndexing && p.descriptors.maxTexture>=65000 && p.descriptors.maxStorage>=65000)\n    return true;\n  return false;\n  }\n', '#if defined(__ANDROID__)\nstatic bool isTurnipAdreno650() {\n  const std::string_view name = Resources::device().properties().name;\n  return name.find("Turnip")!=std::string_view::npos &&\n         name.find("Adreno")!=std::string_view::npos &&\n         name.find("650")!=std::string_view::npos && opengothic_vulkan_is_turnip()!=0;\n  }\n#endif\n\nstatic bool hasBindless() {\n  const auto& p = Resources::device().properties();\n  const bool supported = p.descriptors.nonUniformIndexing &&\n                         p.descriptors.maxTexture>=65000 && p.descriptors.maxStorage>=65000;\n#if defined(__ANDROID__)\n  const std::string_view name = p.name;\n  if(name.find("Adreno")!=std::string_view::npos && !isTurnipAdreno650()) {\n    Log::i("Disabling bindless material shaders for ",name);\n    return false;\n    }\n  if(isTurnipAdreno650())\n    Log::i("FIX29 Turnip material caps: indexing=",int(p.descriptors.nonUniformIndexing),\n           " textures=",p.descriptors.maxTexture," storage=",p.descriptors.maxStorage,\n           " supported=",int(supported));\n#endif\n  return supported;\n  }\n')
replace_once('common/graphics/shaders.cpp', '  opts.doMeshShading    = gpu.meshlets.meshShader && CommandLine::inst().isMeshShading();\n', '  opts.doMeshShading    = gpu.meshlets.meshShader && CommandLine::inst().isMeshShading();\n#if defined(__ANDROID__)\n  if(isTurnipAdreno650()) {\n    // Bindless is a batching change. Keep the previous mobile vertex-stage\n    // and non-ray-query rendering choices instead of enabling extra work.\n    opts.doRayQuery=false;\n    opts.doMeshShading=false;\n    Log::i("FIX29 material mode: ",opts.doBindless ? "bindless batches" : "slot fallback");\n    }\n#endif\n')
replace_once('common/graphics/shaders.cpp', 't==DrawCommands::Landscape && !flatVaryings)', 't==DrawCommands::Landscape && !needsFlatVaryings)')
replace_once('common/graphics/shaders.cpp', 't!=DrawCommands::Pfx && !flatVaryings)', 't!=DrawCommands::Pfx && !needsFlatVaryings)')
replace_once('common/graphics/shaders.cpp', 'Log::i("Using flattened material varyings for ",name);', 'Log::i("FIX29 Adreno material stages: vertex pipelines retained; slot shaders keep flat varyings for ",name);')
replace_once('common/graphics/drawcommands.cpp', '  cmdDurtyBit = false;\n\n  ord.resize(cmd.size());', '  cmdDurtyBit = false;\n#if defined(__ANDROID__)\n  static size_t lastLoggedCount=size_t(-1);\n  if(lastLoggedCount!=cmd.size()) {\n    lastLoggedCount=cmd.size();\n    Log::i("FIX29 draw batches: count=",cmd.size()," bindless=",int(Shaders::options().doBindless));\n    }\n#endif\n\n  ord.resize(cmd.size());')
replace_once("common/graphics/shaders.cpp", 'bool Shaders::isRtsmSupported() {\n  if(!Shaders::options().doBindless) {\n    return false;\n    }\n  auto& gpu = Resources::device().properties();\n  if(!gpu.hasStorageFormat(TextureFormat::RG32U) || !gpu.hasStorageFormat(TextureFormat::R11G11B10UF))\n    return false;\n  if(gpu.compute.maxInvocations<512 || gpu.compute.maxSharedMemory<32*1024 || !gpu.descriptors.nonUniformIndexing) {\n    return false;\n    }\n  return true;\n  }\n', "bool Shaders::isRtsmSupported() {\n#if defined(__ANDROID__)\n  // This path was unavailable with Adreno's previous slot-material mode.\n  // Do not eagerly introduce experimental RTSM kernels as a batching side effect.\n  if(isTurnipAdreno650())\n    return false;\n#endif\n  if(!Shaders::options().doBindless) {\n    return false;\n    }\n  auto& gpu = Resources::device().properties();\n  if(!gpu.hasStorageFormat(TextureFormat::RG32U) || !gpu.hasStorageFormat(TextureFormat::R11G11B10UF))\n    return false;\n  if(gpu.compute.maxInvocations<512 || gpu.compute.maxSharedMemory<32*1024 || !gpu.descriptors.nonUniformIndexing) {\n    return false;\n    }\n  return true;\n  }\n")


replace_once('common/graphics/visualobjects.cpp', '#include "gothic.h"', '#include "gothic.h"\n#include "utils/string_frm.h"')

replace_once('common/graphics/visualobjects.cpp', '  auto view = SceneGlobals::VisCamera(SceneGlobals::V_Shadow0 + layer);\n  drawCmd.drawCommon(cmd, view, Material::Solid);\n  drawCmd.drawCommon(cmd, view, Material::AlphaTest);', '  auto view = SceneGlobals::VisCamera(SceneGlobals::V_Shadow0 + layer);\n#if defined(__ANDROID__)\n  cmd.setDebugMarker(string_frm("ShadowMap #",layer," solid"));\n#endif\n  drawCmd.drawCommon(cmd, view, Material::Solid);\n#if defined(__ANDROID__)\n  cmd.setDebugMarker(string_frm("ShadowMap #",layer," alpha"));\n#endif\n  drawCmd.drawCommon(cmd, view, Material::AlphaTest);')

replace_once('common/graphics/worldview.cpp', '#include "shaders.h"', '#include "shaders.h"\n#include "utils/string_frm.h"')

replace_once('common/graphics/worldview.cpp', '  visuals.drawShadow(cmd,layer);\n  pfxGroup.drawShadow(cmd,fId,layer);', '  visuals.drawShadow(cmd,layer);\n#if defined(__ANDROID__)\n  cmd.setDebugMarker(string_frm("ShadowMap #",layer," particles"));\n#endif\n  pfxGroup.drawShadow(cmd,fId,layer);')

# FIX29: match the layout used by both dynamic and fallback depth attachments.
replace_once('lib/Tempest/Engine/gapi/vulkan/vcommandbuffer.cpp', '  if(rs==ResourceLayout::DepthAttach)\n    return VK_IMAGE_LAYOUT_DEPTH_ATTACHMENT_OPTIMAL;', '  if(rs==ResourceLayout::DepthAttach)\n    return VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;')

replace_once('shader/CMakeLists.txt', 'add_shader(ssao.comp                 ssao/ssao.comp)', 'add_shader(ssao_shared.comp          ssao/ssao_shared.comp -DSSAO_SHARED_BINS)\nadd_shader(ssao_half_shared.comp     ssao/ssao_shared.comp -DSSAO_SHARED_BINS -DSSAO_HALF_RES)\nadd_shader(ssao.comp                 ssao/ssao.comp)')

# Preserve the baseline SSAO source byte-for-byte; specialize a separate candidate.
(root / "shader/ssao/ssao_shared.comp").write_text((root / "shader/ssao/ssao.comp").read_text(encoding="utf-8"), encoding="utf-8")
replace_once('shader/ssao/ssao_shared.comp', 'float hitV[gridQSize];', '#ifdef SSAO_SHARED_BINS\n// Each invocation owns one column; no inter-invocation sharing or new barrier.\nshared float hitVShared[gridQSize][64];\nfloat readHit(uint bin) {return hitVShared[bin][gl_LocalInvocationIndex];}\nvoid writeHit(uint bin,float value) {hitVShared[bin][gl_LocalInvocationIndex]=value;}\n#else\nfloat hitV[gridQSize];\nfloat readHit(uint bin) {return hitV[bin];}\nvoid writeHit(uint bin,float value) {hitV[bin]=value;}\n#endif')

replace_once('shader/ssao/ssao_shared.comp', '  uint uv = pyramidId(dir);\n\n  hits', '  uint uv = pyramidId(dir);\n  // Zero/degenerate directions must not address outside a bin array.\n  if(uv>=uint(gridQSize)) return;\n\n  hits')

replace_once('shader/ssao/ssao_shared.comp', '  uint uv = pyramidId(dir);\n  anySmp', '  uint uv = pyramidId(dir);\n  if(uv>=uint(gridQSize)) return;\n  anySmp')

replace_once('shader/ssao/ssao_shared.comp', '  float value   = hitV[uv];', '  float value   = readHit(uv);')

replace_once('shader/ssao/ssao_shared.comp', '  hitV[uv] = max(value, v);', '  writeHit(uv,max(value, v));')

replace_once('shader/ssao/ssao_shared.comp', '    hitV[i] = 0;', '    writeHit(uint(i),0);')

replace_once('common/graphics/shaders.h', '    Tempest::ComputePipeline ssao, ssaoBlur, ssaoHalf, ssaoUpsample;', '    Tempest::ComputePipeline ssao, ssaoBlur, ssaoHalf, ssaoUpsample;\n    Tempest::ComputePipeline ssaoShared, ssaoHalfShared;')

replace_once('common/graphics/shaders.cpp', '#include "utils/string_frm.h"', '#include "utils/string_frm.h"\n#if defined(__ANDROID__)\n#include "utils/androidframeprofile.h"\n#endif')

replace_once('common/graphics/renderer.cpp', '#include "utils/string_frm.h"', '#include "utils/string_frm.h"\n#if defined(__ANDROID__)\n#include "utils/androidframeprofile.h"\n#endif')

replace_once('common/graphics/shaders.cpp', '  opts.doSoftwareShadow = Shaders::isRtsmSupported()', '#if defined(__ANDROID__)\n  AndroidSsaoTuner::configure(isTurnipAdreno650() && gpu.compute.maxSharedMemory>=8192);\n#endif\n  opts.doSoftwareShadow = Shaders::isRtsmSupported()')

replace_once('common/graphics/shaders.cpp', '  ssaoUpsample        = computeShader("ssao_upsample.comp.sprv");', '  ssaoUpsample        = computeShader("ssao_upsample.comp.sprv");\n#if defined(__ANDROID__)\n  if(AndroidSsaoTuner::supported()) {\n    ssaoShared     = computeShader("ssao_shared.comp.sprv");\n    ssaoHalfShared = computeShader("ssao_half_shared.comp.sprv");\n    Log::i("FIX29 SSAO A/B: private vs shared bins; 8 pairs; shared requires >5% median gain and 6 pair wins");\n    }\n#endif')

replace_once('common/graphics/renderer.cpp', '  cmd.setDebugMarker("SSAO");', '#if defined(__ANDROID__)\n  const bool sharedBins=AndroidSsaoTuner::useShared(halfResolution);\n  cmd.setDebugMarker(halfResolution ? (sharedBins?"SSAO shared half":"SSAO private half") :\n                                     (sharedBins?"SSAO shared full":"SSAO private full"));\n#else\n  cmd.setDebugMarker("SSAO");\n#endif')

replace_once('common/graphics/renderer.cpp', '  cmd.setPipeline(halfResolution ? shaders.ssaoHalf : shaders.ssao);', '#if defined(__ANDROID__)\n  if(sharedBins)\n    cmd.setPipeline(halfResolution ? shaders.ssaoHalfShared : shaders.ssaoShared);\n  else\n#endif\n    cmd.setPipeline(halfResolution ? shaders.ssaoHalf : shaders.ssao);')
