#!/usr/bin/env python3
import sys, xml.etree.ElementTree as ET
from pathlib import Path

NAMES = """
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
vkWaitForFences
""".strip().splitlines()

def text_of(elem):
    return ''.join(elem.itertext()).replace('\n',' ').replace('\t',' ')

def norm(s):
    return ' '.join(s.split()).replace(' *','*').replace('* ','* ')

xml_path=Path(sys.argv[1])
out_path=Path(sys.argv[2])
root=ET.parse(xml_path).getroot()
commands={}
for cmd in root.findall('./commands/command'):
    proto=cmd.find('proto')
    if proto is None:
        continue
    nm=proto.find('name')
    if nm is None or nm.text not in NAMES:
        continue
    name=nm.text
    ptxt=text_of(proto)
    pos=ptxt.rfind(name)
    ret=norm(ptxt[:pos])
    params=[]
    args=[]
    for p in cmd.findall('param'):
        api=p.get('api')
        if api and 'vulkan' not in api.split(','):
            continue
        params.append(norm(text_of(p)))
        ne=p.find('name')
        args.append(ne.text)
    commands[name]=(ret,', '.join(params),', '.join(args))

missing=[n for n in NAMES if n not in commands]
if missing:
    raise SystemExit('Missing commands: '+', '.join(missing))

head=r'''#include "vulkan_redirect.h"
// Generated at build time from Khronos vk.xml.
// OpenGothic FIX20 app-local Vulkan proxy.
// Tries Mesa Turnip via libadrenotools, falls back to Android system Vulkan.

#define VK_USE_PLATFORM_ANDROID_KHR 1
#include <vulkan/vulkan.h>
#include <android/log.h>
#include <dlfcn.h>
#include <mutex>
#include <string>
#include <cstring>
#include <cstdlib>
#include <array>
#include <atomic>
#include <thread>
#include <chrono>
#include <sys/syscall.h>
#include <unistd.h>

#define OG_TAG "OpenGothicVk"

namespace {
using OpenVk = void*(*)(int,int,const char*,const char*,const char*,const char*,const char*,void**);
std::once_flag g_once;
void* g_loader=nullptr;
bool g_turnip=false;

// Keep this process-lifetime state alive while detached diagnostics run.
// Never change Vulkan timeouts or synthesize a successful completion.
struct PendingCall {
  uint64_t id=0, start=0, reported=0, detail0=0, detail1=0;
  long tid=0;
  const char* name=nullptr;
  void* caller=nullptr;
};
uint64_t nowMs() {
  return std::chrono::duration_cast<std::chrono::milliseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count();
}
struct CallWatchdog {
  std::mutex mutex;
  std::array<PendingCall,64> calls{};
  uint64_t next=0;
  CallWatchdog() {
    std::thread([this] {
      for(;;) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        std::array<PendingCall,64> overdue{};
        size_t count=0;
        const auto now=nowMs();
        {
          std::lock_guard<std::mutex> lock(mutex);
          for(auto& call:calls) {
            if(call.id && now-call.start>=3000 &&
               (!call.reported || now-call.reported>=5000)) {
              call.reported=now;
              overdue[count++]=call;
            }
          }
        }
        for(size_t i=0;i<count;++i) {
          const auto& call=overdue[i];
          Dl_info info{};
          dladdr(call.caller,&info);
          const auto offset=reinterpret_cast<uintptr_t>(call.caller)-
                            reinterpret_cast<uintptr_t>(info.dli_fbase);
          __android_log_print(ANDROID_LOG_ERROR,OG_TAG,
              "FIX22 Vulkan pending: %s tid=%ld elapsed=%llums caller=%s+0x%llx detail0=0x%llx detail1=0x%llx",
              call.name,call.tid,(unsigned long long)(now-call.start),
              info.dli_fname ? info.dli_fname : "unknown",(unsigned long long)offset,
              (unsigned long long)call.detail0,(unsigned long long)call.detail1);
        }
      }
    }).detach();
  }
};
CallWatchdog& watchdog() {
  static auto* value=new CallWatchdog;
  return *value;
}
struct WatchCall {
  CallWatchdog& state;
  uint64_t id=0;
  WatchCall(const char* name,void* caller,uint64_t detail0=0,uint64_t detail1=0)
    :state(watchdog()) {
    std::lock_guard<std::mutex> lock(state.mutex);
    for(auto& call:state.calls) {
      if(call.id) continue;
      id=++state.next;
      call={id,nowMs(),0,detail0,detail1,syscall(SYS_gettid),name,caller};
      break;
    }
  }
  ~WatchCall() {
    std::lock_guard<std::mutex> lock(state.mutex);
    for(auto& call:state.calls) {
      if(!id || call.id!=id) continue;
      if(call.reported)
        __android_log_print(ANDROID_LOG_ERROR,OG_TAG,
            "FIX22 Vulkan returned: %s tid=%ld elapsed=%llums",call.name,call.tid,
            (unsigned long long)(nowMs()-call.start));
      call={};
      break;
    }
  }
};
std::atomic<PFN_vkQueueSubmit2> g_submit2{nullptr};
VkResult VKAPI_CALL observedQueueSubmit2(VkQueue queue,uint32_t count,
                                        const VkSubmitInfo2* submits,VkFence fence) {
  WatchCall watch("vkQueueSubmit2[KHR]",__builtin_return_address(0),count,0);
  return g_submit2.load()(queue,count,submits,fence);
}

std::string dirOf(void* p) {
  Dl_info info{};
  if(!dladdr(p,&info) || info.dli_fname==nullptr)
    return {};
  std::string s(info.dli_fname);
  auto at=s.find_last_of('/');
  if(at==std::string::npos)
    return {};
  s.resize(at+1);
  return s;
}

void initLoader() {
  const std::string nativeDir=dirOf((void*)&initLoader);
  if(nativeDir.empty()) {
    __android_log_print(ANDROID_LOG_ERROR,OG_TAG,"cannot determine nativeLibraryDir");
    return;
  }

  const std::string atPath=nativeDir+"libadrenotools.so";
  void* at=dlopen(atPath.c_str(),RTLD_NOW|RTLD_LOCAL);
  auto openVk=at ? reinterpret_cast<OpenVk>(dlsym(at,"adrenotools_open_libvulkan")) : nullptr;
  if(openVk) {
    g_loader=openVk(RTLD_NOW|RTLD_LOCAL,1,nullptr,
                    nativeDir.c_str(),nativeDir.c_str(),
                    "libvulkan_freedreno.so",nullptr,nullptr);
    if(g_loader) {
      g_turnip=true;
      __android_log_print(ANDROID_LOG_INFO,OG_TAG,
                          "FIX20 Vulkan driver: Mesa Turnip 26.3.0-R6");
      return;
    }
    __android_log_print(ANDROID_LOG_WARN,OG_TAG,
                        "Turnip load failed; trying system Vulkan");
  } else {
    __android_log_print(ANDROID_LOG_WARN,OG_TAG,
                        "libadrenotools unavailable; trying system Vulkan");
  }

  g_loader=dlopen("/system/lib64/libvulkan.so",RTLD_NOW|RTLD_LOCAL);
  if(g_loader)
    __android_log_print(ANDROID_LOG_INFO,OG_TAG,"FIX20 Vulkan driver: system Qualcomm fallback");
  else
    __android_log_print(ANDROID_LOG_ERROR,OG_TAG,"unable to open Vulkan loader: %s",dlerror());
}

void* sym(const char* name) {
  std::call_once(g_once,initLoader);
  return g_loader ? dlsym(g_loader,name) : nullptr;
}
}

extern "C" __attribute__((visibility("default"))) int opengothic_vulkan_is_turnip() {
  std::call_once(g_once,initLoader);
  return g_turnip ? 1 : 0;
}

'''
src=[head]

for name in NAMES:
    ret,sig,args=commands[name]
    if name=='vkGetInstanceProcAddr':
        src.append(r'''extern "C" __attribute__((visibility("default"))) VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetInstanceProcAddr(VkInstance instance, const char* pName) {
  auto fn=reinterpret_cast<PFN_vkGetInstanceProcAddr>(sym("vkGetInstanceProcAddr"));
  if(!fn) return nullptr;
  if(pName && std::strcmp(pName,"vkGetInstanceProcAddr")==0)
    return reinterpret_cast<PFN_vkVoidFunction>(&vkGetInstanceProcAddr);
  return fn(instance,pName);
}

''')
        continue
    if name=='vkGetDeviceProcAddr':
        src.append(r'''extern "C" __attribute__((visibility("default"))) VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetDeviceProcAddr(VkDevice device, const char* pName) {
  auto fn=reinterpret_cast<PFN_vkGetDeviceProcAddr>(sym("vkGetDeviceProcAddr"));
  if(!fn) return nullptr;
  if(pName && std::strcmp(pName,"vkGetDeviceProcAddr")==0)
    return reinterpret_cast<PFN_vkVoidFunction>(&vkGetDeviceProcAddr);
  auto result=fn(device,pName);
  if(result && pName && (std::strcmp(pName,"vkQueueSubmit2KHR")==0 ||
                        std::strcmp(pName,"vkQueueSubmit2")==0)) {
    g_submit2.store(reinterpret_cast<PFN_vkQueueSubmit2>(result));
    return reinterpret_cast<PFN_vkVoidFunction>(&observedQueueSubmit2);
  }
  return result;
}

''')
        continue
    src.append(f'extern "C" __attribute__((visibility("default"))) VKAPI_ATTR {ret} VKAPI_CALL {name}({sig}) {{\n')
    src.append(f'  auto fn=reinterpret_cast<PFN_{name}>(sym("{name}"));\n')
    if name in {'vkAcquireNextImageKHR','vkDeviceWaitIdle','vkQueueWaitIdle',
                'vkWaitForFences','vkQueuePresentKHR','vkQueueSubmit',
                'vkCreateGraphicsPipelines','vkCreateComputePipelines'}:
        details = {
            'vkAcquireNextImageKHR': 'timeout,0',
            'vkWaitForFences': 'fenceCount,timeout',
            'vkQueueSubmit': 'submitCount,0',
        }.get(name,'0,0')
        src.append(f'  WatchCall watch("{name}",__builtin_return_address(0),{details});\n')
    if ret=='void':
        src.append(f'  if(!fn) return;\n  fn({args});\n}}\n\n')
    else:
        src.append(f'  if(!fn) return {ret}{{}};\n  return fn({args});\n}}\n\n')

out_path.parent.mkdir(parents=True,exist_ok=True)
out_path.with_name('vulkan_redirect.h').write_text(
    '#pragma once\n' + ''.join(f'#define {name} opengothic_{name}\n' for name in NAMES),
    encoding='utf-8')
out_path.write_text(''.join(src),encoding='utf-8')
print(f'generated {len(NAMES)} Vulkan wrappers -> {out_path}')

