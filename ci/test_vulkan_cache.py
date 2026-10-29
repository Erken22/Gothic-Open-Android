#!/usr/bin/env python3
"""Verify once-only symbol resolution with concurrent real wrapper calls."""
import pathlib,subprocess,sys,tempfile
repo=pathlib.Path(__file__).resolve().parent.parent
headers=pathlib.Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='gothic-dispatch-test-') as tmp:
    p=pathlib.Path(tmp);inc=p/'include/android';inc.mkdir(parents=True)
    (inc/'native_window.h').write_text('#pragma once\ntypedef struct ANativeWindow ANativeWindow;\n')
    (inc/'log.h').write_text('#pragma once\n#define ANDROID_LOG_INFO 4\n#define ANDROID_LOG_WARN 5\n#define ANDROID_LOG_ERROR 6\nstatic inline int __android_log_print(int,const char*,const char*,...){return 0;}\n')
    subprocess.run([sys.executable,str(repo/'overlay/gen_vulkan_proxy.py'),str(headers/'registry/vk.xml'),str(p/'vulkan_proxy.cpp')],check=True)
    (p/'test.cpp').write_text(r'''
#include "vulkan_proxy.cpp"
#include <atomic>
#include <cassert>
#include <thread>
#include <vector>
#include <cstdio>
static std::atomic_int bindLookups=0,bindCalls=0,gpaLookups=0,gpaCalls=0;
static void VKAPI_CALL fakeBind(VkCommandBuffer cmd,VkPipelineBindPoint point,VkPipeline pipeline) {
  assert(cmd==(VkCommandBuffer)0x1234 && point==VK_PIPELINE_BIND_POINT_GRAPHICS && pipeline==(VkPipeline)0x5678);
  ++bindCalls;
}
static void VKAPI_CALL procA(){}
static void VKAPI_CALL procB(){}
static PFN_vkVoidFunction VKAPI_CALL fakeGpa(VkDevice dev,const char* name) {
  ++gpaCalls;
  if(!strcmp(name,"unsupported"))return nullptr;
  return dev==(VkDevice)0x1111 ? &procA : &procB;
}
extern "C" void* __wrap_dlsym(void*,const char* name) {
  if(!strcmp(name,"vkCmdBindPipeline")){++bindLookups;return (void*)&fakeBind;}
  if(!strcmp(name,"vkGetDeviceProcAddr")){++gpaLookups;return (void*)&fakeGpa;}
  assert(false);return nullptr;
}
int main() {
  std::call_once(g_once,[]{});g_loader=(void*)0x1;
  std::vector<std::thread> threads;
  for(int i=0;i<8;++i)threads.emplace_back([]{
    for(int j=0;j<10000;++j)vkCmdBindPipeline((VkCommandBuffer)0x1234,VK_PIPELINE_BIND_POINT_GRAPHICS,(VkPipeline)0x5678);
  });
  for(auto& thread:threads)thread.join();
  assert(bindCalls==80000 && bindLookups==1);
  assert(vkGetDeviceProcAddr((VkDevice)0x1111,"test")==&procA);
  assert(vkGetDeviceProcAddr((VkDevice)0x2222,"test")==&procB);
  assert(vkGetDeviceProcAddr((VkDevice)0x1111,"unsupported")==nullptr);
  assert(gpaLookups==1 && gpaCalls==3);
  puts("PASS: 80000 concurrent calls use one symbol lookup; arguments, per-device queries and unsupported results preserved.");
}
''')
    subprocess.run(['g++','-std=c++20','-pthread','-I'+str(p/'include'),'-I'+str(headers/'include'),str(p/'test.cpp'),'-Wl,--wrap=dlsym','-ldl','-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True,timeout=10)
