#!/usr/bin/env python3
"""Test actual spatial AO kernel invariants and integration; no claim of old/new image equality."""
from pathlib import Path
import sys,hashlib,subprocess,tempfile
r=Path(sys.argv[1]);s=(r/'shader/ssao/sao39.comp').read_text();old=(r/'shader/ssao/ssao.comp').read_text()
for p,h in {
 'ssao.comp':'a3fb0c36ceed39f0f0d8747418d2715e57d8f594b0d997217db28bcf80a23317',
 'half_resolution.glsl':'29570325da3dc936d3bcf97f31a13cb86bea2f0c87cfbdd175c9b12248b97fd1',
 'ssao_upsample.comp':'4314b6d21ef95a8201b78cd0922e85758ff7954bf4f825d4307cfd691374af92',
}.items():assert hashlib.sha256((r/'shader/ssao'/p).read_bytes()).hexdigest()==h,p
def fn(text,start,end):return text[text.index(start):text.index(end,text.index(start))]
assert fn(s,'vec3 reconstructNormal(','\n// Alchemy') .rstrip()==fn(old,'vec3 reconstructNormal(','\nvoid main()').rstrip()
for forbidden in ['barrier(', 'atomic', 'hitV[', 'ssaoIsSolved(']:assert forbidden not in s,forbidden
assert 'saoSampleCount39=32u' in s and 'saoRadius39=100.0' in s
assert s.index('greaterThanEqual(outputPixel,imageSize(result))')<s.index('ssaoNearestDepthPixel(depthBuf,outputPixel)')
assert s.index('if(depth>=1.0)')<s.index('const vec3 normal=')
assert 'vec2(tap)+0.5' in s and 'tapDepth>=1.0' in s
assert 'vec4(ao,linearDepth(depth,scene.clipInfo),0,0)' in s
constants=fn(s,'const uint saoSampleCount39','\nivec2 screenSize;')
kernel=fn(s,'float saoContribution39(','\nvoid storeAo39(')
code=r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <random>
using uint=unsigned;
struct vec3 {float x,y,z;};
float dot(vec3 a,vec3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
float max(double a,double b){return float(std::max(a,b));}
using std::clamp;
'''+constants+'\n'+kernel+r'''
float corner(float wall,float angle){
 float sum=0;
 for(uint i=0;i<saoSampleCount39;++i){
  const float a=(float(i)+0.5f)/float(saoSampleCount39);
  const float theta=angle+float(i)*2.f*3.14159265358979323846f*7.f/float(saoSampleCount39);
  const float x=std::cos(theta)*saoRadius39*a*a,y=std::sin(theta)*saoRadius39*a*a;
  // Perspective view of a plane at z=-200 and perpendicular wall x=wall.
  float t=x>wall?wall/x:1.f;
  sum+=saoContribution39({x*t,y*t,200.f*(1.f-t)},{0,0,1});
 }
 return saoVisibility39(sum);
}
int main(){
 assert(saoVisibility39(0)==1.f);
 assert(saoContribution39({0,0,0},{0,0,1})==0.f);
 for(int i=-200;i<=200;++i){
  assert(saoContribution39({float(i),0,0},{0,0,1})==0.f); // flat plane
  assert(saoContribution39({0,0,-float(std::abs(i))},{0,0,1})==0.f); // below horizon
  assert(saoContribution39({0,0,float(100+std::abs(i))},{0,0,1})==0.f); // outside radius
 }
 float meanCorner=0.f,minCorner=1.f;int nearWhite=0;
 for(int i=0;i<64;++i){
  float a=float(i)*0.1f,c=corner(10.f,a);
  assert(c>=0.f && c<=1.f);meanCorner+=c;minCorner=std::min(minCorner,c);nearWhite+=int(c>0.99f);
  assert(corner(200.f,a)==1.f); // distant wall cannot darken
 }
 assert(meanCorner/64.f<0.95f && minCorner<0.9f);
 printf("Synthetic contact mean=%f min=%f; near-white noise phases=%d/64 (spatial sampling variance; image review required).\n",double(meanCorner/64.f),double(minCorner),nearWhite);
 std::mt19937 gen(39067);std::uniform_real_distribution<float> d(-500.f,500.f);
 for(int i=0;i<100000;++i){
  vec3 v{d(gen),d(gen),d(gen)},n{d(gen),d(gen),d(gen)};
  float len=std::sqrt(dot(n,n));if(len<0.001f)continue;n={n.x/len,n.y/len,n.z/len};
  float c=saoContribution39(v,n),a=saoVisibility39(c*32.f);
  assert(std::isfinite(c) && c>=0.f && std::isfinite(a) && a>=0.f && a<=1.f);
 }
 puts("PASS: actual SAO kernel: flat/below-horizon/radius/coincident invariants, 64 perspective corner scenes, 100000 finite bounded cases. Old producer/filter intact; phone image comparison still required.");
}
'''
with tempfile.TemporaryDirectory() as t:
 p=Path(t);(p/'test.cpp').write_text(code)
 subprocess.run(['g++','-std=c++20','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=20)
renderer=(r/'common/graphics/renderer.cpp').read_text();menu=(r/'common/ui/gamemenu.cpp').read_text()
assert 'halfResolution && !settings.pathTraceEnabled && AndroidSaoCompare39::supported()' in renderer
assert 'settings.aoMethod39==1 || (compare39 && AndroidSaoCompare39::useFused())' in renderer
assert 'Original|SAO test|Compare' in menu and '"ENGINE","aoMethod39"' in menu
assert 'int y=1450;' in menu and '1000,7350,6200' in menu
# Nine 600-high rows at existing 625 spacing fit between title and Back.
assert 750+650<=1450 and 1450+8*625+600<7350 and 7350+650<=8192
print('PASS: manual/compare/original modes, half-AO target gate and nine-row menu bounds.')
