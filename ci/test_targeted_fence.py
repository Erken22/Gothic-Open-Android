#!/usr/bin/env python3
"""Exercise the actual patched waitFence body against a deterministic Vulkan stub."""
import ast
import pathlib
import subprocess
import tempfile
repo=pathlib.Path(__file__).resolve().parent.parent
body=None
for node in ast.walk(ast.parse((repo/'apply_067.py').read_text())):
    if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Name) or node.func.id!='replace_once': continue
    if ast.literal_eval(node.args[0])!='lib/Tempest/Engine/gapi/vulkan/vdevice.cpp': continue
    old=ast.literal_eval(node.args[1])
    if old.startswith('VkResult VDevice::waitFence('):body=ast.literal_eval(node.args[2])
assert body
stub=r'''
#include <mutex>
#include <chrono>
#include <limits>
#include <cstring>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <atomic>
#include <thread>
using VkResult=int;
using VkFence=uint64_t;
constexpr VkResult VK_SUCCESS=0,VK_NOT_READY=1,VK_TIMEOUT=2,VK_ERROR_DEVICE_LOST=-4;
constexpr VkFence VK_NULL_HANDLE=0;
constexpr bool VK_TRUE=true;
static bool turnip=true;
int opengothic_vulkan_is_turnip(){return turnip;}
struct VFence {
  VkFence fence=7;
  VkResult status=VK_NOT_READY;
  int payload=1;
  void setStatus(VkResult r){status=r;if(r==VK_SUCCESS || r<0 || r==VK_TIMEOUT)payload=0;}
};
static int nativeCalls=0,queryCalls=0;
static VkResult nativeResult=VK_SUCCESS,queryResult=VK_NOT_READY;
static uint32_t nativeCount=0;
static uint64_t nativeTimeout=0;
static VkFence nativeFence=0;
static bool nativeAll=false;
static bool concurrent=false;
static std::atomic_bool entered=false,releaseWait=false;
VkResult vkWaitForFences(int,uint32_t count,const VkFence* f,bool all,uint64_t timeout) {
  ++nativeCalls;nativeCount=count;nativeFence=*f;nativeAll=all;nativeTimeout=timeout;
  if(concurrent){entered.store(true);while(!releaseWait.load())std::this_thread::yield();}
  return nativeResult;
}
VkResult vkGetFenceStatus(int,VkFence){++queryCalls;return queryResult;}
struct VDevice {
  struct {int impl=1;} device;
  struct {char name[64]="Turnip Adreno (TM) 650";} props;
  struct {std::mutex sync;} timeline;
  VFence* requested=nullptr;
  int anyCalls=0;
  void waitAny(uint64_t){++anyCalls;requested->setStatus(VK_SUCCESS);}
  VkResult waitFence(VFence&,uint64_t);
};
'''
main=r'''
int main() {
  VDevice d;VFence t;d.requested=&t;
  auto reset=[&]{t=VFence{};nativeCalls=0;queryCalls=0;nativeResult=VK_SUCCESS;queryResult=VK_NOT_READY;d.anyCalls=0;turnip=true;};
  reset();assert(d.waitFence(t,25)==VK_SUCCESS);assert(nativeCalls==1 && nativeCount==1 && nativeFence==7 && nativeAll && nativeTimeout==25000000);assert(t.status==VK_SUCCESS && t.payload==0 && d.anyCalls==0);
  reset();nativeResult=VK_TIMEOUT;assert(d.waitFence(t,25)==VK_NOT_READY);assert(t.status==VK_NOT_READY && t.payload==1);
  reset();assert(d.waitFence(t,std::numeric_limits<uint64_t>::max())==VK_SUCCESS);assert(nativeTimeout==std::numeric_limits<uint64_t>::max());
  reset();nativeResult=VK_ERROR_DEVICE_LOST;assert(d.waitFence(t,25)==VK_ERROR_DEVICE_LOST);assert(t.payload==1);
  reset();assert(d.waitFence(t,0)==VK_NOT_READY);assert(nativeCalls==0 && queryCalls==1 && t.payload==1);
  reset();queryResult=VK_SUCCESS;assert(d.waitFence(t,0)==VK_SUCCESS);assert(nativeCalls==0 && t.payload==0);
  reset();t.fence=VK_NULL_HANDLE;assert(d.waitFence(t,25)==VK_SUCCESS && nativeCalls==0);
  reset();t.status=VK_SUCCESS;assert(d.waitFence(t,25)==VK_SUCCESS && nativeCalls==0);
  reset();t.status=VK_ERROR_DEVICE_LOST;assert(d.waitFence(t,25)==VK_ERROR_DEVICE_LOST && nativeCalls==0);
  reset();turnip=false;assert(d.waitFence(t,25)==VK_SUCCESS && nativeCalls==0 && d.anyCalls==1);
  reset();std::strcpy(d.props.name,"Turnip Adreno (TM) 740");assert(d.waitFence(t,25)==VK_SUCCESS && nativeCalls==0 && d.anyCalls==1);
  reset();std::strcpy(d.props.name,"Turnip Adreno (TM) 650");concurrent=true;
  std::thread waiter([&]{assert(d.waitFence(t,25)==VK_SUCCESS);});
  while(!entered.load())std::this_thread::yield();
  assert(!d.timeline.sync.try_lock());
  assert(t.payload==1);
  releaseWait.store(true);waiter.join();
  assert(t.payload==0 && d.timeline.sync.try_lock());d.timeline.sync.unlock();
  puts("PASS: target fence stays locked against recycling until native completion.");
  puts("PASS: exact target wait; poll/timeout/error/resource semantics; system and other GPUs keep existing path.");
}
'''
with tempfile.TemporaryDirectory(prefix='gothic-fence-test-') as tmp:
    src=pathlib.Path(tmp)/'test.cpp';exe=pathlib.Path(tmp)/'test'
    src.write_text(stub+body+main)
    subprocess.run(['g++','-std=c++20','-D__ANDROID__','-pthread',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=10)
