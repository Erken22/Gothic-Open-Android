#!/usr/bin/env python3
"""Check old/new fog mask math and the pre-water/noise/consumer contracts."""
from pathlib import Path
import re,subprocess,sys,tempfile
root=Path(sys.argv[1]);a=(root/'shader/sky/fog.frag').read_text();b=(root/'shader/sky/fog_fused.frag').read_text()
loop=a[a.index('  uint occlusion = 0;'):a.index('\n#else\n  vec3  scatteredLight')]
assert loop in b, '32-step mask arithmetic must be copied unchanged'
# The final fragment integration, scaling and sky handling stay unchanged.
assert a[a.index('#if !defined(GL_COMPUTE_SHADER)\nvoid main_frag()'):]==b[b.index('#if !defined(GL_COMPUTE_SHADER)\nvoid main_frag()'):]
x=a[a.index('  [[dont_unroll]]\n  for(int i=0; i<steps; i++)'):a.index('\n#else\nvec4 fog(vec2 uv')]
assert x in b
helper=b[b.index('uint fogMask35()'):b.index('\n#if defined(VOLUMETRIC)\nvec4 fog')]
assert 'textureLod(opaqueDepth,depthUv,0)' in helper and 'textureLod(depth,' not in helper
assert 'interleavedGradientNoise(vec2(uvec2(pixel)))' in helper
assert 'dFogMax' in helper and 'scene.viewShadowLwc[1]' in helper
r=(root/'common/graphics/renderer.cpp').read_text()
assert 'fogFusionActive=fogFusionEligible && AndroidFogFusion::useFused();' in r
assert 'if(fogFusionActive)break;' in r
assert 'cmd.setBinding(4, sceneDepth, Sampler::nearest());' in r
assert 'cmd.setBinding(2, zbuffer,        Sampler::nearest());' in r
assert '!settings.vsmEnabled && !settings.rtsmEnabled && !settings.pathTraceEnabled' in r
assert r.index('stashSceneAux(cmd);')<r.index('drawGWater(cmd, wview);')<r.index('drawFog(cmd, wview);')
stash=(root/'shader/stash.frag').read_text();assert 'outDepth = texelFetch(zs,' in stash
# Convert the actual candidate GLSL helper to a tiny CPU vector model.
fn=helper.replace('[[dont_unroll]]','').replace('gl_FragCoord.xy','gl_FragCoord.xy()').replace(').r',').x')
noise=(root/'shader/common.glsl').read_text();noise=noise[noise.index('float interleavedGradientNoise(vec2 pixel)'):];noise=noise[:noise.index('\n  }')+4]
cpp=r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <random>
using uint=uint32_t;using std::min;using std::abs;
struct ivec2;struct uvec2;
struct vec2{float x,y;vec2(float v=0):x(v),y(v){}vec2(float a,float b):x(a),y(b){}vec2(const ivec2&);vec2(const uvec2&);};
struct ivec2{int x,y;explicit ivec2(vec2 v):x(int(v.x)),y(int(v.y)){}ivec2(int a,int b):x(a),y(b){}};
struct uvec2{uint x,y;explicit uvec2(ivec2 v):x(uint(v.x)),y(uint(v.y)){}uvec2(uint a,uint b):x(a),y(b){}};
vec2::vec2(const ivec2& v):x(float(v.x)),y(float(v.y)){}vec2::vec2(const uvec2& v):x(float(v.x)),y(float(v.y)){}
vec2 operator+(vec2 a,vec2 b){return {a.x+b.x,a.y+b.y};}vec2 operator+(uvec2 a,vec2 b){return vec2(a)+b;}
vec2 operator-(vec2 a,vec2 b){return {a.x-b.x,a.y-b.y};}vec2 operator*(vec2 a,vec2 b){return {a.x*b.x,a.y*b.y};}
vec2 operator*(vec2 a,float b){return {a.x*b,a.y*b};}vec2 operator/(vec2 a,vec2 b){return {a.x/b.x,a.y/b.y};}
struct vec3{float x,y,z;vec3(float a,float b,float c):x(a),y(b),z(c){}vec3(vec2 a,float b):x(a.x),y(a.y),z(b){}};
struct vec4{float x,y,z,w;vec4(float a,float b,float c,float d):x(a),y(b),z(c),w(d){}vec4(vec3 a,float b):x(a.x),y(a.y),z(a.z),w(b){}vec2 xy()const{return {x,y};}};
struct mat4{float m[4][4]{};};
vec4 operator*(const mat4& a,vec4 v){float o[4]{};float in[]={v.x,v.y,v.z,v.w};for(int r=0;r<4;++r)for(int c=0;c<4;++c)o[r]+=a.m[r][c]*in[c];return {o[0],o[1],o[2],o[3]};}
vec4 mix(vec4 a,vec4 b,float t){return {a.x*(1-t)+b.x*t,a.y*(1-t)+b.y*t,a.z*(1-t)+b.z*t,a.w*(1-t)+b.w*t};}
vec3 project(const mat4& m,vec3 v){auto p=m*vec4(v,1);return {p.x/p.w,p.y/p.w,p.z/p.w};}
float fract(float x){return x-std::floor(x);}
struct Scene{mat4 viewProjectLwcInv,viewShadowLwc[2];}scene;
vec4 gl_FragCoord(0,0,0,1);constexpr int opaqueDepth=0;constexpr float dFogMin=0,dFogMax=0.9999f;
ivec2 imageDim(1800,810);float preWater=1,currentDepth=1;
ivec2 textureSize(int sampler,int lod){assert(sampler==opaqueDepth && lod==0);return imageDim;}
vec4 textureLod(int sampler,vec2 uv,int lod){assert(sampler==opaqueDepth && lod==0);assert(uv.x>=0 && uv.x<=1 && uv.y>=0 && uv.y<=1);return {preWater,0,0,0};}
bool shadowFactor(vec4 p){if(abs(p.x)>=p.w || abs(p.y)>=p.w)return true;float x=p.x/p.w,y=p.y/p.w,z=p.z/p.w;float sh=0.5f+0.25f*std::sin(x*7+y*5);return sh<z;}
'''
cpp+=noise+'\n'+fn+'\n'
cpp+='uint reference(uvec2 invocationID){\n const uint steps=32;\n const vec2 inPos=vec2(invocationID+vec2(0.5))/vec2(imageDim)*2.0f-vec2(1.0f);\n const vec2 uv=inPos*vec2(0.5)+vec2(0.5);\n float z=min(textureLod(opaqueDepth,uv,0).x,dFogMax);\n const float noise=interleavedGradientNoise(vec2(invocationID))/steps;\n const vec3 pos0=project(scene.viewProjectLwcInv,vec3(inPos,dFogMin));\n const vec3 posz=project(scene.viewProjectLwcInv,vec3(inPos,z));\n const vec4 shPos0=scene.viewShadowLwc[1]*vec4(pos0,1);\n const vec4 shPos1=scene.viewShadowLwc[1]*vec4(posz,1);\n'+loop.replace('[[dont_unroll]]','')+'\n return occlusion;\n}\n'
cpp+=r'''
int main(){
 std::mt19937 gen(35067);uint waterMismatch=0;
 for(int test=0;test<50000;++test){
  imageDim=ivec2(test%2?1800:127,test%2?810:63);
  uint x=gen()%uint(imageDim.x),y=gen()%uint(imageDim.y);gl_FragCoord=vec4(float(x)+0.5f,float(y)+0.5f,0,1);
  for(auto m:{&scene.viewProjectLwcInv,&scene.viewShadowLwc[1]}){
   *m=mat4{};for(int i=0;i<4;++i)m->m[i][i]=1;
   for(int i=0;i<3;++i)for(int j=0;j<4;++j)m->m[i][j]+=float(int(gen()%200)-100)/300.f;
   m->m[3][2]=float(gen()%100)/300.f;
  }
  preWater=test%5==0?1.f:float(gen()%1000000)/1000000.f;
  currentDepth=preWater*0.3f; // Moving water can alter the final depth, never the old mask input.
  const uint expected=reference({x,y}),actual=fogMask35();assert(expected==actual);
  float saved=preWater;preWater=currentDepth;waterMismatch+=uint(reference({x,y})!=expected);preWater=saved;
 }
 assert(waterMismatch>1000);
 puts("PASS: actual fused mask helper matches reference for 50000 random projections/pixels/depths; integer noise, depth clamp, odd sizes, sky and water-depth distinction exercised. Original final integration retained. CPU model does not validate GPU pixels/performance.");
}
'''
with tempfile.TemporaryDirectory() as t:
 p=Path(t);(p/'test.cpp').write_text(cpp)
 subprocess.run(['g++','-std=c++20','-O2','-ffp-contract=off','-Wall','-Wextra','-Werror','-Wno-sign-compare',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
