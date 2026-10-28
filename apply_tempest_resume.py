#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()

def replace_once(rel, old, new):
    p = root / rel
    s = p.read_text(encoding="utf-8")
    if old not in s:
        raise SystemExit(f"post-config resume patch anchor not found in {rel}: {old[:180]!r}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")

# This script MUST run after CMake configure: the Android fork applies
# patches/tempest-opengothic.patch to lib/Tempest during configure.

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.h",
'''    static std::filesystem::path internalDataPath();
    static std::filesystem::path externalDataPath();

    /// The application gets every input event of Android (keys, pads, touches) before Tempest: a non-zero result means that it is handled.
''',
'''    static std::filesystem::path internalDataPath();
    static std::filesystem::path externalDataPath();
    static void*                 nativeWindow(SystemApi::Window* w);

    /// The application gets every input event of Android (keys, pads, touches) before Tempest: a non-zero result means that it is handled.
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''static bool             active     = false;
static bool             hasWindow  = false;
''',
'''static bool             active     = false;
static bool             hasWindow  = false;

struct AndroidWindowHandle {
  ANativeWindow* native = nullptr;
  };
static AndroidWindowHandle androidWindow;
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''std::filesystem::path AndroidApi::externalDataPath() {
  assert(app!=nullptr && app->activity!=nullptr);
  const char* path = app->activity->externalDataPath;
  return path!=nullptr ? path : "";
  }
''',
'''std::filesystem::path AndroidApi::externalDataPath() {
  assert(app!=nullptr && app->activity!=nullptr);
  const char* path = app->activity->externalDataPath;
  return path!=nullptr ? path : "";
  }

void* AndroidApi::nativeWindow(SystemApi::Window* w) {
  if(w==nullptr)
    return nullptr;
  auto* h = reinterpret_cast<AndroidWindowHandle*>(w);
  return h->native;
  }
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''void AndroidApi::updateWindow() {
  if(app==nullptr || app->window==nullptr)
    return;

  hasWindow = true;
  if(mainWindow==nullptr)
    return;

  SizeEvent event(ANativeWindow_getWidth(app->window),ANativeWindow_getHeight(app->window));
  AndroidApi::dispatchResize(*mainWindow,event);
  }
''',
'''void AndroidApi::updateWindow() {
  if(app==nullptr || app->window==nullptr)
    return;

  hasWindow = true;
  if(mainWindow==nullptr)
    return;

  ANativeWindow* oldWindow = androidWindow.native;
  ANativeWindow* newWindow = app->window;
  if(oldWindow!=newWindow) {
    ANativeWindow_acquire(newWindow);
    androidWindow.native = newWindow;
    }

  Log::i("Android window init/resume: ",
         ANativeWindow_getWidth(newWindow),"x",ANativeWindow_getHeight(newWindow));

  // MainWindow::resizeEvent waits in-flight fences and resets the swapchain.
  // VSwapchain::reset() below recreates VkSurfaceKHR against newWindow.
  SizeEvent event(ANativeWindow_getWidth(newWindow),ANativeWindow_getHeight(newWindow));
  AndroidApi::dispatchResize(*mainWindow,event);

  // Keep the old ANativeWindow alive until the old VkSurfaceKHR is destroyed.
  if(oldWindow!=nullptr && oldWindow!=newWindow)
    ANativeWindow_release(oldWindow);
  }
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''    case APP_CMD_TERM_WINDOW:
    case APP_CMD_DESTROY:
      hasWindow = false;
      if(mainWindow!=nullptr) {
        CloseEvent event;
        AndroidApi::dispatchClose(*mainWindow,event);
        }
      isExit.store(true);
      break;
''',
'''    case APP_CMD_TERM_WINDOW:
      // Backgrounding/recents destroys only the NativeWindow surface. Do not
      // turn that into CloseEvent/application exit; INIT_WINDOW will resume.
      hasWindow = false;
      active = false;
      releaseAllTouches();
      Log::i("Android window suspended (TERM_WINDOW), keeping game alive");
      break;
    case APP_CMD_DESTROY:
      hasWindow = false;
      if(mainWindow!=nullptr) {
        CloseEvent event;
        AndroidApi::dispatchClose(*mainWindow,event);
        }
      isExit.store(true);
      break;
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''  mainWindow = owner;
  ANativeWindow_acquire(app->window);
  return reinterpret_cast<SystemApi::Window*>(app->window);
''',
'''  mainWindow = owner;
  androidWindow.native = app->window;
  ANativeWindow_acquire(androidWindow.native);
  return reinterpret_cast<SystemApi::Window*>(&androidWindow);
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''void AndroidApi::implDestroyWindow(SystemApi::Window* w) {
  ANativeWindow_release(reinterpret_cast<ANativeWindow*>(w));
  mainWindow = nullptr;
  touches.clear();
  }
''',
'''void AndroidApi::implDestroyWindow(SystemApi::Window* w) {
  auto* h = reinterpret_cast<AndroidWindowHandle*>(w);
  if(h!=nullptr && h->native!=nullptr) {
    ANativeWindow_release(h->native);
    h->native = nullptr;
    }
  mainWindow = nullptr;
  touches.clear();
  }
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''Rect AndroidApi::implWindowClientRect(SystemApi::Window* w) {
  const auto window = reinterpret_cast<ANativeWindow*>(w);
  return Rect(0,0,ANativeWindow_getWidth(window),ANativeWindow_getHeight(window));
  }
''',
'''Rect AndroidApi::implWindowClientRect(SystemApi::Window* w) {
  auto* h = reinterpret_cast<AndroidWindowHandle*>(w);
  if(h==nullptr || h->native==nullptr)
    return Rect();
  return Rect(0,0,ANativeWindow_getWidth(h->native),ANativeWindow_getHeight(h->native));
  }
'''
)

replace_once(
    "lib/Tempest/Engine/gapi/vulkan/vswapchain.cpp",
'''#elif defined(__ANDROID__)
#  include <android/native_window.h>
#  include <vulkan/vulkan_android.h>
''',
'''#elif defined(__ANDROID__)
#  include <android/native_window.h>
#  include <vulkan/vulkan_android.h>
#  include "system/api/androidapi.h"
'''
)

replace_once(
    "lib/Tempest/Engine/gapi/vulkan/vswapchain.cpp",
'''#elif defined(__ANDROID__)
  VkAndroidSurfaceCreateInfoKHR createInfo = {};
  createInfo.sType  = VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR;
  createInfo.window = reinterpret_cast<ANativeWindow*>(hwnd);
  return vkCreateAndroidSurfaceKHR(instance,&createInfo,nullptr,pSurface);
''',
'''#elif defined(__ANDROID__)
  VkAndroidSurfaceCreateInfoKHR createInfo = {};
  createInfo.sType  = VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR;
  createInfo.window = reinterpret_cast<ANativeWindow*>(
      AndroidApi::nativeWindow(reinterpret_cast<SystemApi::Window*>(hwnd)));
  if(createInfo.window==nullptr)
    return VK_ERROR_SURFACE_LOST_KHR;
  return vkCreateAndroidSurfaceKHR(instance,&createInfo,nullptr,pSurface);
'''
)

replace_once(
    "lib/Tempest/Engine/gapi/vulkan/vswapchain.cpp",
'''void VSwapchain::reset() {
  cleanupSwapchain();
  createSwapchain(device);
  }
''',
'''void VSwapchain::reset() {
  cleanupSwapchain();
#if defined(__ANDROID__)
  // A resumed NativeActivity has a new ANativeWindow; VkSurfaceKHR from the
  // previous one is no longer reusable.
  cleanupSurface();
#endif
  createSwapchain(device);
  }
'''
)

print("Post-config Tempest Android suspend/resume patch applied")
