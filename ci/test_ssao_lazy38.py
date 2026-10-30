#!/usr/bin/env python3
"""Compare actual bucket functions with read-before-write tracking and poisoned backing storage."""
from pathlib import Path
import sys,tempfile,subprocess,hashlib
root=Path(sys.argv[1]);a=(root/'shader/ssao/ssao.comp').read_text();b=(root/'shader/ssao/ssao_lazy38.comp').read_text()
assert hashlib.sha256(a.encode()).hexdigest()=='a3fb0c36ceed39f0f0d8747418d2715e57d8f594b0d997217db28bcf80a23317'
def fn(s,start,end):return s[s.index(start):s.index(end,s.index(start))]
x=fn(a,'void addHit(','\nvoid addMis(');y=fn(b,'void addHit(','\nvoid addMis(')
assert a.replace(x,y).replace('  for(int i=0; i<gridQSize; ++i)\n    hitV[i] = 0;\n\n','')==b,'Only hit-bin initialization/load may change'
assert 'if((hits & (1u << uv))!=0u)\n    value = hitV[uv];' in y
mis=fn(a,'void addMis(','\nshared uint shMaxSteps;')
resolve=fn(a,'float resolveOcclusion(','\nvec3 unproject(')
code=r'''
#define SSAO_HALF_RES
#include <algorithm>
#include <array>
#include <bit>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <random>
using uint=unsigned;using vec3=uint;using std::max;
uint pyramidId(uint x){return x;}
int bitCount(uint x){return std::popcount(x);}
// Conversion instruments the actual candidate's dynamic read. Poisoned values
// also expose accidental reuse across invocations. Assignment marks a write.
struct Slot {
 float value=std::numeric_limits<float>::quiet_NaN(); bool written=false;
 operator float() const {assert(written);return value;}
 Slot& operator=(float v){value=v;written=true;return *this;}
};
'''
for name,hit,array in [('Original',x,'float hitV[25]{};'),('Candidate',y,'Slot hitV[25];')]:
 code+='namespace '+name+' { uint hits=0,anySmp=0;float occlusionAll=0;'+array+'\n'+hit+mis+resolve+'}\n'
code+=r'''
int main(){
 std::mt19937 gen(38067);
 for(unsigned run=0;run<20000;++run){
  Original::hits=Original::anySmp=Candidate::hits=Candidate::anySmp=0;
  Original::occlusionAll=Candidate::occlusionAll=0;
  std::fill_n(Original::hitV,25,0.f);
  for(auto& s:Candidate::hitV){s.value=std::numeric_limits<float>::quiet_NaN();s.written=false;}
  for(unsigned j=0;j<64;++j){
   unsigned bin=run<25?run:gen()%25;
   if(gen()%4==0){Original::addMis(bin);Candidate::addMis(bin);}
   else {
    float v=float(gen()%1000001)/500000.f;
    Original::addHit(bin,v);Candidate::addHit(bin,v);
   }
   assert(Original::hits==Candidate::hits && Original::anySmp==Candidate::anySmp);
   assert(std::bit_cast<uint>(Original::occlusionAll)==std::bit_cast<uint>(Candidate::occlusionAll));
   assert(std::bit_cast<uint>(Original::resolveOcclusion())==std::bit_cast<uint>(Candidate::resolveOcclusion()));
   for(unsigned k=0;k<25;++k){
    assert(Candidate::hitV[k].written==bool(Candidate::hits & (1u<<k)));
    if(Candidate::hitV[k].written)assert(std::bit_cast<uint>(Original::hitV[k])==std::bit_cast<uint>(Candidate::hitV[k].value));
   }
  }
 }
 puts("PASS: 1280000 actual old/new hit/miss updates; CPU-bit-identical accumulations/AO; no unwritten bin reads; poisoned invocation resets, all bins and repeats; unchanged shader outside initialization/load.");
}
'''
with tempfile.TemporaryDirectory() as t:
 p=Path(t);(p/'test.cpp').write_text(code)
 subprocess.run(['g++','-std=c++20','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=20)
