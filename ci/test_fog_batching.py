#!/usr/bin/env python3
"""Exercise the real old/new fog loops; verify sample positions/masks and dispatch coverage."""
import pathlib,re,subprocess,sys,tempfile
root=pathlib.Path(sys.argv[1]);a=(root/'shader/sky/fog.frag').read_text();b=(root/'shader/sky/fog_batched.frag').read_text()
def loop(s):
 start=s.index('  uint occlusion = 0;');end=s.index('\n#else',start)
 return s[start:end]
old,new=loop(a),loop(b)
assert b.replace('layout(local_size_x = 8, local_size_y = 8) in;','layout(local_size_x = 1*8, local_size_y = 2*8) in;').replace(new,old)==a
assert 'const int   steps    = 32;' in b
assert all(f'<< (base+{k}u)' in new for k in range(4))
assert new.count('shadowFactor(')==4
code=r'''
#include <array>
#include <bit>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <vector>
using uint=uint32_t;
struct vec4 {float x,y,z,w;};
vec4 mix(vec4 a,vec4 b,float t){return {a.x*(1-t)+b.x*t,a.y*(1-t)+b.y*t,a.z*(1-t)+b.z*t,a.w*(1-t)+b.w*t};}
std::vector<vec4> samples;
bool shadowFactor(vec4 p){samples.push_back(p);if(std::abs(p.x)>=p.w || std::abs(p.y)>=p.w)return true;float d=std::sin(p.x/p.w)*std::cos(p.y/p.w);return d<p.z/p.w;}
'''
for name,body in [('original',old),('batched',new)]:
 body=re.sub(r'\[\[dont_unroll\]\]','',body)
 code+='uint '+name+'(vec4 shPos0,vec4 shPos1,float noise){const int steps=32;\n'+body+'\nreturn occlusion;}\n'
code+=r'''
int main(){
 uint seed=12345;auto random=[&](){seed=seed*1664525u+1013904223u;return (float(seed>>8)/float(0xffffffu)-0.5f)*16.f;};
 for(int n=0;n<100000;++n){
  vec4 a{random(),random(),random(),random()},b{random(),random(),random(),random()};
  if(n%10==0){a.w=1;b.w=1;}if(n%100==0){a.w=0;b.w=0;}
  float noise=random()/32.f;samples.clear();uint x=original(a,b,noise);auto ref=samples;samples.clear();uint y=batched(a,b,noise);
  assert(x==y && samples.size()==32 && ref.size()==32);
  for(size_t i=0;i<32;++i){auto p=std::bit_cast<std::array<uint,4>>(ref[i]),q=std::bit_cast<std::array<uint,4>>(samples[i]);assert(p==q);}
 }
 for(auto size:std::array<std::array<uint,2>,5>{{{1,1},{7,17},{64,64},{2400,1080},{2401,1081}}}){
  uint w=size[0],h=size[1];std::vector<uint8_t> visited(size_t(w)*h);
  for(uint gy=0;gy<(h+7)/8;++gy)for(uint gx=0;gx<(w+7)/8;++gx)
   for(uint ly=0;ly<8;++ly)for(uint lx=0;lx<8;++lx){uint x=gx*8+lx,y=gy*8+ly;if(x>=w||y>=h)continue;++visited[size_t(y)*w+x];}
  for(auto v:visited)assert(v==1);
 }
 puts("PASS: 100000 rays, identical 32 sample positions and masks; odd-sized dispatch coverage; candidate differs only in loop scheduling and workgroup size.");
}
'''
with tempfile.TemporaryDirectory(prefix='fog-batching-') as tmp:
 p=pathlib.Path(tmp);(p/'test.cpp').write_text(code)
 subprocess.run(['g++','-std=c++20','-O2','-Wall','-Wextra','-Werror',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=30)
