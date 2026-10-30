#!/usr/bin/env python3
"""Compare actual original/candidate update arithmetic for repeated bucket hits."""
from pathlib import Path
import sys,subprocess,tempfile
root=Path(sys.argv[1]);a=(root/'shader/ssao/ssao.comp').read_text();b=(root/'shader/ssao/ssao_bucket.comp').read_text()
def fn(s):return s[s.index('void addHit('):s.index('\nvoid addMis(')]
x=fn(a);y=fn(b)
assert a.replace(x,y)==b, 'Only addHit may change'
assert y.count('case ')==25
for i in range(25):assert f'case {i}u:' in y and f'hitV[{i}]' in y
for token in ['numSamples     = 32','numIter        = 8','sphereLen      = 100','ssaoIsSolved(abs(occlusion-prev), samples)']:
 assert token in b
stub='''
#include <algorithm>
#include <cassert>
#include <bit>
#include <cstdint>
#include <cstdio>
#include <random>
using uint=unsigned;using vec3=uint;
uint pyramidId(uint x){return x;}
using std::max;
'''
code=stub
for name,body in [('Original',x),('Candidate',y)]:
 code+='namespace '+name+' { uint hits=0,anySmp=0;float occlusionAll=0,hitV[25]{};\n'+body+'}\n'
code+='''
int main(){
 std::mt19937 gen(34067);
 for(unsigned run=0;run<10000;++run){
  Original::hits=Original::anySmp=Candidate::hits=Candidate::anySmp=0;
  Original::occlusionAll=Candidate::occlusionAll=0;
  std::fill_n(Original::hitV,25,0.f);std::fill_n(Candidate::hitV,25,0.f);
  for(unsigned j=0;j<64;++j){
   unsigned bin=(run<25)?run:gen()%25;
   float v=float(gen()%1000001)/500000.f;
   Original::addHit(bin,v);Candidate::addHit(bin,v);
   assert(Original::hits==Candidate::hits && Original::anySmp==Candidate::anySmp);
   assert(std::bit_cast<uint>(Original::occlusionAll)==std::bit_cast<uint>(Candidate::occlusionAll));
   for(int k=0;k<25;++k)assert(std::bit_cast<uint>(Original::hitV[k])==std::bit_cast<uint>(Candidate::hitV[k]));
  }
 }
 puts("PASS: 640000 real old/new hit updates bit-identical on CPU; all 25 bins, repeated hits and random sequences. Shader differs only in bucket addressing; phone/GPU visual validation remains required.");
}
'''
with tempfile.TemporaryDirectory() as t:
 p=Path(t);(p/'test.cpp').write_text(code)
 subprocess.run(['g++','-std=c++20','-O2','-Wall','-Wextra','-Werror',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
