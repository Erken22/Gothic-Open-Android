#!/usr/bin/env python3
"""Run real patched bin helpers with interleaved invocations against private-bin reference."""
import pathlib,subprocess,sys,tempfile
root=pathlib.Path(sys.argv[1]);s=(root/'shader/ssao/ssao_shared.comp').read_text()
original=(root/'shader/ssao/ssao.comp').read_text()
a=s.index('uint  hits   =');b=s.index('shared uint shMaxSteps;',a);block=s[a:b]
x=original.index('uint  hits   =');y=original.index('shared uint shMaxSteps;',x);originalBlock=original[x:y]
assert s.count('barrier();')==2
for literal in ['const uint  numSamples     = 32;','const uint  numIter        = 8;','const float sphereLen      = 100;','layout(local_size_x = 8, local_size_y = 8) in;']:
 assert literal in s
stub=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
using uint=uint32_t;
using std::max;
constexpr int gridQSize=25;
struct vec3 {uint bin;};
uint pyramidId(vec3 dir){return dir.bin;}
#define shared
'''
# Compile identical real bin arithmetic twice, with only the storage qualifier changed.
code=stub+'namespace Private {float occlusionAll=0;\n'+originalBlock+'}\n'
code+='#define SSAO_SHARED_BINS\nnamespace Shared {uint gl_LocalInvocationIndex=0;float occlusionAll=0;\n'+block+'}\n'
main=r'''
struct State {float occlusion=0;uint hits=0,any=0;std::array<float,25> bins{};};
int main(){
 static_assert(sizeof(Shared::hitVShared)==6400);
 std::array<State,64> ref{},actual{};
 for(uint lane=0;lane<64;++lane){Shared::gl_LocalInvocationIndex=lane;for(uint bin=0;bin<25;++bin)Shared::writeHit(bin,0);}
 uint seed=7331;
 for(uint step=0;step<100000;++step){
  seed=seed*1664525u+1013904223u;uint lane=(seed>>16)%64;
  seed=seed*1664525u+1013904223u;uint bin=(seed>>16)%25;
  seed=seed*1664525u+1013904223u;float weight=float((seed>>16)%1000)/500.f;
  auto& r=ref[lane];auto& t=actual[lane];
  std::copy(r.bins.begin(),r.bins.end(),Private::hitV);
  Private::occlusionAll=r.occlusion;Private::hits=r.hits;Private::anySmp=r.any;
  Shared::gl_LocalInvocationIndex=lane;Shared::occlusionAll=t.occlusion;Shared::hits=t.hits;Shared::anySmp=t.any;
  if((seed&4)!=0){Private::addHit({bin},weight);Shared::addHit({bin},weight);}
  else{Private::addMis({bin});Shared::addMis({bin});}
  assert(std::memcmp(&Private::occlusionAll,&Shared::occlusionAll,sizeof(float))==0);
  assert(Private::hits==Shared::hits && Private::anySmp==Shared::anySmp);
  for(uint j=0;j<25;++j){assert(std::memcmp(&Private::hitV[j],&Shared::hitVShared[j][lane],sizeof(float))==0);r.bins[j]=Private::hitV[j];}
  r.occlusion=Private::occlusionAll;r.hits=Private::hits;r.any=Private::anySmp;
  t.occlusion=Shared::occlusionAll;t.hits=Shared::hits;t.any=Shared::anySmp;
 }
 // Invalid directions must not write other invocations' shared columns.
 std::array<unsigned char,6400> snapshot{};std::memcpy(snapshot.data(),Shared::hitVShared,6400);
 Shared::addHit({25},2);Shared::addHit({0xffffffffu},2);Shared::addMis({0xffffffffu});
 assert(std::memcmp(snapshot.data(),Shared::hitVShared,6400)==0);
 puts("PASS:100000 interleaved hit/miss operations preserve float bits and masks across64 independent lanes;6400-byte shared layout, bounds guards,32 samples/radius/barriers preserved.");
}
'''
with tempfile.TemporaryDirectory(prefix='ssao-bins-') as tmp:
 p=pathlib.Path(tmp);(p/'test.cpp').write_text(code+main)
 subprocess.run(['g++','-std=c++20','-O2','-Wall','-Wextra','-Wconversion','-Wsign-conversion','-Werror',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
