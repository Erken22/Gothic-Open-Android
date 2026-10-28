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

# This script runs after the first CMake configure, when the Android fork has
# already applied its normal Tempest patch.

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
    "lib/Tempest/Engine/system/api/androidapi.h",
'''    static bool processTouchEvents(AppCallBack& cb);
    static void updateFocus();
    static void updateWindow();
''',
'''    static bool processTouchEvents(AppCallBack& cb);
    static void updateFocus();
    static void updateWindow();
    static void applyPendingWindowReset();
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
  int32_t        width  = 0;
  int32_t        height = 0;
  };
static AndroidWindowHandle androidWindow;
static ANativeWindow* retiredWindow = nullptr;
static bool windowInvalidated = false;
static bool windowResetPending = false;
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
'''void AndroidApi::updateFocus() {
  const bool next = resumed && focused;
  if(active==next)
    return;
  active = next;
  if(mainWindow!=nullptr) {
    FocusEvent event(active,Event::FocusReason::UnknownReason);
    AndroidApi::dispatchFocus(*mainWindow,event);
    }
  }
''',
'''void AndroidApi::applyPendingWindowReset() {
  if(!windowResetPending || !active || !hasWindow || mainWindow==nullptr || androidWindow.native==nullptr)
    return;

  windowResetPending = false;
  Log::i("Android applying deferred surface/swapchain reset: ",
         androidWindow.width,"x",androidWindow.height);

  SizeEvent event(androidWindow.width,androidWindow.height);
  AndroidApi::dispatchResize(*mainWindow,event);

  if(retiredWindow!=nullptr) {
    ANativeWindow_release(retiredWindow);
    retiredWindow = nullptr;
    }
  }

void AndroidApi::updateFocus() {
  // Rendering must not depend on GAINED_FOCUS. Some MIUI builds can restore
  // the NativeWindow/RESUME before focus arrives (or delay focus indefinitely),
  // which otherwise leaves a valid swapchain permanently black.
  const bool next = resumed && hasWindow;
  if(active!=next) {
    active = next;
    if(mainWindow!=nullptr) {
      FocusEvent event(focused && active,Event::FocusReason::UnknownReason);
      AndroidApi::dispatchFocus(*mainWindow,event);
      }
    }

  // Do not reset here. INIT_WINDOW/CONFIG_CHANGED/RESIZE can arrive in a
  // burst during resume; implProcessEvents() applies one reset only after the
  // Android looper queue is drained and the final landscape surface is known.
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
  const int32_t w = ANativeWindow_getWidth(newWindow);
  const int32_t h = ANativeWindow_getHeight(newWindow);

  const bool surfaceChanged = windowInvalidated || oldWindow!=newWindow;
  const bool sizeChanged    = androidWindow.width!=w || androidWindow.height!=h;

  if(surfaceChanged || sizeChanged) {
    if(oldWindow!=newWindow) {
      ANativeWindow_acquire(newWindow);

      // Keep the window referenced by the current VkSurfaceKHR alive until the
      // deferred reset has destroyed that surface. Intermediate NativeWindows
      // that Vulkan never used can be released immediately.
      if(retiredWindow==nullptr)
        retiredWindow = oldWindow;
      else if(oldWindow!=nullptr && oldWindow!=retiredWindow)
        ANativeWindow_release(oldWindow);

      androidWindow.native = newWindow;
      }

    androidWindow.width  = w;
    androidWindow.height = h;
    windowInvalidated    = false;
    windowResetPending   = true;

    Log::i("Android window available: ",w,"x",h,
           ", surfaceChanged=",surfaceChanged,", sizeChanged=",sizeChanged,
           ", deferredReset=1");
    }

  // INIT_WINDOW may arrive before RESUME or GAINED_FOCUS. If lifecycle flags
  // are already active this applies immediately; otherwise updateFocus() on a
  // later command will perform exactly one reset.
  updateFocus();
  }
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''    case APP_CMD_CONFIG_CHANGED:
      // Android often emits CONFIG_CHANGED immediately after INIT_WINDOW on
      // resume/rotation. Route it through the same generation/size dedupe so
      // one NativeWindow can never cause a second swapchain reset.
      updateWindow();
      break;
''',
'''    case APP_CMD_CONFIG_CHANGED:
      updateWindow();
      break;
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
'''    case APP_CMD_TERM_WINDOW: {
      // NativeActivity still gives us the old ANativeWindow while handling
      // TERM_WINDOW. Tear Vulkan presentation down immediately, before Android
      // destroys the BufferQueue, instead of carrying acquired images into the
      // next surface generation.
      hasWindow = false;
      windowInvalidated = true;
      windowResetPending = false;
      releaseAllTouches();
      updateFocus();

      ANativeWindow* oldWindow = androidWindow.native;
      androidWindow.native = nullptr;
      androidWindow.width  = 0;
      androidWindow.height = 0;

      if(mainWindow!=nullptr) {
        SizeEvent event(0,0);
        AndroidApi::dispatchResize(*mainWindow,event);
        }

      if(retiredWindow!=nullptr) {
        ANativeWindow_release(retiredWindow);
        retiredWindow = nullptr;
        }
      if(oldWindow!=nullptr)
        ANativeWindow_release(oldWindow);

      Log::i("Android window suspended: Vulkan surface released, game kept alive");
      break;
      }
    case APP_CMD_DESTROY:
      hasWindow = false;
      updateFocus();
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
  androidWindow.width   = ANativeWindow_getWidth(androidWindow.native);
  androidWindow.height  = ANativeWindow_getHeight(androidWindow.native);
  retiredWindow         = nullptr;
  windowInvalidated     = false;
  windowResetPending    = false;
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
  if(retiredWindow!=nullptr) {
    ANativeWindow_release(retiredWindow);
    retiredWindow = nullptr;
    }
  if(h!=nullptr && h->native!=nullptr) {
    ANativeWindow_release(h->native);
    h->native = nullptr;
    h->width  = 0;
    h->height = 0;
    }
  windowResetPending = false;
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
'''  std::initializer_list<VkPresentModeKHR> modes={
    VK_PRESENT_MODE_FIFO_KHR,         // vsync; optimal
    VK_PRESENT_MODE_MAILBOX_KHR,      // vsync; wait until vsync
    VK_PRESENT_MODE_FIFO_RELAXED_KHR, // vsync; optimal, but tearing
    VK_PRESENT_MODE_IMMEDIATE_KHR,    // no vsync
    };
''',
'''#if defined(__ANDROID__)
  // MAILBOX keeps VSync but does not force the renderer into FIFO's coarse
  // 60->30 pacing step when a frame narrowly misses a refresh. Fall back to
  // required Android FIFO if the driver does not expose MAILBOX.
  std::initializer_list<VkPresentModeKHR> modes={
    VK_PRESENT_MODE_MAILBOX_KHR,
    VK_PRESENT_MODE_FIFO_RELAXED_KHR,
    VK_PRESENT_MODE_IMMEDIATE_KHR,
    VK_PRESENT_MODE_FIFO_KHR,
    };
#else
  std::initializer_list<VkPresentModeKHR> modes={
    VK_PRESENT_MODE_FIFO_KHR,
    VK_PRESENT_MODE_MAILBOX_KHR,
    VK_PRESENT_MODE_FIFO_RELAXED_KHR,
    VK_PRESENT_MODE_IMMEDIATE_KHR,
    };
#endif
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
  // Surface lifetime follows ANativeWindow lifetime. TERM_WINDOW intentionally
  // clears the current native handle: destroy the old VkSurfaceKHR and remain
  // suspended. INIT_WINDOW later installs the new handle and reset recreates
  // both the surface and swapchain.
  cleanupSurface();
  if(AndroidApi::nativeWindow(hwnd)==nullptr) {
    swapChainExtent = {};
    return;
    }
#endif
  createSwapchain(device);
  }
'''
)

replace_once(
    "lib/Tempest/Engine/system/api/androidapi.cpp",
'''  if(!visible || isExit.load())
    return;

  if(cb.onTimer()==0)
    std::this_thread::yield();

  if(mainWindow!=nullptr)
    dispatchRender(*mainWindow);
''',
'''  if(!visible || isExit.load())
    return;

  // All currently queued NativeActivity commands have been consumed when
  // pollOnce() reaches here. Rebuild now, after INIT_WINDOW + rotation/config
  // + resize have settled, so the swapchain targets the final landscape
  // surface instead of an intermediate one.
  if(windowResetPending) {
    applyPendingWindowReset();
    return;
    }

  if(cb.onTimer()==0)
    std::this_thread::yield();

  if(mainWindow!=nullptr)
    dispatchRender(*mainWindow);
'''
)


# Do not block the CPU at the end of every present waiting for the next
# swapchain image. Acquire lazily when the next frame actually asks for the
# backbuffer; game tick/UI work can then overlap display/GPU progress.
replace_once(
    "lib/Tempest/Engine/gapi/vulkan/vswapchain.cpp",
'''uint32_t VSwapchain::currentBackBufferIndex() {
  return imgIndex;
  }
''',
'''uint32_t VSwapchain::currentBackBufferIndex() {
  if(imgIndex==uint32_t(-1))
    acquireNextImage();
  return imgIndex;
  }
'''
)

replace_once(
    "lib/Tempest/Engine/gapi/vulkan/vswapchain.cpp",
'''  //Log::i("vkQueuePresentKHR[",imgIndex,"] = ", tx);
  Detail::vkAssert(code);

  acquireNextImage();
  }
''',
'''  //Log::i("vkQueuePresentKHR[",imgIndex,"] = ", tx);
  Detail::vkAssert(code);

  // Acquire on demand in currentBackBufferIndex(). Keeping present() free of
  // an infinite-timeout vkAcquireNextImageKHR avoids serializing the whole
  // next CPU frame behind SurfaceFlinger.
  imgIndex = uint32_t(-1);
  }
'''
)

print("Post-config Tempest lazy-acquire + settled resume patch applied")
