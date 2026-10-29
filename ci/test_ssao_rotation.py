#!/usr/bin/env python3
"""Compare real GLSL sampling functions as float C++; run on an already patched source."""
import pathlib, subprocess, sys, tempfile
root=pathlib.Path(sys.argv[1])
common=(root/'shader/common.glsl').read_text()
ssao=(root/'shader/ssao/ssao.comp').read_text()
def function(text, name):
    start=text.index(name);start=text.rfind('\n',0,start)+1
    at=text.index('{',start);depth=1;end=at+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
assert 'const uint  numSamples     = 32;' in ssao
assert 'const uint  numIter        = 8;' in ssao
assert 'const float sphereLen      = 100;' in ssao
assert 'if(ssaoIsSolved(abs(occlusion-prev), samples))' in ssao
assert ssao.count('barrier();')==2 # no extra barrier added by the cache
assert ssao.index('hemisphereBase[gl_LocalInvocationIndex] =')<ssao.index('barrier();')
assert 'gl_LocalInvocationIndex<numSamples' in ssao
shader_cpp='\n'.join([function(common,'vec2 sampleHammersley('),function(common,'vec3 sampleHemisphereCos('),function(ssao,'vec3 cachedHemisphere(')])
stub=r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
using uint=uint32_t;
constexpr float M_PI_VALUE=3.14159265358979323846f;
#undef M_PI
#define M_PI M_PI_VALUE
using std::sin; using std::cos; using std::sqrt;
struct vec2 {float x,y;vec2(float a,float b):x(a),y(b){}};
struct vec3 {float x,y,z;vec3(float a,float b,float c):x(a),y(b),z(c){}};
uint bitfieldReverse(uint x){uint r=0;for(int k=0;k<32;++k){r=(r<<1)|(x&1);x>>=1;}return r;}
constexpr uint numSamples=32;
vec3 hemisphereBase[32]={
#define Z vec3(0,0,0)
 Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z,Z
#undef Z
};
vec2 hemisphereRotation(0,0);
'''
main=r'''
int main(){
 for(uint i=0;i<32;++i)hemisphereBase[i]=sampleHemisphereCos(i,32,0.f);
 float maxError=0;
 for(uint p=0;p<8192;++p){
   float f=M_PI*2.f*float(p)/8192.f;
   hemisphereRotation=vec2(cos(f),sin(f));
   for(uint i=0;i<32;++i){
     auto a=sampleHemisphereCos(i,32,f),b=cachedHemisphere(i);
     maxError=std::max({maxError,std::abs(a.x-b.x),std::abs(a.y-b.y),std::abs(a.z-b.z)});
     assert(a.z==b.z);
   }
 }
 assert(maxError<0.000002f);
 bool visited[32]={};
 for(uint seed=0;seed<8;++seed)for(uint j=0;j<4;++j){uint i=j*8+seed;assert(i<32&&!visited[i]);visited[i]=true;}
 for(bool v:visited)assert(v);
 printf("PASS: 262144 sample comparisons; maximum component error %.9g; same 32 samples, radius, resolution, convergence and barriers.\n",double(maxError));
}
'''
with tempfile.TemporaryDirectory(prefix='ssao-rotation-') as tmp:
    p=pathlib.Path(tmp);(p/'test.cpp').write_text(stub+shader_cpp+main)
    subprocess.run(['g++','-std=c++20','-O2','-Wall','-Wextra','-Werror','-Wno-unknown-pragmas',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
print('PASS: shader cache is published before use and keeps all invocations at existing barriers.')
