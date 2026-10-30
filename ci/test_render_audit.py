#!/usr/bin/env python3
"""Compile actual audit helper against Vulkan headers and mock extension responses."""
import os,pathlib,subprocess,sys,tempfile
root=pathlib.Path(sys.argv[1]);headers=pathlib.Path(sys.argv[2]).resolve()
h=(root/'lib/Tempest/Engine/gapi/vulkan/vandroidrenderaudit.h').read_text()
d=(root/'lib/Tempest/Engine/gapi/vulkan/vdevice.cpp').read_text();pso=(root/'lib/Tempest/Engine/gapi/vulkan/vpipeline.cpp').read_text()
for contract in ('androidAuditTarget && hasDeviceFeatures2 && !props.hasDescriptorHeap','extensionSupport(extensionsList(pdev),VK_KHR_PIPELINE_EXECUTABLE_PROPERTIES_EXTENSION_NAME)','if(query!=nullptr)','auditFeatures.pipelineExecutableInfo==VK_TRUE','if(pipelineAuditEnabled) features.pNext=&auditFeatures;'):assert contract in d
assert 'device.pipelineAuditEnabled && AndroidPipelineAudit::target(comp.dbgShortName())' in pso
assert 'if(captureStats)info.flags|=VK_PIPELINE_CREATE_CAPTURE_STATISTICS_BIT_KHR;' in pso
assert 'WAIT_BIT' not in h and 'vkDeviceWaitIdle' not in h and 'vkGetQueryPoolResults' not in h
stub='''#pragma once
#include <sstream>
#include <vector>
#include <string>
namespace Tempest {struct Log {inline static std::vector<std::string> lines;template<class... Args>static void i(const Args&...args){std::ostringstream s;(s<<...<<args);lines.push_back(s.str());}};}
'''
code=r'''
#include "audit.h"
#include <cassert>
#include <cstring>
#include <thread>
#include <vector>
int mode=0,propsCalls=0,statsCalls=0;
VkResult VKAPI_CALL properties(VkDevice,const VkPipelineInfoKHR*,uint32_t* count,VkPipelineExecutablePropertiesKHR* values){
 ++propsCalls;if(mode==1)return VK_ERROR_UNKNOWN;
 if(!values){*count=mode==2?10000u:1u;return VK_SUCCESS;}
 for(uint32_t i=0;i<*count;++i){assert(values[i].sType==VK_STRUCTURE_TYPE_PIPELINE_EXECUTABLE_PROPERTIES_KHR);std::strcpy(values[i].name,"compute");values[i].subgroupSize=64;}
 return mode==2?VK_INCOMPLETE:VK_SUCCESS;
}
VkResult VKAPI_CALL statistics(VkDevice,const VkPipelineExecutableInfoKHR*,uint32_t* count,VkPipelineExecutableStatisticKHR* values){
 ++statsCalls;if(mode==3)return VK_ERROR_UNKNOWN;
 if(!values){*count=mode==2?10000u:4u;return VK_SUCCESS;}
 for(uint32_t i=0;i<*count;++i){assert(values[i].sType==VK_STRUCTURE_TYPE_PIPELINE_EXECUTABLE_STATISTIC_KHR);std::strcpy(values[i].name,"stat");values[i].format=VkPipelineExecutableStatisticFormatKHR(i%4);
 switch(i%4){case 0:values[i].value.b32=VK_TRUE;break;case 1:values[i].value.i64=-7;break;case 2:values[i].value.u64=99;break;default:values[i].value.f64=1.25;break;}}
 return mode==2?VK_INCOMPLETE:VK_SUCCESS;
}
PFN_vkVoidFunction VKAPI_CALL getProc(VkDevice,const char* name){
 if(mode==4)return nullptr;
 if(std::strcmp(name,"vkGetPipelineExecutablePropertiesKHR")==0)return reinterpret_cast<PFN_vkVoidFunction>(properties);
 if(std::strcmp(name,"vkGetPipelineExecutableStatisticsKHR")==0)return reinterpret_cast<PFN_vkVoidFunction>(statistics);
 return nullptr;
}
int main(){
 assert(AndroidPipelineAudit::target("ssao.comp") && AndroidPipelineAudit::target("fog.frag"));
 assert(!AndroidPipelineAudit::target("fog_batched.frag") && !AndroidPipelineAudit::target("vsm_list_pages.comp"));
 auto has=[](const char* text){for(auto& l:Tempest::Log::lines)if(l.find(text)!=std::string::npos)return true;return false;};
 AndroidPipelineAudit::report(VK_NULL_HANDLE,VK_NULL_HANDLE,"ssao.comp",8,8,1,getProc);
 assert(has("compile-time-only=1") && has("value=-7") && has("value=99") && has("value=1.25"));
 mode=1;AndroidPipelineAudit::report(VK_NULL_HANDLE,VK_NULL_HANDLE,"ssao.comp",8,8,1,getProc);assert(has("no executables"));
 mode=2;Tempest::Log::lines.clear();AndroidPipelineAudit::report(VK_NULL_HANDLE,VK_NULL_HANDLE,"ssao.comp",8,8,1,getProc);
 assert(has("executables=16") && has("partial=1") && Tempest::Log::lines.size()<=1041);
 mode=3;Tempest::Log::lines.clear();AndroidPipelineAudit::report(VK_NULL_HANDLE,VK_NULL_HANDLE,"ssao.comp",8,8,1,getProc);assert(!has("FIX37 stat:"));
 mode=4;AndroidPipelineAudit::report(VK_NULL_HANDLE,VK_NULL_HANDLE,"ssao.comp",8,8,1,getProc);assert(has("unavailable entry points"));
 AndroidCommandAudit::tickets=0;AndroidCommandAudit a;a.begin(false);assert(!a.active && AndroidCommandAudit::tickets==0);
 a.begin(true);a.marker("GBuffer");a.pass();
 a.attachment(VK_FORMAT_R8G8B8A8_UNORM,2400,1080,VK_ATTACHMENT_LOAD_OP_LOAD,VK_ATTACHMENT_STORE_OP_STORE);
 a.attachment(VK_FORMAT_D16_UNORM,2400,1080,VK_ATTACHMENT_LOAD_OP_CLEAR,VK_ATTACHMENT_STORE_OP_STORE);
 a.attachment(VK_FORMAT_UNDEFINED,1,1,VK_ATTACHMENT_LOAD_OP_LOAD,VK_ATTACHMENT_STORE_OP_STORE);
 a.draw(12,false);a.draw(0,true);a.dispatch(15);a.barrier(VK_PIPELINE_STAGE_ALL_GRAPHICS_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,2);
 auto& r=a.rows[a.index];assert(r.loads==10368000 && r.stores==15552000 && r.clears==1 && r.unknown==1);
 assert(r.draws==2 && r.indirect==1 && r.vertices==12 && r.groups==15 && r.broad==1 && r.images==2);
 for(int i=0;i<300;++i)a.marker("limit");assert(a.index==127);a.finish();assert(!a.active);
 for(int i=0;i<3;++i){a.begin(true);assert(a.active);a.finish();}a.begin(true);assert(!a.active);
 AndroidCommandAudit::tickets=0;std::atomic_uint captured{0};std::vector<std::thread> workers;
 for(int i=0;i<8;++i)workers.emplace_back([&](){AndroidCommandAudit b;for(int n=0;n<20;++n){b.begin(true);if(b.active)++captured;}});
 for(auto& t:workers)t.join();assert(captured==4);
 puts("PASS: real compiler query handling, bounded/incomplete data, all value formats, capability/flag gates; nominal attachment arithmetic, indirect unknown counts, row limit and four-sample concurrency budget.");
}
'''
with tempfile.TemporaryDirectory(prefix='renderer-audit-') as tmp:
 p=pathlib.Path(tmp);(p/'Tempest').mkdir();(p/'Tempest/Log').write_text(stub);(p/'audit.h').write_text(h);(p/'vulkan_sdk.h').write_text('#include <vulkan/vulkan.h>\n');(p/'test.cpp').write_text(code)
 subprocess.run(['g++','-std=c++20','-O1','-g','-fsanitize=address,undefined','-pthread','-I'+str(p),'-I'+str(headers/'include'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=20,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
