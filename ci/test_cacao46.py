#!/usr/bin/env python3
"""Execute official depth constants and the actual comparison controller; inspect SPIR-V."""
import pathlib,subprocess,sys,tempfile,re,struct
root=pathlib.Path(sys.argv[1]).resolve()
engine=root/'lib/Tempest/Engine'
vendor=engine/'thirdparty/cacao46'
modules=list((vendor/'src/PrecompiledShadersSPIRV').glob('*.spv'))
assert len(modules)==33,len(modules)
capabilities=set();max_threads=0
image_formats=set();seen_resources=set()
expected_formats={
 'g_ClearLoadCounter_LoadCounter':'R32ui','g_ImportanceBLoadCounter':'R32ui',
 'g_EdgeSensitiveBlur_Output':'Rg8','g_SSAOOutput':'Rg8',
 'g_ApplyOutput':'R8','g_BilateralUpscaleOutput':'R8',
 'g_PrepareDepthsOut':'R16f','g_PrepareNormals_NormalOut':'Rgba8Snorm',
 'g_ImportanceOut':'R8','g_ImportanceAOut':'R8','g_ImportanceBOut':'R8',
 **{f'g_PrepareDepthsAndMips_OutMip{i}':'R16f' for i in range(4)},
}
for module in modules:
    header=pathlib.Path(str(module)[:-4]).read_text()
    capabilities.update(re.findall(r'OpCapability (\w+)',header))
    assert not re.search(r'OpTypeFloat 16\b|OpCapability Float16\b',header)
    types={}
    pointers={}
    for line in header.splitlines():
        m=re.search(r'(%\S+)\s*=\s*OpTypeImage\s+%\S+\s+\S+\s+\d+\s+\d+\s+\d+\s+2\s+(\w+)',line)
        if m:types[m[1]]=m[2];image_formats.add(m[2])
        m=re.search(r'(%\S+)\s*=\s*OpTypePointer\s+UniformConstant\s+(%\S+)',line)
        if m:pointers[m[1]]=m[2]
    for name,expected in expected_formats.items():
        m=re.search(r'%'+name+r'\s*=\s*OpVariable\s+(%\S+)\s+UniformConstant',header)
        if m:
            actual=types[pointers[m[1]]]
            assert actual==expected,(module.name,name,actual,expected)
            seen_resources.add(name)
    for x,y,z in re.findall(r'LocalSize (\d+) (\d+) (\d+)',header):
        max_threads=max(max_threads,int(x)*int(y)*int(z))
assert capabilities <= {'Shader','Image1D','Sampled1D','StorageImageExtendedFormats','ImageGatherExtended'},capabilities
assert max_threads<=256,max_threads
assert seen_resources==set(expected_formats),(seen_resources,set(expected_formats))
assert image_formats=={'R32ui','Rg8','R8','R16f','Rgba8Snorm'},image_formats

with tempfile.TemporaryDirectory(prefix='cacao46-') as tmp:
    p=pathlib.Path(tmp);(p/'Tempest').mkdir()
    (p/'Tempest/Log').write_text('''#pragma once
#include <sstream>
#include <string>
#include <vector>
namespace Tempest {struct Log {inline static std::vector<std::string> lines;
template<class... A>static void i(const A&... a){std::ostringstream s;(s<<...<<a);lines.push_back(s.str());}};}
''')
    (p/'test.cpp').write_text(r'''
#include "ffx_cacao.h"
#include "utils/androidframeprofile.h"
#include <cassert>
#include <cmath>
#include <string>
#include <vector>
struct Timing {std::string name; double milliseconds;};
int main(){
  FFX_CACAO_BufferSizeInfo size{};
  FFX_CACAO_UpdateBufferSizeInfo(1800,810,FFX_CACAO_TRUE,&size);
  assert(size.ssaoBufferWidth==450 && size.ssaoBufferHeight==203);
  FFX_CACAO_UpdateBufferSizeInfo(1801,811,FFX_CACAO_TRUE,&size);
  assert(size.ssaoBufferWidth==451 && size.ssaoBufferHeight==203);
  // Exact layout supplied by Tempest Matrix4x4::at(column,row).
  FFX_CACAO_Matrix4x4 projection{};
  const float near=10.f,far=100000.f,k=far/(far-near);
  projection.elements[0][0]=1.2f;projection.elements[1][1]=2.f;
  projection.elements[2][2]=k;projection.elements[2][3]=1.f;
  projection.elements[3][2]=-near*k*0.01f;
  FFX_CACAO_Constants constants{};
  auto settings=FFX_CACAO_DEFAULT_SETTINGS;settings.generateNormals=FFX_CACAO_TRUE;settings.radius=1.f;
  FFX_CACAO_UpdateConstants(&constants,&settings,&size,&projection,nullptr);
  for(float distance:{10.f,100.f,1000.f,10000.f,60000.f}) {
    const double z=double(k)-double(near*k)/distance;
    const double metres=constants.DepthUnpackConsts[0]/(constants.DepthUnpackConsts[1]-z);
    assert(std::abs(metres-distance*0.01)<std::max(0.001,double(distance)*0.00001));
    assert(std::isfinite(metres) && metres<65504);
    }
  assert(std::abs(constants.DepthUnpackConsts[0]/(constants.DepthUnpackConsts[1]-1.0)-1000)<1);
  AndroidCacaoCompare46::configure(true);AndroidCacaoCompare46::state()={};
  auto send=[](bool candidate){
    AndroidCacaoCompare46::observe(std::vector<Timing>{
      {candidate ? "AO46 CACAO" : "AO46 original",candidate ? 4.0 : 9.0},
      {"Rest",34.0}});
    };
  send(false);assert(AndroidCacaoCompare46::useFused());
  send(true);assert(AndroidCacaoCompare46::useFused());
  send(true);assert(!AndroidCacaoCompare46::useFused());
  send(false);assert(!AndroidCacaoCompare46::useFused());
  for(int i=0;i<6;++i){send(false);send(true);}
  assert(AndroidCacaoCompare46::state().decided && !AndroidCacaoCompare46::useFused());
  bool pass=false;for(auto& s:Tempest::Log::lines)pass|=s.find("performance=pass")!=std::string::npos;
  assert(pass); // Performance never silently approves different visual output.
  AndroidCacaoCompare46::state()={};send(false);AndroidCacaoCompare46::finish();
  assert(!AndroidCacaoCompare46::useFused());
  }
''')
    subprocess.run(['g++','-std=c++20','-fsanitize=undefined','-fno-sanitize-recover=all',
      '-I'+str(p),'-I'+str(root/'common'),'-I'+str(vendor/'inc'),
      str(p/'test.cpp'),str(vendor/'src/ffx_cacao.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
bridge=(engine/'gapi/vulkan/vcacao46.inc').read_text()
assert 'info.flags=0' in bridge and 'resState.flush(*this)' in bridge
assert bridge.index('resState.flush(*this)') < bridge.index('FFX_CACAO_VkDraw(')
assert 'VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL' in bridge and 'VK_IMAGE_LAYOUT_GENERAL' in bridge
assert 'resState.forceLayout(output,ResourceLayout::Default)' in bridge
assert 'pipelineLayout=VK_NULL_HANDLE;bindings.durty=true;pushData.durty=true;' in bridge
assert 'vkDeviceWaitIdle' not in bridge and 'vkWaitForFences' not in bridge
device=(engine/'gapi/vulkan/vdevice.cpp').read_text()
assert 'deviceFeatures.shaderStorageImageExtendedFormats=VK_TRUE' in device
assert 'deviceFeatures.shaderImageGatherExtended=VK_TRUE' in device
impl=(vendor/'src/ffx_cacao_impl.cpp').read_text()
assert impl.count('imageInfos[cur].imageLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL;')==5
renderer=(root/'common/graphics/renderer.cpp').read_text()
assert 'if(!compare46) cmd.setDebugMarker(halfResolution' in renderer
assert 'settings.aoMethod39 = 0;' in renderer
assert 'if(cmd.renderCacao46(zbuffer,ssao.ssaoBlur,projection46,halfResolution)) return;' in renderer
print('FIX46 official constants/units, odd dimensions, actual ABBA, feature/layout gates: PASS')
print('FP32 SPIR-V modules:',len(modules),'capabilities:',sorted(capabilities),'max group invocations:',max_threads)
