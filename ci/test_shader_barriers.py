#!/usr/bin/env python3
"""Exercise the actual stage projection across all sync masks and enabled shader stages."""
import pathlib,subprocess,sys,tempfile
root=pathlib.Path(sys.argv[1]);headers=pathlib.Path(sys.argv[2]).resolve()
base=root/'lib/Tempest/Engine/gapi/vulkan';s=(base/'vcommandbuffer.cpp').read_text();h=(base/'vbarrierstages32.h').read_text()
a=s.index('static void toStage(');b=s.index('\nstatic VkImageLayout toLayout',a);fn=s[a:b]
original=fn.replace('toStage(','originalStage(',1).replace('dev.graphicsReadStageMask','VK_PIPELINE_STAGE_ALL_GRAPHICS_BIT').replace('dev.graphicsWriteStageMask','VK_PIPELINE_STAGE_ALL_GRAPHICS_BIT')
d=(base/'vdevice.cpp').read_text();dh=(base/'vdevice.h').read_text()
assert 'graphicsReadStageMask=VK_PIPELINE_STAGE_ALL_GRAPHICS_BIT' in dh
assert 'graphicsWriteStageMask=VK_PIPELINE_STAGE_ALL_GRAPHICS_BIT' in dh
assert 'graphicsBarrierStages32(features.features,' in d
assert 'props.meshlets.meshShader && meshFeatures.taskShader==VK_TRUE' in d
assert 'props.meshlets.meshShader && meshFeatures.meshShader==VK_TRUE' in d
assert 'graphicsBarrierStages32(deviceFeatures,false,false)' in d
flags=(root/'lib/Tempest/Engine/gapi/flags.h').read_text();a=flags.index('enum class SyncStage');b=flags.index('\ninline SyncStage operator |',a);enum=flags[a:b]
stub='''
#include <vulkan/vulkan.h>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <initializer_list>
'''+enum+'''
SyncStage operator &(SyncStage a,SyncStage b){return SyncStage(uint32_t(a)&uint32_t(b));}
struct VDevice {
 struct {struct {bool rayQuery=false;}raytracing;}props;
 VkPipelineStageFlags graphicsReadStageMask=VK_PIPELINE_STAGE_ALL_GRAPHICS_BIT,graphicsWriteStageMask=VK_PIPELINE_STAGE_ALL_GRAPHICS_BIT;
};
'''
main=r'''
int main(){
 for(uint32_t enabled=0;enabled<16;++enabled){
  VkPhysicalDeviceFeatures f{};f.geometryShader=(enabled&1)!=0;f.tessellationShader=(enabled&2)!=0;
  const bool task=(enabled&4)!=0,mesh=(enabled&8)!=0;
  auto masks=graphicsBarrierStages32(f,task,mesh);
  const auto shader=VK_PIPELINE_STAGE_VERTEX_SHADER_BIT|VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT;
  assert((masks.write&shader)==shader);
  assert(masks.read==(masks.write|VK_PIPELINE_STAGE_VERTEX_INPUT_BIT));
  assert(bool(masks.write&VK_PIPELINE_STAGE_GEOMETRY_SHADER_BIT)==bool(f.geometryShader));
  assert(bool(masks.write&VK_PIPELINE_STAGE_TESSELLATION_CONTROL_SHADER_BIT)==bool(f.tessellationShader));
  assert(bool(masks.write&VK_PIPELINE_STAGE_TESSELLATION_EVALUATION_SHADER_BIT)==bool(f.tessellationShader));
  assert(bool(masks.write&VK_PIPELINE_STAGE_TASK_SHADER_BIT_EXT)==task);
  assert(bool(masks.write&VK_PIPELINE_STAGE_MESH_SHADER_BIT_EXT)==mesh);
  assert(!(masks.read&(VK_PIPELINE_STAGE_DRAW_INDIRECT_BIT|VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT|VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT|VK_PIPELINE_STAGE_LATE_FRAGMENT_TESTS_BIT|VK_PIPELINE_STAGE_ALL_GRAPHICS_BIT)));
  for(bool ray:{false,true})for(bool src:{false,true})for(uint32_t rs=0;rs<4096;++rs){
   VDevice standard,narrow;standard.props.raytracing.rayQuery=narrow.props.raytracing.rayQuery=ray;
   narrow.graphicsReadStageMask=masks.read;narrow.graphicsWriteStageMask=masks.write;
   VkPipelineStageFlags oldStage=0,standardStage=0,newStage=0,expected=0;VkAccessFlags oldAccess=0,standardAccess=0,newAccess=0,tmp=0;
   originalStage(standard,oldStage,oldAccess,SyncStage(rs),src);
   toStage(standard,standardStage,standardAccess,SyncStage(rs),src);
   assert(oldStage==standardStage && oldAccess==standardAccess);
   toStage(narrow,newStage,newAccess,SyncStage(rs),src);assert(newAccess==oldAccess);
   // All non-GraphicsRead/Write mappings, including AS, remain identical.
   const auto without=SyncStage(rs&~uint32_t(SyncStage::GraphicsRead)&~uint32_t(SyncStage::GraphicsWrite));
   originalStage(standard,expected,tmp,without,false);
   if(rs&uint32_t(SyncStage::GraphicsRead))expected|=masks.read;
   if(rs&uint32_t(SyncStage::GraphicsWrite))expected|=masks.write;
   if(src && expected==0)expected=VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT;
   assert(newStage==expected);
   if(rs&uint32_t(SyncStage::Indirect))assert(newStage&VK_PIPELINE_STAGE_DRAW_INDIRECT_BIT);
   if(rs&uint32_t(SyncStage::GraphicsDraw))assert(newStage&VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT);
   if(rs&uint32_t(SyncStage::GraphicsDepth))assert((newStage&(VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT|VK_PIPELINE_STAGE_LATE_FRAGMENT_TESTS_BIT))==(VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT|VK_PIPELINE_STAGE_LATE_FRAGMENT_TESTS_BIT));
  }
 }
 puts("PASS: actual stage mapping for all 4096 sync masks, 16 shader-feature sets, source/destination and AS modes; access masks and non-target behavior identical; attachment, depth, indirect, compute, transfer and host mappings preserved.");
}
'''
with tempfile.TemporaryDirectory(prefix='shader-barriers-') as tmp:
 p=pathlib.Path(tmp);(p/'vulkan_sdk.h').write_text('#include <vulkan/vulkan.h>\n');(p/'stages.h').write_text(h);(p/'test.cpp').write_text(stub+'\n#include "stages.h"\n'+original+'\n'+fn+main)
 subprocess.run(['g++','-std=c++20','-O2','-Wall','-Wextra','-Werror','-I'+str(p),'-I'+str(headers/'include'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=20)
