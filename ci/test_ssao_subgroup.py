#!/usr/bin/env python3
"""Run the real convergence helpers with CPU barriers and a subgroup-reduction model."""
import pathlib,subprocess,sys,tempfile,re,hashlib
root=pathlib.Path(sys.argv[1]);a=(root/'shader/ssao/ssao.comp').read_text();b=(root/'shader/ssao/ssao_wave.comp').read_text();old=(root/'shader/ssao/convergence.glsl').read_text();new=(root/'shader/ssao/convergence_wave.glsl').read_text()
# The expensive sampling/normal/output math must not change.
for start,end in [('void calcOcclussion(','vec3 reconstructNormal('),('vec3 reconstructNormal(','void main(')]:
 x=a[a.index(start):a.index(end)];y=b[b.index(start):b.index(end)];assert x==y
for literal in ('numSamples     = 32;','numIter        = 8;','sphereLen      = 100;','layout(local_size_x = 8, local_size_y = 8) in;'):
 assert literal in a and literal in b
assert 'gl_NumSubgroups==1u' in b and 'groupMaxSteps=subgroupMax(uint(maxSteps));' in b
assert 'atomicMax(shMaxSteps, maxSteps);' in b
assert 'void main() [[subgroup_uniform_control_flow]]' in b
assert '#extension GL_EXT_subgroup_uniform_control_flow : require' in b
fn0=old[old.index('bool ssaoIsSolved'):old.rindex('\n#endif')].strip();fn1=new[new.index('bool ssaoIsSolved'):new.rindex('\n#endif')].strip()
start=fn1.index('  if(gl_NumSubgroups==1u)');end=fn1.index('\n  if(gl_LocalInvocationIndex',start)
assert fn1[:start]+fn1[end+1:]==fn0
assert 'subgroupMax(floatBitsToUint(diff))' in fn1
s=(root/'lib/Tempest/Engine/gapi/vulkan/vdevice.cpp').read_text()
for literal in ('hasDeviceFeatures2 && devP.apiVersion>=VK_API_VERSION_1_1','VK_SUBGROUP_FEATURE_BASIC_BIT|VK_SUBGROUP_FEATURE_ARITHMETIC_BIT','VK_SHADER_STAGE_COMPUTE_BIT','waveFeatures.shaderSubgroupUniformControlFlow==VK_TRUE','rqExt.push_back(VK_KHR_SHADER_SUBGROUP_UNIFORM_CONTROL_FLOW_EXTENSION_NAME);','waveFeatures.pNext=features.pNext;features.pNext=&waveFeatures;'):assert literal in s
sh=(root/'common/graphics/shaders.cpp').read_text();assert 'isTurnipAdreno650() && gpu.compute.subgroupArithmetic && gpu.compute.subgroupUniformControlFlow' in sh
stub=r'''
#include <algorithm>
#include <array>
#include <atomic>
#include <barrier>
#include <bit>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <thread>
#include <vector>
using uint=uint32_t;
constexpr uint rounds=256;
std::array<std::array<uint,64>,rounds> patterns;
std::barrier rendezvous(64);
thread_local uint gl_LocalInvocationIndex=0,gl_NumSubgroups=1,roundIndex=0;
uint floatBitsToUint(float x){return std::bit_cast<uint>(x);}
float uintBitsToFloat(uint x){return std::bit_cast<float>(x);}
void barrier(){rendezvous.arrive_and_wait();}
void atomicMax(std::atomic_uint& p,uint v){auto old=p.load();while(old<v && !p.compare_exchange_weak(old,v)){};}
// This is the specified collective result, not an emulation of GPU execution.
uint subgroupMax(uint x){assert(x==patterns[roundIndex][gl_LocalInvocationIndex]);return *std::max_element(patterns[roundIndex].begin(),patterns[roundIndex].end());}
'''
code=stub+'namespace Original {std::atomic_uint ssaoMaxDiff{0};\n'+fn0+'}\nnamespace Wave {std::atomic_uint ssaoMaxDiff{0};\n'+fn1+'}\n'
code+=r'''
int main(){
 uint seed=17;
 for(uint r=0;r<rounds;++r)for(uint l=0;l<64;++l){seed=seed*1664525u+1013904223u;patterns[r][l]=seed;}
 patterns[0].fill(0);patterns[1].fill(std::bit_cast<uint>(0.01f));patterns[2].fill(std::bit_cast<uint>(0.9f));
 for(uint r=3;r<10;++r){patterns[r].fill(0);patterns[r][r]=std::array<uint,7>{0x7fc00000,0xffc00000,0x7f800000,0xff800000,0x80000000,0x7fffffff,0x00000001}[r-3];}
 for(uint r=10;r<18;++r)patterns[r].fill(std::bit_cast<uint>(float(0.1 + double((r%8+1)*4)*0.005)));
 std::vector<std::thread> workers;
 for(uint lane=0;lane<64;++lane)workers.emplace_back([lane](){
  gl_LocalInvocationIndex=lane;
  for(uint r=0;r<rounds;++r){roundIndex=r;gl_NumSubgroups=(r%3)==0?2u:1u;
   float diff=uintBitsToFloat(patterns[r][lane]);int samples=int((r%8+1)*4);
   const bool expected=Original::ssaoIsSolved(diff,samples);
   const bool actual=Wave::ssaoIsSolved(diff,samples);
   assert(actual==expected);
   barrier();
  }
 });
 for(auto& t:workers)t.join();
 puts("PASS: real old/new convergence decisions for 256 groups of 64 invocations, NaN/Inf/signed-zero/threshold edges, single-subgroup reduction model and original multi-subgroup fallback. Sampling/normal math, workgroup size and 32-sample contracts preserved; Vulkan capabilities and reconvergence gates checked.");
}
'''
with tempfile.TemporaryDirectory(prefix='ssao-subgroup-') as tmp:
 p=pathlib.Path(tmp);(p/'test.cpp').write_text(code)
 subprocess.run(['g++','-std=c++20','-O2','-pthread','-Wall','-Wextra','-Werror',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=30)
