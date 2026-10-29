#!/usr/bin/env python3
"""Execute generated loader to check configuration order, overrides and fallback restoration."""
import pathlib, subprocess, sys, tempfile
repo=pathlib.Path(__file__).resolve().parent.parent
headers=pathlib.Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='turnip-tuning-') as tmp:
 p=pathlib.Path(tmp);inc=p/'include/android';inc.mkdir(parents=True)
 (inc/'native_window.h').write_text('#pragma once\ntypedef struct ANativeWindow ANativeWindow;\n')
 (inc/'log.h').write_text('#pragma once\n#define ANDROID_LOG_INFO 4\n#define ANDROID_LOG_WARN 5\n#define ANDROID_LOG_ERROR 6\nstatic inline int __android_log_print(int,const char*,const char*,...){return 0;}\n')
 subprocess.run([sys.executable,str(repo/'overlay/gen_vulkan_proxy.py'),str(headers/'registry/vk.xml'),str(p/'vulkan_proxy.cpp')],check=True)
 (p/'test.cpp').write_text(r'''
#include "vulkan_proxy.cpp"
#include <cassert>
#include <cstdio>
static bool customSuccess=true,toolsAvailable=true;
static const char* expectedAlgo="profiled";
static const char* expectedFlags="tune_small";
static int openCalls=0;
static bool eq(const char* a,const char* b){return a && !strcmp(a,b);}
static void* fakeOpen(int,int,const char*,const char*,const char*,const char*,const char*,void**){
 ++openCalls;
 assert(eq(getenv("TU_AUTOTUNE_ALGO"),expectedAlgo));
 assert(eq(getenv("TU_AUTOTUNE_FLAGS"),expectedFlags));
 assert(strstr(getenv("TU_DEBUG"),"startup"));
 return customSuccess ? (void*)0x2 : nullptr;
}
extern "C" int __wrap_dladdr(const void*,Dl_info* i){i->dli_fname="/app/libproxy.so";return 1;}
extern "C" void* __wrap_dlopen(const char* s,int){
 if(strstr(s,"libadrenotools.so"))return toolsAvailable ? (void*)0x1 : nullptr;
 assert(eq(s,"/system/lib64/libvulkan.so"));return (void*)0x3;
}
extern "C" void* __wrap_dlsym(void*,const char* s){assert(eq(s,"adrenotools_open_libvulkan"));return (void*)&fakeOpen;}
void reset(){g_loader=nullptr;g_turnip=false;openCalls=0;unsetenv("TU_AUTOTUNE_ALGO");unsetenv("TU_AUTOTUNE_FLAGS");unsetenv("TU_DEBUG");}
int main(){
 reset();initLoader();assert(g_turnip&&g_loader==(void*)0x2&&openCalls==1);
 assert(eq(getenv("TU_AUTOTUNE_ALGO"),"profiled"));assert(eq(getenv("TU_AUTOTUNE_FLAGS"),"tune_small"));
 reset();customSuccess=false;initLoader();assert(!g_turnip&&g_loader==(void*)0x3&&openCalls==1);
 assert(!getenv("TU_AUTOTUNE_ALGO")&&!getenv("TU_AUTOTUNE_FLAGS")&&!getenv("TU_DEBUG"));
 for(bool success:{false,true}){
  reset();customSuccess=success;expectedAlgo="bandwidth";expectedFlags="big_gmem";
  setenv("TU_AUTOTUNE_ALGO",expectedAlgo,1);setenv("TU_AUTOTUNE_FLAGS",expectedFlags,1);setenv("TU_DEBUG","perf",1);
  initLoader();assert(g_turnip==success&&openCalls==1);
  assert(eq(getenv("TU_AUTOTUNE_ALGO"),expectedAlgo)&&eq(getenv("TU_AUTOTUNE_FLAGS"),expectedFlags));
  assert(eq(getenv("TU_DEBUG"),success?"perf,startup":"perf"));
 }
 reset();toolsAvailable=false;initLoader();assert(!g_turnip&&g_loader==(void*)0x3&&openCalls==0);
 assert(!getenv("TU_AUTOTUNE_ALGO")&&!getenv("TU_AUTOTUNE_FLAGS")&&!getenv("TU_DEBUG"));
 puts("PASS: generated loader sets measured policy before opening Turnip; preserves overrides, restores environment on failure, leaves system-only path untouched.");
}
''')
 subprocess.run(['g++','-std=c++20','-pthread','-I'+str(p/'include'),'-I'+str(headers/'include'),str(p/'test.cpp'),'-Wl,--wrap=dlsym','-Wl,--wrap=dlopen','-Wl,--wrap=dladdr','-ldl','-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=10)
